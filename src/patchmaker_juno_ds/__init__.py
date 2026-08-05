"""Public API for the Patchmaker JUNO-DS Phase 1 prototype."""

from .client import JunoClient, MidiTransport
from .codec import (
    build_edit_buffer_requests,
    decode_edit_buffer,
    encode_edit_buffer,
    parse_message,
    split_sysex,
)
from .errors import PatchValidationError, ProtocolError, TransportError
from .model import JunoPatch

__all__ = [
    "JunoClient",
    "JunoPatch",
    "MidiTransport",
    "PatchValidationError",
    "ProtocolError",
    "TransportError",
    "build_edit_buffer_requests",
    "decode_edit_buffer",
    "encode_edit_buffer",
    "parse_message",
    "split_sysex",
]

__version__ = "0.1.0"
