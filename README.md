# AI JUNO-DS Patch Creator

An AI-assisted patch creator for the **Roland JUNO-DS**. The goal is to let musicians design synthesizer sounds from natural-language descriptions or reference audio without manually programming every oscillator, filter, envelope, effect, and modulation parameter.

## Phase 1 prototype

The repository now includes a hardware-safe Python prototype of the JUNO patch API:

- Strict, versioned JSON validation for a complete JUNO-DS patch
- Lossless preservation of all nine temporary-patch data blocks
- Human-editable patch name and category
- Verified semantic editing for core patch, tone, filter, envelope, and LFO parameters
- Deterministic Roland RQ1/DT1 framing and checksum validation
- `.syx` to JSON and JSON to `.syx` conversion
- Transport-neutral read/write API with an optional Mido hardware adapter
- Explicit confirmation before the CLI writes to the temporary edit buffer
- Standard-library unit and mock-transport tests

The unnamed device parameters remain as validated 7-bit block arrays. This is deliberate: the prototype preserves every byte without claiming semantic parameter offsets that have not yet been verified.

Semantic JSON fields are derived from—and written back into—the lossless blocks. Current coverage includes patch level/tuning/portamento and sound-shaping offsets; tone enable/level/tuning/pan; waveform number; TVF filter type, cutoff, resonance, and envelope; TVA envelope; and LFO1 waveform/depth. Unmapped bytes remain untouched.

### Run the tests

From the repository root:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -v
```

### Install the CLI

For file conversion only:

```powershell
python -m pip install -e .
```

For physical MIDI ports, install the optional adapter:

```powershell
python -m pip install -e ".[midi]"
patchmaker-juno list-ports
```

### File workflow

```powershell
patchmaker-juno syx-to-json current-patch.syx current-patch.json
patchmaker-juno validate current-patch.json
patchmaker-juno json-to-syx current-patch.json current-patch.syx
```

### Hardware workflow

```powershell
patchmaker-juno read current-patch.json `
  --input-port "JUNO-DS" `
  --output-port "JUNO-DS"

patchmaker-juno write current-patch.json `
  --input-port "JUNO-DS" `
  --output-port "JUNO-DS" `
  --confirm-temporary-write
```

`write` targets the temporary edit buffer; it does not store or overwrite a user patch. Port names vary by operating system. The hardware workflow requires a connected JUNO-DS and has not been exercised by the repository's automated tests.

### LLM refinement

Patchmaker uses a provider-neutral planner interface. The included adapter calls an OpenAI-compatible Chat Completions endpoint and asks it for a semantic change plan; the deterministic patch API validates and applies that plan. Raw blocks, SysEx addresses, and device bytes are never sent to or accepted from the model.

Configure the adapter with environment variables. The API key is optional for local endpoints and is intentionally not accepted as a command-line argument:

```powershell
$env:PATCHMAKER_LLM_BASE_URL = "http://localhost:8000/v1"
$env:PATCHMAKER_LLM_MODEL = "your-model-id"
$env:PATCHMAKER_LLM_API_KEY = "your-api-key" # omit when not required

patchmaker-juno refine current-patch.json `
  "Make it darker, soften the attack, and add subtle movement" `
  refined-patch.json
```

Any service that implements the expected `/chat/completions` request and response shape can be substituted by changing the URL and model variables. Automated tests use a fake HTTP transport and never make a paid or external model call.

### Local GUI

For first-time keyboard setup and a safe hardware test sequence, see the [Hardware Quick Start](output/pdf/quickstart.pdf).

Launch the browser interface from the repository environment:

```powershell
patchmaker-juno gui
```

Patchmaker opens `http://127.0.0.1:8765` and keeps all operations on the local machine except the configured LLM request. From the interface you can:

- Start immediately with an automatically loaded neutral patch, then optionally load and validate another patch JSON file
- Configure any OpenAI-compatible endpoint and model
- Paste an API key directly into the session-only web field and test the endpoint, model, and authentication before generating
- Describe and generate a patch variation
- Start with an automatically randomized, editable sound description and generate another with **Randomize prompt**
- Inspect common parameters and all four tones
- Automatically save every successful generation to a persistent local patch library and reopen any earlier version
- Download the refined JSON patch
- Discover MIDI ports, read the current JUNO-DS patch, and send a result to its temporary edit buffer

The model panel can save the API key, endpoint URL, and model ID to a repository-local `.env` file. This plaintext file is Git-ignored and is read automatically on later launches. Saved keys are never returned to browser JavaScript; the GUI reports only whether one is configured. A newly pasted key exists in the browser only until it is saved or the page closes. Hardware writes still require an explicit confirmation dialog and target only the temporary edit buffer.

When testing `openrouter/free`, the GUI pins the exact compatible model returned by the successful test so the generation request does not get routed to a different model with different structured-output behavior. Generation failures remain visible below the prompt with their complete error message.

