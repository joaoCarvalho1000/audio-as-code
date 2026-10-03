# Full original compositions

[Source](../examples/full_compositions.py) builds four original arrangements entirely
from the procedural voices in Audio as Code. These are complete short pieces with
introductions, contrasting sections, returns and written final cadences. They are
not transcriptions and use no recordings, SoundFonts or measured impulse responses.

Run from the repository root:

```sh
uv run python examples/full_compositions.py
# Optional destination or a quick score/MIDI-only export:
uv run python examples/full_compositions.py output/my-compositions
uv run python examples/full_compositions.py output/my-scores --scores-only
# Optional MP3 previews; FFmpeg is not a framework dependency:
uv run python examples/full_compositions.py output/my-compositions --ffmpeg ffmpeg
```

The default destination is `output/full-compositions/`. Full export creates stereo
44.1 kHz, 16-bit WAVs, standard MIDI, validated score JSON, a copy of the complete
Python source, per-piece signal reports and `manifest.json`. Score-only export writes
`scores-manifest.json`; it does not publish an incomplete listening manifest.
Any export first removes an existing listening manifest in that destination, so
interrupted rendering or score-only changes cannot advertise stale audio. Use a
separate destination to preserve an existing listening package.
Rendering these longer arrangements can take several minutes on a CPU.

| Piece / build function | Form and sound | Length |
| --- | --- | --- |
| Lanterns on the Water / `lanterns_on_the_water()` | D-major 3/4 chamber waltz; piano, flute, clarinet, violin and cello. The minor crossing gives the cello the line; development exchanges the motif among voices. | 102.86 s, 84 BPM |
| Copper Street / `copper_street()` | E-dorian groove; bass guitar, electric piano, electric guitar, saxophone, trumpet, trombone and electronic kick/snare/hat. Harmonic bridge, sax variation, stop time and a fuller horn return. | 120 s, 104 BPM |
| Night Signal / `night_signal()` | F-minor electronic ensemble; pad, pluck, sine sub, bass, synthesizer, theremin, triangle and generated drum kit. An isolated signal becomes a sequence, breaks down and returns with reversed arpeggios and changed harmony. | 112 s, 120 BPM |
| Clockwork Garden / `clockwork_garden()` | 7/8 grouped 2+2+3; marimba, harp, vibraphone, glockenspiel, xylophone, bell, timpani and bongos. Chorale interrupts the gears; the mallets trade phrases before the return. | 97.5 s, 112 BPM |

All score time is in quarter-note beats: one 7/8 bar therefore occupies 3.5 beats.
MIDI currently exports tempo but does not encode the piece's time signature; use the
form/source when importing the waltz or seven-eighths piece into a notation tool.
The single `FORMS` table drives both note placement and section metadata. Arrangement
logic uses each section's index to change melody, harmony, texture and dynamics.

`Arrangement.phrase` makes rhythmic placement explicit; `None` is a rest.
`Arrangement.cadence` reserves the last bar for a tonic arrival and its decay.
Sustained/plucked tails are written inside the score duration. A repeated pitch
releases its earlier note before retriggering, keeping MIDI note ownership clear.
The source extracts each educational `code_excerpt` from marked lines in its actual
builder. These fragments demonstrate arrangement techniques and rely on surrounding
builder variables; download the full source to run them.

Every piece has a fixed seed (2101–2104), stable ID, explicit gain/pan, and only
supported tone controls. Rendering is deterministic within a fixed engine and
numerical environment. A future DSP update can change the same score's sound.
The exporter disables normalization so a level problem remains visible; it rejects
silent, non-finite or full-scale output. Its reports contain peak/RMS levels and warnings.
MIDI uses approximate General MIDI programs and a receiving synthesizer will sound
different from this framework's WAV.

The acoustic names describe playable synthesis prototypes, not calibrated replicas:
struck/plucked modes, harmonic/formant sources and designed percussion. The pieces
illustrate arrangement and the current timbres. Finite samples, MIDI validity,
headroom and deterministic rebuilding are numerical/structural checks, not proof of
perceptual realism or musical quality. These artifacts have not been claimed as
subjectively auditioned.

Focused validation:

```sh
uv run pytest tests/test_full_compositions.py
uv run ruff check examples/full_compositions.py tests/test_full_compositions.py
uv run ruff format --check examples/full_compositions.py tests/test_full_compositions.py
```

The tests check form boundaries, complete durations, changing orchestration, final
cadences, score determinism, JSON round trips, balanced MIDI note events, source
copy rebuilding and manifest consistency. Generated WAV/MIDI files belong under
`output/` and should not be committed as source.
