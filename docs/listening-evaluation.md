# Reproducible instrument listening evaluation

Availability: Unreleased source tooling, absent from published PyPI 0.5.0.
Use a repository checkout or source ZIP containing `examples/listening_evaluation.py`.
From its extracted root, run `uv sync --locked`, then the commands below; installing
`audio-as-code==0.5.0` from PyPI alone does not provide this tooling.

Generate original, isolated gestures for piano, violin, flute, marimba and kick:

```sh
uv run python examples/listening_evaluation.py output/listening/baseline
uv run python examples/listening_evaluation.py output/listening/repeat --baseline output/listening/baseline
```

Each voice has two control states, three pitches and two velocities. Violin and
flute compare soft and accented articulation; the other voices compare dry and
0.2-second releases. The kick is unpitched: changing its score pitch does not
establish a tuned drum. A folder must not already exist. Preserve the baseline,
then run a changed model into a new candidate folder with `--baseline` pointing
to the original. This also works for a deliberate coefficient edit in a separate
checkout; keep the original scores and compare the same protocol version.

The manifest stores score IDs, PCM WAV hashes, render settings, source commit,
source hashes, dirty status, dependency-lock hash and Python/NumPy/platform
versions. Commit and dirty status are `null` (unknown) in source archives, when
Git is unavailable, or when this source directory is not itself a Git checkout.
An enclosing unrelated checkout is never used. Content hashes remain available
in all these cases. Each clip has an editable score and complete render report, including
encoded peak, RMS, full-scale sample count and silence. Tuning entries report a
Hann-window spectral maximum within 10% of the nominal fundamental. This local
measurement can follow a partial or noise and is not a general pitch detector.
Kick tuning is explicitly not applicable. Fixed inputs in a fixed environment
must reproduce score IDs and WAV hashes. Cross-platform equality is not promised.

## Human listening record

The generated manifest deliberately starts every clip as `not_listened`. Fill
its separate `listening` object only after playing the saved WAV. Record the
listener's name, date, player, headphones or speakers, and playback conditions.
Use `notes` to record concrete observations against these five questions:

| Field | Listening question |
| --- | --- |
| onset | Is the attack clear at both velocities? Is there an unintended click? |
| sustain | What changes during the held sound? Is it stable or unintentionally beating? |
| release | Is the ending appropriate, abrupt, noisy or unnaturally prolonged? |
| recognizability | What instrument/family does it suggest, and at which registers does that fail? |
| artifacts | Where are buzzes, alias-like tones, discontinuities or other unwanted sounds heard? |

For baseline/candidate comparison, keep playback level and equipment fixed,
alternate the two files and note the exact clip and timestamp. Record uncertainty
and preference separately. Do not turn a spectral check into a listening verdict
or a claim of acoustic realism. A narrower demonstrated capability should prompt
an evidence-backed catalog-description change, not a generic replacement voice.

The generator does not perform a listening pass. Completion of the human record
is required before treating an instrument evaluation as finished. All synthesis
sources remain generated code; no recordings or measured impulse responses are
inputs to this protocol or the voices.

## Combined listening and target-player pack

From the same Unreleased source checkout or extracted ZIP, run:

```sh
uv run python examples/audio_review_pack.py output/review-pack/baseline
uv run python examples/serve_site.py --directory output/review-pack/baseline --port 8765
```

Open the printed localhost URL. The pack includes the ten original auditions,
the lifted/half/held repeated-key study, dry/wet loop cycles and two-cycle
previews. Editable scores, pedal sidecars in the experiment report, numerical
reports, source/runtime provenance and file hashes remain alongside the WAVs.
Every output directory must be new. Run the same source again into a separate
folder to compare score and WAV hashes while preserving the baseline.

The two cycle players enable the browser's native `loop` property. Keep the page
foregrounded, play one cycle at a time for at least three wraps without seeking,
then save the browser observations. These record user agent, playback errors and
animation-frame samples around candidate wraps. Timer sampling can miss wraps;
a manual backward seek can be counted. They do not measure device output gaps or
prove audible continuity. Compare the two-cycle preview too, and record player
and version when testing a downloaded cycle in another intended target player.

Human acceptance checklist:

- Record listener, date, playback software/version, equipment and listening level.
- Complete all five rubric fields for every voice/state, including both velocities
  and all three written pitches. Keep unpitched kick observations separate.
- Compare lifted, half and held decay after key release, repeated attacks and final
  lift. Record timestamps and whether intermediate damping is audibly useful.
- Listen across three dry and wet joins in each intended player and compare the
  preview. Record clicks, gaps, level changes or uncertainty with filenames.
- Retain the baseline and any candidate, their pack manifests and saved browser
  observations. Propose catalog changes only from actual observations.
- Keep issues 3, 4 and 5 open until their human acceptance and, for issue 4,
  the documented score-contract/MIDI/release-control decisions are complete.

The pack and automated browser checks leave human listening as `not_listened`.
