#!/usr/bin/env python3
"""
Test script for reliable Arduino communication protocol.
Tests setup exchange, hardware control, and simulated trials.
"""

import serial
import time
import json
import struct
from cobs import cobs
from queue import Queue, Empty
from threading import Thread, Event
from colorama import init, Fore, Style
from typing import Optional, Dict, Any
import sys

# Initialize colorama for cross-platform colored output
init(autoreset=True)

class MessageType:
    """Message type constants"""
    MSG_SETUP = 0x01
    MSG_TRIAL = 0x02
    MSG_ACK = 0x03
    MSG_RESPONSE = 0x04
    MSG_EVENT = 0x05
    MSG_TEST = 0x06


class ReliableArduinoComm:
    """
    Reliable communication with Arduino using COBS framing and CRC validation.
    """
    
    def __init__(self, port: str, baudrate: int = 2000000):
        """
        Initialise communication handler.
        
        Args:
            port: Serial port (e.g., 'COM3' or '/dev/ttyACM0')
            baudrate: Communication speed
        """
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.receive_queue = Queue()
        self.ack_queue = Queue()
        self.running = False
        self.sequence_id = 0
        self.receive_thread = None
        
    def connect(self) -> bool:
        """
        Establish connection with Arduino.
        
        Returns:
            bool: True if successful
        """
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.1
            )
            
            # Clear buffers
            time.sleep(2)  # Wait for Arduino reset
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            # Start receive thread
            self.running = True
            self.receive_thread = Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            
            print(f"{Fore.GREEN}Connected to Arduino on {self.port}")
            
            # Wait for ready signal
            start_time = time.time()
            while time.time() - start_time < 5:
                try:
                    msg = self.receive_queue.get(timeout=0.1)
                    if msg.get('status') == 'ready':
                        print(f"{Fore.GREEN}Arduino ready! Version: {msg.get('version')}")
                        return True
                except Empty:
                    continue
            
            print(f"{Fore.RED}Timeout waiting for Arduino ready signal")
            return False
            
        except serial.SerialException as e:
            print(f"{Fore.RED}Failed to connect: {e}")
            return False
    
    def _calculate_crc16(self, data: bytes) -> int:
        """Calculate CRC16 checksum."""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc = crc >> 1
        return crc & 0xFFFF
    
    def _create_packet(self, msg_type: int, data: Dict[str, Any]) -> bytes:
        """
        Create a packet with JSON payload.
        
        Args:
            msg_type: Message type constant
            data: Dictionary to send as JSON
            
        Returns:
            bytes: Complete packet with header and CRC
        """
        # Convert data to JSON
        json_bytes = json.dumps(data).encode('utf-8')
        
        # Create packet
        packet = bytearray()
        packet.append(msg_type)
        packet.append(self.sequence_id)
        packet.append(len(json_bytes))
        packet.extend(json_bytes)
        
        # Add CRC
        crc = self._calculate_crc16(bytes(packet))
        packet.append(crc & 0xFF)
        packet.append((crc >> 8) & 0xFF)
        
        # Increment sequence ID
        self.sequence_id = (self.sequence_id + 1) % 256
        
        return bytes(packet)
    
    def _send_raw(self, data: bytes):
        """Send COBS-encoded data."""
        encoded = cobs.encode(data)
        self.serial.write(encoded + b'\x00')
    
    def send_with_ack(self, msg_type: int, data: Dict[str, Any], timeout: float = 1.0) -> bool:
        """
        Send message and wait for acknowledgement.
        
        Args:
            msg_type: Message type
            data: Data to send
            timeout: Timeout in seconds
            
        Returns:
            bool: True if acknowledged
        """
        packet = self._create_packet(msg_type, data)
        seq_id = self.sequence_id - 1  # We already incremented it
        
        # Try up to 3 times
        for attempt in range(3):
            self._send_raw(packet)
            
            # Wait for ACK
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    ack_seq = self.ack_queue.get(timeout=0.01)
                    if ack_seq == seq_id:
                        return True
                except Empty:
                    continue
            
            print(f"{Fore.YELLOW}Retry {attempt + 1}/3...")
        
        print(f"{Fore.RED}Failed to receive ACK")
        return False
    
    def _receive_loop(self):
        """Background thread for receiving data."""
        buffer = bytearray()
        
        while self.running:
            try:
                if self.serial and self.serial.in_waiting:
                    data = self.serial.read(self.serial.in_waiting)
                    buffer.extend(data)
                    
                    # Process complete COBS frames
                    while b'\x00' in buffer:
                        frame_end = buffer.index(b'\x00')
                        if frame_end > 0:
                            try:
                                decoded = cobs.decode(bytes(buffer[:frame_end]))
                                self._process_packet(decoded)
                            except cobs.DecodeError:
                                print(f"{Fore.RED}COBS decode error")
                        
                        buffer = buffer[frame_end + 1:]
                        
            except Exception as e:
                print(f"{Fore.RED}Receive error: {e}")
            
            time.sleep(0.001)
    
    def _process_packet(self, packet: bytes):
        """Process received packet."""
        if len(packet) < 5:
            return
        
        # Parse header
        msg_type = packet[0]
        seq_id = packet[1]
        payload_length = packet[2]
        
        # Verify CRC
        received_crc = packet[-2] | (packet[-1] << 8)
        calculated_crc = self._calculate_crc16(packet[:-2])
        
        if received_crc != calculated_crc:
            print(f"{Fore.RED}CRC mismatch")
            return
        
        # Handle ACK
        if msg_type == MessageType.MSG_ACK:
            self.ack_queue.put(seq_id)
            return
        
        # Parse JSON payload
        if payload_length > 0:
            try:
                payload = json.loads(packet[3:3+payload_length].decode('utf-8'))
                
                # Handle different message types
                if msg_type in [MessageType.MSG_RESPONSE, MessageType.MSG_EVENT]:
                    self.receive_queue.put(payload)
                    
            except json.JSONDecodeError as e:
                print(f"{Fore.RED}JSON decode error: {e}")
    
    def get_message(self, timeout: float = 0.1) -> Optional[Dict[str, Any]]:
        """
        Get message from receive queue.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Received message or None
        """
        try:
            return self.receive_queue.get(timeout=timeout)
        except Empty:
            return None
    
    def close(self):
        """Close connection."""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1)
        if self.serial:
            self.serial.close()


