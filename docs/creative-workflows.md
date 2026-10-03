# Compose to a video, game or presentation brief

The original compositions in `examples/creative_workflows.py` demonstrate a full
agent delivery: a first version, a constrained revision, editable scores, audio,
MIDI, the composer and measured acceptance checks. They use the public Python API
and code-generated voices. No source recordings or sample libraries are used.

Run from the extracted source folder containing `pyproject.toml`:

```sh
uv sync --locked --no-dev
uv run --no-dev python examples/creative_workflows.py output/creative-workflows
```

Use a fresh or empty destination; the example refuses to replace prior candidates.
The full run synthesizes each of six versions three times to check floating-point
output and byte reproducibility, so allow several minutes. For a quick editable
score and MIDI pass, add `--scores-only`. To render one candidate:

```sh
uv run --no-dev python examples/creative_workflows.py output/game-revision --brief game --version v2
```

| Brief | Musical construction | Requested revision | Preserved material |
| --- | --- | --- | --- |
| Warm, playful 30-second video | Twelve bars at 96 BPM; marimba motif, electric piano, bass, light kick/hat; celesta reveal at 20 seconds; tonic cadence at 27.5 seconds | Soften the drums | Melody, harmony, bass, reveal, seed, tempo and duration; only the two drum gains change |
| 12-second exploration game loop | Four bars at 80 BPM; marimba motif over minor/major chords, bass and a chromatic tension layer | Reduce tension | Motif, harmony, bass, seed, tempo and loop length; remove the tension layer |
| Nine-second presentation sting | Eighteen beats at 120 BPM; rising identity phrase and dominant-to-tonic finish | More triumphant | Every original track, seed, tempo and duration; add a trumpet layer |

These are compositional intentions, not claims that the output has been auditioned
or that its instrument models sound realistic. The manifest records `auditioned:
false`. Listen to the candidates before selecting one for a creative project.

## Exact cuts and cues

At constant tempo, `beats = seconds * bpm / 60`. A 30-second piece at 96 BPM is
48 quarter-note beats; its 20-second cue is beat 32. Store cue and section metadata
in a sidecar or composer because score version 1 rejects custom marker fields.
For a tempo map, use `song.beat_to_seconds(beat)` to check actual cue timing.

`song.seconds` measures the score; `song.render_seconds` also reserves release and
effect tails. The examples keep effects and `release_seconds` at their zero/empty
defaults, and put the ending inside the score. A longer `tone.decay_seconds` does
not extend a note past its gate. The last notes finish slightly before the cut,
leaving a short, intentional silent margin rather than chopping an active tail.

Check the saved WAV frame count, not just the score or MIDI length. Expected
frames are `round(target_seconds * sample_rate)`; arbitrary target times may only
be representable to one sample. These three targets are exact at 44.1 kHz:
1,323,000, 529,200 and 396,900 frames. MIDI is checked separately to within 1 ms.
MIDI has a tick grid and does not carry the framework's effects, releases or sounds.

If a requested revision needs a longer final release while keeping the same cut,
move its note-off earlier or revise the arrangement. Recheck the WAV duration;
adding a release or reverb can reserve a tail even when the score length is fixed.

## A loop with a measured join

The game uses a dry, articulated arrangement. Notes fade within their gates and
leave brief rests at bar lines, including the loop boundary. The harmonic sequence
returns to its opening on repetition. There is no cropping, crossfade, tail
wrapping or claim of a general-purpose loop export API.

`verify_loop()` reads the actual 16-bit PCM, measures the last-to-first-frame jump
and adjacent sample steps, then writes two unchanged cycles to `two-cycles.wav`.
It confirms the cycles are identical and the preview lasts 24 seconds. The
delivered examples have zero boundary jump and zero adjacent steps at that join.
Those checks establish sample continuity for these files, not whether a listener
finds the musical return convincing. Audition the middle of the two-cycle file,
then test continuous playback in the game's actual audio system; player scheduling
can introduce gaps even when the asset itself is continuous.

A continuous pad, release across the boundary, or wet reverb loop needs a different
approach: render repeated context and design/test the crop or process the tail
periodically. Merely concatenating ordinary renders does not create a seamless
wet loop. The example's seam test deliberately rejects an abrupt join.

## Revisions you can verify

Convert the original immutable score to data with `model_dump(mode="json")`, make
the scoped change, and reconstruct it with `Song.model_validate(data)`. Keep the
seed, track names and unchanged note ordering stable: they affect seeded synthesis.
`revision_contract()` compares whole preserved tracks, all global settings, the
track set and the allowed gain change. An accidental melody edit fails the check.

This does not make natural-language composition automatic. An agent interprets
“softer” as lower drum gain, “less tense” as removing the chromatic layer, and “more
triumphant” as brass reinforcement here. Other briefs can require other choices.
State the interpretation and preserve the material the user identified.

## What the output contains

Each `video`, `game` or `presentation` directory contains `v1` and `v2` candidates.
The root `manifest.json` uses relative artifact paths so the whole folder can move
to another machine. `uv.lock` is copied when run from a source checkout root.

| File | Purpose |
| --- | --- |
| `song.wav` | 16-bit stereo soundtrack asset |
| `song.mid` | Editable MIDI interchange; the receiving instrument determines its sound |
| `score.json`, `composer.py` | Validated editable score and complete original composer |
| `brief.json` | Request, revision, version and section timings in seconds |
| `inspection.json` | Export readiness checked before synthesis |
| `report.json`, `analysis.json`, `midi-report.json` | Renderer, saved WAV and MIDI diagnostics |
| `acceptance.json` | Actual duration, float finiteness, clipping, final silence, reproducibility and applicable cue/loop checks |
| `reproduction.wav` | Second byte-identical WAV export used for the hash comparison |
| `two-cycles.wav` | Game-only repeated loop for seam audition |

`--scores-only` writes the editable score, MIDI, inspection, composer and brief;
it does not claim to check or deliver audio. Its manifest marks `scores_only: true`.
The copied composer is self-contained except for the installed framework and its
runtime dependencies. Rebuild it in that environment with the same `--brief` and
`--version` options, directing it to a fresh folder.

The full checks establish finite stereo samples, no full-scale PCM values, exact
media lengths, byte reproducibility in the same environment, and preserved
revision constraints. They do not assess loudness against narration, timbre,
phrasing or musical quality. Keep the score, composer, lockfile and reports for
reproduction, and report listening separately from numerical validation.
