import json
import tempfile
import unittest
from pathlib import Path

from patchmaker_juno_ds.errors import PatchValidationError
from patchmaker_juno_ds.patch_library import PatchLibrary

from .helpers import make_patch


class PatchLibraryTests(unittest.TestCase):
    def test_saved_patch_survives_new_library_instance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory, "patches")
            record = PatchLibrary(root).save(
                make_patch("FIRST PATCH"),
                request="make it warm",
                explanation="Lowered the cutoff.",
            )
            loaded = PatchLibrary(root).load(record.id)
            self.assertEqual(loaded, record)
            self.assertEqual(PatchLibrary(root).list(), [record.summary()])

    def test_multiple_versions_retain_parent_relationship(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = PatchLibrary(Path(directory))
            first = library.save(
                make_patch("VERSION ONE"), request="first", explanation="First version"
            )
            second = library.save(
                make_patch("VERSION TWO"),
                request="second",
                explanation="Second version",
                parent_id=first.id,
            )
            self.assertEqual(library.load(second.id).parent_id, first.id)
            self.assertEqual({item["id"] for item in library.list()}, {first.id, second.id})

    def test_invalid_ids_cannot_escape_library(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = PatchLibrary(Path(directory))
            with self.assertRaisesRegex(PatchValidationError, "UUID"):
                library.load("../../secret")
            with self.assertRaisesRegex(PatchValidationError, "parent_id"):
                library.save(
                    make_patch(), request="request", explanation="explanation", parent_id="bad"
                )

    def test_delete_removes_only_the_selected_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = PatchLibrary(Path(directory))
            first = library.save(make_patch("FIRST"), request="first", explanation="first")
            second = library.save(make_patch("SECOND"), request="second", explanation="second")
            self.assertEqual(library.delete(first.id), first)
            self.assertEqual([item["id"] for item in library.list()], [second.id])
            with self.assertRaisesRegex(PatchValidationError, "not found"):
                library.load(first.id)

    def test_corrupt_records_do_not_hide_valid_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library = PatchLibrary(root)
            valid = library.save(make_patch(), request="valid", explanation="valid record")
            root.joinpath("corrupt.json").write_text("{bad json", encoding="utf-8")
            self.assertEqual([item["id"] for item in library.list()], [valid.id])


if __name__ == "__main__":
    unittest.main()
