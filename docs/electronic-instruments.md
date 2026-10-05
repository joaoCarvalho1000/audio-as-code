# Electronic instruments and dance arrangements

Version 0.3.0 adds these voices and effects, bringing the catalog to 70 playable
entries. Inspect the installed catalog when using an older version.
All instrument sources are generated
from equations, including the electronic drums. There are no recordings,
SoundFonts, sampled breakbeats or measured impulse responses.

## Choose a voice

| Use | IDs | Model and useful controls |
| --- | --- | --- |
| Disco and funk | `clavinet`, `disco_bass`, `string_machine` | Clavinet uses finite hammer contact and damped strings with dual pickup weighting. Synth bass has a decaying saw/filter envelope. The ensemble uses five detuned pulse spectra with slow width modulation. |
| Techno | `acid_bass`, `sync_lead`, `fm_percussion` | Resonant saw spectrum with accent, a sweeping harmonic formant that approximates hard sync, and inharmonic two-operator percussion. |
| Trance | `supersaw`, `trance_pluck`, `fm_bell`, `wavetable_pad` | Seven detuned saws, a resonant pluck, decaying phase modulation, and evolving analytic harmonic tables. |
| Drum & bass | `reese_bass`, `fm_bass`, `hoover`, `sub_bass` | Detuned saw beating, a moving FM index, detuned PWM with a sub-octave, and a sine foundation with optional second harmonic. |
| Electronic kit | `kick_808`, `kick_909`, `clap`, `electronic_snare`, `metal_hat`, `open_hat`, `electronic_ride` | Designed oscillator/noise hits. The kick names describe familiar sound families, not replicas of proprietary circuits. |

Discover each voice's supported controls rather than sending every tone field:

```sh
uv run aac instruments --family electronic
uv run aac instruments --family percussion
uv run aac schema
```

The new drum voices are individual tracks, so each hit type has its own tuning,
decay and gain. The original `drum_machine` pitch map is unchanged. Drum note
pitch does not retune these new hits: use `tuning_semitones` where advertised.
`clap` has no pitch control. Set open-hat note durations to end at the desired
choke; there is no automatic choke group across tracks.

Metallic hats and ride have frequency-dependent damping: their upper partials
and noise fade sooner than the lower ringing modes. The parameters are designed,
not fitted to particular hardware. Clavinet's finite contact similarly shapes
its attack spectrum without an electromechanical or nonlinear string solver.

## Compose an acid phrase

```python
from audio_as_code import Distortion, Note, Song, Tone, Track, render

song = Song(
    title="Acid phrase",
    bpm=132,
    beats=4,
    seed=12,
    tracks=[
        Track(
            name="Acid",
            instrument="acid_bass",
            gain=0.5,
            tone=Tone(
                cutoff_hz=500, resonance=0.7, filter_env_octaves=3, filter_decay_seconds=0.15
            ),
            effects=[Distortion(drive=2, mix=0.2)],
            release_seconds=0.06,
            notes=[
                Note(pitch="A1", start=0, duration=0.4, articulation="accented"),
                Note(pitch="A2", start=0.5, duration=0.35),
                Note(pitch="G2", start=1, duration=0.4),
                Note(pitch="E2", start=1.75, duration=0.2),
                Note(pitch="A1", start=2, duration=1.5, articulation="accented"),
            ],
        )
    ],
)
render(song, "output/acid.wav")
```

For an explicit note-local slide, set `Tone(glide_semitones=-12,
glide_seconds=0.08)`. The note starts one octave below its written pitch and
approaches it exponentially in frequency. The time value is a time constant,
not an exact time to the target. This retriggers independently on every note;
it does not infer the previous pitch, preserve phase between notes, or provide
monophonic legato. Use separate tracks when different notes need different
tone settings. Release tails can overlap; keep bass gates deliberate.

## Tone controls

All controls are per track. `brightness` defaults to 0.5; other omitted controls
use the instrument's advertised defaults or the documented engine default below.

| Control | Range | Meaning |
| --- | --- | --- |
| `cutoff_hz` | 20–20000 | Base spectral low-pass cutoff; instantaneous cutoff clamps to 44% of sample rate. Omitted: instrument default, otherwise `500 + 6500 * effective_brightness²`. |
| `resonance` | 0–1 | Spectral resonance; omitted 0.15 unless catalog overrides. |
| `filter_env_octaves` | 0–6 | Initial cutoff rise in octaves, decaying toward the base; omitted 2 unless catalog overrides. |
| `filter_decay_seconds` | 0.01–10 | Envelope time constant; omitted 0.25 unless catalog overrides. |
| `detune_cents` | 0–40 | Outer unison offset in each direction. Zero removes frequency beating but retains seeded oscillator phases. |
| `glide_semitones` | −24–24 | Initial offset relative to the written pitch; omitted zero. |
| `glide_seconds` | 0.005–2 | Exponential glide time constant; omitted 0.08. Has no effect with zero glide. |
| `fm_index` | 0–12 | Modulation depth, further shaped by brightness/velocity and the voice envelope. |
| `fm_ratio` | 0.25–8 | Modulator/carrier frequency ratio. Integer ratios produce harmonic sidebands; other values can sound inharmonic. |
| `modulation_rate_hz` | 0.05–20 | FM growl's index-motion rate, independent of score tempo. |
| `tuning_semitones` | −24–24 | Electronic drum oscillator tuning; omitted zero. |
| `decay_seconds` | 0.1–20 | Natural amplitude decay where advertised; does not extend written gates. |

