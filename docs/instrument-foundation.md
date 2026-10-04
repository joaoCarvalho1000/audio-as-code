# Instrument foundation

Audio as Code generates instrument sounds from equations. No recordings, sample libraries, SoundFonts, measured impulse responses, or external synthesis services are used. All 49 catalog entries are playable prototypes, including the composite drum-machine kit. **Available means renderable, not calibrated or perceptually realistic.** See [orchestra models and limits](orchestra.md).

## Musical families

Families describe how a musician finds instruments. These practical groups are not mutually exclusive acoustic classifications: a piano has a keyboard interface and vibrating strings; timpani is both a drum and pitched percussion. Each entry has one primary family.

| Family ID | Playable IDs |
| --- | --- |
| `plucked_strings` | `guitar`, `electric_guitar`, `bass_guitar`, `harp`, `ukulele`, `banjo`, `mandolin` |
| `bowed_strings` | `violin`, `viola`, `cello`, `double_bass` |
| `keyboards` | `piano`, `electric_piano`, `organ`, `harpsichord`, `celesta` |
| `woodwinds` | `flute`, `clarinet`, `saxophone`, `oboe`, `bassoon`, `recorder` |
| `brass` | `trumpet`, `trombone`, `french_horn`, `tuba` |
| `percussion` | `kick`, `snare`, `hat`, `toms`, `cymbal`, `congas`, `bongos`, `tambourine` |
| `pitched_percussion` | `marimba`, `xylophone`, `vibraphone`, `glockenspiel`, `bell`, `timpani`, `kalimba` |
| `electronic` | `sine`, `triangle`, `pluck`, `bass`, `pad`, `synthesizer`, `drum_machine`, `theremin` |

`bass` remains the original synth bass; `bass_guitar` is a modal string/pickup approximation. `guitar` remains the original damped-string model. Existing IDs retain their meanings.

The [extended instrument models](extended-instruments.md) add paired mandolin
strings, kalimba lamellae, celesta bars, and a recorder jet-spectrum approximation.
These have distinct generated models, controls and useful registers; their MIDI
programs are approximate interchange mappings, not equivalent instrument sounds.

## Shared synthesis-engine groups

Groups describe the modeled sound mechanism; they do not promise the same simulation fidelity. A spectral source/filter approximation and a nonlinear physical simulation are different algorithms. Catalog descriptions identify the actual implementation.

| Engine ID | Current implementation | Still outside the model |
| --- | --- | --- |
| `string` | Original guitar delay loop; plucked/struck string modes; simplified coupled piano unisons and mandolin pairs; bowed harmonic sources with complex body bands/noise | Nonlinear bow friction, full string/body coupling, sympathetic strings |
| `air_column` | Instrument-specific harmonic sources, formants, breath and onset behavior | Coupled nonlinear jet/reed/lip and bore solvers |
| `modal` | Decaying bars, bells, tines, and generated metal-mode collisions | Calibrated geometries, nonlinear plates, pickup circuits |
| `membrane` | Designed drumhead modes, strike transients, and tension relaxation | Shell/kettle air coupling and spatial head simulation |
| `electronic` | Harmonic oscillators, seeded percussion, a generated kit, detuning and glide | Arbitrary synthesis graphs and continuous tone/pitch automation |

Kick/snare/hat retain their electronic-engine classification. The new membrane voices do not relabel those existing synthetic drums as physical models.

## Discovery contract

```sh
uv run aac instruments
uv run aac instruments --family woodwinds
uv run aac instruments --engine modal
uv run aac instruments --all
```

Discovery defaults to available entries. `--all` also includes any future planned entries; none remain in the current 49-entry catalog. Family and engine filters can be combined. The JSON response includes:

- `catalog_version`, `synthesis_policy` (`code_only`), families, and engine definitions.
- Instrument IDs, names, availability, and truthful descriptions.
- Supported `tone_controls`, optional `default_tone` pairs, and default natural decay.
- Supported optional `articulations`; an empty list means no articulation switches.
- Approximate MIDI program/percussion mappings and a suggested `preview_pitch`.
- Counts for the selected instruments, split into available and planned.

`default_tone` is a sequence of `[control, value]` pairs. Brightness defaults to 0.5. Original guitar defaults to pluck position 0.22. `default_decay_seconds` remains a separate field. A missing default is not an invitation to pass an unsupported control.

```python
from audio_as_code import get_instrument, instrument_catalog, list_instruments

flute = get_instrument("flute")
print(flute.description, flute.tone_controls, dict(flute.default_tone))
resonators = list_instruments(engine="modal")
catalog = instrument_catalog(include_planned=True)
```

Metadata records are immutable. Catalog dictionaries are independent JSON-serializable copies. The score schema lists playable IDs; unknown or future planned IDs produce validation errors instead of fallback sounds.

## Implementation boundary

`instruments.py` owns discovery, capabilities, defaults, and MIDI mapping.
`physical.py` implements the original guitar/bar/bell algorithms. `orchestra.py`
implements the additional modal and source/filter models, including the
[piano and bowed strings](synthesis.md#piano-and-bowed-strings); its immutable
coefficients live in `_orchestra_profiles.py`. `extended.py` implements mandolin,
kalimba, celesta and recorder. `_voices.py` dispatches these engines, routes the
generated kit, and applies note envelopes. `render.py` schedules note gates and
handles velocity/gain/pan and mixing. `model.py` validates instrument-specific
controls and kit pitches.

For a new entry: implement its synthesis, describe the algorithm and limitations, register only controls that affect it, add the typed ID and MIDI mapping, regenerate the schema, test numerical behavior, and regenerate the instrument browser. Listen before making claims about realism. Planned/available distinction remains part of the API for future additions.

The renderer supports optional [tempo changes, gain/pan automation, generated effects
and note-release envelopes](expressive-engine.md). Bowed strings and selected winds
also offer [soft and accented source gestures](articulations.md), including separate
harmonic/noise decays during release. These are source/filter approximations,
not a physically coupled note-off transition.

Piano additionally accepts [binary pedal events](piano-sustain.md). They extend
independent note gates until lift and export MIDI CC64, without half-pedaling
or cross-note sympathetic resonance.

The next fidelity work is deeper coupling and nonlinear excitation, more articulations,
physical sustain/release transitions, continuous tone/pitch performance curves, and
perceptual evaluation. A broader playable catalog does not complete those tasks.
