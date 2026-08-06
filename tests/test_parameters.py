import copy
import unittest

from patchmaker_juno_ds.errors import PatchValidationError
from patchmaker_juno_ds.model import JunoPatch
from patchmaker_juno_ds.parameters import FILTER_TYPES, LFO_WAVEFORMS

from .helpers import make_patch


class ParameterTests(unittest.TestCase):
    def test_common_parameter_offsets_are_encoded_exactly(self) -> None:
        patch = make_patch().with_common_parameters(
            level=101,
            pan=-12,
            coarse_tune=-7,
            fine_tune=9,
            octave_shift=2,
            analog_feel=44,
            mono_poly="MONO",
            legato=True,
            portamento=True,
            portamento_time=35,
            cutoff_offset=-20,
            resonance_offset=5,
            attack_offset=22,
            release_offset=33,
        )
        common = patch.blocks["patch_common"]
        expected = {
            0x0E: 101,
            0x0F: 52,
            0x11: 57,
            0x12: 73,
            0x13: 66,
            0x15: 44,
            0x16: 0,
            0x17: 1,
            0x19: 1,
            0x1D: 35,
            0x22: 44,
            0x23: 69,
            0x24: 86,
            0x25: 97,
        }
        for offset, value in expected.items():
            self.assertEqual(common[offset], value)
        self.assertEqual(patch.common_parameters.level, 101)
        self.assertEqual(patch.common_parameters.cutoff_offset, -20)

    def test_tone_parameter_offsets_and_nibble_wave_number(self) -> None:
        patch = make_patch().with_tone_parameters(
            2,
            enabled=True,
            level=105,
            coarse_tune=-12,
            fine_tune=7,
            pan=15,
            chorus_send=50,
            reverb_send=60,
            wave_number=0x1234,
            filter_type="LPF3",
            cutoff=72,
            resonance=28,
            filter_env_depth=-17,
            filter_attack=85,
            filter_decay_1=70,
            filter_decay_2=60,
            filter_release=95,
            amp_attack=81,
            amp_decay_1=71,
            amp_decay_2=61,
            amp_release=91,
            amp_level_1=100,
            amp_level_2=90,
            amp_level_3=80,
            lfo1_waveform="TRI",
            lfo1_pitch_depth=-3,
            lfo1_filter_depth=4,
            lfo1_amp_depth=5,
            lfo1_pan_depth=6,
        )
        data = patch.blocks["tone_2"]
        self.assertEqual(data[0x00:0x05], (105, 52, 71, data[3], 79))
        self.assertEqual(data[0x2C:0x30], (1, 2, 3, 4))
        self.assertEqual(data[0x48], 6)
        self.assertEqual(data[0x4D], 28)
        self.assertEqual(data[0x55:0x59], (85, 70, 60, 95))
        self.assertEqual(data[0x66:0x6D], (81, 71, 61, 91, 100, 90, 80))
        self.assertEqual(data[0x77:0x7B], (61, 68, 69, 70))
        self.assertEqual(patch.blocks["tone_mix"][0x0E], 1)
        tone = patch.tone_parameters[1]
        self.assertEqual(tone.wave_number, 0x1234)
        self.assertEqual(tone.filter_type, "LPF3")

    def test_semantic_json_edits_update_raw_blocks(self) -> None:
        value = make_patch().to_dict()
        value["parameters"]["common"]["cutoff_offset"] = -31
        value["parameters"]["tones"][0]["cutoff"] = 42
        value["parameters"]["tones"][0]["enabled"] = True
        patch = JunoPatch.from_dict(value)
        self.assertEqual(patch.blocks["patch_common"][0x22], 33)
        self.assertEqual(patch.blocks["tone_1"][0x49], 42)
        self.assertEqual(patch.blocks["tone_mix"][0x05], 1)

    def test_semantic_round_trip_preserves_unmapped_bytes(self) -> None:
        patch = make_patch()
        original = copy.deepcopy(patch.blocks)
        restored = JunoPatch.from_dict(patch.to_dict())
        self.assertEqual(restored.blocks, original)

    def test_invalid_semantic_values_fail_closed(self) -> None:
        with self.assertRaisesRegex(PatchValidationError, "tone.cutoff"):
            make_patch().with_tone_parameters(1, cutoff=128)
        with self.assertRaisesRegex(PatchValidationError, "common.cutoff_offset"):
            make_patch().with_common_parameters(cutoff_offset=-64)
        value = make_patch().to_dict()
        value["parameters"]["tones"] = value["parameters"]["tones"][:3]
        with self.assertRaisesRegex(PatchValidationError, "exactly four"):
            JunoPatch.from_dict(value)

    def test_invalid_raw_enums_and_nibbles_fail_closed(self) -> None:
        value = make_patch().to_dict()
        value.pop("parameters")
        value["blocks"]["tone_1"][0x48] = 7
        patch = JunoPatch.from_dict(value)
        with self.assertRaisesRegex(PatchValidationError, "tone.filter_type"):
            _ = patch.tone_parameters

        value = make_patch().to_dict()
        value.pop("parameters")
        value["blocks"]["tone_1"][0x2F] = 16
        patch = JunoPatch.from_dict(value)
        with self.assertRaisesRegex(PatchValidationError, "four 4-bit"):
            _ = patch.tone_parameters

    def test_official_enumerations_are_complete(self) -> None:
        self.assertEqual(FILTER_TYPES, ("OFF", "LPF", "BPF", "HPF", "PKG", "LPF2", "LPF3"))
        self.assertEqual(len(LFO_WAVEFORMS), 13)
