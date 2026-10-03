# Immutable composition tools

`Pattern` is a phrase of existing `Note` objects with an explicit length in
quarter-note beats. Every transformation returns a new pattern; source phrases
stay unchanged. Its `.at(beat)` method produces a tuple of ordinary notes for a
`Track`, which serializes as the existing version 1 `Song` JSON format.

```python
from audio_as_code import Pattern, Song, Track

motif = Pattern.sequence(["C4", None, "E4", "G4", None, None], step=0.5)
answer = motif.transpose(12).stretch(0.5).scale_velocity(0.6)
duet = motif.overlay(answer, offset=1.5)  # Both phrases end at beat 3.
arrangement = motif.then(duet).repeat(2)
song = Song(
    title="Call and answer",
    beats=arrangement.beats,
    tracks=(Track(name="Duet", instrument="pluck", notes=arrangement.at(0)),),
)
song.save("output/composition-tools/short-score.json")
```

## Phrase operations

| Operation | Musical effect | Length |
| --- | --- | --- |
| `pattern.then(other)` | Append the other phrase | Sum of both lengths |
| `pattern.overlay(other, offset=0)` | Layer another phrase at an offset in beats | `max(pattern.beats, offset + other.beats)` |
| `pattern.stretch(factor)` | Multiply onsets and note durations by a factor | Original length times factor |
| `pattern.scale_velocity(factor)` | Multiply every note velocity by a factor | Unchanged |
| `pattern.repeat(times)` | Repeat the complete phrase | Original length times count |
| `pattern.transpose(semitones)` | Chromatic pitch shift | Unchanged |
| `pattern.at(beat)` | Produce score notes starting at an absolute beat | Returns notes, not a pattern |

Declared length includes leading and trailing rests. Overlaying a silent phrase
can extend the result. Stretching by `2` plays the phrase over twice as many beats;
`0.5` plays it over half as many. Song tempo is unchanged. Stretching preserves
pitch, velocity, and `release_seconds`: release is a synthesis control in seconds,
not a beat duration. Other transformations also preserve unrelated note fields.

Overlay keeps the original notes in their original order, then the other phrase's
placed notes. It keeps overlapping notes and exact duplicates, so identical
layers can increase output level. It does not sort, merge, truncate, or assign
instruments. Use separate tracks when layers need different instruments, tone,
effects, gain, or pan.

Velocity factors must be positive and finite. Every resulting velocity must stay
in `(0, 1]`; exceeding 1 raises `ValueError`, without clipping relative accents.
A zero velocity is not a rest: use `None` in a sequence or omit a note to create
silence. A silent pattern still validates its factor, but has no note velocities
to constrain. Velocity affects instrument response and is not a linear loudness
control; use track gain for mixing.

Stretch factors must be positive and finite; offsets must be finite and
nonnegative. Booleans and numeric strings are rejected. Operations validate
resulting notes and lengths too, including nonfinite or zero values produced by
floating-point overflow or underflow. A pattern must have a positive length,
and every note must end within it (with the score's existing `1e-9` beat tolerance).
Placing a pattern into a song still requires the song's note-count, duration,
instrument, and other limits to be satisfied.

`Pattern.sequence` accepts a nonempty sequence of pitches, chords (sequences of
pitches), and `None` rests. Empty chords also occupy a rest step. Strings and
bytes are not outer sequences; bytes, mappings, sets, generators, and scalar
non-pitches are rejected as chords. Pitch validation remains the existing `Note`
validation, including MIDI range 0–127. All-rest phrases are valid.

## Runnable example

From the checkout root after `uv sync --locked`, run:

```console
uv run python examples/composition_tools.py
uv run aac validate output/composition-tools/song.json
```

The example arranges a motif, a faster octave answer, a louder variation, and a
bass part using the procedural `pluck` and `bass` voices. It writes `song.json`,
`song.mid`, `song.wav`, and `report.json` under `output/composition-tools/`.
The fixed seed makes rendering deterministic within a fixed environment.
MIDI carries notes and timing; it does not reproduce the procedural timbre.
Listen to the WAV to judge the result; numerical audio checks do not establish
perceptual realism.
