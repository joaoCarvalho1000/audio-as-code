"""Render five contrasting compositions: uv run python examples/showcase.py."""

from __future__ import annotations

import html
import json
from pathlib import Path

from audio_as_code import Note, Pattern, Song, Track, export_midi, render


def line(pitches, *, start=0, step=0.5, gate=0.7, velocity=0.7, swing=0) -> tuple[Note, ...]:
    """Place a phrase; swing delays alternate steps by an explicit beat offset."""
    phrase = Pattern.sequence(pitches, step=step, gate=gate, velocity=velocity)
    return tuple(
        Note(
            pitch=note.pitch,
            start=start + note.start + (swing if round(note.start / step) % 2 else 0),
            duration=note.duration,
            velocity=note.velocity,
        )
        for note in phrase.notes
    )


def chord(pitches, start, duration, velocity=0.6) -> tuple[Note, ...]:
    return tuple(
        Note(pitch=pitch, start=start, duration=duration, velocity=velocity) for pitch in pitches
    )


def after_hours() -> Song:
    """Swung eighths, minor ninths, laid-back bass, and a sparse plucked melody."""
    voicings = [
        ["C4", "Eb4", "G4", "Bb4", "D5"],
        ["Ab3", "C4", "Eb4", "G4", "Bb4"],
        ["Eb3", "G3", "Bb3", "D4", "F4"],
        ["Bb3", "D4", "F4", "G4", "C5"],
    ]
    roots = ["C2", "Ab1", "Eb2", "Bb1"]
    fifths = ["G2", "Eb2", "Bb2", "F2"]
    motifs = [
        ["G4", None, "Bb4", "D5", None, "C5", "Bb4", None],
        ["G4", "Eb4", None, "C5", "Bb4", None, "G4", None],
        ["F4", None, "G4", "Bb4", "D5", None, "Bb4", "G4"],
        ["F4", "G4", None, "D5", "C5", "Bb4", None, "G4"],
    ]
    pads, bass, lead, kick, snare, hats = [], [], [], [], [], []
    for bar in range(8):
        at = bar * 4
        index = bar // 2
        pads.extend(chord(voicings[index], at + 0.08, 3.6, 0.5))
        bass.extend(
            line(
                [roots[index], None, fifths[index], roots[index]],
                start=at,
                step=1,
                gate=0.62,
                velocity=0.8,
            )
        )
        if bar % 2 or bar == 6:
            lead.extend(line(motifs[index], start=at, gate=0.54, swing=0.08))
        for offset, velocity in [(0, 0.9), (1.7, 0.65), (2.5, 0.78)]:
            kick.append(Note(pitch=36, start=at + offset, duration=0.34, velocity=velocity))
        for offset in [1.04, 3.04]:
            snare.append(Note(pitch=38, start=at + offset, duration=0.22, velocity=0.7))
        for tick in range(8):
            hats.append(
                Note(
                    pitch=42,
                    start=at + tick / 2 + (0.08 if tick % 2 else 0),
                    duration=0.08,
                    velocity=0.42 if tick % 2 else 0.6,
                )
            )
    pads.extend(chord(voicings[0], 32, 1.8, 0.4))
    bass.extend(chord(["C2"], 32, 1.5, 0.65))
    lead.extend(chord(["G4", "D5"], 32, 1.3, 0.5))
    return Song(
        title="After Hours",
        bpm=80,
        beats=34,
        seed=11,
        tracks=[
            Track(name="Ninth chords", instrument="pad", gain=0.22, pan=-0.25, notes=pads),
            Track(name="Round bass", instrument="bass", gain=0.7, notes=bass),
            Track(name="Late melody", instrument="pluck", gain=0.5, pan=0.25, notes=lead),
            Track(name="Loose kick", instrument="kick", gain=0.85, notes=kick),
            Track(name="Backbeat", instrument="snare", gain=0.4, pan=-0.1, notes=snare),
            Track(name="Swung hats", instrument="hat", gain=0.34, pan=0.35, notes=hats),
        ],
    )


