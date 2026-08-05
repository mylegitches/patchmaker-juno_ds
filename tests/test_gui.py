import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

from patchmaker_juno_ds.designer import PatchChangePlan
from patchmaker_juno_ds.gui import GuiService, demo_patch, make_handler
from patchmaker_juno_ds.gui import _configuration_value
from patchmaker_juno_ds.model import JunoPatch
from patchmaker_juno_ds.patch_library import PatchLibrary


class FakePlanner:
    init_args = None

    def __init__(self, **kwargs: object) -> None:
        FakePlanner.init_args = kwargs

    def create_plan(self, request: str, patch: JunoPatch) -> PatchChangePlan:
        return PatchChangePlan(
            explanation=f"Applied: {request}",
            name="DARKER PAD",
            common={"cutoff_offset": -18},
        )

    def test_connection(self) -> str:
        return "resolved-test-model"


class GuiServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.library_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.library_directory.cleanup)
        self.service = GuiService(
            planner_factory=FakePlanner,
            ports_provider=lambda: (["JUNO IN"], ["JUNO OUT"]),
            library=PatchLibrary(Path(self.library_directory.name)),
        )

    def test_demo_is_a_valid_patch(self) -> None:
        value = self.service.dispatch("/api/demo")
        patch = JunoPatch.from_dict(value["patch"])
        self.assertEqual(patch.name, "INIT PATCH")
        self.assertTrue(patch.tone_parameters[0].enabled)

    def test_configuration_prefers_process_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_path = str(Path(directory, ".env"))
            with patch.dict(
                os.environ,
                {"PATCHMAKER_ENV_FILE": env_path, "PATCHMAKER_TEST_VALUE": "process-value"},
            ):
                self.assertEqual(_configuration_value("PATCHMAKER_TEST_VALUE"), "process-value")

    def test_gui_saves_and_reads_local_configuration_without_returning_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_path = str(Path(directory, ".env"))
            with patch.dict(os.environ, {"PATCHMAKER_ENV_FILE": env_path}, clear=False):
                saved = self.service.dispatch(
                    "/api/save-configuration",
                    {
                        "base_url": "https://router.test/v1",
                        "model": "author/model:free",
                        "api_key": "local-secret",
                    },
                )
                self.assertTrue(saved["api_key_configured"])
                self.assertNotIn("local-secret", json.dumps(saved))
                loaded = self.service.dispatch("/api/configuration")
                self.assertEqual(loaded["base_url"], "https://router.test/v1")
                self.assertEqual(loaded["model"], "author/model:free")
                self.assertTrue(loaded["api_key_configured"])
                self.assertNotIn("local-secret", json.dumps(loaded))

    def test_validate_normalizes_patch(self) -> None:
        result = self.service.dispatch("/api/validate", {"patch": demo_patch().to_dict()})
        self.assertIn("is valid", result["message"])
        self.assertEqual(JunoPatch.from_dict(result["patch"]), demo_patch())

    def test_refine_uses_config_and_returns_valid_patch(self) -> None:
        result = self.service.dispatch(
            "/api/refine",
            {
                "patch": demo_patch().to_dict(),
                "request": "make it darker",
                "base_url": "http://model.test/v1",
                "model": "test-model",
                "api_key": "secret",
            },
        )
        patch = JunoPatch.from_dict(result["patch"])
        self.assertEqual(patch.name, "DARKER PAD")
        self.assertEqual(patch.common_parameters.cutoff_offset, -18)
        self.assertEqual(FakePlanner.init_args["api_key"], "secret")
        self.assertNotIn("secret", json.dumps(result))
        self.assertEqual(result["record"]["name"], "DARKER PAD")

    def test_generations_are_saved_and_can_be_reopened(self) -> None:
        first = self.service.dispatch(
            "/api/refine",
            {
                "patch": demo_patch().to_dict(), "request": "first version",
                "base_url": "http://model.test/v1", "model": "test", "api_key": "key",
            },
        )
        second = self.service.dispatch(
            "/api/refine",
            {
                "patch": first["patch"], "request": "second version",
                "base_url": "http://model.test/v1", "model": "test", "api_key": "key",
                "parent_id": first["record"]["id"],
            },
        )
        history = self.service.dispatch("/api/history")["patches"]
        self.assertEqual(len(history), 2)
        reopened = self.service.dispatch("/api/history/get", {"id": first["record"]["id"]})
        self.assertEqual(JunoPatch.from_dict(reopened["patch"]), JunoPatch.from_dict(first["patch"]))
        self.assertEqual(second["record"]["parent_id"], first["record"]["id"])

    def test_frontend_versions_duplicate_history_names(self) -> None:
        javascript = files("patchmaker_juno_ds.web_assets").joinpath("app.js").read_text("utf-8")
        self.assertIn("duplicateCounts", javascript)
        self.assertIn("`${record.name} · v${version}`", javascript)
        self.assertIn("deleteHistoryPatch(record)", javascript)

    def test_saved_patch_can_be_deleted_without_affecting_other_versions(self) -> None:
        first = self.service.dispatch(
            "/api/refine",
            {"patch": demo_patch().to_dict(), "request": "first", "base_url": "x", "model": "x"},
        )
        second = self.service.dispatch(
            "/api/refine",
            {"patch": first["patch"], "request": "second", "base_url": "x", "model": "x"},
        )
        deleted = self.service.dispatch("/api/history/delete", {"id": first["record"]["id"]})
        self.assertEqual(deleted["id"], first["record"]["id"])
        self.assertEqual(
            [item["id"] for item in self.service.dispatch("/api/history")["patches"]],
            [second["record"]["id"]],
        )

    def test_ports_are_json_friendly(self) -> None:
        self.assertEqual(
            self.service.dispatch("/api/ports"),
            {"inputs": ["JUNO IN"], "outputs": ["JUNO OUT"]},
        )

    def test_random_prompt_includes_parameter_mapping(self) -> None:
        result = self.service.dispatch("/api/random-prompt")
        self.assertTrue(result["prompt"])
        self.assertGreaterEqual(len(result["attributes"]), 15)
        self.assertGreater(len(result["parameter_mapping"]), 10)

    def test_connection_uses_key_without_returning_it(self) -> None:
        result = self.service.dispatch(
            "/api/test-connection",
            {
                "base_url": "https://router.test/v1",
                "model": "requested-model",
                "api_key": "session-secret",
            },
        )
        self.assertEqual(result["message"], "Connection successful")
        self.assertEqual(result["model"], "resolved-test-model")
        self.assertTrue(result["authenticated"])
        self.assertEqual(FakePlanner.init_args["api_key"], "session-secret")
        self.assertNotIn("session-secret", json.dumps(result))

    def test_interface_loads_default_patch_on_startup(self) -> None:
        script = files("patchmaker_juno_ds.web_assets").joinpath("app.js").read_text("utf-8")
        self.assertIn("loadConfiguration()", script)
        self.assertIn('$("#test-connection").addEventListener', script)
        self.assertIn('$("#save-configuration").addEventListener', script)
        self.assertIn('requestedModel === "openrouter/free"', script)
        self.assertIn("showGenerationError(error.message)", script)
        self.assertIn("refreshHistory()", script)
        self.assertIn("renderPatch(data.patch, data.message, data.record)", script)

    def test_interface_defaults_to_openrouter_free(self) -> None:
        script = files("patchmaker_juno_ds.web_assets").joinpath("app.js").read_text("utf-8")
        self.assertIn('"https://openrouter.ai/api/v1"', script)
        self.assertIn('"openrouter/free"', script)


class GuiHttpTests(unittest.TestCase):
    @contextmanager
    def server(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(GuiService()))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_serves_interface_and_demo_api(self) -> None:
        with self.server() as base:
            with urllib.request.urlopen(base + "/") as response:
                html = response.read().decode("utf-8")
            self.assertIn("What should this patch become?", html)

            request = urllib.request.Request(
                base + "/api/demo",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request) as response:
                result = json.loads(response.read())
            self.assertEqual(result["patch"]["name"], "INIT PATCH")

    def test_invalid_patch_returns_json_error(self) -> None:
        with self.server() as base:
            request = urllib.request.Request(
                base + "/api/validate",
                data=b'{"patch":{}}',
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request)
            self.assertEqual(caught.exception.code, 400)
            self.assertIn("error", json.loads(caught.exception.read()))


if __name__ == "__main__":
    unittest.main()
