# Cues, sections, and loop previews

`audio_as_code.arrangement` adds composition helpers around the immutable version 1
`Song`. It does not add fields to score JSON. Keep section names and loop intentions
in the composer or a sidecar file if you need to save them.

Run the complete example from the repository root:

```sh
uv run python examples/arrangement_workflow.py output/arrangement
```

It writes an original score with a cue at 3.5 seconds across a tempo change, a
scoped revision, and a two-cycle PCM preview with join measurements. All voices
are synthesized from code.

## Place a cue at a timestamp

`beat_at_seconds(song, seconds)` integrates the song's piecewise constant BPM in
reverse. It accepts times from zero through `song.seconds` and returns a continuous
quarter-note beat. `place_at_seconds(song, pattern, seconds)` moves a `Pattern` to
that beat and rejects one that extends beyond the musical score. For example:

```python
from audio_as_code import Pattern, Song, TempoChange, Track
from audio_as_code.arrangement import beat_at_seconds, place_at_seconds

song = Song(
    bpm=120,
    beats=8,
    tempo_map=(TempoChange(beat=4, bpm=60),),
    tracks=(Track(name="Lead"),),
)
assert beat_at_seconds(song, 4) == 6
notes = place_at_seconds(song, Pattern.sequence(["C5"], step=0.5), 4)
# Put notes on a track when building the final immutable Song.
```

The requested time determines the note onset in score time. The renderer rounds
onsets to `round(seconds * sample_rate)`, so the physical onset lies on the sample
grid, generally within half a sample of the requested time. Instrument attacks
can peak later than the note onset. Reserve room for the cue's full pattern length
and for any release or effect tail needed at an exact media cut.

## Revise a named section

`Section(name, start_beat, end_beat)` uses a half-open interval: the start belongs
to the section and the end belongs to the next one. `Arrangement(song, sections)`
rejects duplicate names, overlaps and out-of-bounds sections. Sections may leave
gaps; they need not cover the whole song.

```python
from audio_as_code import Pattern
from audio_as_code.arrangement import Arrangement, Section

arrangement = Arrangement(song, (Section("opening", 0, 4), Section("reveal", 4, 8)))
revision = arrangement.replace_section(
    "reveal", {"Lead": Pattern.sequence(["C5", None, "G5", None])}
)
final_song = revision.song
```

The replacement pattern must have exactly the section's beat length, including
trailing rests. The helper edits only the named tracks, keeps their other controls,
and preserves the song seed, tempo map, track names and track order. Other tracks
are left intact. A note on an edited track that crosses either section boundary
causes an error; the helper will not split or truncate it. Edited tracks and
replacement patterns must have chronological note starts. Existing pedal,
automation and effects remain in place, so their behavior can span sections.
Note releases can also sound beyond a written section.

The renderer seeds each voice from the song seed, track name and **note index**.
If a replacement changes the note count on an edited track, unchanged later notes
on that track keep their data but move to new indices and may sound different.
Keeping the same count preserves those indices. Changed notes, mix normalization,
automation and effects can still change audio outside the edited region. Check the
render when a revision promises an exact sonic match elsewhere.

## Repeat and inspect a loop region

`LoopRegion(start_beat, end_beat)` marks an interval in musical time.
`render_loop_preview(song, region, repetitions=2)` renders the full song first,
extracts the rounded frame interval, and repeats those exact samples. The result
has `.audio` (stereo float32) and `.report["loop"]`. The report gives rounded
start/end frames, cycle and preview durations, the largest absolute last-to-first
sample jump across channels, the largest adjacent step *inside* one cycle, and an
estimated amount of note/release/effect tail beyond the end. It also flags sound
from before the region that could cross its start. A separate `source_audio` entry
contains full-render metrics; the top-level `audio` metrics describe the repeated
preview.

```python
from audio_as_code.arrangement import LoopRegion, render_loop_preview

preview = render_loop_preview(song, LoopRegion(0, 8), repetitions=2)
print(preview.report["loop"]["boundary_jump"])
```

By default, the helper rejects a loop when a note, release or generated effect
tail crosses either boundary. Use `allow_tail_crop=True` only when deliberately
testing a cut; the report still shows the estimated crossing. The estimate is
conservative and based on score timing and effect tail reservations. It does not
measure whether the tail's signal is actually audible. A quiet sample join does
not prove a musically convincing repeat. The preview does not simulate continuous
effect state from cycle to cycle, wrap a tail, crossfade, or guarantee gapless
playback in a game engine. Listen to the repeated file and test it in the target
player.
