import unittest

from patchmaker_juno_ds.designer import PatchChangePlan, SoundDesigner
from patchmaker_juno_ds.errors import PatchValidationError

from .helpers import make_patch


class StaticPlanner:
    def __init__(self, plan: PatchChangePlan) -> None:
        self.plan = plan
        self.requests: list[str] = []

    def create_plan(self, request, patch):
        self.requests.append(request)
        return self.plan


class DesignerTests(unittest.TestCase):
    def test_plan_builds_from_fully_initialized_blocks(self) -> None:
        patch = make_patch()
        original_mfx = patch.blocks["mfx"]
        plan = PatchChangePlan.from_dict(
            {
                "explanation": "Lower cutoff and soften the attack.",
                "name": "DARK PAD",
                "common": {"cutoff_offset": -24},
                "tones": [
                    {
                        "tone_number": 1,
                        "changes": {"filter_type": "LPF", "cutoff": 48, "amp_attack": 85},
                    }
                ],
            }
        )
        planner = StaticPlanner(plan)
        result = SoundDesigner(planner).refine(patch, "  make it darker  ")
        self.assertEqual(planner.requests, ["make it darker"])
        self.assertEqual(result.patch.name, "DARK PAD")
        self.assertEqual(result.patch.common_parameters.cutoff_offset, -24)
        self.assertEqual(result.patch.tone_parameters[0].cutoff, 48)
        self.assertEqual(result.patch.tone_parameters[0].amp_attack, 85)
        self.assertNotEqual(result.patch.blocks["mfx"], original_mfx)
        self.assertEqual(result.patch.blocks["mfx"][0x01], 127)
        self.assertEqual(result.patch.blocks["mfx"][0x11:0x15], (8, 0, 0, 0))

    def test_plan_result_is_independent_of_every_source_byte(self) -> None:
        first = make_patch(name="FIRST", category=1)
        blocks = {key: tuple(127 for _ in data) for key, data in first.blocks.items()}
        common = list(blocks["patch_common"])
        common[:12] = b"SECOND      "
        common[0x0C] = 2
        blocks["patch_common"] = tuple(common)
        second = type(first)(name="SECOND", category=2, blocks=blocks)
        plan = PatchChangePlan.from_dict(
            {
                "explanation": "Build a complete bass patch.",
                "name": "NEW BASS",
                "category": 13,
                "common": {"level": 105, "cutoff_offset": -12},
                "tones": [{"tone_number": 1, "changes": {"enabled": True, "cutoff": 55}}],
            }
        )
        self.assertEqual(plan.apply(first), plan.apply(second))

    def test_plan_rejects_raw_or_unknown_fields(self) -> None:
        with self.assertRaisesRegex(PatchValidationError, "unknown plan"):
            PatchChangePlan.from_dict(
                {"explanation": "unsafe", "blocks": {"tone_1": [1]}, "common": {"level": 1}}
            )
        with self.assertRaisesRegex(PatchValidationError, "unknown common"):
            PatchChangePlan.from_dict(
                {"explanation": "unsafe", "common": {"sysex_address": 12}}
            )

    def test_plan_rejects_duplicates_and_out_of_range_values(self) -> None:
        with self.assertRaisesRegex(PatchValidationError, "at most once"):
            PatchChangePlan.from_dict(
                {
                    "explanation": "duplicate",
                    "tones": [
                        {"tone_number": 1, "changes": {"cutoff": 50}},
                        {"tone_number": 1, "changes": {"cutoff": 60}},
                    ],
                }
            )
        plan = PatchChangePlan.from_dict(
            {"explanation": "invalid", "tones": [{"tone_number": 1, "changes": {"cutoff": 200}}]}
        )
        with self.assertRaisesRegex(PatchValidationError, "tone.cutoff"):
            plan.apply(make_patch())

    def test_empty_request_and_noop_plan_are_rejected(self) -> None:
        with self.assertRaisesRegex(PatchValidationError, "does not contain"):
            PatchChangePlan.from_dict({"explanation": "nothing"})
        planner = StaticPlanner(
            PatchChangePlan.from_dict({"explanation": "rename", "name": "NEW NAME"})
        )
        with self.assertRaisesRegex(PatchValidationError, "non-empty"):
            SoundDesigner(planner).refine(make_patch(), " ")
