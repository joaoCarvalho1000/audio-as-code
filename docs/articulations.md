# Bowed-string and wind articulations

This page covers `soft`/`accented` held-source gestures. The 0.3.0 electronic
expansion also supports acid-bass `accented`, bass-guitar `slap`/`pop`/`muted`, and
electric-guitar `muted`; see [electronic performance options](electronic-instruments.md).

Optional `articulation` changes how a held source starts and stops. It accepts
`"soft"` or `"accented"` on a track or individual note. Supported instruments are
`violin`, `viola`, `cello`, `double_bass`, `flute`, `clarinet`, `saxophone`, `oboe`,
`bassoon`, `trumpet`, `trombone`, `french_horn`, and `tuba`. Instruments without the
requested value in their catalog, including `recorder`, reject it. Discover support through each
instrument's `articulations` list in `aac instruments` or `get_instrument()`.

```json
{
  "name": "Cello phrase",
  "instrument": "cello",
  "articulation": "soft",
  "release_seconds": 0.25,
  "notes": [
    {"pitch": "C3", "start": 0, "duration": 2, "velocity": 0.7},
    {"pitch": "G3", "start": 2.5, "duration": 1, "velocity": 0.7,
     "articulation": "accented"}
  ]
}
```

A note value overrides the track. Omitted or `null` note articulation inherits
the track; omitted or `null` track articulation selects the default gesture.
To mix default and articulated notes, leave the track field unset and specify
only the notes to change. Articulation does not shorten the written duration,
change velocity, transpose the note, or connect it to its neighbors.

| Gesture | Harmonic onset | Noise onset |
| --- | --- | --- |
| `soft` | Slower fundamental buildup, with further delay and temporary suppression of upper harmonics | Bow or breath noise rises gradually with the instrument's attack |
| `accented` | Faster buildup and a brief emphasis of upper harmonics | A short increase of the instrument's existing colored bow or breath excitation |

Both gestures return toward the instrument's existing sustained spectrum. A
double bass still takes longer to speak than a violin; a clarinet retains its
odd-harmonic emphasis. The gesture uses the existing body/formant response,
brightness, velocity and vibrato controls. It is not just a volume multiplier.
Very short soft notes can end before their upper spectrum develops.

## Release behavior

In version 0.3.0, when a supported note has positive `release_seconds`, its fundamental,
upper harmonics and excitation noise begin separate exponential decays at
note-off. Upper harmonics disappear faster than the fundamental, and noise has
its own instrument-specific decay. For bowed voices, fundamental decay time
constants range from 65 ms for violin to 130 ms for double bass; wind constants
range from 40 to 105 ms. These are designed coefficients, not measured decay
times. They are time constants, not times to silence.

The existing cosine release fade still reaches zero at the requested endpoint.
`release_seconds` allocates the tail and controls this fade; it does not stretch
the source decay constants. A longer tail can therefore mostly contain silence.
With zero release, the original fade remains inside the written duration and
there is no additional source-release interval. Release does not begin early on
short notes. Default, soft and accented use the same release law for a given instrument.
In the published 0.2.0 engine this separate source decay applies only to soft/accented notes.

## Model limits and comparison

These are designed gestures for harmonic source/filter models. They do not solve
nonlinear bow friction, bow reversal, reed/tongue contact, a jet or lip coupled
to a bore, or a freely ringing instrument body after excitation stops. There is
no legato connection, pizzicato switch or recorded articulation source. Score
IDs remain stable; synthesis refinements can change audio between engine versions.
Pin the engine and runtime for repeatable seeded audio. MIDI keeps
the notes and velocity but does not encode these synthesis gestures.

Run `uv run python examples/articulations.py`, then open
`output/articulations/index.html`. It compares original, soft and accented
versions of the same phrase, with matched whole-clip RMS levels and no effects.
JSON scores and raw render measurements accompany the WAVs; the WAVs alone have
the documented comparison gain applied. Listen to attacks, sustained timbre and
note-offs. Matching RMS is not a perceptual loudness model, and numerical tests
of tuning, stability and spectral change do not establish acoustic realism.
