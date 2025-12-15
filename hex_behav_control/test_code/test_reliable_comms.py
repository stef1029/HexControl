import struct
import time
import serial
import binascii
from datetime import datetime

START = 0x02

CMD_HELLO     = 0x01
CMD_HELLO_ACK = 0x81
CMD_LED_ON    = 0x10
CMD_LED_OFF   = 0x11
CMD_SHUTDOWN  = 0x7F


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

    log(f"TX frame cmd=0x{cmd:02X} len={len(payload)} "
        f"crc=0x{crc:04X} bytes={binascii.hexlify(frame).decode()}")

    return frame


def read_exact(ser: serial.Serial, n: int) -> bytes:
    out = bytearray()
    while len(out) < n:
        chunk = ser.read(n - len(out))
        if not chunk:
            raise TimeoutError(f"Timeout reading {n} bytes (got {len(out)})")
        out += chunk
        log(f"RX raw chunk: {binascii.hexlify(chunk).decode()}")
    return bytes(out)


def recv_frame(ser: serial.Serial, timeout: float = 2.0) -> tuple[int, bytes]:
    ser.timeout = timeout

    log("Waiting for START byte...")
    while True:
        b = ser.read(1)
        if not b:
            raise TimeoutError("Timeout waiting for START byte")
        log(f"RX byte: {b.hex()}")
        if b[0] == START:
            log("START byte detected")
            break

    # Read cmd + length
    cmd_len = read_exact(ser, 3)
    cmd = cmd_len[0]
    length = struct.unpack_from("<H", cmd_len, 1)[0]

    log(f"Header received: cmd=0x{cmd:02X}, payload_len={length}")

    payload = read_exact(ser, length)
    crc_bytes = read_exact(ser, 2)

    crc_rx = struct.unpack("<H", crc_bytes)[0]
    hdr = bytes([START]) + cmd_len
    crc_calc = crc16_ccitt_false(hdr + payload)

    log(f"CRC rx=0x{crc_rx:04X}, calc=0x{crc_calc:04X}")

    if crc_rx != crc_calc:
        raise ValueError("CRC mismatch")

    log(f"RX frame OK cmd=0x{cmd:02X} payload={binascii.hexlify(payload).decode()}")

    return cmd, payload


def main() -> None:
    port = "COM7"      # <-- change
    baud = 115200

    log(f"Opening serial port {port} @ {baud}")
    with serial.Serial(port, baud) as ser:

        log("Toggling DTR to reset Arduino")
        ser.dtr = False
        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.dtr = True

        log("Waiting for Arduino reboot")
        time.sleep(1.2)

        # Handshake
        log("Sending HELLO")
        ser.write(build_frame(CMD_HELLO))

        cmd, _ = recv_frame(ser, timeout=3.0)
        if cmd != CMD_HELLO_ACK:
            raise RuntimeError(f"Unexpected handshake response: 0x{cmd:02X}")

        log("Handshake successful")

        # LED test
        for i in range(6):
            log(f"Turning LED {i} ON")
            ser.write(build_frame(CMD_LED_ON, bytes([i])))
            time.sleep(0.3)

            log(f"Turning LED {i} OFF")
            ser.write(build_frame(CMD_LED_OFF, bytes([i])))
            time.sleep(0.15)

        # Shutdown
        log("Sending SHUTDOWN")
        ser.write(build_frame(CMD_SHUTDOWN))
        time.sleep(0.3)

        log("Script complete; closing port")


if __name__ == "__main__":
    main()
