"""Verified semantic views over JUNO-DS patch blocks.

Offsets and encodings come from Roland's JUNO-DS MIDI Implementation 1.00:
https://static.roland.com/assets/media/pdf/JUNO-DS_MIDI_Imple_e01_W.pdf
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Mapping, Sequence

from .errors import PatchValidationError

FILTER_TYPES = ("OFF", "LPF", "BPF", "HPF", "PKG", "LPF2", "LPF3")
LFO_WAVEFORMS = (
    "SIN",
    "TRI",
    "SAW_UP",
    "SAW_DOWN",
    "SQUARE",
    "RANDOM",
    "BEND_UP",
    "BEND_DOWN",
    "TRAPEZOID",
    "SAMPLE_HOLD",
    "CHAOS",
    "VSIN",
    "STEP",
)


def _integer(value: object, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PatchValidationError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise PatchValidationError(f"{name} must be between {minimum} and {maximum}")
    return value


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise PatchValidationError(f"{name} must be true or false")
    return value


def _choice(value: object, name: str, choices: tuple[str, ...]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise PatchValidationError(f"{name} must be one of: {', '.join(choices)}")
    return value


@dataclass(frozen=True, slots=True)
class CommonParameters:
    level: int
    pan: int
    coarse_tune: int
    fine_tune: int
    octave_shift: int
    analog_feel: int
    mono_poly: str
    legato: bool
    portamento: bool
    portamento_time: int
    cutoff_offset: int
    resonance_offset: int
    attack_offset: int
    release_offset: int

    def __post_init__(self) -> None:
        _integer(self.level, "common.level", 0, 127)
        _integer(self.pan, "common.pan", -64, 63)
        _integer(self.coarse_tune, "common.coarse_tune", -48, 48)
        _integer(self.fine_tune, "common.fine_tune", -50, 50)
        _integer(self.octave_shift, "common.octave_shift", -3, 3)
        _integer(self.analog_feel, "common.analog_feel", 0, 127)
        _choice(self.mono_poly, "common.mono_poly", ("MONO", "POLY"))
        _boolean(self.legato, "common.legato")
        _boolean(self.portamento, "common.portamento")
        _integer(self.portamento_time, "common.portamento_time", 0, 127)
        for name in ("cutoff_offset", "resonance_offset", "attack_offset", "release_offset"):
            _integer(getattr(self, name), f"common.{name}", -63, 63)

    def updated(self, **changes: object) -> "CommonParameters":
        try:
            return replace(self, **changes)
        except TypeError as error:
            raise PatchValidationError(str(error)) from error


@dataclass(frozen=True, slots=True)
class ToneParameters:
    enabled: bool
    level: int
    coarse_tune: int
    fine_tune: int
    pan: int
    chorus_send: int
    reverb_send: int
    wave_number: int
    filter_type: str
    cutoff: int
    resonance: int
    filter_env_depth: int
    filter_attack: int
    filter_decay_1: int
    filter_decay_2: int
    filter_release: int
    amp_attack: int
    amp_decay_1: int
    amp_decay_2: int
    amp_release: int
    amp_level_1: int
    amp_level_2: int
    amp_level_3: int
    lfo1_waveform: str
    lfo1_pitch_depth: int
    lfo1_filter_depth: int
    lfo1_amp_depth: int
    lfo1_pan_depth: int

    def __post_init__(self) -> None:
        _boolean(self.enabled, "tone.enabled")
        for name in (
            "level",
            "chorus_send",
            "reverb_send",
            "cutoff",
            "resonance",
            "filter_attack",
            "filter_decay_1",
            "filter_decay_2",
            "filter_release",
            "amp_attack",
            "amp_decay_1",
            "amp_decay_2",
            "amp_release",
            "amp_level_1",
            "amp_level_2",
            "amp_level_3",
        ):
            _integer(getattr(self, name), f"tone.{name}", 0, 127)
        _integer(self.coarse_tune, "tone.coarse_tune", -48, 48)
        _integer(self.fine_tune, "tone.fine_tune", -50, 50)
        _integer(self.pan, "tone.pan", -64, 63)
        _integer(self.wave_number, "tone.wave_number", 0, 16384)
        _choice(self.filter_type, "tone.filter_type", FILTER_TYPES)
        _integer(self.filter_env_depth, "tone.filter_env_depth", -63, 63)
        _choice(self.lfo1_waveform, "tone.lfo1_waveform", LFO_WAVEFORMS)
        for name in ("lfo1_pitch_depth", "lfo1_filter_depth", "lfo1_amp_depth", "lfo1_pan_depth"):
            _integer(getattr(self, name), f"tone.{name}", -63, 63)

    def updated(self, **changes: object) -> "ToneParameters":
        try:
            return replace(self, **changes)
        except TypeError as error:
            raise PatchValidationError(str(error)) from error


def _nibbles_to_int(data: Sequence[int], offset: int) -> int:
    nibbles = data[offset : offset + 4]
    if len(nibbles) != 4 or any(value > 0x0F for value in nibbles):
        raise PatchValidationError("tone.wave_number must use four 4-bit data nibbles")
    return (nibbles[0] << 12) | (nibbles[1] << 8) | (nibbles[2] << 4) | nibbles[3]


def _decode_choice(data: Sequence[int], offset: int, name: str, choices: tuple[str, ...]) -> str:
    value = data[offset]
    if value >= len(choices):
        raise PatchValidationError(f"raw {name} value {value} is outside the documented range")
    return choices[value]


def _write_nibbles(data: list[int], offset: int, value: int) -> None:
    for index, shift in enumerate((12, 8, 4, 0)):
        data[offset + index] = (value >> shift) & 0x0F


def decode_common(data: Sequence[int]) -> CommonParameters:
    return CommonParameters(
        level=data[0x0E],
        pan=data[0x0F] - 64,
        coarse_tune=data[0x11] - 64,
        fine_tune=data[0x12] - 64,
        octave_shift=data[0x13] - 64,
        analog_feel=data[0x15],
        mono_poly=_decode_choice(data, 0x16, "common.mono_poly", ("MONO", "POLY")),
        legato=bool(data[0x17]),
        portamento=bool(data[0x19]),
        portamento_time=data[0x1D],
        cutoff_offset=data[0x22] - 64,
        resonance_offset=data[0x23] - 64,
        attack_offset=data[0x24] - 64,
        release_offset=data[0x25] - 64,
    )


def encode_common(original: Sequence[int], parameters: CommonParameters) -> tuple[int, ...]:
    data = list(original)
    data[0x0E] = parameters.level
    data[0x0F] = parameters.pan + 64
    data[0x11] = parameters.coarse_tune + 64
    data[0x12] = parameters.fine_tune + 64
    data[0x13] = parameters.octave_shift + 64
    data[0x15] = parameters.analog_feel
    data[0x16] = ("MONO", "POLY").index(parameters.mono_poly)
    data[0x17] = int(parameters.legato)
    data[0x19] = int(parameters.portamento)
    data[0x1D] = parameters.portamento_time
    data[0x22] = parameters.cutoff_offset + 64
    data[0x23] = parameters.resonance_offset + 64
    data[0x24] = parameters.attack_offset + 64
    data[0x25] = parameters.release_offset + 64
    return tuple(data)


_TONE_SWITCH_OFFSETS = (0x05, 0x0E, 0x17, 0x20)


def decode_tone(data: Sequence[int], tone_mix: Sequence[int], index: int) -> ToneParameters:
    if not 0 <= index <= 3:
        raise PatchValidationError("tone index must be between 0 and 3")
    return ToneParameters(
        enabled=bool(tone_mix[_TONE_SWITCH_OFFSETS[index]]),
        level=data[0x00],
        coarse_tune=data[0x01] - 64,
        fine_tune=data[0x02] - 64,
        pan=data[0x04] - 64,
        chorus_send=data[0x0D],
        reverb_send=data[0x0E],
        wave_number=_nibbles_to_int(data, 0x2C),
        filter_type=_decode_choice(data, 0x48, "tone.filter_type", FILTER_TYPES),
        cutoff=data[0x49],
        resonance=data[0x4D],
        filter_env_depth=data[0x4F] - 64,
        filter_attack=data[0x55],
        filter_decay_1=data[0x56],
        filter_decay_2=data[0x57],
        filter_release=data[0x58],
        amp_attack=data[0x66],
        amp_decay_1=data[0x67],
        amp_decay_2=data[0x68],
        amp_release=data[0x69],
        amp_level_1=data[0x6A],
        amp_level_2=data[0x6B],
        amp_level_3=data[0x6C],
        lfo1_waveform=_decode_choice(data, 0x6D, "tone.lfo1_waveform", LFO_WAVEFORMS),
        lfo1_pitch_depth=data[0x77] - 64,
        lfo1_filter_depth=data[0x78] - 64,
        lfo1_amp_depth=data[0x79] - 64,
        lfo1_pan_depth=data[0x7A] - 64,
    )


def encode_tone(
    original: Sequence[int], tone_mix: Sequence[int], index: int, parameters: ToneParameters
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if not 0 <= index <= 3:
        raise PatchValidationError("tone index must be between 0 and 3")
    data = list(original)
    mix = list(tone_mix)
    mix[_TONE_SWITCH_OFFSETS[index]] = int(parameters.enabled)
    data[0x00] = parameters.level
    data[0x01] = parameters.coarse_tune + 64
    data[0x02] = parameters.fine_tune + 64
    data[0x04] = parameters.pan + 64
    data[0x0D] = parameters.chorus_send
    data[0x0E] = parameters.reverb_send
    _write_nibbles(data, 0x2C, parameters.wave_number)
    data[0x48] = FILTER_TYPES.index(parameters.filter_type)
    data[0x49] = parameters.cutoff
    data[0x4D] = parameters.resonance
    data[0x4F] = parameters.filter_env_depth + 64
    data[0x55:0x59] = (
        parameters.filter_attack,
        parameters.filter_decay_1,
        parameters.filter_decay_2,
        parameters.filter_release,
    )
    data[0x66:0x6A] = (
        parameters.amp_attack,
        parameters.amp_decay_1,
        parameters.amp_decay_2,
        parameters.amp_release,
    )
    data[0x6A:0x6D] = (parameters.amp_level_1, parameters.amp_level_2, parameters.amp_level_3)
    data[0x6D] = LFO_WAVEFORMS.index(parameters.lfo1_waveform)
    data[0x77:0x7B] = (
        parameters.lfo1_pitch_depth + 64,
        parameters.lfo1_filter_depth + 64,
        parameters.lfo1_amp_depth + 64,
        parameters.lfo1_pan_depth + 64,
    )
    return tuple(data), tuple(mix)


def parameters_to_dict(common: CommonParameters, tones: Sequence[ToneParameters]) -> dict[str, Any]:
    return {"common": asdict(common), "tones": [asdict(tone) for tone in tones]}


def parameters_from_dict(value: object) -> tuple[CommonParameters, tuple[ToneParameters, ...]]:
    if not isinstance(value, Mapping) or set(value) != {"common", "tones"}:
        raise PatchValidationError("parameters must contain exactly 'common' and 'tones'")
    common_value = value["common"]
    tones_value = value["tones"]
    if not isinstance(common_value, Mapping):
        raise PatchValidationError("parameters.common must be an object")
    if not isinstance(tones_value, list) or len(tones_value) != 4:
        raise PatchValidationError("parameters.tones must contain exactly four tones")
    if any(not isinstance(tone, Mapping) for tone in tones_value):
        raise PatchValidationError("each parameters.tones item must be an object")
    try:
        common = CommonParameters(**common_value)
        tones = tuple(ToneParameters(**tone) for tone in tones_value)
    except TypeError as error:
        raise PatchValidationError(str(error)) from error
    return common, tones
