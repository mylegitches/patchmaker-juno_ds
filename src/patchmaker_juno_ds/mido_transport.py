"""Optional Mido transport for physical MIDI ports."""

from __future__ import annotations

import time

from .errors import TransportError


class MidoTransport:
    """Adapt Mido input/output ports to the full-SysEx transport protocol."""

    def __init__(self, input_name: str, output_name: str) -> None:
        try:
            import mido
        except ImportError as error:
            raise TransportError(
                "Mido is not installed; install the project with the 'midi' extra"
            ) from error
        try:
            self._mido = mido
            self._input = mido.open_input(input_name)
            self._output = mido.open_output(output_name)
        except Exception as error:
            raise TransportError(f"could not open MIDI ports: {error}") from error

    def send(self, message: bytes) -> None:
        if len(message) < 2 or message[0] != 0xF0 or message[-1] != 0xF7:
            raise TransportError("MidoTransport.send requires a complete SysEx message")
        self._output.send(self._mido.Message("sysex", data=message[1:-1]))

    def receive(self, timeout: float) -> bytes | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            incoming = self._input.poll()
            if incoming is not None and incoming.type == "sysex":
                return bytes((0xF0, *incoming.data, 0xF7))
            time.sleep(0.001)
        return None

    def close(self) -> None:
        self._input.close()
        self._output.close()

    def __enter__(self) -> "MidoTransport":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def port_names() -> tuple[list[str], list[str]]:
    try:
        import mido
    except ImportError as error:
        raise TransportError("Mido is not installed; install the project with the 'midi' extra") from error
    return list(mido.get_input_names()), list(mido.get_output_names())
