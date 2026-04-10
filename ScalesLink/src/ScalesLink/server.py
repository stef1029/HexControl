"""
Scales Server - TCP server subprocess for scales communication.

This module runs as a separate subprocess to avoid blocking the main behaviour loop.
It continuously reads weight data from the scales hardware, stores all readings in
memory, and serves weight data to clients via TCP. Readings are saved to CSV at shutdown.

Usage (as subprocess):
    python -m ScalesLink.server --port COM7 --baud 115200 --tcp 5100 --log scales.csv

The server accepts TCP commands:
    - "PING" -> "PONG"
    - "GET" -> current weight as string (e.g., "123.45") or "NONE" if no reading
    - "SHUTDOWN" -> stops the server gracefully
"""

import argparse
import logging
import socket
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# Import the Scales class for hardware communication
from .scales import Scales, ScalesConfig


# =============================================================================
# Constants
# =============================================================================

DEFAULT_TCP_PORT = 5100
SOCKET_TIMEOUT = 1.0  # Seconds to wait for socket operations


# =============================================================================
# Scales Server
# =============================================================================

class ScalesServer:
    """
    TCP server that wraps the Scales hardware interface.
    
    Runs in a separate process, reads from scales hardware in a background thread,
    and serves weight data to clients via TCP socket commands.
    
    All readings are stored in memory throughout the session and saved to CSV
    at shutdown (if log_path is configured).
    """
    
    def __init__(
        self,
        scales_config: ScalesConfig,
        tcp_port: int = DEFAULT_TCP_PORT,
        log_path: Optional[Path] = None,
    ):
        """
        Initialise the scales server.
        
        Args:
            scales_config: Configuration for the scales hardware.
            tcp_port: TCP port to listen on for client connections.
            log_path: Optional path for CSV logging of all readings (saved at shutdown).
        """
        self._scales_config = scales_config
        self._tcp_port = tcp_port
        self._log_path = log_path
        
        # Scales hardware interface
        self._scales: Optional[Scales] = None
        
        # TCP server
        self._server_socket: Optional[socket.socket] = None
        self._running = False
    
    def start(self) -> None:
        """
        Start the scales server.
        
        Opens the scales hardware connection, starts the TCP server,
        and begins accepting client connections.
        """
        print(f"[ScalesServer] Starting server on TCP port {self._tcp_port}")
        print(f"[ScalesServer] Scales config: {self._scales_config.port} @ {self._scales_config.baud_rate}")
        
        # Start scales hardware
        self._scales = Scales(self._scales_config)
        self._scales.start()
        print("[ScalesServer] Scales hardware started")
        
        # Enable in-memory storage if logging is configured
        if self._log_path is not None:
            self._scales.enable_reading_storage()
            print(f"[ScalesServer] Will save readings to {self._log_path} at shutdown")
        
        # Wait for initial reading
        time.sleep(2)
        weight = self._scales.get_weight()
        if weight is not None:
            print(f"[ScalesServer] Initial weight: {weight:.2f}g")
        else:
            print("[ScalesServer] No initial weight reading")
        
        # Start TCP server
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(('localhost', self._tcp_port))
        self._server_socket.listen(5)
        self._server_socket.settimeout(SOCKET_TIMEOUT)
        
        self._running = True
        print(f"[ScalesServer] Listening on localhost:{self._tcp_port}")
        
        # Run main loop
        self._run()
    
    def _run(self) -> None:
        """Main server loop - accepts connections and handles commands."""
        while self._running:
            try:
                
                # Accept new connection
                try:
                    client_socket, addr = self._server_socket.accept()
                    client_socket.settimeout(SOCKET_TIMEOUT)
                    self._handle_client(client_socket)
                except socket.timeout:
                    # No connection, continue loop
                    continue
                except OSError:
                    # Socket closed during shutdown
                    break
                    
            except Exception as e:
                print(f"[ScalesServer] Error in main loop: {e}")
                time.sleep(0.1)
        
        print("[ScalesServer] Main loop exited")
    
    def _handle_client(self, client_socket: socket.socket) -> None:
        """
        Handle a single client connection.
        
        Reads one command, sends response, then closes connection.
        """
        try:
            # Receive command
            data = client_socket.recv(1024)
            if not data:
                return
            
            command = data.decode('utf-8').strip().upper()
            response = self._process_command(command)
            
            # Send response
            client_socket.sendall(response.encode('utf-8'))
            
        except socket.timeout:
            logger.warning("[Scales] scales server client socket timeout")
        except Exception as e:
            print(f"[ScalesServer] Error handling client: {e}")
        finally:
            try:
                client_socket.close()
            except Exception as e:
                logger.warning(f"[Scales] error closing client socket: {e}")
    
    def _process_command(self, command: str) -> str:
        """
        Process a command and return the response.
        
        Commands:
            PING -> PONG
            GET -> weight value or NONE
            SHUTDOWN -> OK (and stop server)
        """
        if command == "PING":
            return "PONG"
        
        elif command == "GET":
            if self._scales is None:
                return "NONE"
            weight = self._scales.get_weight()
            if weight is None:
                return "NONE"
            return f"{weight:.4f}"
        
        elif command == "SHUTDOWN":
            print("[ScalesServer] Shutdown command received")
            self._running = False
            return "OK"
        
        else:
            return f"ERROR: Unknown command: {command}"
    
    def stop(self) -> None:
        """Stop the scales server and save readings to CSV."""
        print("[ScalesServer] Stopping...")
        self._running = False
        
        # Close TCP server
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except Exception as e:
                logger.warning(f"[Scales] error closing server socket: {e}")
            self._server_socket = None
        
        # Save readings to CSV before stopping scales
        if self._scales is not None and self._log_path is not None:
            reading_count = self._scales.get_reading_count()
            print(f"[ScalesServer] Saving {reading_count} readings to {self._log_path}")
            saved = self._scales.save_readings_to_csv(self._log_path)
            print(f"[ScalesServer] Saved {saved} readings")
        
        # Stop scales hardware
        if self._scales is not None:
            self._scales.stop()
            self._scales = None
        
        print("[ScalesServer] Stopped")


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point for running the scales server as a subprocess."""
    parser = argparse.ArgumentParser(description='Scales TCP Server')
    parser.add_argument('--port', required=True, help='Serial port (e.g., COM7)')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate')
    parser.add_argument('--tcp', type=int, default=DEFAULT_TCP_PORT, help='TCP port')
    parser.add_argument('--log', help='Path to CSV log file')
    parser.add_argument('--scale', type=float, default=1.0, help='Calibration scale')
    parser.add_argument('--intercept', type=float, default=0.0, help='Calibration intercept')
    parser.add_argument('--wired', action='store_true', help='Use wired protocol')
    
    args = parser.parse_args()
    
    # Create config
    config = ScalesConfig(
        port=args.port,
        baud_rate=args.baud,
        scale=args.scale,
        intercept=args.intercept,
        is_wired=args.wired,
    )
    
    # Create and run server
    log_path = Path(args.log) if args.log else None
    server = ScalesServer(config, tcp_port=args.tcp, log_path=log_path)
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[ScalesServer] Keyboard interrupt")
    finally:
        server.stop()


if __name__ == '__main__':
    main()
