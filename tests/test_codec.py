import unittest

from patchmaker_juno_ds.codec import (
    build_edit_buffer_requests,
    decode_edit_buffer,
    encode_edit_buffer,
    parse_message,
    roland_checksum,
    split_sysex,
)
from patchmaker_juno_ds.errors import ProtocolError
from patchmaker_juno_ds.spec import BLOCK_SPECS, COMMAND_DT1, COMMAND_RQ1, edit_address

from .helpers import make_patch


class CodecTests(unittest.TestCase):
    def test_checksum_matches_roland_example_rule(self) -> None:
        self.assertEqual(roland_checksum([0x30, 0, 0, 0, 0, 0, 0, 0x50]), 0)

    def test_first_edit_buffer_request_is_exact(self) -> None:
        request = build_edit_buffer_requests()[0]
        self.assertEqual(
            request,
            bytes.fromhex("f0 41 10 00 00 3a 11 1f 00 00 00 00 00 00 50 11 f7"),
        )
        parsed = parse_message(request)
        self.assertEqual(parsed.command, COMMAND_RQ1)
        self.assertEqual(parsed.address, (0x1F, 0, 0, 0))
        self.assertEqual(parsed.data, (0, 0, 0, 0x50))

    def test_complete_patch_round_trip(self) -> None:
        patch = make_patch()
        messages = encode_edit_buffer(patch, device_id=7)
        self.assertEqual(len(messages), 9)
        self.assertTrue(all(parse_message(item).command == COMMAND_DT1 for item in messages))
        self.assertEqual(decode_edit_buffer(messages), patch)
        self.assertEqual(decode_edit_buffer(b"".join(messages)), patch)

    def test_all_addresses_and_sizes_are_exact(self) -> None:
        patch = make_patch()
        for spec, raw in zip(BLOCK_SPECS, encode_edit_buffer(patch), strict=True):
            message = parse_message(raw)
            self.assertEqual(message.address, edit_address(spec))
            self.assertEqual(len(message.data), spec.size)

    def test_rejects_bad_checksum(self) -> None:
        raw = bytearray(build_edit_buffer_requests()[0])
        raw[-2] ^= 1
        with self.assertRaisesRegex(ProtocolError, "checksum mismatch"):
            parse_message(raw)

    def test_rejects_incomplete_and_duplicate_dumps(self) -> None:
        messages = encode_edit_buffer(make_patch())
        with self.assertRaisesRegex(ProtocolError, "requires 9"):
            decode_edit_buffer(messages[:-1])
        duplicate = messages[:-1] + [messages[0]]
        with self.assertRaisesRegex(ProtocolError, "duplicate"):
            decode_edit_buffer(duplicate)

    def test_rejects_mixed_device_ids(self) -> None:
        patch = make_patch()
        messages = encode_edit_buffer(patch, 1)
        messages[-1] = encode_edit_buffer(patch, 2)[-1]
        with self.assertRaisesRegex(ProtocolError, "same Roland device ID"):
            decode_edit_buffer(messages)

    def test_split_sysex_rejects_stray_and_unterminated_bytes(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "stray byte"):
            split_sysex(b"\x01")
        with self.assertRaisesRegex(ProtocolError, "unterminated"):
            split_sysex(b"\xF0\x41")


if __name__ == "__main__":
    unittest.main()
