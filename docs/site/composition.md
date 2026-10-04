# Composition guide

A score is a `Song`: a tempo, a length in beats, and named tracks of notes. This guide covers the musical model and the Python helpers for building it. Every fact here matches the 0.1 source; field limits are collected in the [reference](reference.md).

```text
Song ── bpm, tempo_map, beats, seed, sample_rate, master_gain, automation, effects
 └─ Track ── name, instrument, gain, pan, tone, release_seconds, automation, effects
     └─ Note ── pitch, start, duration, velocity, release_seconds
```

## Time is counted in beats

All positions and lengths are **quarter-note beats** from zero. With constant tempo, convert beats to seconds as follows:

```text
seconds = beats × 60 / bpm
```

| bpm | 1 beat | 4 beats (one 4/4 bar) | 64 beats (16 bars) |
| --- | --- | --- | --- |
| 60 | 1.00 s | 4.00 s | 64.0 s |
| 96 | 0.625 s | 2.50 s | 40.0 s |
| 120 | 0.50 s | 2.00 s | 32.0 s |

- `Song.beats` is the full length, including any silence you want at the end. Every note must end at or before it; validation rejects a note that runs past.
- `Song.seconds` gives the score duration, integrating any tempo changes. `Song.render_seconds` includes automatic release/effect tails. A WAV render is limited to 300 seconds including those tails.
- Tempo is 20–300 BPM. Optional `tempo_map` entries change it in ordered steps (see below). There is no meter field or swing setting. Bars are a convention you keep in code (`BAR = 4`). Swing is written by moving off-beat notes by an explicit offset.

Common durations: whole note 4, half 2, quarter 1, eighth 0.5, sixteenth 0.25, eighth-note triplet 1/3.

## Pitch

A pitch is either a MIDI integer 0–127 or a name like `C4`, `F#3`, `Bb2`. Middle C is `C4` = 60, and `A4` = 69 = 440 Hz in equal temperament. Accidentals are a single `#` or `b`.

```python
from audio_as_code import midi_pitch

midi_pitch("C4")  # 60
midi_pitch("Bb2")  # 46
```

Very high notes can fall above the Nyquist frequency at low sample rates and become silent; very short notes (under about 3 samples) can disappear. The render report warns about the second case.

## Notes and velocity

```python
from audio_as_code import Note

Note(pitch="E4", start=2, duration=1.5, velocity=0.7)
```

- `start` ≥ 0 and `duration` > 0, both in beats.
- `velocity` is in (0, 1]. It scales loudness and, on modeled instruments, excitation brightness. There is no zero-velocity note: leave a note out to make a rest.
- By default, each voice fades to zero inside its duration. A long tone `decay_seconds` alone does **not** extend a short note. Set track `release_seconds` (0–10 seconds) to add a release after note-off; a note can override it, including with zero. Releases may extend past the song beat length and are included in the rendered tail.

## Patterns: phrases you can move around

`Pattern` builds notes without touching playback. Transformations return new patterns; `.at()` returns placed notes.

```python
from audio_as_code import Pattern

riff = Pattern.sequence(["A3", None, "C4", ["E4", "A4"]], step=0.5, gate=0.7, velocity=0.75)
riff.beats  # 2.0: four steps of half a beat, trailing rests included
riff.repeat(4)  # 8 beats
riff.transpose(5)  # up a perfect fourth (semitones, integers only)
riff.then(other)  # riff followed by other
riff.at(16)  # tuple of Notes placed at absolute beat 16
```

