# Reproducible instrument listening evaluation

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
versions. Each clip has an editable score and complete render report, including
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
