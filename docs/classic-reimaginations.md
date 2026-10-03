# Five familiar works, five other worlds

These AI-arranged versions transform the same complete source material as the
faithful listening collection. Every source pitch/onset event remains represented,
with the full formal span and explicitly unfolded repeats. They are complete
arrangements of the named source editions, not expanded loops of short excerpts.

| Source work | Reimagining | Musical transformation |
| --- | --- | --- |
| Beethoven, Für Elise | Elise After Midnight | Electric piano and celesta trade eight-bar lead passages over harp, bass and a restrained three-beat groove |
| Bach, Cello Suite No. 1 Prelude | The Clockwork Aquarium | All arpeggios rise an octave onto marimba; central-register kalimba glints, bass anchors and a changing mechanical pulse reveal the harmony |
| Mozart, Turkish March | The Royal Arcade | Xylophone and mandolin trade the lead over electric piano, nimble bass and a dance pulse with a central breakdown |
| Traditional, Greensleeves | Greensleeves on Europa | Theremin and an octave-higher recorder answer over harp, bass pedals, occasional high bells and subtle generated space |
| Beethoven, Ode to Joy hymn arrangement | Joy at the Lunar Funfair | Banjo and clarinet trade the melody over electric-piano/harp inner voices, bass and a light parade beat |

“Complete” follows the source's scope: Bach is the complete BWV 1007 Prelude;
Turkish March is the complete Rondo alla Turca movement; Greensleeves is the
complete Fontaine two-voice arrangement; Ode to Joy is the complete sixteen-bar
Chubb SATB hymn, not Beethoven's entire Ninth Symphony. The source dataset and
manifest retain edition credits and URLs.

## Arrangement decisions

An AI agent using **gpt-6-astra** wrote the transformations and creative briefs.
The runtime performs deterministic procedural synthesis without calling a model.
Manifest provenance distinguishes the new arrangement authorship from the
historical compositions and credited score editions.

Every source part is mapped explicitly. Melodic handoffs occur every eight source
bars where a recipe has two lead voices. Four-bar dynamic contours rise and settle,
with modest metric accents and a longer whole-piece arc; source dynamics remain
the starting point. Short voice-specific releases soften note endings. Source
onsets stay intact, and octave shifts are declared per track.

Celesta receives the central-register Elise passages while electric piano keeps
the contrasting extreme-register episode. Bach's low line remains entirely on
marimba; added kalimba accents stay in C4–E5 rather than forcing low cello notes
onto a lamella model. Mandolin's source pitches stay within its useful treble
register. Recorder answers an octave above the theremin's source register.

Bass anchors derive from the low source part. Sparse phrase glints and percussion
are added accompaniment, never replacements for source events. The groove enters
after the opening, thins in the middle, and leaves the final cadence space. Exact
duplicate unisons merge within a lane, and same-pitch gates stop at retriggers for
valid MIDI. Source-note accounting remains in every report.

All recipes use fixed tempos, real playable catalog voices and fixed seeds.
Only Greensleeves uses subtle generated reverb; the others are dry. No recordings,
sample libraries, SoundFonts or measured impulse responses supply instrument
sounds. These arrangements do not use the piano sustain pedal; shared legato is
not modeled. Signal measurements do not prove acoustic realism or musical quality.

Score-level balances keep the melody exposed and accompaniment restrained. Relative
RMS and, when measured, integrated loudness/true peak help compare a reimagining
with its classic companion. Those measurements are not claims of equal perceived
loudness. WAVs and MP3 previews come from the saved scores without later loudness
processing.

## Reproduce and revise

From the complete project, install dependencies with `uv sync --locked`, then run:

```sh
uv run python examples/classic_reimaginations.py --ffmpeg ffmpeg
```

FFmpeg must be installed for the 192 kbps MP3 previews. To produce validated editable
scores and MIDI without rendering audio:

```sh
uv run python examples/classic_reimaginations.py output/reimagined-scores --scores-only
```

Score-only generation removes an existing listening manifest in its destination
so older audio is not advertised beside changed scores. Existing audio files are
preserved; use a separate folder when keeping a prior listening collection.

The generator reads `examples/music/classics-full.json` and writes five WAVs, MP3s,
MIDI files, JSON scores and reports under `output/classic-reimaginations/`, plus
the paired manifest and `classic-reimaginations-source.zip`. Stable pair IDs
continue to link each reimagining to its complete classic version.

The ZIP contains the current engine, type marker, full note dataset, generator,
dependency metadata and this guide in a runnable project layout. Rendering has
no network dependency. The displayed Python recipe requires its full project and
dataset; it is not an audio-generating service.

Edit `RECIPES`, `_source_tracks` or `_added_tracks` to revise the arrangement.
Keep the score, dependency lock and report together. Verify complete source-event
coverage and export timing after edits. MIDI retains written notes and tempo on
its tick grid, but not equivalent procedural effects or audio tails.
