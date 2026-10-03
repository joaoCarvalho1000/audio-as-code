"""Four original, fully arranged scores. Run with an optional output directory.

All time is in quarter-note beats. No external audio assets are used.
"""

from __future__ import annotations

import argparse
import inspect
import json
import math
import shutil
import subprocess
from pathlib import Path

from audio_as_code import Note, Song, Tone, Track, export_midi, get_instrument, render

# Single source of truth: section names, bar counts, and meter.
FORMS = {
    "lanterns-on-the-water": (
        3,
        [
            ("Ripples", 4),
            ("Lantern theme", 12),
            ("B minor crossing", 8),
            ("Passing lights", 8),
            ("Homeward", 12),
            ("Shore", 4),
        ],
    ),
    "copper-street": (
        4,
        [
            ("Footsteps", 4),
            ("Street theme", 8),
            ("Horn reply", 8),
            ("Side street", 8),
            ("Sax variation", 8),
            ("Stop time", 4),
            ("Home chorus", 8),
            ("Last corner", 4),
        ],
    ),
    "night-signal": (
        4,
        [
            ("Distant carrier", 8),
            ("Acquisition", 8),
            ("Transmission", 12),
            ("Lost signal", 8),
            ("Reconnection", 4),
            ("Clear channel", 12),
            ("Dawn", 4),
        ],
    ),
    "clockwork-garden": (
        3.5,
        [
            ("Winding", 4),
            ("Seven petals", 12),
            ("Glasshouse", 8),
            ("Insects", 12),
            ("Bloom", 12),
            ("Unwinding", 4),
        ],
    ),
}
DESCRIPTIONS = {
    "lanterns-on-the-water": (
        "A D-major chamber waltz: a rising lantern motif crosses into B minor, "
        "passes between winds and strings, and settles on the shore."
    ),
    "copper-street": (
        "An E-dorian street groove with clipped horn answers, a harmonic detour, "
        "sax variations and a stop-time return."
    ),
    "night-signal": (
        "An F-minor electronic transmission that grows from isolated pulses into "
        "interlocking sequences, loses its carrier and reconnects."
    ),
    "clockwork-garden": (
        "A mallet-and-harp miniature in seven eighths (2+2+3), interrupted by a "
        "slow glasshouse chorale and playful antiphonal figures."
    ),
}


def sections(piece_id):
    meter, form = FORMS[piece_id]
    result, beat = [], 0.0
    for name, bars in form:
        result.append(dict(name=name, start_beat=beat, end_beat=beat + meter * bars))
        beat += meter * bars
    return result


def bars(piece_id):
    meter, _ = FORMS[piece_id]
    for section_index, section in enumerate(sections(piece_id)):
        count = round((section["end_beat"] - section["start_beat"]) / meter)
        for local in range(count):
            yield section_index, local, count, section["start_beat"] + local * meter


