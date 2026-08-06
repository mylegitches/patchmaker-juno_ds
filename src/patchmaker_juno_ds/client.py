"""Transport-neutral API for reading and writing the JUNO-DS edit buffer."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .codec import build_edit_buffer_requests, encode_edit_buffer, parse_message
from .errors import ProtocolError, TransportError
from .model import JunoPatch
from .spec import BLOCK_SPECS, COMMAND_DT1, DEFAULT_DEVICE_ID, edit_address


@runtime_checkable
class MidiTransport(Protocol):
    """Minimal full-SysEx transport required by :class:`JunoClient`."""

    def send(self, message: bytes) -> None: ...

    def receive(self, timeout: float) -> bytes | None: ...


class JunoClient:
    def __init__(
        self,
        transport: MidiTransport,
        *,
        device_id: int = DEFAULT_DEVICE_ID,
        response_timeout: float = 2.0,
    ) -> None:
        if not isinstance(transport, MidiTransport):
            raise TypeError("transport must implement send(message) and receive(timeout)")
        if not 0 <= device_id <= 0x1F:
            raise ValueError("device_id must be between 0 and 31")
        if response_timeout <= 0:
            raise ValueError("response_timeout must be positive")
        self.transport = transport
        self.device_id = device_id
        self.response_timeout = response_timeout

    def read_current_patch(self) -> JunoPatch:
        """Request and assemble all nine temporary-patch blocks."""
        replies: list[bytes] = []
        for spec, request in zip(BLOCK_SPECS, build_edit_buffer_requests(self.device_id), strict=True):
            self.transport.send(request)
            reply = self.transport.receive(self.response_timeout)
            if reply is None:
                raise TransportError(f"timed out waiting for {spec.label}")
            try:
                parsed = parse_message(reply)
            except ProtocolError as error:
                raise TransportError(f"invalid response for {spec.label}: {error}") from error
            if parsed.command != COMMAND_DT1 or parsed.address != edit_address(spec):
                raise TransportError(f"received an unexpected response while waiting for {spec.label}")
            replies.append(reply)

        from .codec import decode_edit_buffer

        return decode_edit_buffer(replies)

    def write_temporary_patch(self, patch: JunoPatch) -> None:
        """Send a validated patch to the temporary buffer; does not store it."""
        for message in encode_edit_buffer(patch, self.device_id):
            self.transport.send(message)
