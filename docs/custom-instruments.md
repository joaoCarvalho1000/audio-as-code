# User-defined procedural instruments

This source revision adds song-local patches. Published Audio as Code 0.4.0 does
not have this API. Inspect your installed schema and use this source revision
until a release includes it. The built-in catalog still contains 70 voices.

Patches are portable data. They contain generated oscillators, noise, damped modes
and two-operator phase modulation, with envelopes and an optional filter. They do
not load recordings, SoundFonts, wavetables, impulse responses or executable code.

```python
from audio_as_code import (
    CustomInstrument,
    Delay,
    Envelope,
    FMLayer,
    Note,
    OscillatorLayer,
    PatchFilter,
    Song,
    Track,
    render,
)

glass = CustomInstrument(
    name="Glass pad",
    layers=[
        OscillatorLayer(waveform="triangle", gain=0.3),
        FMLayer(
            gain=0.2,
            ratio=2.01,
            index=2.5,
            envelope=Envelope(attack_seconds=0.02, sustain=0.5, release_seconds=0.4),
        ),
    ],
    filter=PatchFilter(cutoff_hz=4000),
    midi_program=89,
)
song = Song(
    beats=4,
    seed=37,
    custom_instruments={"custom:glass_pad": glass},
    tracks=[
        Track(
            name="Glass",
            instrument="custom:glass_pad",
            effects=[Delay(mix=0.2)],
            notes=[Note(pitch="A4", duration=3)],
        )
    ],
)
song.save("output/glass.json")
render(song, "output/glass.wav")
```

The corresponding JSON fields use the same names:

```json
{
  "beats": 4,
  "seed": 37,
  "custom_instruments": {
    "custom:glass": {
      "name": "Glass",
      "layers": [
        {"type": "oscillator", "waveform": "triangle", "gain": 0.3},
        {"type": "modal", "gain": 0.2, "partials": [
          {"ratio": 1, "amplitude": 1, "decay_seconds": 1.5},
          {"ratio": 2.7, "amplitude": 0.2, "decay_seconds": 0.4}
        ]}
      ]
    }
  },
  "tracks": [{
    "name": "Glass", "instrument": "custom:glass",
    "notes": [{"pitch": "A4", "start": 0, "duration": 3}]
  }]
}
```

## Patch contract

Names match `custom:[a-z][a-z0-9_]{0,63}`. Definitions belong to the song, not a
global registry. A track can be constructed before the song; song validation
requires every referenced custom name to exist. Unknown built-in IDs and planned
instruments still fail validation. Definitions are immutable and serialize with
`Song.save()` and Pydantic's normal dump methods.

There are at most 64 definitions, eight layers per patch, and 64 partials per
modal layer. All numeric controls are finite. Unknown fields are rejected.

| Layer | Parameters beyond `gain` and `envelope` |
| --- | --- |
| `OscillatorLayer`, `oscillator` | `waveform`: sine (default), triangle, saw or pulse; `pulse_width` 0.05 to 0.95, default 0.5, used only by pulse |
| `NoiseLayer`, `noise` | Seeded uniform white noise; no pitch control |
| `ModalLayer`, `modal` | Required `partials`: frequency `ratio` 0.125 to 64, `amplitude` 0 to 1, exponential `decay_seconds` 0.001 to 20 |
| `FMLayer`, `fm` | `ratio` 0.25 to 8 (default 2), `index` 0 to 12 (default 2), exponential `index_decay_seconds` 0.001 to 20 (default 1) |

Pitched layers also accept `tuning_semitones`, -48 to 48, default zero, relative
to equal-tempered note pitch (A4 = 440 Hz). Layer gain defaults to 0.5 and accepts
0 to 1. Gains add directly; there is no per-note normalization. Ordinary note
velocity scales amplitude after synthesis. Oscillator starting phases and noise
are seeded from the song, track name, note index and layer index.

`Envelope` has linear attack and decay, a sustain level, and linear release from
the level at note-off. Attack/decay range from 0.0001 to 10 seconds, defaults 0.005
and 0.1. Sustain is 0 to 1, default 0.8. Release is 0 to 10 seconds, default 0.1.
The longest layer release determines the patch's tail. A note's explicit
`release_seconds` overrides all layers, including zero. Otherwise a positive
track release overrides them; zero track release uses each layer's release.
Zero release uses a short fade inside the gate. Release/effect tails count toward
the existing 300-second render limit.

`PatchFilter` applies the existing state-variable filter to the summed note:
`mode` lowpass/highpass/bandpass, `cutoff_hz` 30 to 20000 (default 2000), and
`resonance` 0 to 1 (default 0.2). Cutoff clamps to 44% of sample rate. The filter
is contained within the note's release, with a final short fade; it adds no extra
tail. Custom patches reject `Tone`, articulations and pedal events.

## Effects, discovery and interchange

Custom voices use the ordinary gain, pan, automation and effect pipeline. Delay,
Reverb, Filter, Distortion, Chorus, Phaser, Tremolo and Ducker work at track and
master level, with the existing order, limits and tails. Ducker remains a
scheduled envelope, not an audio sidechain. Optional mastering also works on
custom mixes; see [production output](production-output.md).

Use `aac instruments --score output/glass.json` or
`instrument_catalog(custom_instruments=song.custom_instruments)`. The same keyword
works with `list_instruments` and `get_instrument`. Custom entries have
`origin="user_defined"`; built-ins have `origin="builtin"`. A modal-only patch is
in the modal engine and pitched-percussion family; other patches use electronic.
Availability means the patch can render, not that its sound has been calibrated.

MIDI requires an explicit `midi_program` from 0 to 127 on every used custom
definition. Inspection reports an export blocker without it. With it, MIDI carries
notes and an approximate program selection, never the custom synthesis itself.

Run `uv run python examples/custom_mastering.py` for dry/wet and mastered files,
editable JSON, MIDI and reports under `output/custom-mastering/`.

## Synthesis limits

Oscillators use at most 96 Fourier harmonics and a Nyquist taper. Modal layers are
independent decaying sines, not a coupled physical instrument. FM uses four-times
oversampling and the existing bandwidth guard. High notes can lose partials or
modulation depth, and rapid envelopes/modulation are not perfectly band-limited.
There is no arbitrary synthesis graph, feedback routing, inter-note legato or
continuous tone automation. Numerical tuning, stability and control checks do not
establish perceptual realism or musical quality. Audition patches before delivery.