class Arrangement:
    """Explicit note placement, with deterministic velocity shaping and MIDI-safe gates."""

    def __init__(self, specs):
        self.specs = specs
        self.notes = {name: [] for name in specs}

    def note(self, voice, pitch, start, duration, velocity=0.65):
        self.notes[voice].append(
            Note(pitch=pitch, start=start, duration=duration, velocity=velocity)
        )

    def chord(self, voice, pitches, start, duration, velocity=0.55):
        for pitch in pitches:
            self.note(voice, pitch, start, duration, velocity)

    def phrase(self, voice, pitches, at, step=0.5, gate=0.85, velocity=0.65):
        for index, pitch in enumerate(pitches):
            if pitch is not None:
                self.note(
                    voice,
                    pitch,
                    at + index * step,
                    step * gate,
                    velocity * (1 if index % 2 == 0 else 0.90),
                )

    def cadence(self, piece_id, voices):
        """Reserve the final bar for a tonic arrival and its written decay."""
        meter = FORMS[piece_id][0]
        at = sections(piece_id)[-1]["end_beat"] - meter
        for name in self.notes:
            self.notes[name] = [n for n in self.notes[name] if n.start < at]
        for name, pitches in voices.items():
            self.chord(name, pitches, at, meter - 0.15, 0.43)

    def song(self, piece_id, bpm, seed):
        tracks = []
        for name, (instrument, gain, pan, brightness) in self.specs.items():
            # Retriggering a pitch deliberately releases its previous gate.
            notes = sorted(self.notes[name], key=lambda n: (n.start, n.pitch))
            next_start = {}
            clean = []
            for note in reversed(notes):
                end = min(
                    note.start + note.duration,
                    next_start.get(note.pitch, float("inf")),
                    sections(piece_id)[-1]["end_beat"],
                )
                if end > note.start:
                    clean.append(note.model_copy(update={"duration": end - note.start}))
                next_start[note.pitch] = note.start
            tracks.append(
                Track(
                    name=name,
                    instrument=instrument,
                    gain=gain,
                    pan=pan,
                    tone=Tone(brightness=brightness)
                    if get_instrument(instrument).tone_controls
                    else None,
                    notes=tuple(reversed(clean)),
                )
            )
        return Song(
            title=piece_id.replace("-", " ").title(),
            bpm=bpm,
            beats=sections(piece_id)[-1]["end_beat"],
            seed=seed,
            master_gain=1.0 if piece_id in ("lanterns-on-the-water", "clockwork-garden") else 0.72,
            tracks=tuple(tracks),
        )


def lanterns_on_the_water():
    a = Arrangement(
        {
            "Piano ripples": ("piano", 0.992, -0.30, 0.40),
            "Flute lantern": ("flute", 0.32, -0.12, 0.38),
            "Clarinet answer": ("clarinet", 0.352, 0.25, 0.42),
            "Violin light": ("violin", 0.256, -0.45, 0.38),
            "Cello crossing": ("cello", 0.432, 0.18, 0.40),
        }
    )
    major = [
        (50, [62, 66, 69]),
        (57, [61, 64, 69]),
        (59, [62, 66, 71]),
        (55, [62, 67, 71]),
        (52, [64, 67, 71]),
        (57, [61, 67, 69]),
    ]
    minor = [(47, [62, 66, 71]), (54, [61, 66, 69]), (55, [62, 67, 71]), (54, [61, 66, 70])]
    for s, b, _count, at in bars("lanterns-on-the-water"):
        root, chord = (minor if s == 2 else major)[b % (4 if s == 2 else 6)]
        if s == 5:
            root, chord = [
                (55, [62, 67, 71]),
                (57, [61, 67, 69]),
                (50, [62, 66, 69]),
                (50, [62, 66, 69]),
            ][b]
        level = 0.48 if s in (0, 5) else 0.64
        # excerpt-start
        # Six ripples per waltz bar; voices enter and leave around this foundation.
        a.phrase(
            "Piano ripples",
            [root, chord[0], chord[1], chord[2], chord[1], chord[0]],
            at,
            gate=2.1,
            velocity=level,
        )
        # excerpt-end
        if s != 2:
            a.note("Cello crossing", root - 12, at, 2.8, level)
        if s in (1, 4):
            motif = [
                [chord[2] + 12, chord[0] + 12, chord[1] + 12, None, chord[0] + 12, chord[2]],
                [chord[1] + 12, None, chord[0] + 12, chord[2], chord[1], None],
                [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[1] + 12, None, chord[0] + 12],
                [chord[2], chord[0] + 12, None, chord[1] + 12, chord[0] + 12, None],
            ][b % 4]
            a.phrase("Flute lantern", motif, at, velocity=0.63 if s == 1 else 0.71)
            if b % 4 >= 2:
                a.phrase(
                    "Clarinet answer",
                    [chord[1], None, chord[2], chord[0] + 12],
                    at + 1,
                    velocity=0.53,
                )
            if s == 4:
                a.note("Violin light", chord[b % 3], at, 2.75, 0.47)
        elif s == 2:
            a.phrase(
                "Cello crossing",
                [root, root + 7, root + 12, root + 10],
                at,
                step=0.75,
                gate=0.94,
                velocity=0.72,
            )
            if b % 2:
                a.note("Clarinet answer", chord[1], at + 1, 1.8, 0.5)
        elif s == 3:
            voice = ["Flute lantern", "Violin light", "Clarinet answer", "Cello crossing"][b % 4]
            shift = -12 if voice == "Cello crossing" else 0
            a.phrase(
                voice,
                [chord[2] + shift, chord[0] + 12 + shift, chord[1] + 12 + shift],
                at,
                step=0.75,
                gate=0.93,
                velocity=0.64,
            )
        elif s == 5:
            a.note("Flute lantern", 74 if b < 2 else 78, at, 2.7, 0.43 - b * 0.04)
    a.cadence(
        "lanterns-on-the-water",
        {"Piano ripples": [50, 62, 66, 69], "Cello crossing": [38], "Flute lantern": [74]},
    )
    return a.song("lanterns-on-the-water", 84, 2101)


