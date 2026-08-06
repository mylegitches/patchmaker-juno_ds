"""Deterministic Roland JUNO-DS SysEx encoding and decoding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .errors import ProtocolError
from .model import JunoPatch
from .spec import (
    BLOCK_SPECS,
    COMMAND_DT1,
    COMMAND_RQ1,
    DEFAULT_DEVICE_ID,
    JUNO_DS_MODEL_ID,
    ROLAND_MANUFACTURER_ID,
    edit_address,
    int_to_seven_bit,
)


@dataclass(frozen=True, slots=True)
class RolandMessage:
    device_id: int
    command: int
    address: tuple[int, int, int, int]
    data: tuple[int, ...]


def roland_checksum(values: Iterable[int]) -> int:
    """Return Roland's 7-bit complement checksum."""
    return (-sum(values)) & 0x7F


def _validate_7bit(values: Iterable[int], label: str) -> tuple[int, ...]:
    clean = tuple(values)
    for index, value in enumerate(clean):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0x7F:
            raise ProtocolError(f"{label}[{index}] is not a 7-bit integer")
    return clean


def build_message(
    command: int,
    address: Iterable[int],
    data: Iterable[int],
    device_id: int = DEFAULT_DEVICE_ID,
) -> bytes:
    if not 0 <= device_id <= 0x1F:
        raise ProtocolError("Roland device_id must be between 0 and 31")
    if command not in (COMMAND_RQ1, COMMAND_DT1):
        raise ProtocolError("command must be RQ1 (0x11) or DT1 (0x12)")
    clean_address = _validate_7bit(address, "address")
    if len(clean_address) != 4:
        raise ProtocolError("JUNO-DS addresses must contain exactly four bytes")
    clean_data = _validate_7bit(data, "data")
    checked = clean_address + clean_data
    return bytes(
        (0xF0, ROLAND_MANUFACTURER_ID, device_id, *JUNO_DS_MODEL_ID, command)
        + checked
        + (roland_checksum(checked), 0xF7)
    )


def parse_message(message: bytes | bytearray | Iterable[int]) -> RolandMessage:
    raw = bytes(message)
    if len(raw) < 13:
        raise ProtocolError("message is too short to be a JUNO-DS SysEx message")
    if raw[0] != 0xF0 or raw[-1] != 0xF7:
        raise ProtocolError("SysEx message must start with F0 and end with F7")
    if raw[1] != ROLAND_MANUFACTURER_ID:
        raise ProtocolError("message is not from Roland")
    if tuple(raw[3:6]) != JUNO_DS_MODEL_ID:
        raise ProtocolError("message is not for a Roland JUNO-DS")
    if raw[2] > 0x1F:
        raise ProtocolError("invalid Roland device ID")
    command = raw[6]
    if command not in (COMMAND_RQ1, COMMAND_DT1):
        raise ProtocolError(f"unsupported Roland command 0x{command:02X}")
    body = raw[7:-2]
    if any(value > 0x7F for value in body):
        raise ProtocolError("address and data bytes must be 7-bit values")
    expected_checksum = roland_checksum(body)
    if raw[-2] != expected_checksum:
        raise ProtocolError(
            f"checksum mismatch: message has 0x{raw[-2]:02X}, expected 0x{expected_checksum:02X}"
        )
    return RolandMessage(
        device_id=raw[2],
        command=command,
        address=tuple(raw[7:11]),  # type: ignore[arg-type]
        data=tuple(raw[11:-2]),
    )


def split_sysex(stream: bytes | bytearray | Iterable[int]) -> list[bytes]:
    """Split a byte stream into complete SysEx messages, rejecting stray data."""
    raw = bytes(stream)
    messages: list[bytes] = []
    start: int | None = None
    for index, value in enumerate(raw):
        if value == 0xF0:
            if start is not None:
                raise ProtocolError("nested F0 before the previous SysEx message ended")
            start = index
        elif value == 0xF7:
            if start is None:
                raise ProtocolError("stray F7 outside a SysEx message")
            messages.append(raw[start : index + 1])
            start = None
        elif start is None:
            raise ProtocolError(f"stray byte 0x{value:02X} outside a SysEx message")
    if start is not None:
        raise ProtocolError("unterminated SysEx message")
    return messages


def build_edit_buffer_requests(device_id: int = DEFAULT_DEVICE_ID) -> list[bytes]:
    return [
        build_message(COMMAND_RQ1, edit_address(spec), int_to_seven_bit(spec.size), device_id)
        for spec in BLOCK_SPECS
    ]


def encode_edit_buffer(patch: JunoPatch, device_id: int = DEFAULT_DEVICE_ID) -> list[bytes]:
    return [
        build_message(COMMAND_DT1, edit_address(spec), patch.blocks[spec.key], device_id)
        for spec in BLOCK_SPECS
    ]


def decode_edit_buffer(messages: Iterable[bytes] | bytes | bytearray) -> JunoPatch:
    message_list = split_sysex(messages) if isinstance(messages, (bytes, bytearray)) else list(messages)
    if len(message_list) != len(BLOCK_SPECS):
        raise ProtocolError(
            f"complete edit-buffer dump requires {len(BLOCK_SPECS)} messages; got {len(message_list)}"
        )

    specs_by_address = {edit_address(spec): spec for spec in BLOCK_SPECS}
    blocks: dict[str, tuple[int, ...]] = {}
    device_ids: set[int] = set()
    for raw in message_list:
        message = parse_message(raw)
        if message.command != COMMAND_DT1:
            raise ProtocolError("edit-buffer dump may contain DT1 messages only")
        device_ids.add(message.device_id)
        spec = specs_by_address.get(message.address)
        if spec is None:
            formatted = " ".join(f"{value:02X}" for value in message.address)
            raise ProtocolError(f"unexpected edit-buffer address {formatted}")
        if spec.key in blocks:
            raise ProtocolError(f"duplicate edit-buffer block: {spec.key}")
        if len(message.data) != spec.size:
            raise ProtocolError(
                f"{spec.key} has {len(message.data)} bytes; expected exactly {spec.size}"
            )
        blocks[spec.key] = message.data
    if len(device_ids) != 1:
        raise ProtocolError("all edit-buffer messages must use the same Roland device ID")
    return JunoPatch.from_blocks(blocks)