New browser profiles default to OpenRouter at `https://openrouter.ai/api/v1` with the capability-aware `openrouter/free` model router. You can replace either field with another OpenAI-compatible endpoint or a specific model at any time.

The randomizer uses a JUNO-oriented vocabulary covering sound role, mood, tonal and source character, register, density, filtering, filter and amplifier envelopes, modulation, stereo image, space, tuning, articulation, performance behavior, dynamics, and era/genre. Every dimension maps back to supported semantic patch controls. A descriptor recipe layer translates beginner-friendly words such as “warm,” “plucky,” “lush,” “wide,” and “haunting” into concrete synthesis guidance before the request reaches the model.

### Patch history

Every successful AI generation is automatically written to the local `.patchmaker/patches` library with its full validated patch, timestamp, source prompt, explanation, and parent-version ID. The GUI lists saved generations newest-first; selecting one restores it as the current result and puts its original prompt back into the editor. Creating another variation from a restored patch records the version relationship. Duplicate synth names receive visible version labels, and the × control deletes only the selected saved snapshot after confirmation. The entire `.patchmaker` directory is Git-ignored.

To run without automatically opening a browser, or to use another local port:

```powershell
patchmaker-juno gui --no-browser --port 9000
```

## Core workflows

### Text to patch

Describe the sound you want:

- “Warm dark analog pad with a slow attack”
- “Bright aggressive 1980s synth brass”
- “Soft bell-like electric piano with a long release”
- “Wide detuned synth lead with a little portamento”
- “Make this patch darker and less resonant”

The system translates the description into synthesis decisions, creates a validated JUNO-DS patch, and sends it to the instrument's temporary edit buffer so it can be played immediately. Natural-language refinement is a first-class part of the workflow: generate a patch, play it, request a change, and send the revised patch back to the instrument.

### Audio to patch

Upload a clean synth recording—or select a range and target instrument from a larger recording—and ask the system to create the closest sound the JUNO-DS can produce.

The intended workflow is:

```text
Reference audio
      ↓
Audio and timbre analysis
      ↓
Find suitable JUNO waveforms and starting patches
      ↓
Generate and render a candidate patch
      ↓
Compare it with the reference
      ↓
Modify and repeat
```

The final output should be a real patch that can be loaded into or sent directly to a JUNO-DS.

## Architecture

The AI must **not generate raw Roland SysEx bytes directly**. It should produce an intermediate, human-readable patch representation:

```text
User request
     │
     ▼
AI sound designer
     │
     ▼
JUNO patch JSON
     │
     ▼
Strict parameter validation
     │
     ▼
Deterministic JUNO SysEx encoder
     │
     ▼
Roland JUNO-DS
```

For example:

```json
{
  "name": "Dark Analog Pad",
  "category": "SYNTH_PAD",
  "tones": [
    {
      "enabled": true,
      "wave_group": "INT",
      "wave_number": 423,
      "level": 105,
      "coarse_tune": 0,
      "fine_tune": -7,
      "filter_type": "LPF",
      "cutoff": 72,
      "resonance": 28,
      "amp_attack": 85,
      "amp_decay": 70,
      "amp_sustain": 110,
      "amp_release": 95
    }
  ],
  "mfx": {
    "type": "chorus",
    "parameters": {}
  },
  "chorus": {},
  "reverb": {}
}
```

This separation keeps subjective sound-design decisions in the AI layer while a deterministic layer handles exact addresses, allowed ranges, encoding, checksums, and device communication. It makes the system safer, testable, and easier to develop.

## JUNO-DS communication

