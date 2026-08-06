"""Verified JUNO-DS patch-buffer constants.

Addresses and sizes are based on the JUNO-DS adaptation in KnobKraft Orm and
captured JUNO-DS traffic. They are kept separate from the AI-facing model so
protocol details remain deterministic and reviewable.
"""

from dataclasses import dataclass

ROLAND_MANUFACTURER_ID = 0x41
JUNO_DS_MODEL_ID = (0x00, 0x00, 0x3A)
DEFAULT_DEVICE_ID = 0x10
COMMAND_RQ1 = 0x11
COMMAND_DT1 = 0x12
EDIT_BUFFER_BASE = (0x1F, 0x00, 0x00, 0x00)
SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class BlockSpec:
    key: str
    label: str
    offset: tuple[int, int, int, int]
    size: int


BLOCK_SPECS = (
    BlockSpec("patch_common", "Patch Common", (0x00, 0x00, 0x00, 0x00), 0x50),
    BlockSpec("mfx", "Patch Common MFX", (0x00, 0x00, 0x02, 0x00), 0x91),
    BlockSpec("chorus", "Patch Common Chorus", (0x00, 0x00, 0x04, 0x00), 0x54),
    BlockSpec("reverb", "Patch Common Reverb", (0x00, 0x00, 0x06, 0x00), 0x53),
    BlockSpec("tone_mix", "Patch Common Tone Mix Table", (0x00, 0x00, 0x10, 0x00), 0x29),
    BlockSpec("tone_1", "Tone 1", (0x00, 0x00, 0x20, 0x00), 0x9A),
    BlockSpec("tone_2", "Tone 2", (0x00, 0x00, 0x22, 0x00), 0x9A),
    BlockSpec("tone_3", "Tone 3", (0x00, 0x00, 0x24, 0x00), 0x9A),
    BlockSpec("tone_4", "Tone 4", (0x00, 0x00, 0x26, 0x00), 0x9A),
)

BLOCK_BY_KEY = {block.key: block for block in BLOCK_SPECS}

CATEGORIES = (
    "NO ASSIGN",
    "AC. PIANO",
    "EL. PIANO",
    "KEYBOARDS",
    "BELL",
    "MALLET",
    "ORGAN",
    "ACCORDION",
    "HARMONICA",
    "AC.GUITAR",
    "EL.GUITAR",
    "DIST.GUITAR",
    "BASS",
    "SYNTH BASS",
    "STRINGS",
    "ORCHESTRA",
    "HIT&STAB",
    "WIND",
    "FLUTE",
    "AC.BRASS",
    "SYNTH BRASS",
    "SAX",
    "HARD LEAD",
    "SOFT LEAD",
    "TECHNO SYNTH",
    "PULSATING",
    "SYNTH FX",
    "OTHER SYNTH",
    "BRIGHT PAD",
    "SOFT PAD",
    "VOX",
    "PLUCKED",
    "ETHNIC",
    "FRETTED",
    "PERCUSSION",
    "SOUND FX",
    "BEAT&GROOVE",
    "DRUMS",
    "COMBINATION",
)

PATCH_NAME_LENGTH = 12
CATEGORY_OFFSET = 0x0C


def seven_bit_to_int(values: tuple[int, ...] | list[int]) -> int:
    result = 0
    for value in values:
        if not 0 <= value <= 0x7F:
            raise ValueError("Roland address and size bytes must be 7-bit values")
        result = (result << 7) | value
    return result


def int_to_seven_bit(value: int, width: int = 4) -> tuple[int, ...]:
    if value < 0 or value >= 1 << (7 * width):
        raise ValueError(f"value does not fit in {width} 7-bit bytes")
    return tuple((value >> (7 * shift)) & 0x7F for shift in reversed(range(width)))


def add_address(base: tuple[int, ...], offset: tuple[int, ...]) -> tuple[int, ...]:
    if len(base) != len(offset):
        raise ValueError("base and offset addresses must have the same width")
    return int_to_seven_bit(seven_bit_to_int(base) + seven_bit_to_int(offset), len(base))


def edit_address(block: BlockSpec) -> tuple[int, int, int, int]:
    return add_address(EDIT_BUFFER_BASE, block.offset)  # type: ignore[return-value]
