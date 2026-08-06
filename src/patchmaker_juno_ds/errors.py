"""Domain-specific exceptions."""


class PatchmakerError(Exception):
    """Base class for expected Patchmaker failures."""


class PatchValidationError(PatchmakerError, ValueError):
    """Raised when human-readable patch data is invalid."""


class ProtocolError(PatchmakerError, ValueError):
    """Raised when a SysEx message or dump violates the JUNO-DS protocol."""


class TransportError(PatchmakerError, RuntimeError):
    """Raised when MIDI communication cannot complete safely."""


class PlannerError(PatchmakerError, RuntimeError):
    """Raised when a sound-design planner fails or returns invalid output."""