def test_hardware(comm: ReliableArduinoComm):
    """Test all hardware components."""
    print(f"\n{Fore.CYAN}{'='*50}")
    print(f"{Fore.CYAN}Testing Hardware Components")
    print(f"{Fore.CYAN}{'='*50}")
    
    # Test LEDs
    print(f"\n{Fore.YELLOW}Testing LEDs...")
    if comm.send_with_ack(MessageType.MSG_TEST, {"test": "leds"}):
        time.sleep(2)
        response = comm.get_message(timeout=0.5)
        if response and response.get('status') == 'complete':
            print(f"{Fore.GREEN}✓ LED test complete")
    
    # Test valves
    print(f"\n{Fore.YELLOW}Testing valves/solenoids...")
    if comm.send_with_ack(MessageType.MSG_TEST, {"test": "valves"}):
        time.sleep(2)
        response = comm.get_message(timeout=0.5)
        if response and response.get('status') == 'complete':
            print(f"{Fore.GREEN}✓ Valve test complete")
    
    # Test buzzer
    print(f"\n{Fore.YELLOW}Testing buzzer...")
    if comm.send_with_ack(MessageType.MSG_TEST, {"test": "buzzer"}):
        time.sleep(2)
        response = comm.get_message(timeout=0.5)
        if response and response.get('status') == 'complete':
            print(f"{Fore.GREEN}✓ Buzzer test complete")


