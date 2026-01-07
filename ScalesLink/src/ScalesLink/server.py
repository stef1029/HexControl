"""
Scales Server - TCP server subprocess for scales communication.

This module runs as a separate subprocess to avoid blocking the main behaviour loop.
It continuously reads weight data from the scales hardware, logs to CSV, and serves
weight data to clients via TCP.

Usage (as subprocess):
    python -m ScalesLink.server --port COM7 --baud 115200 --tcp 5100 --log scales.csv

The server accepts TCP commands:
    - "PING" -> "PONG"
    - "GET" -> current weight as string (e.g., "123.45") or "NONE" if no reading
    - "SHUTDOWN" -> stops the server gracefully
"""

import argparse
import csv
import select
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Optional


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
            log_path: Optional path for CSV logging of all readings.
        """
        self._scales_config = scales_config
        self._tcp_port = tcp_port
        self._log_path = log_path
        
        # Scales hardware interface
        self._scales: Optional[Scales] = None
        
        # TCP server
        self._server_socket: Optional[socket.socket] = None
        self._running = False
        
        # Logging
        self._log_file = None
        self._csv_writer = None
        self._log_start_time: Optional[float] = None
        self._log_lock = threading.Lock()
        
        # Last weight for logging (to avoid duplicate reads from Scales)
        self._last_logged_weight: Optional[float] = None
    
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
        
        # Wait for initial reading
        time.sleep(2)
        weight = self._scales.get_weight()
        if weight is not None:
            print(f"[ScalesServer] Initial weight: {weight:.2f}g")
        else:
            print("[ScalesServer] No initial weight reading")
        
        # Open log file if configured
        if self._log_path is not None:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = open(self._log_path, 'w', newline='')
            self._csv_writer = csv.writer(self._log_file)
            self._csv_writer.writerow(['timestamp_s', 'weight_g', 'message_id'])
            self._log_start_time = time.time()
            print(f"[ScalesServer] Logging to {self._log_path}")
        
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
                # Log current weight periodically
                self._log_weight()
                
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
            pass
        except Exception as e:
            print(f"[ScalesServer] Error handling client: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
    
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
    
    def _log_weight(self) -> None:
        """Log the current weight to CSV if configured."""
        if self._csv_writer is None or self._scales is None:
            return
        
        weight = self._scales.get_weight()
        if weight is None:
            return
        
        # Only log if weight changed (to avoid flooding log with identical values)
        if weight == self._last_logged_weight:
            return
        
        message_id = self._scales.get_message_id()
        
        with self._log_lock:
            timestamp = time.time() - self._log_start_time
            self._csv_writer.writerow([f"{timestamp:.6f}", f"{weight:.4f}", message_id])
            self._log_file.flush()
            self._last_logged_weight = weight
    
    def stop(self) -> None:
        """Stop the scales server."""
        print("[ScalesServer] Stopping...")
        self._running = False
        
        # Close TCP server
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except:
                pass
            self._server_socket = None
        
        # Stop scales hardware
        if self._scales is not None:
            self._scales.stop()
            self._scales = None
        
        # Close log file
        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None
            self._csv_writer = None
        
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