| Method | Returns | Use |
| --- | --- | --- |
| `Pattern.sequence(steps, *, step=1, gate=0.8, velocity=0.8)` | `Pattern` | One item per step: pitch, list/tuple chord, or `None` rest |
| `.repeat(times)` | `Pattern` | Loop end to end |
| `.transpose(semitones)` | `Pattern` | Shift every pitch; result must stay in 0–127 |
| `.then(other)` | `Pattern` | Concatenate phrases |
| `.overlay(other, offset=0)` | `Pattern` | Layer another phrase at a beat offset, preserving both lengths and all notes |
| `.stretch(factor)` | `Pattern` | Scale note positions, durations and phrase length; `2` doubles the length |
| `.scale_velocity(factor)` | `Pattern` | Multiply velocities; results must stay in (0, 1] |
| `.at(beat)` | `tuple[Note, ...]` | Place on the song timeline for a `Track` |
| `.notes`, `.beats` | data | The notes (pattern-relative) and the length |

`Pattern.sequence()` starts with a shared velocity and gate. A pattern can contain
notes with different velocities and durations. For accents or varied lengths, rebuild the notes:

```python
accented = [
    Note(**{**n.model_dump(), "velocity": 0.9 if n.start % 2 == 0 else 0.5})
    for n in riff.repeat(4).notes
]
```

## Chords and harmony

To turn a motif into a quiet, faster answer, use
`answer = riff.transpose(12).stretch(0.5).scale_velocity(0.6)`, then layer it with
`riff.overlay(answer, offset=1)`. Stretch changes beat timing; explicit release
times remain in seconds. Overlay retains duplicates and same-pitch overlaps,
which can raise levels or block MIDI export. Run `aac inspect` on the resulting
score before rendering. Use separate tracks for different instruments or effects.

There is no chord object. A chord is several notes with the same start, either a list inside `Pattern.sequence` or a helper:

```python
def chord(pitches, start, duration, velocity=0.55):
    return [Note(pitch=p, start=start, duration=duration, velocity=velocity) for p in pitches]
```

Practical voicing habits that work well with these synthesizers:

- Keep chord voicings in a close middle register (roughly C3–C5) and move each voice by step between chords instead of shifting the whole shape.
- Put the root in the bass track rather than doubling it low in the chord track; low clusters get muddy.
- End sustained chords slightly before the next chord (`3.9` instead of `4`). Same-pitch notes that overlap on one track are rejected by MIDI export.

[`02_motif_and_progression.py`](examples/02_motif_and_progression.py) works through a I–vi–IV–V progression with stepwise voicings, a bass line with approach notes, an arpeggio, and a transposed motif.

## Motifs and development

A motif is a short `Pattern` you reuse with changes. Useful operations, all plain Python:

- **Sequence it**: `motif.transpose(-3)` restates it a minor third lower over a new chord.
- **Answer it**: follow it with a contrasting phrase that resolves, `motif.then(answer)`.
- **Displace it**: `motif.at(start + 0.5)` shifts it off the beat.
- **Thin or thicken it**: play it on one track in the verse and double it an octave up (`transpose(12)`) on another in the chorus.

Patterns transpose chromatically by semitones. Keeping a motif inside a key (diatonic transposition) is up to your code.

## Form: named sections and explicit notes

Section names stay outside the version 1 score. Use `Section` and `Arrangement`
for validated named ranges and same-length revisions; `beat_at_seconds` and
`place_at_seconds` align cues to a media timeline across tempo changes. See
[arrangement helpers](arrangement.md), including measured loop previews.
A simple section table also works:

```python
FORM = [("intro", 4), ("verse", 8), ("chorus", 8), ("bridge", 4), ("chorus", 8), ("ending", 2)]
sections, beat = [], 0
for name, bars in FORM:
    sections.append({"name": name, "start": beat, "end": beat + bars * 4})
    beat += bars * 4
song_beats = beat
```

Write each part as a function of a section and add its notes with `.at(section["start"])`. Contrast comes from density and register: which tracks play, busier or sparser rhythms, velocity changes, and a cadence (for example a dominant chord) before each return. [`03_song_form.py`](examples/03_song_form.py) builds an 89-second intro / verse / chorus / bridge / chorus / ending piece this way and writes a `sections.json` with beat and second positions.