def neon_circuit() -> Song:
    """Four-on-the-floor groove with offbeat stabs, a breakdown, and a final drop."""
    roots = ["A1", "F2", "C2", "G1"]
    fifths = ["E2", "C3", "G2", "D2"]
    voicings = [["A3", "C4", "E4"], ["F3", "A3", "C4"], ["C4", "E4", "G4"], ["G3", "B3", "D4"]]
    arps = [
        ["A4", "C5", "E5", "C5"],
        ["A4", "C5", "F5", "C5"],
        ["G4", "C5", "E5", "C5"],
        ["G4", "B4", "D5", "B4"],
    ]
    bass, stabs, arp, kick, snare, hats = [], [], [], [], [], []
    for bar in range(12):
        at, index = bar * 4, bar % 4
        breakdown = bar in (6, 7)
        if not breakdown:
            bass.extend(
                line(
                    [
                        roots[index],
                        roots[index],
                        None,
                        fifths[index],
                        roots[index],
                        None,
                        fifths[index],
                        roots[index],
                    ],
                    start=at + 0.25,
                    gate=0.38,
                    velocity=0.86,
                )
            )
            kick.extend(line([36] * 4, start=at, step=1, gate=0.45, velocity=0.96))
            snare.extend(line([None, 38, None, 38], start=at, step=1, gate=0.28))
        for offset in [0.5, 1.5, 2.5, 3.5]:
            stabs.extend(chord(voicings[index], at + offset, 0.28, 0.68))
        if bar >= 2:
            arp.extend(
                line(arps[index] * 2, start=at, gate=0.45, velocity=0.42 if breakdown else 0.62)
            )
        if bar >= 1:
            for tick in range(8):
                hats.append(
                    Note(
                        pitch=42,
                        start=at + tick / 2,
                        duration=0.09,
                        velocity=0.72 if tick % 2 else 0.3,
                    )
                )
        if bar == 7:
            for tick in range(8):
                snare.append(
                    Note(
                        pitch=38,
                        start=at + 2 + tick / 4,
                        duration=0.18,
                        velocity=0.25 + tick * 0.07,
                    )
                )
    stabs.extend(chord(voicings[0], 48, 1.5, 0.6))
    bass.extend(chord(["A1"], 48, 1.4, 0.8))
    kick.extend(chord([36], 48, 0.6, 0.9))
    return Song(
        title="Neon Circuit",
        bpm=128,
        beats=50,
        seed=22,
        tracks=[
            Track(name="Driving bass", instrument="bass", gain=0.7, notes=bass),
            Track(name="Offbeat chords", instrument="triangle", gain=0.31, pan=-0.25, notes=stabs),
            Track(name="Neon arpeggio", instrument="pluck", gain=0.44, pan=0.3, notes=arp),
            Track(name="Four on the floor", instrument="kick", gain=0.95, notes=kick),
            Track(name="Snare and build", instrument="snare", gain=0.46, notes=snare),
            Track(name="Open rhythm", instrument="hat", gain=0.38, pan=0.25, notes=hats),
        ],
    )


def slow_orbit() -> Song:
    """Beatless harmony with staggered chord entrances and quiet, notated echoes."""
    voicings = [
        ["E3", "B3", "F#4", "G#4"],
        ["C#3", "G#3", "D#4", "E4"],
        ["A2", "E3", "B3", "C#4"],
        ["E3", "B3", "E4", "G#4"],
    ]
    pads, low, chimes, echoes = [], [], [], []
    for section, pitches in enumerate(voicings):
        at = section * 6
        for voice, pitch in enumerate(pitches):
            delay = voice * 0.18
            pads.append(
                Note(
                    pitch=pitch,
                    start=at + delay,
                    duration=5.85 - delay,
                    velocity=0.46 - voice * 0.035,
                )
            )
        low.append(
            Note(pitch=["E2", "C#2", "A1", "E2"][section], start=at, duration=5.85, velocity=0.5)
        )
        for delay, pitch in [
            (1.1, ["B5", "G#5", "E5", "B5"][section]),
            (3.6, ["F#5", "D#5", "B4", "E5"][section]),
        ]:
            chimes.append(Note(pitch=pitch, start=at + delay, duration=0.75, velocity=0.58))
            echoes.append(Note(pitch=pitch, start=at + delay + 0.85, duration=0.65, velocity=0.22))
            echoes.append(Note(pitch=pitch, start=at + delay + 1.55, duration=0.65, velocity=0.09))
    return Song(
        title="Slow Orbit",
        bpm=60,
        beats=24,
        seed=33,
        tracks=[
            Track(name="Suspended harmony", instrument="pad", gain=0.32, pan=-0.2, notes=pads),
            Track(name="Low orbit", instrument="sine", gain=0.34, pan=0.05, notes=low),
            Track(name="Distant lights", instrument="pluck", gain=0.44, pan=0.5, notes=chimes),
            Track(name="Written echoes", instrument="pluck", gain=0.44, pan=-0.65, notes=echoes),
        ],
    )


