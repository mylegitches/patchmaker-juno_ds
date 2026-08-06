import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from patchmaker_juno_ds.configuration import local_env_path, read_local_env, update_local_env


class ConfigurationTests(unittest.TestCase):
    def test_round_trip_quotes_secrets_and_preserves_unrelated_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory, ".env")
            target.write_text("# existing\nOTHER_SETTING=keep\n", encoding="utf-8")
            update_local_env(
                {
                    "PATCHMAKER_LLM_API_KEY": 'secret with "quotes"',
                    "PATCHMAKER_LLM_BASE_URL": "https://router.test/v1",
                    "PATCHMAKER_LLM_MODEL": "author/model:free",
                },
                target,
            )
            content = target.read_text(encoding="utf-8")
            self.assertIn("# existing", content)
            self.assertIn("OTHER_SETTING=keep", content)
            values = read_local_env(target)
            self.assertEqual(values["PATCHMAKER_LLM_API_KEY"], 'secret with "quotes"')
            self.assertEqual(values["PATCHMAKER_LLM_MODEL"], "author/model:free")

    def test_updates_managed_values_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory, ".env")
            target.write_text(
                'PATCHMAKER_LLM_MODEL="old"\nPATCHMAKER_LLM_MODEL="stale duplicate"\n',
                encoding="utf-8",
            )
            update_local_env({"PATCHMAKER_LLM_MODEL": "new"}, target)
            content = target.read_text(encoding="utf-8")
            self.assertEqual(content.count("PATCHMAKER_LLM_MODEL="), 1)
            self.assertEqual(read_local_env(target)["PATCHMAKER_LLM_MODEL"], "new")

    def test_environment_can_override_env_file_location(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            expected = str(Path(directory, "settings.env"))
            with patch.dict(os.environ, {"PATCHMAKER_ENV_FILE": expected}):
                self.assertEqual(local_env_path(), Path(expected).resolve())


if __name__ == "__main__":
    unittest.main()
