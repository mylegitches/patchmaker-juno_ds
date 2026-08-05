"""OpenAI-compatible Chat Completions adapter for sound-design planning."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict
from typing import Mapping, Protocol

from .designer import PatchChangePlan
from .errors import PatchValidationError, PlannerError
from .model import JunoPatch
from .parameters import FILTER_TYPES, LFO_WAVEFORMS

SYSTEM_PROMPT = """You are a Roland JUNO-DS sound designer.
Translate the user's requested sound change into a minimal semantic patch-change plan.

Safety and output rules:
- Return one JSON object only. Do not use Markdown.
- Never emit SysEx, byte arrays, raw block data, addresses, or undocumented parameters.
- Change only parameters needed for the request. Preserve everything else.
- Use only the fields and ranges listed in the supplied contract.
- A tone_number is 1 through 4. Do not include the same tone twice.
- Explain the synthesis reasoning briefly in the explanation field.
- If the request cannot be represented by the contract, make the closest conservative changes and explain the limitation.
"""


class JsonHttpTransport(Protocol):
    def post(
        self,
        url: str,
        body: Mapping[str, object],
        headers: Mapping[str, str],
        timeout: float,
    ) -> object: ...


class UrllibJsonTransport:
    def post(
        self,
        url: str,
        body: Mapping[str, object],
        headers: Mapping[str, str],
        timeout: float,
    ) -> object:
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=dict(headers),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            raise PlannerError(f"LLM endpoint returned HTTP {error.code}: {detail}") from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise PlannerError(f"LLM endpoint request failed: {error}") from error


def _contract() -> dict[str, object]:
    return {
        "top_level": {
            "explanation": "required non-empty string",
            "name": "optional string, 1..12 printable ASCII characters",
            "category": "optional integer, 0..38",
            "common": "optional object containing only common fields below",
            "tones": "optional array of {tone_number, changes}",
        },
        "common_fields": {
            "level": "0..127",
            "pan": "-64..63",
            "coarse_tune": "-48..48 semitones",
            "fine_tune": "-50..50 cents",
            "octave_shift": "-3..3",
            "analog_feel": "0..127",
            "mono_poly": ["MONO", "POLY"],
            "legato": "boolean",
            "portamento": "boolean",
            "portamento_time": "0..127",
            "cutoff_offset": "-63..63",
            "resonance_offset": "-63..63",
            "attack_offset": "-63..63",
            "release_offset": "-63..63",
        },
        "tone_fields": {
            "enabled": "boolean",
            "level": "0..127",
            "coarse_tune": "-48..48 semitones",
            "fine_tune": "-50..50 cents",
            "pan": "-64..63",
            "chorus_send": "0..127",
            "reverb_send": "0..127",
            "wave_number": "0..16384; preserve unless specifically choosing a verified wave",
            "filter_type": list(FILTER_TYPES),
            "cutoff": "0..127",
            "resonance": "0..127",
            "filter_env_depth": "-63..63",
            "filter_attack": "0..127",
            "filter_decay_1": "0..127",
            "filter_decay_2": "0..127",
            "filter_release": "0..127",
            "amp_attack": "0..127",
            "amp_decay_1": "0..127",
            "amp_decay_2": "0..127",
            "amp_release": "0..127",
            "amp_level_1": "0..127",
            "amp_level_2": "0..127",
            "amp_level_3": "0..127",
            "lfo1_waveform": list(LFO_WAVEFORMS),
            "lfo1_pitch_depth": "-63..63",
            "lfo1_filter_depth": "-63..63",
            "lfo1_amp_depth": "-63..63",
            "lfo1_pan_depth": "-63..63",
        },
    }


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped


class OpenAICompatiblePlanner:
    """Plan patch changes through a configurable `/chat/completions` endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 60.0,
        transport: JsonHttpTransport | None = None,
    ) -> None:
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url must be a non-empty URL")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        normalized = base_url.rstrip("/")
        self.endpoint = (
            normalized if normalized.endswith("/chat/completions") else normalized + "/chat/completions"
        )
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.transport = transport or UrllibJsonTransport()

    def create_plan(self, request: str, patch: JunoPatch) -> PatchChangePlan:
        patch_context = {
            "name": patch.name,
            "category": patch.category,
            "common": asdict(patch.common_parameters),
            "tones": [asdict(tone) for tone in patch.tone_parameters],
        }
        user_payload = {
            "request": request,
            "current_patch": patch_context,
            "output_contract": _contract(),
        }
        body: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, separators=(",", ":"))},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = self.transport.post(self.endpoint, body, headers, self.timeout)
        if not isinstance(response, Mapping):
            raise PlannerError("LLM endpoint response must be a JSON object")
        try:
            choices = response["choices"]
            if not isinstance(choices, list) or not choices:
                raise KeyError("choices")
            choice = choices[0]
            if not isinstance(choice, Mapping):
                raise KeyError("choices[0]")
            message = choice["message"]
            if not isinstance(message, Mapping):
                raise KeyError("message")
            content = message["content"]
            if not isinstance(content, str):
                raise KeyError("content")
        except (KeyError, IndexError) as error:
            raise PlannerError("LLM endpoint response has no assistant message content") from error
        try:
            return PatchChangePlan.from_dict(json.loads(_strip_json_fence(content)))
        except json.JSONDecodeError as error:
            raise PlannerError(f"LLM returned invalid JSON: {error}") from error
        except PatchValidationError as error:
            raise PlannerError(f"LLM returned an invalid patch-change plan: {error}") from error
