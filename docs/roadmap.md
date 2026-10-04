# Roadmap

Audio as Code is an early prototype for composing with a portable score and
rendering instruments synthesized from code. The items below describe work that
is available in the repository source and areas we want to improve. They are not
release dates or promises of acoustic realism. See [releasing](releasing.md) for
how a checked source version becomes a published package.

## Available in the repository source

- A version 1 JSON score with immutable notes, tracks, tempo changes, pedal
  events, gain/pan automation, generated delay/reverb, and deterministic seeded
  rendering within a fixed environment.
- Forty-nine playable, code-generated instrument entries grouped by musical
  family and synthesis mechanism. They are renderable prototypes; the
  [instrument foundation](instrument-foundation.md) records their model limits.
- Pattern composition, static score inspection, MIDI interchange, stereo WAV
  rendering, stems, and signal measurements. MIDI playback depends on an
  external instrument and need not sound like the generated WAV.
- [Arrangement helpers](arrangement.md) for cues across tempo maps, named section
  revisions, and measured previews of repeated loop regions. These do not make
  musical choices or guarantee a seamless loop.

## Planned work

1. **Evaluate instrument sound with listening evidence.** Add a reproducible
   audition protocol for representative pitches, dynamics, articulations and
   note releases. Use numerical checks for tuning and stability, and report
   listening judgments separately before claiming improved realism.
2. **Develop deeper performance models.** Explore piano half-pedal and
   cross-note resonance, more realistic bowed and wind release transitions, and
   continuous pitch/tone control. Each change needs an explicit score and MIDI
   compatibility decision; no generic voice should stand in for a planned model.
3. **Design loop finishing for sustained and wet material.** The present helper
   repeats one rendered crop and exposes its boundary measurements. A future
   workflow should handle effect context and tails deliberately, then verify
   sample timing and joins without promising an automatically musical result.

The [contributor guide](../CONTRIBUTING.md) explains checks for score changes,
audio behavior, distribution contents and release candidates. New features
should preserve existing score IDs and seeded output when the feature is unused.
