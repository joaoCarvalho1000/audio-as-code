# Orchestra prototypes

The catalog has 70 playable entries. The original 11 voices remain available, and the added models provide distinct generated sound behaviors for the other catalog instruments. Every excitation, partial, noise burst, and resonance comes from code. None of the parameters are fitted to a recorded instrument.

Generate 210 listening previews with:

```sh
uv run python examples/instrument_browser.py
```

Open `output/instruments/index.html` locally. Each entry has a [famous-music excerpt](music-demos.md), a single note/hit, and a phrase, plus the source JSON, approximate MIDI, and stereo WAV. Preview pitches follow useful instrument registers; a phrase is therefore not always the same concert pitch across instruments. All previews now render at 44100 Hz. Music demos include solos, five small ensembles, and nine percussion features with accompaniment.

## What is modeled

| Voices | Implemented behavior | Boundary |
| --- | --- | --- |
| Electric/bass guitar, harp, ukulele, banjo, harpsichord | Pluck-position-dependent string modes, stiffness, two weakly detuned polarizations, upper-mode damping; pickups or driven body filters | No amplifier circuit, fret interaction, feedback-coupled resonator, or sympathetic-string solver |
| Piano | Finite hammer contact, stiff-string modes, narrow unison detuning with shared resistive bridge damping at and above 65 Hz, generated hammer noise, driven soundboard coloration and binary pedal gates | No half-pedal, full soundboard, hammer/string feedback, or sympathetic resonance |
| Violin, viola, cello, double bass | Harmonic spectra with frequency-based excitation bandwidth, complex body-band responses, evolving bow pressure/noise, delayed irregular vibrato and progressive partial onset | Spectral bowed-tone approximations; no stick/slip bow friction; no pizzicato switch |
| Flute, clarinet, saxophone, oboe, bassoon | Different harmonic structures/formants, evolving breath noise, pressure variation, onset evolution and delayed vibrato | Source/filter approximations; no nonlinear jet/reed/bore coupling |
| Trumpet, trombone, French horn, tuba | Different harmonic/formant shapes, onset pitch settling and spectral bloom; brightness follows velocity and pressure | Source/filter approximations; no self-oscillating lip or tube-geometry solver |
| Organ | Sustained harmonic registration and generated onset chiff | Fixed registration; no airflow or stop-selection model |
| Electric piano, xylophone, vibraphone, glockenspiel | Finite strike contact, instrument-specific mode ratios, weak metal-mode splitting and damping; electric-piano/vibraphone amplitude tremolo | Designed tine/bar approximations, not measured resonances or pickup electronics |
| Toms, congas, bongos, timpani | Modal drumheads, generated strikes, transient pitch relaxation and driven shell/kettle coloration | One articulation each; no spatial head or feedback cavity coupling |
| Cymbal, tambourine | Denser seeded inharmonic metal resonances, broadband wash and generated collision onsets | Plate/jingle-inspired modes; no nonlinear plate solver |
| Synthesizer | Three detuned finite-harmonic oscillators and a decaying brightness envelope | Fixed topology, no arbitrary patch graph |
| Theremin | Sustained oscillator harmonics, vibrato, optional per-note pitch glide | No continuous gesture/automation stream |
| Drum machine | Score-note routing to eight generated percussion models | Kit abstraction, not a separate sampled drum sound |
| Mandolin | Paired stiff-string modes, shared bridge stiffness, projected damping, generated pick noise and driven body response | No fret contact, sympathetic courses or calibrated string/body solver |
| Kalimba, celesta | Distinct lamella/bar modes, finite contact excitation and designed driven resonators | No measured geometry, damper mechanics or sympathetic resonances |
| Recorder | Band-limited reconstruction of a prescribed nonlinear jet spectrum, bore coloration, generated breath and pressure variation | No coupled jet/bore solver, fingering or overblowing |

Modal synthesis sums independently decaying resonances. Stiff strings stretch their overtone spacing; the piano model normalizes its first mode to the requested note. These general mechanisms follow established signal models; the profiles and coefficients here are designed approximations. See Julius O. Smith's [modal signal models](https://www.dsprelated.com/freebooks/pasp/Introduction_Physical_Signal_Models.html) and [stiff piano strings](https://www.dsprelated.com/freebooks/pasp/Stiff_Piano_Strings.html).

The clarinet profile emphasizes odd harmonics while retaining weaker even components, consistent with a simplified cylindrical-bore signature. It does not simulate the pressure/reed feedback described in Smith's [single-reed model](https://dsprelated.com/freebooks/pasp/Digital_Waveguide_Single_Reed_Implementation.html); the instrument-specific acoustic discussion at [UNSW](https://www.phys.unsw.edu.au/music/clarinet/G4.html) explains why register and bore resonances matter.

## Controls

