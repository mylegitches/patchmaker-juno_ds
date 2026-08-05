import json
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from importlib.resources import files

from patchmaker_juno_ds.designer import PatchChangePlan
from patchmaker_juno_ds.gui import GuiService, demo_patch, make_handler
from patchmaker_juno_ds.model import JunoPatch


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


class GuiServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = GuiService(
            planner_factory=FakePlanner,
            ports_provider=lambda: (["JUNO IN"], ["JUNO OUT"]),
        )

    def test_demo_is_a_valid_patch(self) -> None:
        value = self.service.dispatch("/api/demo")
        patch = JunoPatch.from_dict(value["patch"])
        self.assertEqual(patch.name, "INIT PATCH")
        self.assertTrue(patch.tone_parameters[0].enabled)

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

    def test_ports_are_json_friendly(self) -> None:
        self.assertEqual(
            self.service.dispatch("/api/ports"),
            {"inputs": ["JUNO IN"], "outputs": ["JUNO OUT"]},
        )

    def test_interface_loads_default_patch_on_startup(self) -> None:
        script = files("patchmaker_juno_ds.web_assets").joinpath("app.js").read_text("utf-8")
        self.assertIn("loadDemo().catch", script)

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