The project does not need to reverse-engineer JUNO-DS communication from scratch. The open-source [KnobKraft Orm](https://github.com/christofmuc/KnobKraft-orm) project includes a working JUNO-DS adaptation whose Python implementation understands user-patch and temporary/edit-buffer structures.

The major patch sections include:

```text
Patch Common
Patch Common MFX
Patch Common Chorus
Patch Common Reverb
Patch Common Tone Mix Table

Tone 1
Tone 2
Tone 3
Tone 4
```

KnobKraft's implementation also includes patch-request logic and conversion of program dumps into the JUNO edit buffer with Roland SysEx messages. It should be used as a reference or communication layer instead of unnecessarily rewriting the protocol.

## Text-to-patch design

Given a request such as:

> Give me a dark cinematic pad. Slow attack, very wide, slightly detuned, with some movement but not too bright.

The AI maps language to synthesis concepts:

| Description | Likely synthesis decision |
| --- | --- |
| Dark | Lower low-pass cutoff |
| Slow | Longer amplifier and filter attack |
| Wide | Layered or detuned tones and chorus |
| Movement | LFO modulation or evolving tone layers |
| Not too bright | Restrained filter envelope and high-frequency content |

It then selects suitable JUNO-DS waveforms and parameters. Early versions can improve reliability by starting with a nearby factory patch and applying controlled modifications rather than constructing every sound from zero.

## Audio matching

[CLAP (Contrastive Language-Audio Pretraining)](https://github.com/LAION-AI/CLAP) can provide audio and text embeddings in a shared representation space. A candidate sound can be scored by comparing its embedding with the reference, then combining that result with measurements such as:

- Spectral envelope and centroid
- Brightness and harmonic distribution
- Transient shape, attack, and decay
- Pitch stability
- Noisiness
- Stereo width
- Modulation rate
- Fundamental-to-harmonic ratios

A combined metric will likely be more useful than any single measurement.

### Uploaded songs

A commercial recording may contain drums, bass, vocals, guitars, synths, ambience, and mastering effects. The UI should therefore let the user:

1. Select a precise time range.
2. Optionally isolate a stem.
3. Identify the sound to reproduce.

For example:

```text
Song: example.wav
Target: 00:34.500 → 00:37.200
Instrument: Synth Lead
```

A clean, isolated synth sample will yield substantially better results. Optional stem-separation software can help prepare material from a full mix.

## Automated hardware optimization

An advanced version can make the computer experiment with the physical JUNO-DS:

```text
Reference audio
       ↓
Initial candidate patch
       ↓
Send patch and standardized MIDI notes to JUNO-DS
       ↓
Record the instrument's audio output
       ↓
Compare with the target
       ↓
Change parameters and repeat
```

Candidate parameters include waveform choice, tone combinations and levels, fine tuning, filter cutoff and resonance, filter and amplifier envelopes, LFOs, pitch modulation, chorus, reverb, and MFX.

Possible optimization strategies include evolutionary algorithms, Bayesian optimization, guided random mutations, reinforcement learning, and coarse-to-fine parameter search. This feedback loop can discover useful parameter combinations that an LLM might not predict directly.

## JUNO sound database

A searchable database built from the instrument itself can provide strong starting points:

```text
Select factory patch
       ↓
Read parameters via SysEx
       ↓
Store the human-readable patch model
       ↓
Play and record a standardized MIDI sequence
       ↓
Calculate an audio embedding
       ↓
Generate a description and store the record
```

Each record could contain:

- Patch name and category
- JUNO parameters and waveforms
- Effects
- Recorded audio
- Audio embedding
- AI-generated description

For a request such as “dark vintage analog brass,” the system could retrieve the nearest factory or previously generated patches, choose the best starting point, and then modify it.

## Proposed application

```text
┌────────────────────────────────────────────┐
│          JUNO-DS AI Patch Creator          │
├────────────────────────────────────────────┤
│ Describe a sound:                          │
│ [ Warm haunting analog pad, slow attack ]  │
│                          [ Generate ]       │
│                                            │
│ Or choose reference audio:                 │
│ [ Upload WAV/MP3 ]                         │
│ Target: [ 00:34.2 ] → [ 00:37.8 ]          │
│                       [ Match Sound ]       │
├────────────────────────────────────────────┤
│ Generated patch: Dark Analog Pad 01        │
│ Starting patch: PRST 443 Analog Pad         │
│ Similarity: 84%                            │
│                                            │
│ [ Send to JUNO ] [ Save ] [ Variation ]    │
│                                            │
│ Refine:                                    │
│ [ Make it darker and add more movement ]   │
│                            [ Update ]       │
└────────────────────────────────────────────┘
```

## Development roadmap

### Phase 1 — JUNO patch API

Build the foundation:

- Read the current JUNO patch: JUNO → JSON
- Write a temporary patch: JSON → JUNO
- Save and load JSON patch files
- Strictly validate all patch values

### Phase 2 — Text to patch

Add an LLM-driven sound-design layer that translates descriptions into synthesis concepts and validated JUNO parameters. Initially, retrieve and modify existing factory patches.

### Phase 3 — JUNO patch database

Catalog factory patches, parameters, standardized recordings, embeddings, and descriptions to create a searchable retrieval and training dataset.

### Phase 4 — Audio matching

Analyze uploaded audio, retrieve the nearest JUNO patches, and generate controlled parameter modifications.

### Phase 5 — Closed-loop optimization

Connect the JUNO's audio output to the computer so the system can generate, listen, compare, modify, and repeat until it finds the closest patch the hardware can produce.

## End goal

The finished product should support interactions such as:

> Give me a huge 1980s synth brass patch.

> Make this sound softer and more atmospheric.

> [Upload audio] Make the closest sound the JUNO-DS can produce.

The necessary pieces already exist independently: JUNO-DS SysEx communication in projects such as KnobKraft, language/audio embedding models such as CLAP, and commercial text/audio-to-preset workflows for software synthesizers. The primary work is integrating those concepts into a reliable, JUNO-DS-specific sound-design and optimization system.