def test_setup_protocol(comm: ReliableArduinoComm):
    """Test setup protocol exchange."""
    print(f"\n{Fore.CYAN}{'='*50}")
    print(f"{Fore.CYAN}Testing Setup Protocol")
    print(f"{Fore.CYAN}{'='*50}")
    
    setup_params = {
        "phase": 5,
        "trials": 20,
        "punishment_ms": 3000,
        "audio": True
    }
    
    print(f"\n{Fore.YELLOW}Sending setup parameters:")
    for key, value in setup_params.items():
        print(f"  {key}: {value}")
    
    if comm.send_with_ack(MessageType.MSG_SETUP, setup_params):
        print(f"{Fore.GREEN}✓ Setup acknowledged")
        
        # Wait for confirmation response
        response = comm.get_message(timeout=1.0)
        if response and response.get('status') == 'setup_complete':
            print(f"{Fore.GREEN}✓ Setup confirmed by Arduino")
            print(f"  Phase: {response.get('phase')}")
            print(f"  Trials: {response.get('trials')}")
        else:
            print(f"{Fore.RED}✗ No setup confirmation received")
    else:
        print(f"{Fore.RED}✗ Setup not acknowledged")


def run_simulated_trials(comm: ReliableArduinoComm, num_trials: int = 5):
    """Run simulated trials."""
    print(f"\n{Fore.CYAN}{'='*50}")
    print(f"{Fore.CYAN}Running {num_trials} Simulated Trials")
    print(f"{Fore.CYAN}{'='*50}")
    
    successes = 0
    failures = 0
    
    for trial_num in range(1, num_trials + 1):
        # Select random port
        port = (trial_num % 6) + 1
        
        print(f"\n{Fore.YELLOW}Trial {trial_num}/{num_trials}: Port {port}")
        
        trial_data = {
            "port": port,
            "type": "visual",
            "trial_number": trial_num
        }
        
        if comm.send_with_ack(MessageType.MSG_TRIAL, trial_data):
            print(f"  {Fore.CYAN}Trial started...")
            
            # Wait for trial result
            start_time = time.time()
            while time.time() - start_time < 5:
                response = comm.get_message(timeout=0.1)
                if response and response.get('event') == 'trial_complete':
                    result = response.get('result')
                    if result == 'success':
                        successes += 1
                        reaction_time = response.get('reaction_time', 0)
                        print(f"  {Fore.GREEN}✓ Success! Reaction time: {reaction_time}ms")
                    else:
                        failures += 1
                        error = response.get('error', 'unknown')
                        print(f"  {Fore.RED}✗ Failed: {error}")
                    break
            else:
                print(f"  {Fore.RED}✗ Trial timeout")
                failures += 1
        else:
            print(f"  {Fore.RED}✗ Failed to start trial")
            failures += 1
        
        time.sleep(0.5)
    
    # Print summary
    print(f"\n{Fore.CYAN}{'='*50}")
    print(f"{Fore.CYAN}Trial Summary")
    print(f"{Fore.CYAN}{'='*50}")
    print(f"{Fore.GREEN}Successes: {successes}/{num_trials}")
    print(f"{Fore.RED}Failures: {failures}/{num_trials}")
    success_rate = (successes / num_trials) * 100 if num_trials > 0 else 0
    print(f"{Fore.CYAN}Success Rate: {success_rate:.1f}%")


def main():
    """Main test function."""
    print(f"{Fore.CYAN}{'='*50}")
    print(f"{Fore.CYAN}Arduino Reliable Communication Test")
    print(f"{Fore.CYAN}{'='*50}")
    
    # Get serial port
    port = "COM7"
    
    # Create communication handler
    comm = ReliableArduinoComm(port)
    
    try:
        # Connect to Arduino
        if not comm.connect():
            print(f"{Fore.RED}Failed to establish connection")
            return
        
        # Listen for heartbeats in background
        def print_heartbeats():
            while comm.running:
                msg = comm.get_message(timeout=0.1)
                if msg and msg.get('event') == 'heartbeat':
                    print(f"{Fore.CYAN}♥ Heartbeat: uptime={msg.get('uptime')}ms, phase={msg.get('phase')}")
        
        heartbeat_thread = Thread(target=print_heartbeats, daemon=True)
        heartbeat_thread.start()
        
        # Run tests
        time.sleep(1)
        test_hardware(comm)
        
        time.sleep(1)
        test_setup_protocol(comm)
        
        time.sleep(1)
        run_simulated_trials(comm)
        
        print(f"\n{Fore.GREEN}All tests complete!")
        print(f"{Fore.YELLOW}Press Enter to exit...")
        input()
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Test interrupted")
        
    finally:
        comm.close()
        print(f"{Fore.CYAN}Connection closed")


if __name__ == "__main__":
    main()