## Tracks, mixing, and pan

```python
Track(name="Bass", instrument="bass_guitar", gain=0.65, pan=-0.1, notes=bass_notes)
```

- `name` must be unique in the song (1–80 characters). The renderer derives each note's noise seed from the song seed, track name, and note index, so renaming a track changes its generated noise.
- Each sample is `voice × velocity × track.gain × song.master_gain`, then panned. `gain` and `master_gain` are linear, 0–1.
- `pan` is −1 (left) to 1 (right) with equal-power panning.
- The renderer only **reduces** the whole mix if its peak exceeds 0.95; it never boosts a quiet mix. If the report shows `gain_applied` below 1, lower your gains rather than relying on it.
- A song holds 1–64 tracks and up to 100,000 notes.

## Choosing instruments

`aac instruments` lists the 49 playable voices with family, engine, supported controls, and defaults. All are generated from code: modal resonances, a damped string loop, harmonic source/filter models, and electronic oscillators. They are approximations, not calibrated replicas; read each entry's `description`.

| Family | Instrument IDs |
| --- | --- |
| Plucked strings | `guitar`, `electric_guitar`, `bass_guitar`, `harp`, `ukulele`, `banjo` |
| Bowed strings | `violin`, `viola`, `cello`, `double_bass` |
| Keyboards | `piano`, `electric_piano`, `organ`, `harpsichord` |
| Woodwinds | `flute`, `clarinet`, `saxophone`, `oboe`, `bassoon` |
| Brass | `trumpet`, `trombone`, `french_horn`, `tuba` |
| Drums and percussion | `kick`, `snare`, `hat`, `toms`, `cymbal`, `congas`, `bongos`, `tambourine` |
| Pitched percussion | `marimba`, `xylophone`, `vibraphone`, `glockenspiel`, `bell`, `timpani` |
| Electronic | `sine`, `triangle`, `pluck`, `bass`, `pad`, `synthesizer`, `drum_machine`, `theremin` |

**Drums.** Individual drum IDs (`kick`, `snare`, `hat`, `toms`, `cymbal`, `congas`, `bongos`, `tambourine`) ignore the written pitch. `drum_machine` uses the pitch to pick a generated voice and rejects other pitches:

| Pitch | 36 | 38 | 42 | 45 | 49 | 54 | 60 | 64 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Voice | kick | snare | closed hat | tom | cymbal | tambourine | bongo | conga |

`timpani` is pitched and follows the written note.

## Tone: instrument-specific controls

`Tone` sets generated-model parameters for a **whole track**. An instrument accepts only the fields in its `tone_controls`; anything else is a validation error, and voices with no controls (`sine`, `triangle`, `pluck`, `bass`, `pad`, `kick`, `snare`, `hat`, `drum_machine`) accept no `tone` at all.

| Field | Range | Accepted by |
| --- | --- | --- |
| `brightness` | 0–1, default 0.5 | Every instrument that has controls |
| `decay_seconds` | 0.1–20 | Plucked strings, piano, electric piano, harpsichord, celesta, pitched percussion, toms, cymbal, congas, bongos, tambourine |
| `pluck_position` | 0.05–0.45 | Plucked strings, harpsichord |
| `breath` | 0–1 | Woodwinds, brass, organ |
| `vibrato_depth_cents` | 0–100 | Bowed strings, woodwinds, brass, theremin |
| `vibrato_rate_hz` | 0.1–12 | Same as vibrato depth |
| `glide_semitones` | −24–24 | Theremin |
| `detune_cents` | 0–40 | Synthesizer (side-oscillator offset), mandolin (total uncoupled pair separation) |

Omitted optional fields use the catalog default (`default_tone`, `default_decay_seconds`). Ask the catalog in code with `get_instrument("violin").tone_controls`.