def copper_street():
    a = Arrangement(
        {
            "Bass walk": ("bass_guitar", 0.62, 0, 0.50),
            "Electric piano comp": ("electric_piano", 0.43, -0.30, 0.45),
            "Guitar chops": ("electric_guitar", 0.32, 0.36, 0.48),
            "Sax storyteller": ("saxophone", 0.26, -0.16, 0.52),
            "Trumpet reply": ("trumpet", 0.20, 0.22, 0.45),
            "Trombone floor": ("trombone", 0.19, -0.32, 0.45),
            "Kick": ("kick", 0.58, 0, 0.5),
            "Snare": ("snare", 0.48, -0.08, 0.5),
            "Hats": ("hat", 0.42, 0.32, 0.5),
        }
    )
    harmony = [
        (40, [62, 66, 67, 71]),
        (45, [61, 64, 67, 71]),
        (40, [62, 66, 67, 71]),
        (47, [63, 66, 69, 73]),
    ]
    bridge = [
        (48, [60, 64, 67, 71]),
        (47, [62, 66, 69, 71]),
        (45, [60, 64, 67, 71]),
        (50, [60, 66, 69, 74]),
        (48, [60, 64, 67, 71]),
        (47, [62, 66, 69, 71]),
        (42, [61, 64, 66, 70]),
        (47, [63, 66, 69, 71]),
    ]
    for s, b, _count, at in bars("copper-street"):
        root, chord = bridge[b] if s == 3 else harmony[b % 4]
        last = s == 7 and b >= 2
        stop = s == 5 or last
        a.phrase(
            "Bass walk",
            [root, None, root + 12, root + 7, None, root + 10, root + 12, root + 11]
            if not stop
            else [root, None, None, None, root + 7],
            at,
            gate=0.72,
            velocity=0.78,
        )
        for offset in [0] if stop else [0.75, 2.5]:
            a.chord("Electric piano comp", chord, at + offset, 0.6, 0.59)
        if s not in (0, 3, 5, 7):
            for offset in [1.5, 3.5]:
                a.chord("Guitar chops", chord[1:3], at + offset, 0.32, 0.58)
        for offset in [0] if stop else [0, 1.75, 2.5]:
            a.note("Kick", 36, at + offset, 0.25, 0.84)
        if not stop:
            for offset in [1.03, 3.03]:
                a.note("Snare", 38, at + offset, 0.22, 0.70)
            a.phrase("Hats", [42] * 8, at, gate=0.17, velocity=0.54)
        if s in (1, 2, 6):
            pitches = (
                [71, 74, None, 76, 74, 71, 69, None]
                if b % 2 == 0
                else [67, None, 69, 71, None, 66, 64, None]
            )
            a.phrase("Sax storyteller", pitches, at + 0.03, velocity=0.68)
            # excerpt-start
            # The reply occupies the second half of the phrase, leaving the sax room.
            if s in (2, 6) and b % 2:
                a.phrase(
                    "Trumpet reply",
                    [chord[2] + 12, chord[1] + 12, chord[0] + 12],
                    at + 2,
                    velocity=0.62,
                )
                a.phrase("Trombone floor", [chord[2], chord[1], chord[0]], at + 2, velocity=0.58)
            # excerpt-end
        elif s == 4:
            scale = [64, 66, 67, 69, 71, 73, 74, 76]
            phrase = [scale[(b * 2 + i + (i // 3)) % 8] for i in range(8)]
            phrase[3 if b % 2 else 6] = None
            a.phrase("Sax storyteller", phrase, at, velocity=0.70)
        elif s in (3, 5):
            a.phrase(
                "Sax storyteller",
                [chord[3], None, chord[2], chord[1]],
                at,
                step=1,
                gate=0.8,
                velocity=0.63,
            )
        elif last:
            a.chord("Electric piano comp", [52, 59, 66, 67], at + 1, 2.8, 0.40)
    a.cadence(
        "copper-street",
        {"Bass walk": [40], "Electric piano comp": [55, 59, 62, 66], "Sax storyteller": [64]},
    )
    return a.song("copper-street", 104, 2102)


def night_signal():
    a = Arrangement(
        {
            "Horizon": ("pad", 0.10, -0.35, 0.30),
            "Clock pulse": ("pluck", 0.27, 0.25, 0.48),
            "Sub carrier": ("sine", 0.20, 0, 0.5),
            "Bass code": ("bass", 0.30, 0, 0.42),
            "Lead transmission": ("synthesizer", 0.16, -0.10, 0.45),
            "Lost voice": ("theremin", 0.12, 0.25, 0.35),
            "Signal": ("triangle", 0.18, -0.42, 0.42),
            "Signal echo": ("triangle", 0.07, 0.50, 0.35),
            "Machine": ("drum_machine", 0.54, 0, 0.52),
        }
    )
    harmony = [(29, [60, 65, 68]), (37, [61, 65, 68]), (32, [60, 63, 68]), (36, [60, 64, 67])]
    for s, b, _count, at in bars("night-signal"):
        root, chord = harmony[(b // 2) % 4]
        if s == 5 and b % 8 >= 4:
            root, chord = [(34, [61, 65, 70]), (36, [60, 64, 67])][(b // 2) % 2]
        a.chord("Horizon", chord, at, 3.9, 0.48 if s in (0, 3, 6) else 0.58)
        a.note("Sub carrier", root, at, 3.7 if s == 3 else 1.6, 0.65)
        if s in (1, 2, 4, 5):
            # excerpt-start
            # The second transmission reverses the arpeggio and shifts its accents.
            arp = [chord[0], chord[2], chord[1], chord[2]]
            if s == 5:
                arp = list(reversed(arp))
            a.phrase(
                "Clock pulse", (arp * 4), at, step=0.25, gate=0.65, velocity=0.48 + 0.02 * (b % 4)
            )
            # excerpt-end
        if s in (2, 5):
            a.phrase(
                "Bass code",
                [root + 12, None, root + 12, root + 19, None, root + 12, root + 15, None],
                at,
                gate=0.63,
                velocity=0.72,
            )
            lead = [
                chord[2] + 12,
                None,
                chord[1] + 12,
                chord[0] + 12,
                None,
                chord[2] + 12,
                chord[1] + 12,
                None,
            ]
            if b % 4 < 3:
                a.phrase(
                    "Lead transmission",
                    lead if b % 2 == 0 else lead[4:] + lead[:4],
                    at,
                    velocity=0.64,
                )
        if s == 3:
            a.phrase(
                "Lost voice",
                [chord[2] + 12, chord[1] + 12, chord[0] + 12],
                at,
                step=1.25,
                gate=0.94,
                velocity=0.56,
            )
        if s in (0, 1, 4, 6) and b % 2 == 0:
            a.phrase("Signal", [77, None, 84, 80], at, step=0.5, velocity=0.51)
            a.phrase("Signal echo", [77, None, 84, 80], at + 0.75, step=0.5, velocity=0.45)
        if s in (1, 2, 4, 5):
            for tick in range(8):
                a.note("Machine", 42, at + tick * 0.5, 0.07, 0.35 if tick % 2 else 0.52)
            for offset in [0, 2] if s == 1 else [0, 1, 2, 3]:
                a.note("Machine", 36, at + offset, 0.28, 0.85)
            for offset in [1, 3]:
                a.note("Machine", 38, at + offset, 0.18, 0.63)
            if s == 4:
                for tick in range(b + 1):
                    a.note("Machine", 38, at + 3.25 + tick * 0.125, 0.08, 0.4 + tick * 0.05)
    a.cadence("night-signal", {"Horizon": [60, 65, 68], "Sub carrier": [29], "Signal": [77]})
    return a.song("night-signal", 120, 2103)


def clockwork_garden():
    a = Arrangement(
        {
            "Marimba gears": ("marimba", 0.52, -0.3, 0.40),
            "Harp tendrils": ("harp", 0.559, 0.32, 0.42),
            "Vibraphone petals": ("vibraphone", 0.377, -0.1, 0.42),
            "Glockenspiel dew": ("glockenspiel", 0.247, 0.42, 0.38),
            "Xylophone insects": ("xylophone", 0.377, -0.42, 0.38),
            "Bell glasshouse": ("bell", 0.182, 0.12, 0.30),
            "Timpani roots": ("timpani", 0.338, 0, 0.35),
            "Bongos": ("bongos", 0.299, -0.2, 0.40),
        }
    )
    harmony = [
        (48, [60, 64, 67, 71]),
        (50, [62, 65, 69, 72]),
        (45, [60, 64, 69, 71]),
        (55, [59, 62, 67, 69]),
    ]
    for s, b, _count, at in bars("clockwork-garden"):
        root, chord = harmony[b % 4]
        if s == 2:
            root, chord = [(53, [60, 65, 69, 72]), (52, [59, 64, 67, 71])][b % 2]
        if s != 2:
            # excerpt-start
            # Seven eighths grouped 2+2+3: lower notes mark the three group starts.
            a.phrase(
                "Marimba gears",
                [root, chord[0], root + 7, chord[1], root + 12, chord[2], chord[1]],
                at,
                gate=1.3,
                velocity=0.58 if s != 5 else 0.40,
            )
            # excerpt-end
        a.phrase("Harp tendrils", chord, at, step=0.75, gate=1.5, velocity=0.48)
        if s in (1, 4):
            tune = [chord[2] + 12, None, chord[1] + 12, chord[0] + 12, None, chord[3], None]
            if b % 4 == 3:
                tune = [chord[1] + 12, chord[0] + 12, None, chord[3], chord[2], None, None]
            a.phrase("Vibraphone petals", tune, at, gate=1.8, velocity=0.62)
            if s == 4 and b % 2:
                a.phrase(
                    "Glockenspiel dew",
                    [chord[0] + 24, None, chord[1] + 24],
                    at + 1.5,
                    gate=1.4,
                    velocity=0.40,
                )
        elif s == 2:
            a.chord("Bell glasshouse", chord[:3], at, 3.4, 0.40)
            a.note("Vibraphone petals", chord[3], at + 1, 2.4, 0.54)
        elif s == 3:
            voice = "Xylophone insects" if b % 2 == 0 else "Glockenspiel dew"
            a.phrase(
                voice,
                [
                    chord[0] + 12,
                    chord[1] + 12,
                    None,
                    chord[2] + 12,
                    chord[3] + 12,
                    chord[2] + 12,
                    None,
                ],
                at,
                gate=0.8,
                velocity=0.52,
            )
        if s in (1, 3, 4):
            for offset in [0, 1, 2]:
                a.note("Bongos", 60, at + offset, 0.22, 0.52 if offset == 0 else 0.40)
        if b % 4 == 0:
            a.note("Timpani roots", root - 12, at, 1.7, 0.58)
        if s == 5:
            a.note("Vibraphone petals", 72 if b < 3 else 76, at, 3.3, 0.43 - b * 0.05)
    a.cadence(
        "clockwork-garden",
        {"Harp tendrils": [48, 60, 64, 67], "Vibraphone petals": [72, 76], "Timpani roots": [36]},
    )
    return a.song("clockwork-garden", 112, 2104)


BUILDERS = dict(
    zip(FORMS, [lanterns_on_the_water, copper_street, night_signal, clockwork_garden], strict=True)
)


def export_all(destination, *, scores_only=False, ffmpeg=None):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    # Asset writes invalidate a prior listening package, including score-only edits.
    # Publish a new listening manifest only after every render/preview succeeds.
    (destination / "manifest.json").unlink(missing_ok=True)
    source = Path(__file__).resolve()
    copied_source = destination / "full_compositions.py"
    if source != copied_source.resolve():
        shutil.copyfile(source, copied_source)
    pieces = []
    for piece_id, builder in BUILDERS.items():
        song = builder()
        song.save(destination / f"{piece_id}.json")
        export_midi(song, destination / f"{piece_id}.mid")
        body = inspect.getsource(builder)
        excerpt = body.split("# excerpt-start\n")[1].split("# excerpt-end")[0]
        piece = dict(
            id=piece_id,
            title=song.title,
            description=DESCRIPTIONS[piece_id],
            bpm=song.bpm,
            beats=song.beats,
            duration_seconds=song.seconds,
            instruments=[t.instrument for t in song.tracks],
            sections=sections(piece_id),
            wav=f"{piece_id}.wav",
            midi=f"{piece_id}.mid",
            score=f"{piece_id}.json",
            source="full_compositions.py",
            code_excerpt=inspect.cleandoc(excerpt),
            source_function=builder.__name__,
            seed=song.seed,
            sample_rate=song.sample_rate,
            tracks=len(song.tracks),
            notes=sum(len(t.notes) for t in song.tracks),
        )
        if not scores_only:
            print(f"Rendering {piece_id} ({song.seconds:.1f}s)", flush=True)
            report = render(song, destination / piece["wav"], normalize=False)
            if (
                report["wav"]["full_scale_samples"]
                or report["wav"]["silent"]
                or not all(math.isfinite(report["audio"][key]) for key in ("peak", "rms"))
            ):
                raise RuntimeError(f"Invalid, silent or clipped output: {piece_id}")
            piece.update(levels=report["wav"], warnings=report["warnings"])
            (destination / f"{piece_id}.report.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8"
            )
            if ffmpeg:
                preview = f"{piece_id}.mp3"
                subprocess.run(
                    [
                        str(ffmpeg),
                        "-v",
                        "error",
                        "-y",
                        "-i",
                        str(destination / piece["wav"]),
                        "-codec:a",
                        "libmp3lame",
                        "-b:a",
                        "192k",
                        str(destination / preview),
                    ],
                    check=True,
                )
                piece["preview"] = preview
        pieces.append(piece)
    # Only completed renders are published as the listening manifest.
    name = "scores-manifest.json" if scores_only else "manifest.json"
    (destination / name).write_text(
        json.dumps({"pieces": pieces}, indent=2) + "\n", encoding="utf-8"
    )
    return pieces


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", default="output/full-compositions")
    parser.add_argument("--scores-only", action="store_true")
    parser.add_argument("--ffmpeg", help="Optional FFmpeg executable for 192 kbps MP3 previews")
    args = parser.parse_args()
    export_all(args.output, scores_only=args.scores_only, ffmpeg=args.ffmpeg)
