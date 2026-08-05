import tempfile
import unittest
from pathlib import Path

from patchmaker_juno_ds.cli import main
from patchmaker_juno_ds.codec import encode_edit_buffer
from patchmaker_juno_ds.model import JunoPatch

from .helpers import make_patch


class CliTests(unittest.TestCase):
    def test_file_conversion_workflow(self) -> None:
        patch = make_patch()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_syx = root / "source.syx"
            patch_json = root / "patch.json"
            result_syx = root / "result.syx"
            source_syx.write_bytes(b"".join(encode_edit_buffer(patch)))

            self.assertEqual(main(["syx-to-json", str(source_syx), str(patch_json)]), 0)
            self.assertEqual(JunoPatch.load(patch_json), patch)
            self.assertEqual(main(["validate", str(patch_json)]), 0)
            self.assertEqual(main(["json-to-syx", str(patch_json), str(result_syx)]), 0)
            self.assertEqual(result_syx.read_bytes(), source_syx.read_bytes())

    def test_hardware_write_requires_explicit_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "patch.json")
            make_patch().save(path)
            result = main(
                [
                    "write",
                    str(path),
                    "--input-port",
                    "input",
                    "--output-port",
                    "output",
                ]
            )
            self.assertEqual(result, 2)


if __name__ == "__main__":
    unittest.main()
