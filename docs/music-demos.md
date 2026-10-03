# Famous music demos

Run `uv run python examples/instrument_browser.py`, then open
`output/instruments/index.html`. **Music** is the default preview mode.
All 49 instruments have a dedicated short music arrangement, a dry phrase, and a
single note/hit preview: 147 clips at 44.1 kHz. Music clips are roughly 11–24 seconds.

The music comes from five credited public-domain score editions. Imported data
contains notes, not audio. Each music demo offers WAV, approximate MIDI, editable
JSON and a score-credit link. The browser demos are excerpts; they are separate
from the five complete [classic performances](classic-showcase.md) and their
[AI reimaginings](classic-reimaginations.md).

| Music | Featured voices |
| --- | --- |
| Greensleeves | Acoustic guitar, harp, ukulele, violin, flute, clarinet, kalimba, recorder, sine, theremin |
| Bach: Cello Suite No. 1 Prelude | Bass guitar, viola, cello, double bass, bassoon, synth bass |
| Beethoven: Für Elise | Piano, electric piano, celesta, vibraphone, glockenspiel, triangle |
| Mozart: Turkish March | Electric guitar, banjo, mandolin, harpsichord, marimba, xylophone, pluck, synthesizer |
| Beethoven: Ode to Joy | Organ, saxophone, oboe, trumpet, trombone, French horn, tuba, bell, timpani, pad, and all nine percussion/kit voices |

There are 35 solo arrangements and 14 combined arrangements. The five small
ensembles are a string trio, flute with harp, woodwind quartet, brass quartet, and
glockenspiel with piano. Each percussion feature plays an original groove beside
Ode to Joy and a bass part. The requested instrument is mixed forward; every voice
also has completely solo phrase and note/hit previews for clearer inspection.

## Hear the instrument's behavior

The melodic phrase repeats its tonic at two velocities, climbs through the voice's
central register, leaves a short gap, and answers with a descending cadence.
Plucked, keyboard and tuned-percussion phrases reach an octave; bowed strings and
winds stay within a fifth. Percussion phrases use contrasting accents and spacing.
These phrases are original audition material, not additional borrowed compositions.

Supported tone controls and short release envelopes are set by voice family.
The music's written gates stay close to their source lengths instead of stretching
every struck note into the next. Deterministic phrase dynamics and per-voice
releases provide articulation and ending space. All browser clips are dry: no
reverb or delay obscures the attacks.

The new voices use sounding pitches in deliberate registers: mandolin plays the
Turkish March excerpt an octave lower; kalimba plays Greensleeves in its middle
register; celesta plays Für Elise an octave higher; recorder plays Greensleeves an
octave higher. These are arrangements, not claims about the original instrumentation.

No recorded samples, SoundFonts or measured impulse responses are instrument
sources. The models remain procedural approximations; MIDI playback uses the
receiving synthesizer. The freely retuned timpani melody is a model demonstration,
not a conventional fixed-set timpani part. These arrangements do not use the piano
sustain pedal; shared legato is not modeled. Numerical checks cannot establish
acoustic realism or replace listening.

## Rebuild efficiently

The default command rebuilds all previews. To reuse only verified matching outputs:

```sh
uv run python examples/instrument_browser.py --resume
```

For a selected group, optionally in a separate output directory:

```sh
uv run python examples/instrument_browser.py output/new-voice-check --instruments mandolin kalimba celesta recorder
```

A cache entry is reusable only when its generated score, every engine Python
module, demo recipes/data, Python/NumPy/Mido/Pydantic versions and platform match,
and the WAV, MIDI, JSON score and report hashes still match. A DSP edit invalidates
the cache even when the package version stays unchanged. Interrupted batches save
completed clips so `--resume` can finish them.

Subset builds publish only current verified previews. Unselected stale clips are
not listed, and `catalog.json` marks the build incomplete with its missing preview
IDs. Run the full `--resume` command before distributing a complete catalog.
Old files can remain on disk, but their presence alone never makes them current.

Each generated clip has a report under `reports/`; `render-cache.json` records
input/output fingerprints. The main arrangement code is
`examples/famous_music.py`. Source notes and edition credits live in
[examples/music](../examples/music/README.md). Normal generation is offline; only
the optional dataset importer downloads notation.