```python
from audio_as_code import Tone, Track

Track(
    name="Violin",
    instrument="violin",
    tone=Tone(brightness=0.55, vibrato_depth_cents=25, vibrato_rate_hz=4.5),
    notes=notes,
)
```

Piano supports binary sustain through `Track.pedal`, an ordered list of
`PedalEvent(beat=..., down=True/False)` values. The pedal extends notes released
while it is down; its final release can extend the WAV. See the
[complete timing and MIDI rules](../piano-sustain.md). Half-pedaling is not implemented.
Thirteen bowed-string and wind voices support `articulation="soft"` or
`"accented"` on a track or note; discover support in the catalog and read
[articulations](articulations.md) for inheritance and synthesis limits. For two tone configurations of
one instrument, use two tracks with different `Tone` values. Gain/pan automation,
tempo changes, releases and effects are described below.
[`04_expressive_controls.py`](examples/04_expressive_controls.py) compares pluck
positions, vibrato, breath, glide, detune, and the kit.

## Tempo, movement, and space

Use expression to serve the phrase. For example, slow the answer slightly, move a
mallet part across the stereo field, and let its last note release into a small
generated reverberation:

```python
from audio_as_code import (
    Automation,
    AutomationPoint,
    Delay,
    Note,
    Reverb,
    Song,
    TempoChange,
    Track,
    export_midi,
    render,
)

song = Song(
    title="Space and breath",
    bpm=120,
    beats=8,
    seed=23,
    tempo_map=[TempoChange(beat=4, bpm=90)],
    automation=[
        Automation(
            parameter="master_gain",
            points=[
                AutomationPoint(beat=0, value=0.7),
                AutomationPoint(beat=8, value=0.5),
            ],
        )
    ],
    effects=[Reverb(mix=0.12, decay_seconds=0.8)],
    tracks=[
        Track(
            name="Mallets",
            instrument="marimba",
            gain=0.4,
            release_seconds=0.4,
            automation=[
                Automation(
                    parameter="pan",
                    points=[
                        AutomationPoint(beat=0, value=-0.3),
                        AutomationPoint(beat=8, value=0.3),
                    ],
                )
            ],
            effects=[Delay(time_seconds=0.2, repeats=2, mix=0.1)],
            notes=[
                Note(pitch=p, start=i * 2, duration=1.5)
                for i, p in enumerate(["C5", "E5", "G5", "C5"])
            ],
        )
    ],
)
song.save("output/space/score.json")
report = render(song, "output/space/song.wav")
export_midi(song, "output/space/song.mid")
print(song.seconds, song.render_seconds, report["warnings"])
```

The score lasts about 4.67 seconds; the WAV reserves about 6.03 seconds including
the release and effects. `tempo_map` contains ordered step changes. Automation
values replace the corresponding static value; they are not multipliers. Linear
interpolation is in beats; choose `interpolation="step"` for sudden changes.
Endpoint values hold before the first and after the last point. For a fade across
a release tail, arrange sufficient beat-space before the score ends; automation
points cannot extend past `beats`.

