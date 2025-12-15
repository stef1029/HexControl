import struct
import time
import serial
import binascii
from datetime import datetime

START = 0x02

CMD_HELLO     = 0x01
CMD_HELLO_ACK = 0x81
CMD_SHUTDOWN  = 0x7F

CMD_LED_SET    = 0x10
CMD_VALVE_SET  = 0x20
CMD_SPOT_SET   = 0x30
CMD_BUZZER_SET = 0x40


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
    frame = hdr + payload + struct.pack("<H", crc)
    log(f"TX cmd=0x{cmd:02X} len={len(payload)} crc=0x{crc:04X} bytes={binascii.hexlify(frame).decode()}")
    return frame


def read_exact(ser: serial.Serial, n: int) -> bytes:
    out = bytearray()
    while len(out) < n:
        chunk = ser.read(n - len(out))
        if not chunk:
            raise TimeoutError(f"Timeout reading {n} bytes (got {len(out)})")
        out += chunk
        log(f"RX chunk: {binascii.hexlify(chunk).decode()}")
    return bytes(out)


def recv_frame(ser: serial.Serial, timeout: float = 2.0) -> tuple[int, bytes]:
    ser.timeout = timeout
    log("Waiting for START...")
    while True:
        b = ser.read(1)
        if not b:
            raise TimeoutError("Timeout waiting for START byte")
        if b[0] == START:
            break

    cmd_len = read_exact(ser, 3)
    cmd = cmd_len[0]
    length = struct.unpack_from("<H", cmd_len, 1)[0]
    payload = read_exact(ser, length)
    crc_bytes = read_exact(ser, 2)

    crc_rx = struct.unpack("<H", crc_bytes)[0]
    hdr = bytes([START]) + cmd_len
    crc_calc = crc16_ccitt_false(hdr + payload)

    log(f"RX frame cmd=0x{cmd:02X} len={length} crc_rx=0x{crc_rx:04X} crc_calc=0x{crc_calc:04X}")
    if crc_rx != crc_calc:
        raise ValueError("CRC mismatch")
    return cmd, payload


def set_channel(ser: serial.Serial, cmd: int, index: int, value: int) -> None:
    if not (0 <= index <= 5):
        raise ValueError("index must be 0..5")
    if value not in (0, 1):
        raise ValueError("value must be 0 or 1")
    ser.write(build_frame(cmd, bytes([index, value])))


def main() -> None:
    port = "COM7"  # <-- set
    baud = 115200

    log(f"Opening {port} @ {baud}")
    with serial.Serial(port, baud) as ser:
        log("Resetting via DTR toggle")
        ser.dtr = False
        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.dtr = True
        time.sleep(1.2)

        log("Handshake: HELLO")
        ser.write(build_frame(CMD_HELLO))
        cmd, _ = recv_frame(ser, timeout=3.0)
        if cmd != CMD_HELLO_ACK:
            raise RuntimeError(f"Unexpected handshake response: 0x{cmd:02X}")
        log("Handshake OK")

        banks = [
            ("LED", CMD_LED_SET, 0.25),
            ("VALVE", CMD_VALVE_SET, 0.25),
            ("SPOT", CMD_SPOT_SET, 0.25),
            ("BUZZER", CMD_BUZZER_SET, 0.15),
        ]

        for name, bank_cmd, t_on in banks:
            log(f"=== Testing bank: {name} ===")
            for i in range(6):
                log(f"{name}[{i}] ON")
                set_channel(ser, bank_cmd, i, 1)
                time.sleep(t_on)
                log(f"{name}[{i}] OFF")
                set_channel(ser, bank_cmd, i, 0)
                time.sleep(0.10)

        log("Requesting Arduino reset (SHUTDOWN)")
        ser.write(build_frame(CMD_SHUTDOWN))
        time.sleep(0.3)

        log("Done.")


if __name__ == "__main__":
    main()
