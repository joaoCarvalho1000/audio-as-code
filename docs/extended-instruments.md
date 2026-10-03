# Mandolin, kalimba, celesta and recorder

These four playable prototypes live in `src/audio_as_code/extended.py`. They use
generated excitation, analytical modes and designed resonator responses. There
are no recordings, SoundFonts, sample libraries, measured impulse responses, or
fallback voices. Availability means that the model renders; it does not certify
perceptual realism or calibration to a particular instrument.

| Score ID | Family / engine | Useful starting register (sounding pitch) | Default natural decay | MIDI program (zero-based) |
| --- | --- | --- | --- | --- |
| `mandolin` | plucked_strings / string | G3–E6 | 1.8 seconds | 25: steel-string guitar approximation |
| `kalimba` | pitched_percussion / modal | C4–C6 | 2.0 seconds | 108: kalimba |
| `celesta` | keyboards / modal | C4–C7 | 3.4 seconds | 8: celesta |
| `recorder` | woodwinds / air_column | C5–C7 | sustained | 74: recorder |

The register suggestions are composition starting points, not measured realism
ranges or new schema limits. MIDI 0–127 remains accepted. Pitches are sounding
pitches: there is no automatic celesta octave transposition. High partials fade
before Nyquist; pitches at or above Nyquist are silent. MIDI uses the receiving
synthesizer and does not reproduce these models or tone controls. Program numbers
follow the zero-based [Music Encoding Initiative MIDI-name table](https://music-encoding.org/guidelines/dev/mei-all/data-types/data.MIDINAMES.html).
The mandolin mapping is intentionally a GM steel-string guitar approximation.

## Supported controls

| Instrument | Controls and defaults |
| --- | --- |
| mandolin | `brightness=0.5`, `decay_seconds=1.8`, `pluck_position=0.18`, `detune_cents=4` |
| kalimba | `brightness=0.5`, `decay_seconds=2.0` |
| celesta | `brightness=0.5`, `decay_seconds=3.4` |
| recorder | `brightness=0.5`, `breath=0.08`, `vibrato_depth_cents=0`, `vibrato_rate_hz=5` |

Controls retain the common score limits: brightness and breath 0–1, decay
0.1–20 seconds, pluck position 0.05–0.45, detune 0–40 cents, vibrato depth
0–100 cents and rate 0.1–12 Hz. Unsupported controls are rejected. The catalog
is authoritative: `aac instruments --family woodwinds`, for example, includes
the recorder's supported controls and actual defaults.

Velocity scales note level in the renderer and changes excitation brightness in
these models: the effective brightness is `0.75 * brightness + 0.25 * velocity`.
Brightness affects upper-mode excitation, contact duration, or the recorder's
jet spectrum. Decay controls natural modal damping; it does not override note
duration. These values are damping scales, not promises that every component
reaches a particular level at that time. Higher modes generally decay faster
than the fundamental.

The renderer still supplies attack/release gates. A short written note can end
before the natural decay. To let a note ring after note-off, use the existing
track/note `release_seconds`, which can extend the WAV and is omitted from MIDI.
There is no physical damper, sustain pedal, legato or fingering state.

## Mandolin: two strings and a shared bridge

Each stiff-string partial is represented by two modes. A symmetric two-by-two
stiffness matrix combines the two nominal string frequencies and a small common
bridge restoring term. Its eigenvectors determine how a pick excites each mode
and how strongly it drives the bridge. Bridge participation changes each mode's
decay, producing a bright initial component and a slower component. Generated
pick noise and a short, causally driven body response complete the voice.

`detune_cents` is the **total separation of the uncoupled strings**, not the
offset of each string. A value of 4 starts the strings at −2 and +2 cents. Shared
bridge stiffness slightly changes that split, including a small residual split
at zero detune. The final mode pair is recentered geometrically on each written
harmonic frequency. Pluck position changes modal excitation; it is not a pan or
stereo-width control.

This design is motivated by paired-string symmetry and bridge-mediated energy
loss described in Jim Woodhouse's [multiple strings and double decays](https://euphonics.org/7-3-multiple-strings-and-double-decays/).
Our stiffness, damping and body coefficients are designed values. We project
damping onto individual normal modes, omit off-diagonal dissipative coupling,
and use a one-way body response. This is not a calibrated coupled string/bridge/
soundboard solver; it has no fret contact, sympathetic courses, tremolo picking,
or instrument-specific radiation geometry.

## Kalimba: lamella modes and a wooden-box response

The vibrating tine uses the first four ideal fixed-free beam roots. Squared root
ratios give frequencies approximately `1, 6.267, 17.548, 34.386` times the written
fundamental. A finite thumb-contact pulse excites the modes; upper modes lose
energy quickly. A short generated contact transient and analytically generated
wooden-box modes add coloration. The model is driven by the note excitation,
not by a prerecorded hit.

The beam relation and boundary conditions come from TU Graz's
[cantilever-beam derivation](https://lampz.tugraz.at/~hadley/memm/mechanics/cbeam.php).
Lamellaphones are plucked idiophones; Grinnell College's
[kangombio collection description](https://omeka-s.grinnell.edu/s/MusicalInstruments/item/3447)
documents the flex-and-release mechanism. The catalog's practical
`pitched_percussion` family does not imply that the instrument is played with a
hammer. Our finite pulse is a prescribed thumb-contact approximation.

This is an equal-tempered generic kalimba-like voice, not a reconstruction of a
specific African instrument, tuning system or playing tradition. Real tine
shape, mounting, nonlinear contact, attached buzzers, resonator-hole gestures,
and interaction between tines are outside the model. A uniform beam and a few
designed cavity modes cannot reproduce those details.

## Celesta: felt hammer, metal bar and tuned resonator

The celesta uses four ideal free-free bending modes, approximately
`1, 2.7565, 5.4039, 8.9329` times the fundamental. A finite raised-cosine hammer
force controls the attack spectrum; brighter or harder excitation shortens
contact and excites more upper-mode energy. The bar drives a generated
pitch-matched resonator. The longer contact, mode damping and driven box make
this a separate implementation from the glockenspiel voice.

Free-free bar modes follow Woodhouse's [beam derivation](https://euphonics.org/3-2-1-bending-beams-and-free-free-modes/).
Yamaha documents the real celesta's [sound bars and mounting](https://www.yamaha.com/en/musical_instrument_guide/celesta/mechanism/mechanism002.html)
and [hammer/resonator arrangements](https://www.yamaha.com/en/musical_instrument_guide/celesta/mechanism/mechanism004.html).
Those sources motivate the mechanisms; they do not provide our damping,
amplitudes or contact times. Actual bars may have weights and nonuniform
geometry. This prototype does not simulate those geometries, hammer rebound,
keyboard mechanics, sympathetic bars, the damper mechanism or a pedal.

## Recorder: prescribed jet spectrum and bore filtering

The recorder computes the Fourier coefficients of an asymmetric saturating jet
waveform on a high-resolution phase grid. It then reconstructs only audible
harmonics, with a designed bore/radiation roll-off, harmonic onset buildup,
small seeded pressure variation, and a brief pitch-settling transient. Breath
adds spectrally shaped generated noise with an onset envelope. Optional vibrato
ramps in after the onset; changing rate at zero depth has no audible effect.

The source/filter approach is motivated by the oscillating jet and air-column
resonance shown in Yamaha's [recorder airflow research](https://www.yamaha.com/en/tech-design/research/technologies/recorder-simulation/).
The saturated source, filter coefficients and transient parameters here are
designed approximations. This is a soprano-like spectrum, not a nonlinear jet
delay model or an acoustic simulation of a particular recorder. It does not
solve bore geometry, tone-hole impedances, fingering, pressure-driven register
changes, overblowing or tongue articulation. Changing pitch simply retunes the
prescribed source and filter. The model does not reuse the flute profile.

## Try a short phrase

From an installed source checkout:

```python
from audio_as_code import Note, Song, Tone, Track, inspect_score, render

song = Song(
    title="Celesta question",
    bpm=100,
    beats=4,
    seed=27,
    tracks=[
        Track(
            name="Celesta",
            instrument="celesta",
            gain=0.55,
            tone=Tone(brightness=0.6, decay_seconds=3.4),
            notes=[
                Note(pitch=pitch, start=i, duration=0.8)
                for i, pitch in enumerate(["E5", "G5", "F#5", "E5"])
            ],
        )
    ],
)
assert inspect_score(song)["readiness"]["render"]["ready"]
song.save("output/celesta-question/score.json")
report = render(song, "output/celesta-question/song.wav")
print(report["wav"])
```

Use a fresh output folder when comparing versions. `aac inspect` can check MIDI
readiness before export. The new voices use melodic channels, including kalimba.

## What the checks establish

Focused tests cover tuning across the suggested registers; mandolin pair
separation and pitch center; lamella/bar inharmonic modes; control and velocity
changes after removing level differences; seeded repeatability; sustained
recorder behavior; short buffers; upper-mode alias rejection; and finite bounded
output across supported sample rates, extreme pitches and control limits.
Integration checks cover actual score rendering, endpoint gates and MIDI programs.

These are numerical checks. They do not establish recognizability, instrument
realism, performer response, mix balance or musical quality. Audition the actual
WAV before making those judgments. Rendered notes are deterministic for an
unchanged score and fixed runtime/platform; no cross-platform byte guarantee is
implied.