def pixel_sprint() -> Song:
    """Fast triangle-wave lead, quarter-beat chord arpeggios, and an arcade cadence."""
    melodies = [
        ["E5", "G5", "C6", None, "B5", "G5", "E5", "D5"],
        ["C5", "E5", "A5", None, "G5", "E5", "C5", "B4"],
        ["A4", "C5", "F5", "A5", "G5", "F5", "E5", "C5"],
        ["D5", "G5", "B5", "A5", "G5", None, "D5", "B4"],
    ]
    chord_steps = [
        ["C4", "E4", "G4", "E4"],
        ["A3", "C4", "E4", "C4"],
        ["F3", "A3", "C4", "A3"],
        ["G3", "B3", "D4", "B3"],
    ]
    roots, fifths = ["C3", "A2", "F2", "G2"], ["G3", "E3", "C3", "D3"]
    lead, arps, bass, kick, snare, hats = [], [], [], [], [], []
    for bar in range(12):
        at, index = bar * 4, bar % 4
        melody = melodies[index] if bar < 8 else list(reversed(melodies[index]))
        lead.extend(line(melody, start=at, gate=0.7, velocity=0.75))
        arps.extend(line(chord_steps[index] * 4, start=at, step=0.25, gate=0.62, velocity=0.5))
        bass.extend(
            line(
                [roots[index], fifths[index], roots[index], fifths[index]],
                start=at,
                step=1,
                gate=0.5,
                velocity=0.82,
            )
        )
        kick.extend(line([36, None, 36, None], start=at, step=1, gate=0.35, velocity=0.8))
        snare.extend(line([None, 38, None, 38], start=at, step=1, gate=0.2, velocity=0.5))
        hats.extend(line([42] * 8, start=at, step=0.5, gate=0.12, velocity=0.4))
    lead.extend(chord(["C6"], 48, 1.6, 0.7))
    arps.extend(chord(["C4", "E4", "G4"], 48, 1.6, 0.35))
    bass.extend(chord(["C3"], 48, 1.6, 0.8))
    return Song(
        title="Pixel Sprint",
        bpm=156,
        beats=50,
        seed=44,
        tracks=[
            Track(name="Arcade lead", instrument="triangle", gain=0.5, pan=0.1, notes=lead),
            Track(name="Rapid arpeggios", instrument="triangle", gain=0.25, pan=-0.4, notes=arps),
            Track(name="Bouncing bass", instrument="sine", gain=0.7, notes=bass),
            Track(name="Pixel kick", instrument="kick", gain=0.6, notes=kick),
            Track(name="Noise snare", instrument="snare", gain=0.3, pan=-0.1, notes=snare),
            Track(name="Clock hats", instrument="hat", gain=0.28, pan=0.45, notes=hats),
        ],
    )


def welcome_signal() -> Song:
    """A five-second product/startup sound: rising notes and a major-ninth resolution."""
    motif = (
        Note(pitch="C5", start=0.2, duration=0.7, velocity=0.6),
        Note(pitch="G5", start=0.95, duration=0.7, velocity=0.66),
        Note(pitch="D6", start=1.7, duration=0.8, velocity=0.72),
        Note(pitch="E6", start=2.6, duration=3.5, velocity=0.8),
    )
    echoes = tuple(
        Note(
            pitch=note.pitch,
            start=note.start + 0.8,
            duration=min(note.duration, 0.6),
            velocity=note.velocity * 0.24,
        )
        for note in motif
    )
    return Song(
        title="Welcome Signal",
        bpm=120,
        beats=10,
        seed=55,
        tracks=[
            Track(name="Four-note signature", instrument="pluck", gain=0.65, pan=0.2, notes=motif),
            Track(name="Soft reflections", instrument="pluck", gain=0.45, pan=-0.55, notes=echoes),
            Track(
                name="Resolution",
                instrument="pluck",
                gain=0.22,
                pan=-0.1,
                notes=chord(["C4", "E4", "G4", "B4", "D5"], 2.6, 6.3, 0.55),
            ),
            Track(
                name="Low arrival", instrument="sine", gain=0.4, notes=chord(["C3"], 2.6, 2, 0.45)
            ),
        ],
    )


