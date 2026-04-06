"""
Scales Client - TCP client for communicating with scales server subprocess.

This module provides a simple client interface for protocols to get weight data
from the scales server running in a separate subprocess.

Usage:
    client = ScalesClient(tcp_port=5100)
    client.connect()
    
    if client.ping():
        weight = client.get_weight()
        print(f"Weight: {weight}g")
    
    client.disconnect()
"""

import logging
import socket
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

DEFAULT_TCP_PORT = 5100
SOCKET_TIMEOUT = 5.0  # Seconds to wait for server responses
CONNECT_TIMEOUT = 10.0  # Seconds to wait when connecting


# =============================================================================
# Scales Client
# =============================================================================

class ScalesClient:
    """
    TCP client for communicating with the scales server subprocess.
    
    Provides a simple interface for protocols to get weight data without
    managing the hardware directly.
    """
    
    def __init__(self, tcp_port: int = DEFAULT_TCP_PORT, host: str = 'localhost'):
        """
        Initialise the scales client.
        
        Args:
            tcp_port: TCP port that the scales server is listening on.
            host: Host address (default 'localhost' for subprocess).
        """
        self._host = host
        self._tcp_port = tcp_port
        self._connected = False
    
    @property
    def is_connected(self) -> bool:
        """Return True if the client has successfully connected to the server."""
        return self._connected
    
    @property
    def tcp_port(self) -> int:
        """Return the TCP port number."""
        return self._tcp_port
    
    def connect(self, timeout: float = CONNECT_TIMEOUT) -> bool:
        """
        Verify connection to the scales server.
        
        Attempts to ping the server to verify it's running.
        
        Args:
            timeout: Maximum time to wait for connection.
            
        Returns:
            True if connection successful, False otherwise.
        """
        try:
            # Try to ping the server
            if self.ping(timeout=timeout):
                self._connected = True
                return True
            return False
        except Exception as e:
            print(f"Warning: scales connect failed: {e}")
            return False
    
    def disconnect(self) -> None:
        """
        Disconnect from the scales server.
        
        Note: This does NOT stop the server subprocess - use shutdown() for that.
        """
        self._connected = False
    
    def shutdown(self) -> bool:
        """
        Send shutdown command to the scales server.
        
        This tells the server subprocess to stop gracefully.
        
        Returns:
            True if shutdown command was acknowledged.
        """
        try:
            response = self._send_command("SHUTDOWN", timeout=SOCKET_TIMEOUT)
            self._connected = False
            return response == "OK"
        except Exception as e:
            print(f"Warning: scales shutdown failed: {e}")
            self._connected = False
            return False
    
    def ping(self, timeout: float = SOCKET_TIMEOUT) -> bool:
        """
        Ping the scales server to check if it's alive.
        
        Args:
            timeout: Maximum time to wait for response.
            
        Returns:
            True if server responds with PONG.
        """
        try:
            response = self._send_command("PING", timeout=timeout)
            return response == "PONG"
        except Exception as e:
            print(f"Warning: scales ping failed: {e}")
            return False
    
    def get_weight(self, timeout: float = SOCKET_TIMEOUT) -> Optional[float]:
        """
        Get the current weight from the scales.
        
        Args:
            timeout: Maximum time to wait for response.
            
        Returns:
            Weight in grams, or None if no reading available.
        """
        try:
            response = self._send_command("GET", timeout=timeout)
            if response == "NONE":
                return None
            return float(response)
        except Exception as e:
            logger.warning("get_weight failed: %s", e)
            return None
    
    def _send_command(self, command: str, timeout: float = SOCKET_TIMEOUT) -> str:
        """
        Send a command to the server and return the response.
        
        Opens a new connection for each command (simple protocol).
        
        Args:
            command: Command string to send.
            timeout: Socket timeout in seconds.
            
        Returns:
            Response string from server.
            
        Raises:
            ConnectionError: If unable to connect to server.
            TimeoutError: If server doesn't respond in time.
        """
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((self._host, self._tcp_port))
            
            # Send command
            sock.sendall(command.encode('utf-8'))
            
            # Receive response
            response = sock.recv(1024)
            return response.decode('utf-8').strip()
            
        except socket.timeout:
            raise TimeoutError(f"Timeout waiting for response to {command}")
        except ConnectionRefusedError:
            raise ConnectionError(f"Connection refused on port {self._tcp_port}")
        except Exception as e:
            raise ConnectionError(f"Error sending command: {e}")
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError as e:
                    print(f"Warning: error closing scales socket: {e}")


# =============================================================================
# Convenience Functions
# =============================================================================

def quick_get_weight(tcp_port: int = DEFAULT_TCP_PORT) -> Optional[float]:
    """
    Quick one-shot function to get the current weight.
    
    Creates a temporary client, gets the weight, and disconnects.
    Useful for simple scripts that just need to read the weight once.
    
    Args:
        tcp_port: TCP port of the scales server.
        
    Returns:
        Weight in grams, or None if unavailable.
    """
    client = ScalesClient(tcp_port=tcp_port)
    try:
        return client.get_weight()
    except Exception as e:
        print(f"Warning: scales quick_read failed: {e}")
        return None
