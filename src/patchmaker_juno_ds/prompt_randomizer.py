"""JUNO-oriented sound-description vocabulary and coherent prompt generation."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Mapping


# This catalog describes musical intent rather than raw device bytes. Its
# categories cover the dimensions musicians commonly use to communicate synth
# sounds while remaining useful to the verified semantic patch planner.
SYNTH_SOUND_ATTRIBUTES: Mapping[str, tuple[str, ...]] = {
    "sound_role": (
        "analog pad", "cinematic pad", "ambient pad", "string pad", "vocal pad",
        "brass pad", "poly synth", "synth brass", "soft lead", "hard lead",
        "monophonic lead", "sync-style lead", "synth bass", "sub bass", "acid bass",
        "pluck bass", "synth pluck", "sequenced pluck", "mallet", "digital bell",
        "electric piano", "synth keys", "organ", "comping chord patch", "synth strings",
        "orchestral texture", "sound-effect texture", "riser", "drone", "percussive hit",
    ),
    "mood": (
        "hopeful", "melancholic", "haunting", "dreamy", "euphoric", "tense",
        "ominous", "mysterious", "nostalgic", "romantic", "serene", "playful",
        "heroic", "dramatic", "intimate", "majestic", "otherworldly", "hypnotic",
        "urgent", "brooding", "delicate", "futuristic", "retro", "cinematic",
    ),
    "tonal_character": (
        "warm", "dark", "bright", "soft", "hard", "smooth", "glassy", "metallic",
        "woody", "hollow", "nasal", "airy", "breathy", "buzzy", "reedy", "silky",
        "creamy", "rounded", "crystalline", "shimmering", "muted", "raw", "gritty",
        "dirty", "clean", "polished", "lo-fi", "vintage", "modern", "analog-like",
        "digital", "organic", "synthetic", "aggressive", "gentle", "lush", "thin",
        "thick", "punchy", "fragile", "icy", "smoky", "rubbery", "liquid",
    ),
    "source_character": (
        "saw-like harmonic layers", "square and pulse-like layers", "rounded sine-like fundamentals",
        "triangle-like soft harmonics", "detuned analog-style oscillators", "stacked unison layers",
        "octave-layered waves", "fifth-layered waves", "bell-like partials", "metallic partials",
        "noise mixed under the pitched tone", "breathy noise", "digital PCM color",
        "acoustic-and-synthetic hybrid layers", "thin pulse-like harmonics", "rich full-spectrum harmonics",
        "a clean fundamental with subtle upper harmonics", "contrasting bright and dark layers",
    ),
    "register": (
        "a deep sub register", "a low register", "a low-mid register", "a centered mid register",
        "an upper-mid register", "a high register", "a wide multi-octave range",
        "a low fundamental with a quiet octave layer", "a centered register with a high shimmer layer",
    ),
    "density": (
        "a sparse single-layer body", "a focused two-layer body", "a balanced layered body",
        "a dense four-tone stack", "a huge wall of harmonics", "a light transparent body",
        "a strong fundamental", "a soft fundamental with rich overtones", "a broad ensemble-like body",
        "a narrow focused body", "an evolving layered body",
    ),
    "filter": (
        "a deeply closed low-pass character", "a gently rolled-off low-pass character",
        "a moderately bright low-pass character", "an open bright low-pass character",
        "a resonant low-pass peak", "a restrained low-pass resonance", "a vocal band-pass color",
        "a narrow resonant band-pass color", "a thin high-pass color", "a bright high-pass edge",
        "almost no filtering", "different filter colors across the layers",
    ),
    "filter_envelope": (
        "almost no filter-envelope movement", "a slow filter fade-in", "a gentle opening filter sweep",
        "a pronounced opening filter sweep", "a short percussive filter snap", "a quick bright attack that darkens",
        "a dark attack that blooms brighter", "a long evolving filter contour", "an inverted filter-envelope feel",
        "a restrained filter contour that follows the amplitude", "a resonant filter-envelope accent",
    ),
    "amplitude_envelope": (
        "an immediate attack and tight release", "a fast attack with a short decay", "a plucky transient and quick release",
        "a firm attack with medium sustain", "a soft attack and natural decay", "a slow attack and long release",
        "a very slow swell and lingering tail", "a bowed attack with steady sustain", "an organ-like instant attack and full sustain",
        "a percussive attack with no sustained body", "a gated envelope", "a reverse-like swell",
        "a breathing envelope with a gentle release", "a punchy attack and controlled tail",
    ),
    "movement": (
        "no obvious modulation", "very subtle pitch drift", "gentle analog instability",
        "slow sine-like filter motion", "slow triangle-like amplitude motion", "a soft random drift",
        "a wide slow pan motion", "a restrained vibrato", "expressive vibrato", "a pulsing amplitude motion",
        "rhythmic filter movement", "sample-and-hold style motion", "chaotic evolving motion",
        "different subtle modulation on each layer", "a slowly evolving timbre", "a steady animated shimmer",
    ),
    "stereo_image": (
        "a centered mono image", "a narrow focused image", "a natural stereo image", "a wide stereo image",
        "an extremely wide layered image", "opposing pan positions across layers", "a centered fundamental with wide upper layers",
        "subtle left-right movement", "a stable stereo image without obvious panning",
    ),
    "space": (
        "nearly dry ambience", "a short intimate room", "a subtle studio ambience", "a medium atmospheric tail",
        "a long lush reverb tail", "a huge distant space", "a dark reverb impression", "a bright shimmering space",
        "a moderate chorus-like width", "a rich ensemble-like width", "subtle chorus and restrained ambience",
        "wide chorus with a controlled reverb tail", "a spacious but clearly defined foreground",
    ),
    "tuning": (
        "precise stable tuning", "barely perceptible detuning", "gentle detuning between layers",
        "wide analog detuning", "octave doubling", "a quiet fifth layer", "octave and fifth layering",
        "a slightly sharp upper layer", "a slightly flat supporting layer", "micro-detuned stereo layers",
        "a stable fundamental with unstable upper layers",
    ),
    "articulation": (
        "smooth and legato", "cleanly separated", "short and staccato", "softly articulated",
        "hard and percussive", "fluid and connected", "gated and precise", "loose and human",
        "expressive under sustained notes", "consistent across repeated notes", "delicate at note onset",
        "forceful at note onset",
    ),
    "performance_behavior": (
        "polyphonic chord playing", "monophonic melodic playing", "legato lead playing", "slow chord changes",
        "fast arpeggiated playing", "repeated rhythmic notes", "sustained single notes", "wide two-handed voicings",
        "bass lines with subtle portamento", "lead lines with audible portamento", "precise playing with portamento off",
        "expressive performance with moderate analog feel", "stable ensemble playing",
    ),
    "dynamics": (
        "soft and restrained", "even and controlled", "moderately dynamic", "highly expressive",
        "punchy and forward", "gentle and distant", "bold without becoming harsh", "quiet but harmonically rich",
        "loud and dense", "clear in a busy mix", "supportive behind other instruments",
    ),
    "era_and_genre": (
        "1970s analog", "1980s synth-pop", "1980s cinematic", "1990s digital", "classic house",
        "Detroit techno", "ambient", "trance", "synthwave", "darkwave", "new wave", "electro",
        "modern pop", "modern film score", "video-game soundtrack", "industrial", "downtempo",
        "progressive electronic", "experimental electronic", "R&B", "funk", "fusion",
    ),
}

# Each plain-language dimension maps to the verified semantic controls that can
# realize it. This guarantees that every randomized phrase has an actionable
# destination even when the listener does not know synthesis terminology.
ATTRIBUTE_PARAMETER_DIMENSIONS: Mapping[str, tuple[str, ...]] = {
    "sound_role": ("category", "common.mono_poly", "tone.enabled", "tone.level", "tone.wave_number"),
    "mood": ("common.cutoff_offset", "common.attack_offset", "common.release_offset", "tone.lfo1_*_depth", "tone.reverb_send"),
    "tonal_character": ("common.cutoff_offset", "common.resonance_offset", "common.analog_feel", "tone.cutoff", "tone.resonance"),
    "source_character": ("tone.wave_number", "tone.enabled", "tone.level", "tone.coarse_tune", "tone.fine_tune"),
    "register": ("common.octave_shift", "tone.coarse_tune", "tone.level"),
    "density": ("tone.enabled", "tone.level", "tone.pan", "tone.coarse_tune", "tone.fine_tune"),
    "filter": ("tone.filter_type", "tone.cutoff", "tone.resonance", "common.cutoff_offset", "common.resonance_offset"),
    "filter_envelope": ("tone.filter_env_depth", "tone.filter_attack", "tone.filter_decay_1", "tone.filter_decay_2", "tone.filter_release"),
    "amplitude_envelope": ("tone.amp_attack", "tone.amp_decay_1", "tone.amp_decay_2", "tone.amp_release", "tone.amp_level_1", "tone.amp_level_2", "tone.amp_level_3"),
    "movement": ("tone.lfo1_waveform", "tone.lfo1_pitch_depth", "tone.lfo1_filter_depth", "tone.lfo1_amp_depth", "tone.lfo1_pan_depth"),
    "stereo_image": ("common.pan", "tone.pan", "tone.lfo1_pan_depth"),
    "space": ("tone.chorus_send", "tone.reverb_send", "tone.pan"),
    "tuning": ("common.analog_feel", "tone.coarse_tune", "tone.fine_tune"),
    "articulation": ("common.mono_poly", "common.legato", "tone.amp_attack", "tone.amp_release"),
    "performance_behavior": ("common.mono_poly", "common.legato", "common.portamento", "common.portamento_time"),
    "dynamics": ("common.level", "tone.level", "tone.amp_attack", "tone.amp_level_1", "tone.amp_level_2", "tone.amp_level_3"),
    "era_and_genre": ("common.analog_feel", "tone.wave_number", "tone.filter_type", "tone.cutoff", "tone.resonance", "tone.chorus_send", "tone.reverb_send"),
}

# High-value adjective recipes supply directional decisions in addition to the
# field mapping above. Exact values remain the planner's job and are validated
# by the deterministic patch model.
DESCRIPTOR_PARAMETER_GUIDANCE: Mapping[str, tuple[str, ...]] = {
    "warm": ("lower cutoff moderately", "keep resonance restrained", "increase analog feel"),
    "dark": ("lower cutoff and cutoff offset", "avoid excessive filter-envelope depth"),
    "bright": ("raise cutoff", "use a positive cutoff offset", "retain controlled resonance"),
    "soft": ("slow the amp attack slightly", "lower brightness and resonance", "use a gentle release"),
    "hard": ("use a fast amp attack", "increase upper harmonics and level"),
    "glassy": ("choose a bright digital wave character", "use high cutoff with modest resonance"),
    "metallic": ("layer inharmonic or bell-like waves", "use band-pass or resonant filtering"),
    "airy": ("add a quiet bright or noise-like layer", "use high cutoff and spacious reverb send"),
    "buzzy": ("favor rich saw or pulse harmonics", "keep cutoff moderately open"),
    "smooth": ("reduce resonance", "use gentle envelope transitions", "avoid deep pitch modulation"),
    "gritty": ("use harmonically dense waves", "add resonance and contrasting layers"),
    "lush": ("enable multiple gently detuned tones", "spread tone pans", "increase chorus and reverb sends moderately"),
    "thin": ("use fewer layers", "reduce low-register support", "consider high-pass filtering"),
    "thick": ("layer multiple tones", "use gentle detuning and octave support", "keep a strong fundamental"),
    "punchy": ("use a fast amp attack and short early decay", "add a brief positive filter envelope"),
    "plucky": ("use immediate attack, fast decay, low sustain, and short release", "add a short filter-envelope snap"),
    "haunting": ("use minor-feeling dark harmonics", "slow attack and release", "add subtle random or sine modulation"),
    "dreamy": ("soften attack", "lengthen release", "use wide detuned layers and spacious sends"),
    "ominous": ("favor low register and dark filtering", "use slow movement and restrained brightness"),
    "euphoric": ("use bright layered harmonics", "open the filter", "increase stereo width and release"),
    "nostalgic": ("increase analog feel", "use gentle detuning", "roll off extreme brightness"),
    "slow attack": ("raise amp attack and filter attack values",),
    "fast attack": ("lower amp attack and filter attack values",),
    "long release": ("raise amp release and filter release values",),
    "short release": ("lower amp release and filter release values",),
    "wide stereo": ("pan supporting tones apart", "keep the fundamental near center", "add modest pan modulation"),
    "centered mono": ("center all tone pans", "avoid pan modulation", "prefer mono performance mode when appropriate"),
    "gentle detuning": ("offset supporting tone fine tuning by small opposite amounts",),
    "wide analog detuning": ("use larger opposite fine-tune offsets while preserving a stable center tone",),
    "octave doubling": ("add a supporting tone at plus or minus 12 semitones",),
    "fifth layer": ("add a quiet supporting tone at plus 7 semitones",),
    "sub bass": ("use mono mode", "favor low register and strong fundamental", "keep stereo width narrow"),
    "lead": ("use mono or legato behavior where appropriate", "keep the main tone forward", "consider portamento"),
    "pad": ("use poly mode", "layer tones", "favor slower attack and longer release"),
    "pluck": ("use fast attack, rapid decay, reduced sustain, and short release"),
    "brass": ("use rich saw-like layers", "add a positive filter-envelope swell", "use a firm attack"),
    "bell": ("favor bright partial-rich waves", "use fast attack, long decay, and low sustain"),
    "organ": ("use instant attack and full sustain", "keep filter-envelope movement minimal"),
    "drone": ("use long sustain and release", "add slow evolving modulation"),
    "portamento": ("enable portamento and set time to match subtle or audible wording",),
    "legato": ("enable mono and legato for connected melodic playing",),
    "chorus": ("increase chorus send while controlling low-frequency smear",),
    "reverb": ("increase reverb send according to the requested distance and tail",),
    "resonant": ("raise resonance carefully and compensate cutoff if the sound becomes too thin",),
    "low-pass": ("select an LPF type and set cutoff from the requested brightness",),
    "band-pass": ("select BPF and use resonance to focus the desired band",),
    "high-pass": ("select HPF and preserve enough body for the requested role",),
    "vibrato": ("use sine or triangle LFO with pitch depth proportional to subtle or expressive wording",),
    "random drift": ("use random LFO with shallow pitch, filter, or pan depth",),
    "pulsing": ("use triangle or square LFO with amplitude or filter depth",),
}


def resolve_sound_language(text: str) -> list[dict[str, object]]:
    """Map natural sound language to supported parameter dimensions and guidance."""
    normalized = text.casefold()
    resolved: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for category, values in SYNTH_SOUND_ATTRIBUTES.items():
        for value in values:
            if value.casefold() in normalized and (category, value) not in seen:
                guidance = [
                    hint
                    for descriptor, hints in DESCRIPTOR_PARAMETER_GUIDANCE.items()
                    if descriptor in value.casefold()
                    for hint in hints
                ]
                resolved.append(
                    {
                        "phrase": value,
                        "dimension": category,
                        "parameters": list(ATTRIBUTE_PARAMETER_DIMENSIONS[category]),
                        "guidance": list(dict.fromkeys(guidance)),
                    }
                )
                seen.add((category, value))
    recognized = {item["phrase"] for item in resolved}
    for descriptor in sorted(DESCRIPTOR_PARAMETER_GUIDANCE, key=len, reverse=True):
        if descriptor in normalized and descriptor not in recognized:
            resolved.append(
                {
                    "phrase": descriptor,
                    "dimension": "descriptor_recipe",
                    "parameters": [],
                    "guidance": list(DESCRIPTOR_PARAMETER_GUIDANCE[descriptor]),
                }
            )
    return resolved


@dataclass(frozen=True, slots=True)
class RandomizedPrompt:
    prompt: str
    attributes: Mapping[str, str]


ROLE_CONSTRAINTS: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    "bass": {
        "register": ("a deep sub register", "a low register", "a low-mid register"),
        "density": ("a sparse single-layer body", "a focused two-layer body", "a balanced layered body", "a strong fundamental"),
        "amplitude_envelope": ("an immediate attack and tight release", "a fast attack with a short decay", "a firm attack with medium sustain", "a punchy attack and controlled tail"),
        "stereo_image": ("a centered mono image", "a narrow focused image", "a natural stereo image", "a centered fundamental with wide upper layers"),
        "space": ("nearly dry ambience", "a short intimate room", "a subtle studio ambience", "subtle chorus and restrained ambience"),
        "performance_behavior": ("monophonic melodic playing", "repeated rhythmic notes", "bass lines with subtle portamento", "precise playing with portamento off"),
    },
    "pad": {
        "density": ("a balanced layered body", "a dense four-tone stack", "a huge wall of harmonics", "a light transparent body", "a broad ensemble-like body", "an evolving layered body"),
        "amplitude_envelope": ("a soft attack and natural decay", "a slow attack and long release", "a very slow swell and lingering tail", "a bowed attack with steady sustain", "a breathing envelope with a gentle release"),
        "stereo_image": ("a natural stereo image", "a wide stereo image", "an extremely wide layered image", "opposing pan positions across layers", "a centered fundamental with wide upper layers", "a stable stereo image without obvious panning"),
        "space": ("a medium atmospheric tail", "a long lush reverb tail", "a huge distant space", "a dark reverb impression", "a bright shimmering space", "a rich ensemble-like width", "wide chorus with a controlled reverb tail"),
        "performance_behavior": ("polyphonic chord playing", "slow chord changes", "sustained single notes", "wide two-handed voicings", "expressive performance with moderate analog feel"),
    },
    "lead": {
        "register": ("a centered mid register", "an upper-mid register", "a high register", "a wide multi-octave range"),
        "density": ("a sparse single-layer body", "a focused two-layer body", "a balanced layered body", "a strong fundamental"),
        "amplitude_envelope": ("an immediate attack and tight release", "a firm attack with medium sustain", "a soft attack and natural decay", "a punchy attack and controlled tail"),
        "stereo_image": ("a centered mono image", "a narrow focused image", "a natural stereo image", "a centered fundamental with wide upper layers"),
        "performance_behavior": ("monophonic melodic playing", "legato lead playing", "sustained single notes", "lead lines with audible portamento", "precise playing with portamento off"),
    },
    "pluck": {
        "filter_envelope": ("a pronounced opening filter sweep", "a short percussive filter snap", "a quick bright attack that darkens", "a resonant filter-envelope accent"),
        "amplitude_envelope": ("an immediate attack and tight release", "a fast attack with a short decay", "a plucky transient and quick release", "a percussive attack with no sustained body", "a gated envelope", "a punchy attack and controlled tail"),
        "performance_behavior": ("fast arpeggiated playing", "repeated rhythmic notes", "precise playing with portamento off"),
    },
    "bell": {
        "filter": ("a moderately bright low-pass character", "an open bright low-pass character", "a resonant low-pass peak", "a vocal band-pass color", "almost no filtering"),
        "amplitude_envelope": ("an immediate attack and tight release", "a fast attack with a short decay", "a percussive attack with no sustained body", "a punchy attack and controlled tail"),
        "performance_behavior": ("fast arpeggiated playing", "repeated rhythmic notes", "sustained single notes"),
    },
    "organ": {
        "filter_envelope": ("almost no filter-envelope movement", "a restrained filter contour that follows the amplitude"),
        "amplitude_envelope": ("an organ-like instant attack and full sustain",),
        "performance_behavior": ("polyphonic chord playing", "fast arpeggiated playing", "wide two-handed voicings", "stable ensemble playing"),
    },
    "drone": {
        "amplitude_envelope": ("a slow attack and long release", "a very slow swell and lingering tail", "a bowed attack with steady sustain", "a breathing envelope with a gentle release"),
        "movement": ("very subtle pitch drift", "gentle analog instability", "slow sine-like filter motion", "a soft random drift", "a wide slow pan motion", "chaotic evolving motion", "a slowly evolving timbre"),
        "space": ("a medium atmospheric tail", "a long lush reverb tail", "a huge distant space", "a dark reverb impression", "a spacious but clearly defined foreground"),
        "performance_behavior": ("sustained single notes", "slow chord changes"),
    },
}


def _options_for_role(role: str, category: str) -> tuple[str, ...]:
    for keyword, constraints in ROLE_CONSTRAINTS.items():
        if keyword in role and category in constraints:
            return constraints[category]
    return SYNTH_SOUND_ATTRIBUTES[category]


def randomize_prompt(rng: random.Random | None = None) -> RandomizedPrompt:
    """Combine complementary attribute dimensions into a ready-to-use prompt."""
    chooser = rng or random.SystemRandom()
    role = chooser.choice(SYNTH_SOUND_ATTRIBUTES["sound_role"])
    selected = {"sound_role": role}
    for key in (
        "mood", "tonal_character", "era_and_genre", "source_character", "register",
        "density", "filter", "filter_envelope", "amplitude_envelope", "movement",
        "stereo_image", "space", "tuning", "articulation", "performance_behavior", "dynamics",
    ):
        selected[key] = chooser.choice(_options_for_role(role, key))
    prompt = (
        f"Create a {selected['mood']}, {selected['tonal_character']} {selected['sound_role']} "
        f"with a {selected['era_and_genre']} character. Build it from {selected['source_character']}, "
        f"using {selected['register']} and {selected['density']}. Shape it with {selected['filter']} "
        f"and {selected['filter_envelope']}, then give it {selected['amplitude_envelope']}. "
        f"Add {selected['movement']}, {selected['stereo_image']}, and {selected['space']}. "
        f"Use {selected['tuning']}; make it {selected['articulation']} for "
        f"{selected['performance_behavior']}. Keep the result {selected['dynamics']}."
    )
    return RandomizedPrompt(prompt=prompt, attributes=selected)
