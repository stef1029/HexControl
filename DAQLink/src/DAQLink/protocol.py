"""
DAQ Protocol — shared constants and binary message decoders.

Extracts the channel map, message format, and decode logic used by both
the acquisition script (``serial_listen.py``) and the live viewer.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Channel map (least-significant-bit first, matching the Arduino pin order)
# ---------------------------------------------------------------------------
CHANNEL_NAMES: tuple[str, ...] = (
    "SENSOR6", "SENSOR1", "SENSOR5", "SENSOR2", "SENSOR4", "SENSOR3",
    "LED_3",   "LED_4",   "LED_2",   "LED_5",   "LED_1",   "LED_6",
    "VALVE4",  "VALVE3",  "VALVE5",  "VALVE2",  "VALVE6",  "VALVE1",
    "GO_CUE",  "NOGO_CUE", "CAMERA", "SCALES", "LASER",
)

NUM_CHANNELS = len(CHANNEL_NAMES)  # 23

# Logical groupings for display (numerically sorted within each group)
CHANNEL_GROUPS: dict[str, list[str]] = {
    "Sensors": ["SENSOR1", "SENSOR2", "SENSOR3", "SENSOR4", "SENSOR5", "SENSOR6"],
    "LEDs":    ["LED_1", "LED_2", "LED_3", "LED_4", "LED_5", "LED_6"],
    "Valves":  ["VALVE1", "VALVE2", "VALVE3", "VALVE4", "VALVE5", "VALVE6"],
    "Cues":    ["GO_CUE", "NOGO_CUE"],
    "System":  ["CAMERA", "SCALES", "LASER"],
}

# Flat display order derived from groups
DISPLAY_ORDER: list[str] = []
for _names in CHANNEL_GROUPS.values():
    DISPLAY_ORDER.extend(_names)

# Reverse lookup: channel name -> bit index in the 40-bit state word
_CHANNEL_BIT_INDEX: dict[str, int] = {name: i for i, name in enumerate(CHANNEL_NAMES)}

# ---------------------------------------------------------------------------
# Serial protocol constants
# ---------------------------------------------------------------------------
BAUDRATE = 115200
HANDSHAKE_BYTE = b"s"
MSG_START = 0x01
MSG_END = 0x02


# ---------------------------------------------------------------------------
# Decode helpers
# ---------------------------------------------------------------------------

def decode_message(raw: bytes) -> tuple[int, int]:
    """Decode 9 interleaved bytes into ``(message_id, state_word)``.

    The Arduino Mega sends 11-byte frames: ``0x01 [9 payload bytes] 0x02``.
    After stripping the delimiters the caller passes the 9 payload bytes here.

    Layout (interleaved for robustness):
        byte 0,2,4,6  -> message_id  (uint32, big-endian nibbles)
        byte 1,3,5,7,8 -> state_word (40-bit, big-endian nibbles)
    """
    message_id = (
        (raw[0] << 24) | (raw[2] << 16) | (raw[4] << 8) | raw[6]
    )
    state_word = (
        (raw[1] << 32) | (raw[3] << 24) | (raw[5] << 16)
        | (raw[7] << 8) | raw[8]
    )
    return message_id, state_word


def extract_channel(state_word: int, channel_name: str) -> int:
    """Return 0 or 1 for a single channel from the state word."""
    return (state_word >> _CHANNEL_BIT_INDEX[channel_name]) & 1


def state_word_to_bits(state_word: int) -> list[int]:
    """Return a list of 23 bit-values in :data:`CHANNEL_NAMES` order."""
    return [(state_word >> i) & 1 for i in range(NUM_CHANNELS)]