SHOWCASE = [
    (
        "01-after-hours",
        after_hours,
        "Mellow groove",
        "Swung drums, warm ninth chords, and a relaxed bass line.",
    ),
    (
        "02-neon-circuit",
        neon_circuit,
        "Dance loop",
        "Four-on-the-floor kick, offbeat chords, and a breakdown into a final drop.",
    ),
    (
        "03-slow-orbit",
        slow_orbit,
        "Ambient",
        "Beatless sustained harmony with sparse chimes and written echoes.",
    ),
    (
        "04-pixel-sprint",
        pixel_sprint,
        "Chiptune",
        "Fast triangle-wave melodies, bouncing bass, and rapid arpeggios.",
    ),
    (
        "05-welcome-signal",
        welcome_signal,
        "Audio logo",
        "A rising four-note signature resolving into a bright chord.",
    ),
]


def write_gallery(
    output: Path,
    entries: list[dict],
    *,
    heading: str = "Five scores. Five different sounds.",
    introduction: str = "Original examples made with the framework's built-in synths and drums. "
    "Each player has its editable JSON score and MIDI file below it.",
) -> None:
    cards = []
    for entry in entries:
        slug = html.escape(entry["slug"], quote=True)
        cards.append(
            f"<article><h2>{html.escape(entry['title'])}</h2>"
            f'<p class="meta">{html.escape(entry["style"])} · '
            f"{entry['duration_seconds']:.1f} seconds · {entry['bpm']:g} BPM</p>"
            f"<p>{html.escape(entry['description'])}</p>"
            '<audio controls preload="none" '
            f'aria-label="{html.escape(entry["title"], quote=True)}" '
            f'src="{slug}.wav"></audio>'
            f'<p><a href="{slug}.wav" download>WAV</a> · '
            f'<a href="{slug}.mid" download>MIDI</a> · '
            f'<a href="{slug}.json" download>Score</a></p></article>'
        )
    document = (
        """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Audio as Code — listening examples</title>
<style>
body{margin:0;background:#f6f4ef;color:#252823;font:17px/1.6 system-ui,sans-serif}
main{max-width:760px;margin:64px auto;padding:0 24px 64px}
h1{font-size:clamp(32px,6vw,48px);line-height:1.15;letter-spacing:-.04em}
h2{margin:0;font-size:24px}article{padding:28px 0;border-top:1px solid #c8cec1}
.meta{font-size:14px;color:#4e5847;margin:8px 0}audio{width:100%;margin-top:8px}
a{color:#315c25;text-underline-offset:4px}a:focus-visible{outline:3px solid #315c25}
</style></head><body><main>
<p class="meta">AUDIO AS CODE / SYNTHESIZED LOCALLY</p>
<h1>{{heading}}</h1>
<p>{{introduction}}</p>
"""
        + "\n".join(cards)
        + """
</main><script>
document.querySelectorAll('audio').forEach(player => {
  player.addEventListener('play', () => {
    document.querySelectorAll('audio').forEach(other => { if(other !== player) other.pause(); });
  });
});
</script></body></html>"""
    )
    document = document.replace("{{heading}}", html.escape(heading))
    document = document.replace("{{introduction}}", html.escape(introduction))
    (output / "index.html").write_text(document, encoding="utf-8")


def main() -> None:
    output = Path("output/showcase")
    output.mkdir(parents=True, exist_ok=True)
    entries = []
    for slug, compose, style, description in SHOWCASE:
        song = compose()
        song.save(output / f"{slug}.json")
        midi = export_midi(song, output / f"{slug}.mid")
        report = render(song, output / f"{slug}.wav")
        (output / f"{slug}.report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        if report["wav"]["silent"] or report["wav"]["full_scale_samples"]:
            raise RuntimeError(f"{slug}: expected audible output without full-scale samples")
        if abs(midi["duration_seconds"] - song.seconds) > 0.01:
            raise RuntimeError(f"{slug}: MIDI timing differs from the score")
        entry = {
            "slug": slug,
            "title": song.title,
            "style": style,
            "description": description,
            "bpm": song.bpm,
            "duration_seconds": report["wav"]["duration_seconds"],
            "tracks": len(song.tracks),
            "notes": report["notes"],
            "peak_dbfs": report["wav"]["peak_dbfs"],
            "rms_dbfs": report["wav"]["rms_dbfs"],
            "warnings": report["warnings"],
        }
        entries.append(entry)
        print(json.dumps(entry), flush=True)
    (output / "manifest.json").write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    write_gallery(output, entries)
    print(f"Listen: {(output / 'index.html').resolve()}")


if __name__ == "__main__":
    main()
