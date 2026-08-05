"""Public API for the Patchmaker JUNO-DS Phase 1 prototype."""

from .client import JunoClient, MidiTransport
from .codec import (
    build_edit_buffer_requests,
    decode_edit_buffer,
    encode_edit_buffer,
    parse_message,
    split_sysex,
)
from .designer import PatchChangePlan, RefinementResult, SoundDesigner, ToneChange
from .errors import PatchValidationError, PlannerError, ProtocolError, TransportError
from .model import JunoPatch
from .openai_compatible import OpenAICompatiblePlanner
from .parameters import CommonParameters, ToneParameters

__all__ = [
    "JunoClient",
    "JunoPatch",
    "CommonParameters",
    "MidiTransport",
    "OpenAICompatiblePlanner",
    "PatchChangePlan",
    "PatchValidationError",
    "PlannerError",
    "ProtocolError",
    "RefinementResult",
    "SoundDesigner",
    "ToneChange",
    "TransportError",
    "ToneParameters",
    "build_edit_buffer_requests",
    "decode_edit_buffer",
    "encode_edit_buffer",
    "parse_message",
    "split_sysex",
]

__version__ = "0.1.0"
