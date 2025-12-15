import struct
import time
import threading
import queue
from collections import deque
from dataclasses import dataclass
from datetime import datetime

import serial

START = 0x02

CMD_HELLO       = 0x01
CMD_HELLO_ACK   = 0x81

CMD_ARM_PORT    = 0x12
CMD_LED_SET     = 0x10
CMD_VALVE_PULSE = 0x21
CMD_EVENT_ACK   = 0x91
CMD_SHUTDOWN    = 0x7F

CMD_ACK          = 0xA0
CMD_SENSOR_EVENT = 0x90


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}")


def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return crc


def build_frame(cmd: int, payload: bytes = b"") -> bytes:
    hdr = struct.pack("<BBH", START, cmd, len(payload))
    crc = crc16_ccitt_false(hdr + payload)
    return hdr + payload + struct.pack("<H", crc)


@dataclass(frozen=True)
class SensorEvent:
    event_id: int
    port: int
    t_ms: int
    received_monotonic: float


class ReliableRigLink:
    """
    Command+event link with:
      - Reliable commands: SEQ(u16) + ACK(SEQ,status), retry on timeout.
      - Latest-wins events from device: SENSOR_EVENT(event_id,port,t_ms) resent until ACKed.
      - Python-side event buffer: deduplicated by event_id, supports latest_event/drain/wait.

    This matches a behavioural control style where Python owns the task state machine
    and Arduino provides low-latency IO + debounced sensor events.
    """

    def __init__(self, ser: serial.Serial, *, rx_timeout_s: float = 0.1):
        self.ser = ser
        self.ser.timeout = rx_timeout_s

        self._stop = threading.Event()
        self._rx_thread: threading.Thread | None = None

        self._ack_waiters: dict[int, queue.Queue[int]] = {}
        self._ack_lock = threading.Lock()

        self._events = deque[SensorEvent](maxlen=1024)
        self._events_lock = threading.Lock()
        self._events_signal = threading.Condition(self._events_lock)

        self._last_event_id_seen: int | None = None
        self._hello_seen = threading.Event()
        self._rx_error: Exception | None = None

        self._seq = 1

    # ---------------- Public API ----------------
    def start(self) -> None:
        self._stop.clear()
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._rx_thread:
            self._rx_thread.join(timeout=1.0)

    def next_seq(self) -> int:
        s = self._seq
        self._seq = (self._seq + 1) & 0xFFFF
        if self._seq == 0:
            self._seq = 1
        return s

    def wait_hello(self, timeout: float = 3.0) -> None:
        if not self._hello_seen.wait(timeout=timeout):
            raise TimeoutError("Did not receive HELLO_ACK")
        if self._rx_error:
            raise RuntimeError(f"RX error: {self._rx_error}")

    def latest_event(self, *, clear: bool = False) -> SensorEvent | None:
        with self._events_lock:
            if not self._events:
                return None
            ev = self._events[-1]
            if clear:
                self._events.clear()
            return ev

    def drain_events(self) -> list[SensorEvent]:
        with self._events_lock:
            out = list(self._events)
            self._events.clear()
            return out

    def wait_for_event(self, *, port: int | None = None, timeout: float | None = None) -> SensorEvent:
        deadline = None if timeout is None else (time.monotonic() + timeout)

        with self._events_lock:
            while True:
                if self._rx_error:
                    raise RuntimeError(f"RX error: {self._rx_error}")

                # Find most recent matching event (latest-wins preference on Python side too)
                if self._events:
                    if port is None:
                        return self._events[-1]
                    for ev in reversed(self._events):
                        if ev.port == port:
                            return ev

                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("Timed out waiting for event")
                    self._events_signal.wait(timeout=remaining)
                else:
                    self._events_signal.wait()

    # ---------------- Reliable commands ----------------
    def send_hello(self) -> None:
        self.ser.write(build_frame(CMD_HELLO))
        log("TX HELLO")

    def send_command(self, cmd: int, payload_rest: bytes, *, retries: int = 10, timeout: float = 0.2) -> int:
        """
        Send a reliable SEQ'd command. Returns status (0 = OK).
        """
        seq = self.next_seq()
        payload = struct.pack("<H", seq) + payload_rest
        frame = build_frame(cmd, payload)

        q = queue.Queue(maxsize=1)
        with self._ack_lock:
            self._ack_waiters[seq] = q

        try:
            for attempt in range(1, retries + 1):
                self.ser.write(frame)
                log(f"TX cmd=0x{cmd:02X} seq={seq} attempt={attempt}")

                try:
                    status = q.get(timeout=timeout)
                    log(f"RX ACK seq={seq} status=0x{status:02X}")
                    return status
                except queue.Empty:
                    log(f"ACK timeout seq={seq} (retrying)")
            raise TimeoutError(f"No ACK after {retries} retries (cmd=0x{cmd:02X}, seq={seq})")
        finally:
            with self._ack_lock:
                self._ack_waiters.pop(seq, None)

    def arm_port(self, port: int) -> None:
        st = self.send_command(CMD_ARM_PORT, struct.pack("<B", port))
        if st != 0:
            raise RuntimeError(f"ARM_PORT failed status=0x{st:02X}")

    def led_set(self, port: int, value: int) -> None:
        st = self.send_command(CMD_LED_SET, struct.pack("<BB", port, value))
        if st != 0:
            raise RuntimeError(f"LED_SET failed status=0x{st:02X}")

    def valve_pulse(self, port: int, duration_ms: int) -> None:
        st = self.send_command(CMD_VALVE_PULSE, struct.pack("<BH", port, duration_ms))
        if st != 0:
            raise RuntimeError(f"VALVE_PULSE failed status=0x{st:02X}")

    def event_ack(self, event_id: int) -> None:
        # ACK is a reliable command too (SEQ'd)
        st = self.send_command(CMD_EVENT_ACK, struct.pack("<H", event_id))
        if st != 0:
            raise RuntimeError(f"EVENT_ACK failed status=0x{st:02X}")

    def shutdown(self) -> None:
        st = self.send_command(CMD_SHUTDOWN, b"")
        log(f"Shutdown status=0x{st:02X}")

    # ---------------- RX loop + framing ----------------
    def _read_exact(self, n: int) -> bytes:
        out = bytearray()
        while len(out) < n and not self._stop.is_set():
            chunk = self.ser.read(n - len(out))
            if not chunk:
                raise TimeoutError(f"Timeout reading {n} bytes (got {len(out)})")
            out += chunk
        return bytes(out)

    def _recv_frame(self) -> tuple[int, bytes] | None:
        """
        Try to receive one framed packet.

        Returns:
            (cmd, payload) if a full valid frame was received.
            None if no data arrived before timeout (normal idle condition).
        """
        # resync scan for START
        while not self._stop.is_set():
            b = self.ser.read(1)
            if not b:
                return None  # idle, not an error
            if b[0] == START:
                break

        if self._stop.is_set():
            return None

        # cmd + len
        cmd_len = self._read_exact(3)  # may raise TimeoutError if stream stalls mid-frame
        cmd = cmd_len[0]
        length = struct.unpack_from("<H", cmd_len, 1)[0]

        payload = self._read_exact(length)
        crc_bytes = self._read_exact(2)

        crc_rx = struct.unpack("<H", crc_bytes)[0]
        hdr = bytes([START]) + cmd_len
        crc_calc = crc16_ccitt_false(hdr + payload)
        if crc_rx != crc_calc:
            raise ValueError(f"CRC mismatch rx=0x{crc_rx:04X} calc=0x{crc_calc:04X}")

        return cmd, payload

    def _rx_loop(self) -> None:
        try:
            while not self._stop.is_set():
                msg = self._recv_frame()
                if msg is None:
                    continue  # idle
                cmd, payload = msg

                if cmd == CMD_HELLO_ACK:
                    self._hello_seen.set()

                elif cmd == CMD_ACK:
                    if len(payload) != 3:
                        continue
                    seq = struct.unpack_from("<H", payload, 0)[0]
                    status = payload[2]
                    with self._ack_lock:
                        q = self._ack_waiters.get(seq)
                    if q:
                        q.put(status)

                elif cmd == CMD_SENSOR_EVENT:
                    if len(payload) != 7:
                        continue
                    event_id = struct.unpack_from("<H", payload, 0)[0]
                    port = payload[2]
                    t_ms = struct.unpack_from("<I", payload, 3)[0]

                    # Deduplicate repeats
                    if self._last_event_id_seen == event_id:
                        with self._events_lock:
                            self._events_signal.notify_all()
                        continue
                    self._last_event_id_seen = event_id

                    ev = SensorEvent(
                        event_id=event_id,
                        port=port,
                        t_ms=t_ms,
                        received_monotonic=time.monotonic(),
                    )
                    with self._events_lock:
                        self._events.append(ev)
                        self._events_signal.notify_all()

                else:
                    # ignore unknown frames
                    pass

        except Exception as e:
            self._rx_error = e
            with self._events_lock:
                self._events_signal.notify_all()


