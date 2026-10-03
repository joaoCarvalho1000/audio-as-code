# Piano sustain pedal

`piano` supports a binary damper pedal. Put ordered `PedalEvent(beat=..., down=True)`
and `PedalEvent(beat=..., down=False)` events on `Track.pedal`. Beats follow the
song's tempo map. Written note duration still describes how long the key is held.

```python
from audio_as_code import Note, PedalEvent, Song, Track, export_midi, render

song = Song(
    beats=4,
    tracks=[
        Track(
            name="Piano",
            instrument="piano",
            notes=[Note(pitch="C4", duration=0.5), Note(pitch="G4", start=1, duration=0.5)],
            pedal=[PedalEvent(beat=0, down=True), PedalEvent(beat=3, down=False)],
        )
    ],
)
render(song, "output/pedal.wav")
export_midi(song, "output/pedal.mid")
```

In JSON, the track field is `"pedal": [{"beat": 0, "down": true},
{"beat": 3, "down": false}]`. `down` requires a boolean. Events must have
strictly increasing finite, nonnegative beats, alternate down/up starting with
down, stay within the song, and number no more than 1,024 per track. Other
instruments reject nonempty pedal lists, including `electric_piano`. Empty pedal
lists are accepted on every instrument. Existing scores and explicit empty pedal
defaults retain their canonical score IDs, audio and MIDI output.

Pedal state changes apply before note-offs at the same beat: down is inclusive,
up is exclusive. If the pedal is down when a key is released, that voice keeps
its natural decay until the next pedal-up. A pedal left down lifts automatically
at the song end. A key still held when the pedal lifts continues until its own
written release. Pressing the pedal after a key release does not recapture that
note, even if its release tail is still sounding.

Notes actually extended by the pedal get a 0.12-second damper release after
lift. A positive track `release_seconds` replaces this default. Any explicit
note `release_seconds` takes precedence, including zero. Zero adds no tail and
uses the existing short end taper, which ends at lift. Notes not extended by the
pedal retain their existing release behavior. Release durations are seconds,
independent of tempo; pedal timing uses beats. Releases and chained track/master
effects contribute to `render_seconds` and the 300-second render guard, including
an automatic pedal lift at score end.

Repeated strikes of the same pitch create independent decaying voices. The
earlier tail continues under the new strike; there is no voice stealing or
shared vibrating-string state. This is a damper gate approximation on the
generated piano model, with no half-pedaling, sympathetic resonance, pedal noise,
or repedaling of released tails. It does not introduce samples, recordings,
SoundFonts, or measured responses.

MIDI retains written note-on/off times and exports binary CC64 values 127/0.
At a shared tick, pedal changes precede note-offs, then note-ons. An open final
pedal emits CC64=0 at the score end. MIDI timing uses 480 ticks per beat;
very close events can collapse to the same tick, keeping their order. Pedal
release sound and repeated-pitch behavior depend on the receiving synthesizer;
audio damper envelopes and effect tails are not reproduced by this export.
Overlapping written notes of the same pitch still fail MIDI validation.

`inspect_score` reports `pedal_event_count`, `pedal_auto_lift`, and
`pedal_sustained_note_count` per track, includes sustain in tail horizons, and
warns about receiver behavior and pedal tick rounding. Its polyphony values
continue to count written key intervals, excluding pedal/release/effect tails.
Inspection does not synthesize audio or establish perceptual realism.

Run `uv run python examples/piano_sustain.py` for a short original A/B phrase.
It writes dry and pedaled scores, WAVs, MIDI files, and numerical reports under
`output/piano-sustain/`. Pass `--output PATH` to choose another directory. The
phrase includes repeated notes, explicit lifts, and a final automatic lift.
Compare `dry.wav` and `pedal.wav`; numerical checks do not substitute for listening.
