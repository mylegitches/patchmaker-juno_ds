import json
import unittest

from patchmaker_juno_ds.errors import PatchValidationError, PlannerError
from patchmaker_juno_ds.openai_compatible import OpenAICompatiblePlanner

from .helpers import make_patch


class RecordingTransport:
    def __init__(self, response) -> None:
        self.response = response
        self.calls = []

    def post(self, url, body, headers, timeout):
        self.calls.append((url, body, headers, timeout))
        return self.response


def completion(content: str):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


class OpenAICompatiblePlannerTests(unittest.TestCase):
    def test_connection_checks_auth_model_and_structured_output(self) -> None:
        transport = RecordingTransport(
            {"model": "provider/resolved-model", "choices": [{"message": {"content": '{"ok":true}'}}]}
        )
        planner = OpenAICompatiblePlanner(
            base_url="https://router.test/v1",
            model="requested-model",
            api_key="test-secret",
            transport=transport,
        )
        self.assertEqual(planner.test_connection(), "provider/resolved-model")
        url, body, headers, timeout = transport.calls[0]
        self.assertEqual(url, "https://router.test/v1/chat/completions")
        self.assertEqual(body["model"], "requested-model")
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(headers["Authorization"], "Bearer test-secret")
        self.assertEqual(timeout, 60.0)

    def test_standard_chat_completions_request_and_plan_response(self) -> None:
        response_plan = {
            "explanation": "Darken all enabled tones.",
            "common": {"cutoff_offset": -18},
            "tones": [{"tone_number": 1, "changes": {"cutoff": 52}}],
        }
        transport = RecordingTransport(completion(json.dumps(response_plan)))
        planner = OpenAICompatiblePlanner(
            base_url="http://localhost:8000/v1/",
            model="test-model",
            api_key="secret-token",
            timeout=12.5,
            transport=transport,
        )
        plan = planner.create_plan("make it darker", make_patch())
        self.assertEqual(plan.name, "Darker")
        self.assertEqual(plan.common, {"cutoff_offset": -18})
        self.assertEqual(plan.tones[0].changes, {"cutoff": 52})

        url, body, headers, timeout = transport.calls[0]
        self.assertEqual(url, "http://localhost:8000/v1/chat/completions")
        self.assertEqual(body["model"], "test-model")
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(headers["Authorization"], "Bearer secret-token")
        self.assertEqual(timeout, 12.5)
        user_payload = json.loads(body["messages"][1]["content"])
        self.assertEqual(user_payload["request"], "make it darker")
        recognized = user_payload["recognized_sound_language"]
        self.assertTrue(any(item["phrase"] == "dark" for item in recognized))
        self.assertTrue(any("cutoff" in " ".join(item["guidance"]) for item in recognized))
        self.assertNotIn("blocks", user_payload["current_patch"])
        self.assertIn("tone_fields", user_payload["output_contract"])
        self.assertIn("required distinctive", user_payload["output_contract"]["top_level"]["name"])

    def test_missing_or_repeated_name_gets_a_fresh_request_based_name(self) -> None:
        transport = RecordingTransport(
            completion('{"explanation":"reshape","name":"TEST PATCH","common":{"level":100}}')
        )
        planner = OpenAICompatiblePlanner(
            base_url="http://example.test/v1", model="model", transport=transport
        )
        plan = planner.create_plan("hypnotic shimmering drone", make_patch())
        self.assertEqual(plan.name, "HypnoticShim")

    def test_api_key_is_optional_for_local_endpoints(self) -> None:
        transport = RecordingTransport(
            completion('{"explanation":"rename","name":"LOCAL PATCH"}')
        )
        planner = OpenAICompatiblePlanner(
            base_url="http://localhost:11434/v1/chat/completions",
            model="local",
            transport=transport,
        )
        self.assertEqual(planner.create_plan("rename it", make_patch()).name, "LOCAL PATCH")
        self.assertNotIn("Authorization", transport.calls[0][2])

    def test_markdown_fence_is_tolerated_but_invalid_output_fails(self) -> None:
        transport = RecordingTransport(
            completion('```json\n{"explanation":"rename","name":"FENCED"}\n```')
        )
        planner = OpenAICompatiblePlanner(
            base_url="http://example.test/v1", model="model", transport=transport
        )
        self.assertEqual(planner.create_plan("rename", make_patch()).name, "FENCED")

        transport.response = completion("not json")
        with self.assertRaisesRegex(PlannerError, "invalid JSON"):
            planner.create_plan("rename", make_patch())

    def test_missing_content_and_invalid_plan_fail_closed(self) -> None:
        transport = RecordingTransport({"choices": []})
        planner = OpenAICompatiblePlanner(
            base_url="http://example.test/v1", model="model", transport=transport
        )
        with self.assertRaisesRegex(PlannerError, "no assistant message"):
            planner.create_plan("dark", make_patch())

        transport.response = completion(
            '{"explanation":"unsafe","tones":[{"tone_number":1,"changes":{"cutoff":999}}]}'
        )
        plan = planner.create_plan("dark", make_patch())
        with self.assertRaisesRegex(PatchValidationError, "tone.cutoff"):
            plan.apply(make_patch())