def reset_arduino_via_dtr(ser: serial.Serial) -> None:
    """
    Many Arduino-class USB CDC devices reset on DTR toggle.
    This makes tests repeatable and clears stale bytes.
    """
    ser.dtr = False
    time.sleep(0.2)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.dtr = True
    time.sleep(1.2)


def main() -> None:
    PORT = "COM7"     # <-- set this
    BAUD = 115200

    with serial.Serial(PORT, BAUD, timeout=0.1) as ser:
        log(f"Open {PORT} @ {BAUD}")
        reset_arduino_via_dtr(ser)

        link = ReliableRigLink(ser)
        link.start()

        link.send_hello()
        link.wait_hello(timeout=3.0)
        log("Handshake OK")

        # Test cycle across all ports for easy validation
        for port in range(6):
            log(f"\n=== TEST PORT {port} ===")
            link.arm_port(port)

            # Clear any old events you don't care about before starting a new trial
            drained = link.drain_events()
            if drained:
                log(f"Drained {len(drained)} old events before trial")

            link.led_set(port, 1)
            log(f"LED[{port}] ON; waiting for debounced touch (LOW >= 50ms)")

            ev = link.wait_for_event(port=port, timeout=30.0)
            log(f"Got EVENT id={ev.event_id} port={ev.port} t_ms={ev.t_ms}")

            # Important: ACK immediately so Arduino stops resending
            link.event_ack(ev.event_id)
            log(f"ACKed event_id={ev.event_id}")

            link.led_set(port, 0)
            link.valve_pulse(port, 500)
            log(f"LED[{port}] OFF; VALVE[{port}] pulse 500ms")

            # small pause between ports
            time.sleep(0.25)

        log("\nAll ports tested. Shutting down Arduino.")
        link.shutdown()
        link.stop()
        log("Done.")


if __name__ == "__main__":
    main()