Track effects run before master gain; song effects run on the summed mix. The
renderer preserves finite tails automatically, and the entire WAV must stay at
or below 300 seconds. MIDI exports the tempo changes but omits the automation,
effects and releases. Stems contain track processing and master gain but omit
master effects, so they do not reconstruct a master-processed mix. The
[reference](reference.md#tempo-automation-and-effects) lists supported ranges.

## Full pieces to study

The website pairs familiar public-domain scores with new arrangements by an
AI agent. Listen to **The classic**, then **Reimagined**, and compare how a change
of instruments, rhythm or mood affects the same musical material. Both versions
are synthesized from editable scores. Read the [score credits](classic-showcase.md)
and inspect the [generator](../music/classic_showcase.py); the complete
[source download](../source.html) includes the runnable project.

Four additional original compositions remain in the source project at
`examples/full_compositions.py`. They are separate from the website's paired
listening program. Each uses a shared `FORMS` table for note placement and section
metadata, showing how these techniques scale to a whole piece.

| ID | Build function | Form and ensemble | Tempo, beats, length |
| --- | --- | --- | --- |
| `lanterns-on-the-water` | `lanterns_on_the_water()` | D-major 3/4 chamber waltz: piano, flute, clarinet, violin, cello | 84 BPM, 144 beats, 102.86 s |
| `copper-street` | `copper_street()` | E-dorian groove: bass guitar, electric piano, electric guitar, saxophone, trumpet, trombone, kick/snare/hat | 104 BPM, 208 beats, 120 s |
| `night-signal` | `night_signal()` | F-minor electronic piece: pad, pluck, sine, bass, synthesizer, theremin, triangle, drum kit | 120 BPM, 224 beats, 112 s |
| `clockwork-garden` | `clockwork_garden()` | 7/8 grouped 2+2+3: marimba, harp, vibraphone, glockenspiel, xylophone, bell, timpani, bongos | 112 BPM, 182 beats, 97.5 s |

Meter is a convention in code: a 3/4 bar is 3 beats and a 7/8 bar is 3.5 quarter-note beats. MIDI export carries the tempo but not a time signature.

Reproduce them from the source folder:

```sh
python examples/full_compositions.py                      # WAV, MIDI, JSON, reports, manifest.json in output/full-compositions/
python examples/full_compositions.py output/my-pieces     # another destination
python examples/full_compositions.py output/my-scores --scores-only   # JSON + MIDI only, much faster
```

Full rendering takes several minutes on a CPU. Seeds are fixed (2101–2104), so a rebuild in the same environment matches; a later synthesis change can alter the sound of the same score. Each manifest entry lists the piece's sections as beat ranges, and its `code_excerpt` is a fragment of the builder that depends on surrounding variables, so run the full source rather than the excerpt. Like everything here, these are code-generated approximations; levels and signal reports are numerical checks, not a judgment of realism or quality.

## Editing an existing score

Models are frozen and validated. Edit through data so the result is checked again:

```python
from audio_as_code import Song

data = Song.load("output/song.json").model_dump(mode="json")
data["tracks"][0]["gain"] = 0.4
revised = Song.model_validate(data)
revised.save("output/song-v2.json")
```

Avoid `model_copy(update=...)` and `model_construct()`: they skip validation. Rendering and MIDI export revalidate anyway, so errors would surface later and further from the edit.

## Rendering, stems, and MIDI

```python
from audio_as_code import export_midi, render

report = render(song, "output/song.wav", stems_dir="output/stems")
export_midi(song, "output/song.mid")
```

- WAV: stereo PCM16 by default, optionally PCM24 or float32, at the song's `sample_rate` (22050, 44100, or 48000 Hz; default 44100). Stems are named `01.wav`, `02.wav`, … in track order.
- MIDI is a score approximation for a DAW or hardware synth: notes, tempo, programs, volume, and pan. It carries step tempo changes but not these synthesizers, `Tone` settings, automation, effects, releases, audio tails or normalization. Drums share channel 10 with no per-track pan; their events are grouped in the first percussion track. Export rejects more than 15 melodic tracks, more than one track per drum ID, and overlapping same-pitch notes on one channel.
- The report's measurements (peak, RMS, clipping, silence) are signal checks. They say nothing about whether the music is good. Listen to the result.

## Reproducibility

The same score, seed, software versions, and platform produce byte-identical WAV files. Different NumPy versions, platforms, or library releases may change the bytes. Keep the JSON score, the lock file, and the render report (which records `score_sha256`, `engine_version`, `numpy_version`, and `seed`) beside any audio you need to reproduce.

For excerpt exports, optional LUFS targeting, progress and cancellation, see
[production output](production-output.md). Excerpts retain full-song context and
cost a full render. Higher bit depth does not improve the synthesis model.
