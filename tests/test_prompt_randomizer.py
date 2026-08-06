import random
import unittest

from patchmaker_juno_ds.prompt_randomizer import (
    ATTRIBUTE_PARAMETER_DIMENSIONS,
    SYNTH_SOUND_ATTRIBUTES,
    randomize_prompt,
    resolve_sound_language,
)


class PromptRandomizerTests(unittest.TestCase):
    def test_catalog_dimensions_are_complete_and_actionable(self) -> None:
        self.assertGreaterEqual(len(SYNTH_SOUND_ATTRIBUTES), 15)
        self.assertEqual(set(SYNTH_SOUND_ATTRIBUTES), set(ATTRIBUTE_PARAMETER_DIMENSIONS))
        for category, values in SYNTH_SOUND_ATTRIBUTES.items():
            self.assertGreater(len(values), 5, category)
            self.assertTrue(ATTRIBUTE_PARAMETER_DIMENSIONS[category], category)
            self.assertEqual(len(values), len(set(values)), category)

    def test_seeded_randomization_is_repeatable_and_fully_mapped(self) -> None:
        first = randomize_prompt(random.Random(42))
        second = randomize_prompt(random.Random(42))
        self.assertEqual(first, second)
        self.assertGreater(len(first.prompt), 300)
        self.assertEqual(set(first.attributes), set(SYNTH_SOUND_ATTRIBUTES))
        mapping = resolve_sound_language(first.prompt)
        mapped_dimensions = {item["dimension"] for item in mapping}
        self.assertTrue(set(first.attributes).issubset(mapped_dimensions))
        self.assertTrue(
            all(item["parameters"] for item in mapping if item["dimension"] != "descriptor_recipe")
        )

    def test_common_beginner_words_resolve_to_parameter_guidance(self) -> None:
        mapping = resolve_sound_language(
            "Give me a warm, dark, lush pad with a slow attack, long release, "
            "wide stereo, and gentle detuning"
        )
        phrases = {item["phrase"] for item in mapping}
        for expected in (
            "warm", "dark", "lush", "pad", "slow attack", "long release",
            "wide stereo", "gentle detuning",
        ):
            self.assertIn(expected, phrases)
        guidance = " ".join(hint for item in mapping for hint in item["guidance"])
        self.assertIn("cutoff", guidance)
        self.assertIn("amp attack", guidance)
        self.assertIn("tone pans", guidance)

    def test_random_prompts_vary(self) -> None:
        prompts = {randomize_prompt(random.Random(seed)).prompt for seed in range(12)}
        self.assertEqual(len(prompts), 12)

    def test_role_constraints_prevent_obvious_mismatches(self) -> None:
        for seed in range(250):
            attributes = randomize_prompt(random.Random(seed)).attributes
            role = attributes["sound_role"]
            if "bass" in role:
                self.assertIn(
                    attributes["register"],
                    ("a deep sub register", "a low register", "a low-mid register"),
                )
                self.assertNotEqual(attributes["stereo_image"], "an extremely wide layered image")
            if "organ" in role:
                self.assertEqual(
                    attributes["amplitude_envelope"], "an organ-like instant attack and full sustain"
                )


if __name__ == "__main__":
    unittest.main()
