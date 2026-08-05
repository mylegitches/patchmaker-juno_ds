"""Local browser GUI for Patchmaker JUNO-DS."""

from __future__ import annotations

import json
import os
import sys
import threading
import webbrowser
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import Callable, Mapping

from .client import JunoClient
from .configuration import read_local_env, update_local_env
from .designer import PatchChangePlan, SoundDesigner
from .errors import PatchmakerError, PatchValidationError, PlannerError
from .mido_transport import MidoTransport, port_names
from .model import JunoPatch
from .openai_compatible import OpenAICompatiblePlanner
from .patch_library import PatchLibrary
from .prompt_randomizer import SYNTH_SOUND_ATTRIBUTES, randomize_prompt, resolve_sound_language
from .spec import BLOCK_SPECS

MAX_REQUEST_BYTES = 2 * 1024 * 1024


def demo_patch() -> JunoPatch:
    """Return a valid, neutral patch for exploring the GUI without hardware."""
    blocks = {spec.key: tuple(0 for _ in range(spec.size)) for spec in BLOCK_SPECS}
    common = list(blocks["patch_common"])
    for offset in (0x0F, 0x11, 0x12, 0x13, 0x22, 0x23, 0x24, 0x25):
        common[offset] = 64
    common[0x0E] = 100
    common[0x16] = 1
    blocks["patch_common"] = tuple(common)
    mix = list(blocks["tone_mix"])
    mix[0x05] = 1
    blocks["tone_mix"] = tuple(mix)
    for tone_number in range(1, 5):
        tone = list(blocks[f"tone_{tone_number}"])
        for offset in (0x01, 0x02, 0x04, 0x4F, 0x77, 0x78, 0x79, 0x7A):
            tone[offset] = 64
        tone[0x00] = 100 if tone_number == 1 else 0
        tone[0x48] = 1
        tone[0x49] = 96
        tone[0x4D] = 16
        tone[0x6A] = 127
        tone[0x6B] = 127
        tone[0x6C] = 127
        blocks[f"tone_{tone_number}"] = tuple(tone)
    return JunoPatch(name="INIT PATCH", category=29, blocks=blocks)


def _required_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PatchValidationError(f"{name} must be a non-empty string")
    return value.strip()


def _device_id(value: object) -> int:
    if value is None:
        return 0x10
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0x1F:
        raise PatchValidationError("device_id must be an integer between 0 and 31")
    return value


def _configuration_value(name: str) -> str | None:
    """Read local `.env`, process configuration, then Windows user environment."""
    local = read_local_env().get(name)
    if local:
        return local
    value = os.environ.get(name)
    if value:
        return value
    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            stored, _ = winreg.QueryValueEx(key, name)
        return stored if isinstance(stored, str) and stored else None
    except OSError:
        return None


