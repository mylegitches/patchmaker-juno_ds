import unittest

from patchmaker_juno_ds.client import JunoClient
from patchmaker_juno_ds.codec import build_message, parse_message
from patchmaker_juno_ds.errors import TransportError
from patchmaker_juno_ds.spec import BLOCK_SPECS, COMMAND_DT1, COMMAND_RQ1, edit_address

from .helpers import make_patch


class FakeTransport:
    def __init__(self, patch=None, *, time_out=False) -> None:
        self.patch = patch
        self.time_out = time_out
        self.sent: list[bytes] = []
        self.pending: bytes | None = None

    def send(self, raw: bytes) -> None:
        self.sent.append(raw)
        message = parse_message(raw)
        if message.command == COMMAND_RQ1 and self.patch is not None:
            for spec in BLOCK_SPECS:
                if message.address == edit_address(spec):
                    self.pending = build_message(
                        COMMAND_DT1,
                        message.address,
                        self.patch.blocks[spec.key],
                        message.device_id,
                    )
                    break

    def receive(self, timeout: float) -> bytes | None:
        if self.time_out:
            return None
        response, self.pending = self.pending, None
        return response


class ClientTests(unittest.TestCase):
    def test_reads_current_patch_one_block_at_a_time(self) -> None:
        expected = make_patch()
        transport = FakeTransport(expected)
        actual = JunoClient(transport, device_id=3).read_current_patch()
        self.assertEqual(actual, expected)
        self.assertEqual(len(transport.sent), 9)
        self.assertTrue(all(parse_message(item).device_id == 3 for item in transport.sent))

    def test_writes_only_validated_patch_to_temporary_buffer(self) -> None:
        transport = FakeTransport()
        JunoClient(transport).write_temporary_patch(make_patch())
        self.assertEqual(len(transport.sent), 9)
        self.assertTrue(all(parse_message(item).command == COMMAND_DT1 for item in transport.sent))

    def test_timeout_names_the_missing_block(self) -> None:
        transport = FakeTransport(make_patch(), time_out=True)
        with self.assertRaisesRegex(TransportError, "Patch Common"):
            JunoClient(transport).read_current_patch()


if __name__ == "__main__":
    unittest.main()