Piano, electric piano, xylophone, vibraphone and glockenspiel drive their modes with an analytically integrated, finite raised-cosine strike (also used by [marimba](synthesis.md)). The force starts and ends at zero, has unit area, and lets each resonance ring freely after contact; it alters excitation amplitude and phase without retuning the modal frequency. Piano's unison strings share the force from rest. At and above 65 Hz, intrinsic and shared bridge damping produce different decay rates for common and differential string motion; the lower single-string register retains its prescribed two-component decay. Instrument-specific contact lengths distinguish soft mallets from hard bar strikes. Brightness/velocity shorten contact, with a pitch-relative cap preserving high-register fundamentals. There is no new score control or nonlinear hammer/rebound solver. Bell and clavinet now use this finite contact too, with shorter strike profiles; drumhead attacks retain their pitch-relaxation model. See the [piano and bowed-string models](synthesis.md#piano-and-bowed-strings) and the four [extended instrument models](extended-instruments.md) for implementation details and limits.

Only pass controls listed by the instrument's `tone_controls`. The model rejects unsupported settings. For optional fields, `null` selects the catalog/default profile value; brightness is a required finite number when present.

| Control | Range | Meaning |
| --- | --- | --- |
| `brightness` | 0–1; default 0.5 | Spectral balance/excitation; also influenced by note velocity |
| `decay_seconds` | 0.1–20 | Natural decay parameter for struck/plucked/resonant voices |
| `pluck_position` | 0.05–0.45 | Fraction of string length selecting excited modes |
| `breath` | 0–1 | Generated breath/chiff level on supported winds/organ |
| `vibrato_depth_cents` | 0–100 | Pitch variation depth on supported held voices |
| `vibrato_rate_hz` | 0.1–12 | Vibrato cycles per second; set nonzero depth to hear it |
| `glide_semitones` | -24–24 | Theremin's initial offset, settling exponentially toward the scored pitch |
| `detune_cents` | 0–40 | Synthesizer's symmetric side-oscillator offset; mandolin's total uncoupled string-pair separation |

The catalog exposes per-instrument defaults; the browser displays those used in each preview. Decay is not universally an exact measured T60: individual modes and register-dependent damping alter it. By default, note duration contains the release gate. A six-second natural decay on a half-second note does not create a six-second tail. Use track/note `release_seconds` to extend the gate after note-off; this extends audio only, not MIDI note duration. Piano also supports [binary pedal events](piano-sustain.md) and MIDI CC64. Other instruments have no shared pedal or articulation state.

The 0.3.0 polish makes generated noise independent of requested note length, using causal generated filters with deterministic prehistory. Normal bowed-string and wind notes now share the separate harmonic/noise release laws of articulated notes. Bell and clavinet use finite strike contact; electronic hats and ride have evolving decay spectra. Earlier refinements added seeded pressure and onset variation, and velocity-sensitive kick/snare/hat excitation. Analytic body responses are sums of damped modes generated in code and driven by the string or membrane signal; they are not measured impulse responses and do not feed energy back into the source. Partial and noise-sideband tapers reduce aliasing near Nyquist. These algorithm changes preserve score IDs and deterministic rendering within a fixed build, but intentionally change the output from earlier builds.

```python
from audio_as_code import Note, Song, Tone, Track, render

song = Song(
    bpm=80,
    beats=8,
    tracks=[
        Track(
            name="Cello",
            instrument="cello",
            tone=Tone(brightness=0.4, vibrato_depth_cents=12, vibrato_rate_hz=4.7),
            notes=[Note(pitch="C3", duration=3.8), Note(pitch="G3", start=4, duration=4)],
        ),
        Track(
            name="Piano",
            instrument="piano",
            tone=Tone(brightness=0.65, decay_seconds=4),
            notes=[Note(pitch=pitch, duration=4) for pitch in ["C4", "E4", "G4"]],
        ),
    ],
)
render(song, "output/cello-and-piano.wav")
```

## Generated kit and MIDI

For `drum_machine`, the score's note pitch selects a voice:

| MIDI pitch | Generated voice |
| --- | --- |
| 36 | Kick |
| 38 | Snare |
| 42 | Closed hi-hat |
| 45 | Tom |
| 49 | Cymbal |
| 54 | Tambourine |
| 60 | Bongo |
| 64 | Conga |

Other pitches are rejected. Kit notes use the same voice generation and seed path as individual drums. Individual drum IDs ignore scored pitch and use fixed tuning/mappings; timpani is a pitched melodic instrument. Use explicit note durations for ringing percussion.

MIDI preserves the kit's selected pitches on channel 10. A kit and an individual drum cannot overlap the same MIDI pitch on that shared channel; export rejects the ambiguity. Audio rendering may layer them. Melodic mappings are approximate General MIDI programs: for example ukulele uses nylon guitar and theremin uses a synth-lead program. MIDI cannot reproduce these synthesis algorithms, controls, or exact timbres.

## Validation and remaining fidelity work

Automated checks cover rendering across all entries, sample-rate/register/control extremes, note endpoints, repeatability, tuning, damping, sustained energy, differences between woodwind spectra, control validation and kit MIDI routing. The browser checks actual file playback and export links. These establish numerical and transport behavior, not listening quality.

The coefficients need human audition across registers and dynamics. More realistic performance will require note-to-note articulation, coupling, physically driven excitation, and expression curves; adding catalog coverage does not replace that work.
