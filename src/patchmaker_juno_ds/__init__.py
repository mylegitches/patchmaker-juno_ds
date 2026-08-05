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
from .parameters import CommonParameters, ToneParameters

__all__ = [
    "JunoClient",
    "JunoPatch",
    "CommonParameters",
    "MidiTransport",
    "PatchValidationError",
    "ProtocolError",
    "TransportError",
    "ToneParameters",
    "build_edit_buffer_requests",
    "decode_edit_buffer",
    "encode_edit_buffer",
    "parse_message",
    "split_sysex",
]

__version__ = "0.1.0"
