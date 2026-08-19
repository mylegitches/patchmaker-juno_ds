"""Deterministic, fully-owned JUNO-DS temporary-patch initialization."""

from __future__ import annotations

from .spec import BLOCK_SPECS, CATEGORY_OFFSET, PATCH_NAME_LENGTH


def _write_nibbles(data: list[int], offset: int, value: int, width: int = 4) -> None:
    for index in range(width):
        shift = (width - index - 1) * 4
        data[offset + index] = (value >> shift) & 0x0F


def initialized_blocks(name: str, category: int) -> dict[str, tuple[int, ...]]:
    """Build all nine blocks without inheriting a byte from another patch.

    Defaults are neutral values from the JUNO-DS MIDI implementation. Reserved
    bytes are deliberately zero. Effect parameter words use the documented
    zero point (32768, encoded as four nibbles) rather than an out-of-range
    all-zero word.
    """
    blocks = {spec.key: [0] * spec.size for spec in BLOCK_SPECS}

    common = blocks["patch_common"]
    common[:PATCH_NAME_LENGTH] = name.ljust(PATCH_NAME_LENGTH).encode("ascii")
    common[CATEGORY_OFFSET] = category
    common[0x0E] = 127
    for offset in (0x0F, 0x11, 0x12, 0x13, 0x22, 0x23, 0x24, 0x25, 0x26):
        common[offset] = 64
    common[0x16] = 1
    common[0x29] = common[0x2A] = 2
    for control in range(4):
        base = 0x2B + control * 9
        for destination in range(4):
            common[base + 2 + destination * 2] = 64
    common[0x4F] = 1

    mfx = blocks["mfx"]
    mfx[0x01] = 127
    for offset in (0x06, 0x08, 0x0A, 0x0C):
        mfx[offset] = 64
    for parameter in range(32):
        _write_nibbles(mfx, 0x11 + parameter * 4, 32768)

    chorus = blocks["chorus"]
    for parameter in range(20):
        _write_nibbles(chorus, 0x04 + parameter * 4, 32768)

    reverb = blocks["reverb"]
    for parameter in range(20):
        _write_nibbles(reverb, 0x03 + parameter * 4, 32768)

    mix = blocks["tone_mix"]
    for tone_index in range(4):
        base = 0x05 + tone_index * 9
        mix[base] = int(tone_index == 0)
        mix[base + 2] = 127
        mix[base + 5] = 1
        mix[base + 6] = 127

    for tone_index in range(4):
        tone = blocks[f"tone_{tone_index + 1}"]
        tone[0x00] = 127 if tone_index == 0 else 0
        tone[0x01] = tone[0x02] = tone[0x04] = 64
        tone[0x05] = tone[0x07] = 64
        tone[0x08] = 1
        tone[0x0C] = 127
        tone[0x12] = tone[0x13] = tone[0x14] = 1
        tone[0x34] = 1
        for offset in (0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E):
            tone[offset] = 64
        for offset in range(0x43, 0x48):
            tone[offset] = 64
        tone[0x48] = 1
        tone[0x49] = 127
        for offset in (0x4A, 0x4C, 0x4E, 0x4F, 0x51, 0x52, 0x53, 0x54):
            tone[offset] = 64
        tone[0x5E] = 64
        tone[0x5F] = 60
        tone[0x60] = 3
        for offset in (0x62, 0x63, 0x64, 0x65):
            tone[offset] = 64
        tone[0x6A] = tone[0x6B] = tone[0x6C] = 127
        tone[0x70] = tone[0x7E] = 2
        for offset in (0x73, 0x77, 0x78, 0x79, 0x7A, 0x81, 0x85, 0x86, 0x87, 0x88):
            tone[offset] = 64
        for offset in range(0x8A, 0x9A):
            tone[offset] = 64

    return {key: tuple(data) for key, data in blocks.items()}