class GuiService:
    """JSON-friendly operations used by the HTTP layer and unit tests."""

    def __init__(
        self,
        *,
        planner_factory: Callable[..., object] = OpenAICompatiblePlanner,
        ports_provider: Callable[[], tuple[list[str], list[str]]] = port_names,
        transport_factory: Callable[[str, str], object] = MidoTransport,
        library: PatchLibrary | None = None,
    ) -> None:
        self.planner_factory = planner_factory
        self.ports_provider = ports_provider
        self.transport_factory = transport_factory
        self.library = library or PatchLibrary()

    def dispatch(self, path: str, payload: object | None = None) -> dict[str, object]:
        data = payload if isinstance(payload, Mapping) else {}
        if path == "/api/demo":
            return {"patch": demo_patch().to_dict()}
        if path == "/api/random-prompt":
            result = randomize_prompt()
            return {
                "prompt": result.prompt,
                "attributes": dict(result.attributes),
                "parameter_mapping": resolve_sound_language(result.prompt),
            }
        if path == "/api/prompt-attributes":
            return {"attributes": {key: list(values) for key, values in SYNTH_SOUND_ATTRIBUTES.items()}}
        if path == "/api/history":
            return {"patches": self.library.list()}
        if path == "/api/history/get":
            record_id = _required_string(data.get("id"), "id")
            record = self.library.load(record_id)
            return {
                "record": record.summary(),
                "patch": record.patch.to_dict(),
                "message": record.explanation,
            }
        if path == "/api/history/delete":
            record_id = _required_string(data.get("id"), "id")
            record = self.library.delete(record_id)
            return {"id": record.id, "message": f"Deleted {record.patch.name} from the library"}
        if path == "/api/configuration":
            return {
                "base_url": _configuration_value("PATCHMAKER_LLM_BASE_URL") or "https://openrouter.ai/api/v1",
                "model": _configuration_value("PATCHMAKER_LLM_MODEL") or "openrouter/free",
                "api_key_configured": bool(_configuration_value("PATCHMAKER_LLM_API_KEY")),
                "storage": ".env",
            }
        if path == "/api/save-configuration":
            base_url = _required_string(data.get("base_url"), "base_url")
            model = _required_string(data.get("model"), "model")
            supplied_key = data.get("api_key")
            if supplied_key is not None and not isinstance(supplied_key, str):
                raise PatchValidationError("api_key must be a string")
            api_key = supplied_key.strip() if isinstance(supplied_key, str) else ""
            if not api_key:
                api_key = _configuration_value("PATCHMAKER_LLM_API_KEY") or ""
            update_local_env(
                {
                    "PATCHMAKER_LLM_API_KEY": api_key,
                    "PATCHMAKER_LLM_BASE_URL": base_url,
                    "PATCHMAKER_LLM_MODEL": model,
                }
            )
            return {
                "message": "Settings saved locally",
                "api_key_configured": bool(api_key),
                "storage": ".env",
            }
        if path == "/api/test-connection":
            base_url = _required_string(
                data.get("base_url") or _configuration_value("PATCHMAKER_LLM_BASE_URL"), "base_url"
            )
            model = _required_string(
                data.get("model") or _configuration_value("PATCHMAKER_LLM_MODEL"), "model"
            )
            api_key = data.get("api_key") or _configuration_value("PATCHMAKER_LLM_API_KEY")
            if api_key is not None and not isinstance(api_key, str):
                raise PatchValidationError("api_key must be a string")
            planner = self.planner_factory(
                base_url=base_url,
                model=model,
                api_key=api_key,
                timeout=30.0,
            )
            resolved_model = planner.test_connection()  # type: ignore[attr-defined]
            return {
                "message": "Connection successful",
                "model": resolved_model,
                "authenticated": bool(api_key),
            }
        if path == "/api/ports":
            inputs, outputs = self.ports_provider()
            return {"inputs": inputs, "outputs": outputs}
        if path == "/api/validate":
            patch = JunoPatch.from_dict(data.get("patch"))
            return {"patch": patch.to_dict(), "message": f"{patch.name} is valid"}
        if path == "/api/refine":
            patch = JunoPatch.from_dict(data.get("patch"))
            request = _required_string(data.get("request"), "request")
            base_url = _required_string(
                data.get("base_url") or _configuration_value("PATCHMAKER_LLM_BASE_URL"), "base_url"
            )
            model = _required_string(
                data.get("model") or _configuration_value("PATCHMAKER_LLM_MODEL"), "model"
            )
            api_key = data.get("api_key") or _configuration_value("PATCHMAKER_LLM_API_KEY")
            if api_key is not None and not isinstance(api_key, str):
                raise PatchValidationError("api_key must be a string")
            planner = self.planner_factory(
                base_url=base_url,
                model=model,
                api_key=api_key,
                timeout=60.0,
            )
            result = SoundDesigner(planner).refine(patch, request)  # type: ignore[arg-type]
            plan = asdict(result.plan)
            parent_value = data.get("parent_id")
            if parent_value is not None and not isinstance(parent_value, str):
                raise PatchValidationError("parent_id must be a string or null")
            record = self.library.save(
                result.patch,
                request=request,
                explanation=result.plan.explanation,
                parent_id=parent_value,
            )
            return {
                "patch": result.patch.to_dict(),
                "plan": plan,
                "message": result.plan.explanation,
                "record": record.summary(),
            }
        if path == "/api/read":
            input_port = _required_string(data.get("input_port"), "input_port")
            output_port = _required_string(data.get("output_port"), "output_port")
            with self.transport_factory(input_port, output_port) as transport:  # type: ignore[attr-defined]
                patch = JunoClient(transport, device_id=_device_id(data.get("device_id"))).read_current_patch()
            return {"patch": patch.to_dict(), "message": f"Read {patch.name} from the JUNO-DS"}
        if path == "/api/write":
            if data.get("confirm") is not True:
                raise PatchValidationError("temporary-buffer write must be explicitly confirmed")
            patch = JunoPatch.from_dict(data.get("patch"))
            input_port = _required_string(data.get("input_port"), "input_port")
            output_port = _required_string(data.get("output_port"), "output_port")
            with self.transport_factory(input_port, output_port) as transport:  # type: ignore[attr-defined]
                JunoClient(transport, device_id=_device_id(data.get("device_id"))).write_temporary_patch(patch)
            return {"message": f"Sent {patch.name} to the temporary edit buffer"}
        raise PatchValidationError(f"unknown API route: {path}")


def _asset(name: str) -> tuple[bytes, str]:
    content_types = {
        "index.html": "text/html; charset=utf-8",
        "app.css": "text/css; charset=utf-8",
        "app.js": "text/javascript; charset=utf-8",
    }
    if name not in content_types:
        raise FileNotFoundError(name)
    return files("patchmaker_juno_ds.web_assets").joinpath(name).read_bytes(), content_types[name]


def make_handler(service: GuiService) -> type[BaseHTTPRequestHandler]:
    class GuiRequestHandler(BaseHTTPRequestHandler):
        server_version = "PatchmakerJuno/0.1"

        def _json(self, status: HTTPStatus, value: Mapping[str, object]) -> None:
            body = json.dumps(value).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/api/ports":
                try:
                    self._json(HTTPStatus.OK, service.dispatch(self.path))
                except (PatchmakerError, OSError, RuntimeError) as error:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            asset_name = {"/": "index.html", "/app.css": "app.css", "/app.js": "app.js"}.get(
                self.path
            )
            if asset_name is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            body, content_type = _asset(asset_name)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_REQUEST_BYTES:
                    raise PatchValidationError("request body size is invalid")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                self._json(HTTPStatus.OK, service.dispatch(self.path, payload))
            except (PatchmakerError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

        def log_message(self, format: str, *args: object) -> None:
            return

    return GuiRequestHandler


def serve_gui(*, port: int = 8765, open_browser: bool = True) -> None:
    """Serve the GUI on localhost until interrupted."""
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    url = f"http://127.0.0.1:{port}"
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(GuiService()))
    print(f"Patchmaker JUNO-DS GUI: {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.25, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