Brightness changes the harmonic slope of the subtractive-style voices, not only
their volume. Velocity contributes to brightness before its normal mix-level
scaling. Envelopes and detuning use bounded partials with a Nyquist shoulder.
FM uses four-times oversampling and a windowed-sinc decimator; a bandwidth guard
reduces modulation depth at high pitches. High notes can consequently lose
character. These measures reduce aliasing; rapid modulation is not perfectly
band-limited. There is no claim of zero aliasing or perceptual realism.

The saw/PWM voices apply a moving low-pass magnitude to each partial. They do
not solve a nonlinear ladder filter. `sync_lead` is a spectral approximation,
and `wavetable_pad` generates its own evolving Fourier tables; it does not load
arbitrary wavetables. The source is mono. Use chorus or separately panned tracks
to make a stereo ensemble.

## Funk performance options

`bass_guitar` accepts `slap`, `pop` and `muted`. `electric_guitar` accepts `muted`.
These are note or track articulations, with the existing note-over-track
inheritance rule. Slap/pop add generated fret/contact noise and upper-string
excitation to the modal bass. Muting shortens the source decay and darkens it;
it does not change written note times. These are designed gestures, not a
nonlinear finger/string/fret collision solver. Unspecified articulation selects
the default playing gesture. MIDI omits all these gestures.

## Effects for electronic arrangements

The existing track/master `effects` list accepts these additional types in
order, up to four effects per chain. They are Pydantic objects in Python and
tagged objects such as `{"type": "chorus", "mix": 0.3}` in JSON.

| Python class / JSON type | Controls and defaults | Behavior |
| --- | --- | --- |
| `Filter` / `filter` | `mode="lowpass"` (also `highpass`, `bandpass`), `cutoff_hz=2000`, `resonance=0.2`, `end_cutoff_hz=None`, `sweep_seconds=1`, `mix=1` | Causal state-variable filter. Optional logarithmic whole-track/master sweep starts at song time zero, then holds its destination. Cutoff 30–20000 Hz, resonance 0–1, sweep 0.01–300 seconds. |
| `Distortion` / `distortion` | `drive=2` (1–20), `mix=0.5` | Symmetric tanh saturation with four-times oversampling, sinc reconstruction and low-pass decimation. Drive 1 still saturates; use mix 0 for bypass. It is not a limiter and filtering can overshoot. |
| `Chorus` / `chorus` | `rate_hz=0.7` (0.05–8), `depth_ms=3` (0–10), `delay_ms=18` (11–40), `mix=0.35` | Stereo fractional delay with offset modulation phases, no feedback. |
| `Phaser` / `phaser` | `rate_hz=0.4` (0.05–8), `depth=0.7` (0–1), `mix=0.5` | Four moving first-order all-pass stages. No feedback. |
| `Tremolo` / `tremolo` | `period_beats=0.5` (0.125–32), `depth=0.7`, `shape="sine"` (also `gate`), `mix=1` | Smooth tempo-synced gain modulation; phase follows the tempo map and continues into tails. Gate edges are smoothed. |
| `Ducker` / `ducker` | required `trigger_beats`, `depth=0.75`, `attack_seconds=0.005`, `release_seconds=0.18`, `mix=1` | Scheduled gain dips for kick-driven pumping. This is an envelope, not an audio-detecting sidechain compressor. |

All mixes/depths are 0–1. Ducker triggers are strictly increasing, before the
song ends, at most 4096. Attack is 0.001–0.1 seconds and recovery 0.01–2 seconds.
For a four-on-the-floor groove, pass the kick onsets as `trigger_beats` on the
bass/pad track. Overlapping dips choose the deeper envelope. A dip starts at its
trigger and reaches maximum depth after the attack; there is no lookahead.

Filter/chorus/phaser tails are conservatively included in render duration.
Modulation effects operate on full track buffers and can cost more than plain
synthesis. MIDI exports notes and tempo, not these effects or tone controls.
The filter implementation follows the trapezoidal state-variable derivation in
[Andrew Simper's Cytomic paper](https://cytomic.com/files/dsp/SvfLinearTrapOptimised2.pdf).

## Listen and edit

```sh
uv run --extra loudness python examples/electronic_music.py
```

Open `output/electronic-music/index.html`. It contains the complete original
16-bar hymn edition of “Ode to Joy”, four AI-written dance arrangements,
21 dry voice auditions and bass/guitar gesture comparisons. The hymn edition
is not Beethoven's entire Ninth Symphony. The four source parts preserve their
written rhythm and duration; pitches can shift by octaves. Added drum patterns
are original. Edition credits and source links are included on the page.

Each entry includes WAV, MIDI and editable JSON. The examples target −18 LUFS
with a −1.5 dBFS **sample**-peak ceiling; transients may prevent reaching the
loudness target. See `measurements.json` for actual gains/results. This is not
a true-peak mastering limiter. With core dependencies only, use `--no-loudness`.
Use a separate output folder with `--only trance` to iterate on one arrangement.
Use `--html-only` to update the local listening page from existing renders
without regenerating the audio or changing its measurements.

Tune the music by listening to low-end balance, attacks, note endings, beating,
stereo width, resonant sweeps and loudness between examples. Tests cover stable
output, tuning, explicit control behavior, exports, timing and compatibility.
They cannot establish that an instrument sounds convincing to a listener.
