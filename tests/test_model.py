import json
import tempfile
import unittest
from pathlib import Path

from patchmaker_juno_ds.errors import PatchValidationError
from patchmaker_juno_ds.model import JunoPatch
from patchmaker_juno_ds.spec import CATEGORY_OFFSET, PATCH_NAME_LENGTH

from .helpers import make_patch


class JunoPatchTests(unittest.TestCase):
    def test_metadata_is_synchronized_into_patch_common(self) -> None:
        patch = make_patch("DARK PAD", 29)
        common = patch.blocks["patch_common"]
        self.assertEqual(bytes(common[:PATCH_NAME_LENGTH]), b"DARK PAD    ")
        self.assertEqual(common[CATEGORY_OFFSET], 29)

    def test_dict_round_trip_is_lossless(self) -> None:
        patch = make_patch()
        restored = JunoPatch.from_dict(json.loads(json.dumps(patch.to_dict())))
        self.assertEqual(restored, patch)
        self.assertEqual(restored.to_dict()["category_name"], "SOFT PAD")

    def test_save_and_load(self) -> None:
        patch = make_patch()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "patch.json")
            patch.save(path)
            self.assertEqual(JunoPatch.load(path), patch)
            self.assertTrue(path.read_bytes().endswith(b"\n"))

    def test_rejects_unknown_fields(self) -> None:
        value = make_patch().to_dict()
        value["surprise"] = True
        with self.assertRaisesRegex(PatchValidationError, "unknown top-level"):
            JunoPatch.from_dict(value)

    def test_rejects_inconsistent_category_label(self) -> None:
        value = make_patch().to_dict()
        value["category_name"] = "SYNTH BRASS"
        with self.assertRaisesRegex(PatchValidationError, "category_name must be"):
            JunoPatch.from_dict(value)

    def test_rejects_missing_block(self) -> None:
        value = make_patch().to_dict()
        del value["blocks"]["tone_4"]
        with self.assertRaisesRegex(PatchValidationError, "missing: tone_4"):
            JunoPatch.from_dict(value)

    def test_rejects_wrong_block_size(self) -> None:
        value = make_patch().to_dict()
        value["blocks"]["mfx"].pop()
        with self.assertRaisesRegex(PatchValidationError, "exactly 145"):
            JunoPatch.from_dict(value)

    def test_rejects_non_7_bit_data(self) -> None:
        value = make_patch().to_dict()
        value["blocks"]["tone_1"][3] = 128
        with self.assertRaisesRegex(PatchValidationError, "7-bit integer"):
            JunoPatch.from_dict(value)

    def test_rejects_invalid_name_and_category(self) -> None:
        value = make_patch().to_dict()
        value["name"] = "NAME IS TOO LONG"
        with self.assertRaisesRegex(PatchValidationError, "1 to 12"):
            JunoPatch.from_dict(value)
        value = make_patch().to_dict()
        value["category"] = 39
        with self.assertRaisesRegex(PatchValidationError, "between 0 and 38"):
            JunoPatch.from_dict(value)


if __name__ == "__main__":
    unittest.main()
