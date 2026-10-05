"""Complete classical edition in four dance arrangements, plus dry voice auditions.

Run: uv run --extra loudness python examples/electronic_music.py
Open output/electronic-music/index.html. All audio is synthesized locally.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from audio_as_code import (
    Automation,
    Chorus,
    Delay,
    Distortion,
    Ducker,
    Note,
    Phaser,
    Reverb,
    Song,
    Tone,
    Track,
    Tremolo,
    export_midi,
    get_instrument,
    render,
)
from audio_as_code.electronic import ELECTRONIC_INSTRUMENTS

ROOT = Path(__file__).resolve().parents[1]
STYLES = {
    "disco": (118, ("clavinet", "string_machine", "electric_guitar", "bass_guitar")),
    "techno": (132, ("acid_bass", "sync_lead", "disco_bass", "sub_bass")),
    "trance": (138, ("supersaw", "trance_pluck", "string_machine", "disco_bass")),
    "drum-and-bass": (174, ("fm_bell", "wavetable_pad", "hoover", "reese_bass")),
}
PARTS = ("soprano", "alto", "tenor", "bass")


def source_piece() -> dict:
    return json.loads((ROOT / "examples/music/classics-full.json").read_text(encoding="utf-8"))[
        "ode_to_joy"
    ]


def genre_song(style: str) -> Song:
    """Preserve all four source parts and the complete 16-bar hymn arrangement.

    Pitches may shift by octaves; note onsets and written durations are retained.
    The added groove is original and does not contain a sampled breakbeat.
    """
    piece = source_piece()
    bpm, voices = STYLES[style]
    end = piece["beats"]
    tracks = []
    kicks = [float(i) for i in range(int(end))]
    if style == "drum-and-bass":
        kicks = [bar + offset for bar in range(0, int(end), 4) for offset in (0, 1.75, 2.5)]
    for index, (part, instrument) in enumerate(zip(PARTS, voices, strict=True)):
        transpose = -12 if part == "bass" else 0
        if style == "techno":
            transpose = -24 if part == "soprano" else -12
        if style == "drum-and-bass" and part == "tenor":
            transpose = -12
        articulation = None
        if instrument == "electric_guitar":
            articulation = "muted"
        notes = [
            Note(
                pitch=pitch + transpose,
                start=start,
                duration=duration,
                velocity=min(0.85, max(0.45, velocity)),
                articulation=("pop" if int(start) % 4 == 3 else "slap")
                if instrument == "bass_guitar"
                else "accented"
                if instrument == "acid_bass" and start % 4 == 0
                else None,
            )
            for pitch, start, duration, velocity in piece["parts"][part]
        ]
        effects = []
        tone = None
        if instrument == "clavinet":
            effects = [Phaser(mix=0.28, depth=0.6, rate_hz=0.25)]
        elif instrument in {"string_machine", "wavetable_pad"}:
            effects = [Chorus(mix=0.3), Reverb(mix=0.12, decay_seconds=0.8)]
        elif instrument == "supersaw":
            effects = [Chorus(mix=0.23), Ducker(trigger_beats=kicks, depth=0.55)]
            tone = Tone(brightness=0.6, detune_cents=19)
        elif instrument == "trance_pluck":
            effects = [Delay(time_seconds=60 / bpm * 0.75, mix=0.18, repeats=3)]
        elif instrument in {"acid_bass", "reese_bass", "hoover"}:
            effects = [Distortion(drive=2.4, mix=0.2), Ducker(trigger_beats=kicks, depth=0.4)]
        elif instrument == "sync_lead":
            effects = [Tremolo(period_beats=0.5, depth=0.6, shape="gate")]
        elif instrument == "fm_bell":
            tone = Tone(fm_ratio=2, fm_index=1.5, decay_seconds=1.8)
            effects = [Delay(time_seconds=60 / bpm * 0.75, repeats=3, mix=0.15)]
        gain = (0.45, 0.19, 0.17, 0.55)[index]
        tracks.append(
            Track(
                name=part,
                instrument=instrument,
                notes=notes,
                gain=gain,
                pan=(0, -0.25, 0.25, 0)[index],
                release_seconds=0.08,
                articulation=articulation,
                tone=tone,
                effects=effects,
            )
        )
    kit = {
        "disco": (("kick_909", kicks, 0.6), ("clap", None, 0.55)),
        "techno": (("kick_909", kicks, 0.75), ("clap", None, 0.5)),
        "trance": (("kick_909", kicks, 0.65), ("electronic_snare", None, 0.45)),
        "drum-and-bass": (("kick_808", kicks, 0.65), ("electronic_snare", None, 0.6)),
    }
    for instrument, starts, gain in kit[style]:
        starts = starts if starts is not None else list(range(1, int(end), 2))
        notes = [
            Note(
                pitch=get_instrument(instrument).preview_pitch,
                start=start,
                duration=min(0.65, end - start),
                velocity=0.85,
            )
            for start in starts
        ]
        if style == "drum-and-bass" and instrument == "electronic_snare":
            notes += [
                Note(pitch=38, start=bar + offset, duration=0.12, velocity=0.27)
                for bar in range(0, int(end), 4)
                for offset in (0.75, 2.75, 3.75)
            ]
            notes.sort(key=lambda n: n.start)
        tracks.append(Track(name=instrument, instrument=instrument, gain=gain, notes=notes))
    hats = [
        Note(pitch=42, start=i * 0.5, duration=0.16, velocity=0.45 if i % 2 == 0 else 0.65)
        for i in range(int(end * 2))
    ]
    tracks.append(Track(name="Pulse hats", instrument="metal_hat", gain=0.36, pan=0.18, notes=hats))
    if style in {"disco", "trance"}:
        tracks.append(
            Track(
                name="Offbeat open hats",
                instrument="open_hat",
                gain=0.24,
                pan=-0.15,
                notes=[
                    Note(pitch=46, start=i + 0.5, duration=0.42, velocity=0.65)
                    for i in range(int(end))
                ],
            )
        )
    # Keep the complete source material; a short master fade shapes only its final cadence.
    return Song(
        title=f"Ode to Joy / {style}",
        bpm=bpm,
        beats=end,
        seed=901,
        sample_rate=44100,
        master_gain=0.8,
        tracks=tracks,
        automation=[
            Automation(
                parameter="master_gain",
                points=[
                    {"beat": 0, "value": 0.8},
                    {"beat": end - 1, "value": 0.8},
                    {"beat": end, "value": 0},
                ],
            )
        ],
    )


def original_song() -> Song:
    piece = source_piece()
    return Song(
        title="Ode to Joy / original hymn edition",
        bpm=piece["bpm"],
        beats=piece["beats"],
        tracks=[
            Track(
                name=part,
                instrument="piano",
                gain=0.6 if part == "soprano" else 0.35,
                release_seconds=0.12,
                notes=[Note(pitch=p, start=s, duration=d, velocity=v) for p, s, d, v in rows],
            )
            for part, rows in piece["parts"].items()
        ],
    )


def audition_song(instrument: str) -> Song:
    info = get_instrument(instrument)
    if info.midi_note is not None:
        notes = [
            Note(pitch=info.preview_pitch, start=0, duration=3.5, velocity=0.85),
            Note(pitch=info.preview_pitch, start=4, duration=1, velocity=0.4),
            Note(pitch=info.preview_pitch, start=5.5, duration=2, velocity=0.85),
        ]
    else:
        notes = [
            Note(pitch=info.preview_pitch + offset, start=i, duration=0.7, velocity=v)
            for i, offset, v in ((0, 0, 0.5), (1, 0, 0.9), (2, 7, 0.7), (3, 12, 0.8))
        ]
        notes.append(Note(pitch=info.preview_pitch, start=4.5, duration=3, velocity=0.7))
    return Song(
        title=info.name,
        bpm=110,
        beats=8,
        seed=901,
        tracks=[
            Track(
                name=info.name, instrument=instrument, gain=0.7, notes=notes, release_seconds=0.12
            )
        ],
    )


def build(
    output: Path, *, loudness: bool = True, only: str | None = None, html_only: bool = False
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    songs = {"original": original_song(), **{style: genre_song(style) for style in STYLES}}
    songs.update({voice: audition_song(voice) for voice in sorted(ELECTRONIC_INSTRUMENTS)})
    for instrument, gestures in (
        ("bass_guitar", ("slap", "pop", "muted")),
        ("electric_guitar", ("muted",)),
    ):
        base = audition_song(instrument)
        songs[f"{instrument}-original"] = base
        for gesture in gestures:
            data = base.model_dump()
            data["title"] = f"{base.title} / {gesture}"
            data["tracks"][0]["articulation"] = gesture
            songs[f"{instrument}-{gesture}"] = Song.model_validate(data)
    if only is not None and only not in songs:
        raise ValueError(f"unknown audition {only!r}; choose from {', '.join(songs)}")
    rows = []
    reports = (
        json.loads((output / "measurements.json").read_text(encoding="utf-8")) if html_only else {}
    )
    for key, song in songs.items():
        if only is not None and key != only:
            continue
        if html_only:
            if key not in reports or not all(
                (output / f"{key}.{ext}").is_file() for ext in ("wav", "json", "mid")
            ):
                continue
            report = reports[key]
        else:
            score_path = output / f"{key}.json"
            score_path.write_text(song.model_dump_json(indent=2), encoding="utf-8")
            kwargs = {"target_lufs": -18, "peak_ceiling_dbfs": -1.5} if loudness else {}
            report = render(song, output / f"{key}.wav", **kwargs)
            export_midi(song, output / f"{key}.mid")
            reports[key] = report
        label = (
            "Complete 16-bar hymn edition"
            if key == "original"
            else (
                "Complete AI-written genre arrangement" if key in STYLES else "Dry voice audition"
            )
        )
        rows.append(
            f"<article><small>{html.escape(label)}</small><h2>{html.escape(song.title)}</h2>"
            f'<button data-play="{key}" aria-pressed="false" '
            f'aria-label="Play {html.escape(song.title, quote=True)}">Play</button>'
            f'<audio controls preload="none" src="{key}.wav"></audio>'
            f'<p><a href="{key}.json">Editable score</a> · <a href="{key}.wav">WAV</a>'
            f' · <a href="{key}.mid">MIDI</a></p></article>'
        )
        if not html_only:
            print(f"Rendered {key}: {report['audio']['duration_seconds']:.2f}s", flush=True)
    if not html_only:
        (output / "measurements.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    page = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dance floor, meet source code · Audio as Code</title><style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f5f0dd;color:#161616;
font:18px/1.5 system-ui,sans-serif}main{max-width:1180px;margin:auto;padding:40px 24px 80px}
h1{font-size:clamp(42px,8vw,96px);line-height:1;letter-spacing:-.06em;max-width:900px}
.tag{background:#f784b7;padding:8px 14px;display:inline-block;font-weight:800;border:2px solid}
.intro{max-width:800px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:20px}
article{border:2px solid;padding:22px;background:#fffdf5;box-shadow:5px 5px 0 #161616}
article:first-child{background:#d0ee63}h2{font-size:26px;line-height:1.1;margin:10px 0 20px}
small{font:12px monospace;text-transform:uppercase}a{color:inherit;text-underline-offset:4px}
audio{width:100%}article p{font-size:14px}footer{margin-top:40px;font-size:14px}
button{border:2px solid #161616;background:#161616;color:white;font:700 16px system-ui;
padding:10px 24px;cursor:pointer;margin:0 0 12px;min-height:44px}
button[aria-pressed=true]{background:#f784b7;color:#161616}
button:focus-visible{outline:3px solid #c42670;outline-offset:3px}
details{margin:20px 0}summary{cursor:pointer;font-weight:700}
</style><main><span class="tag">AUDIO AS CODE / ELECTRONIC LAB</span>
<h1>Dance floor,<br>meet source code.</h1><p class="intro">One complete classical hymn.
Four new dance arrangements. Then hear every new voice on its own.</p>
<details><summary>About the music and listening comparisons</summary>
<p class="intro">The source is the complete 16-bar, four-part “Ode to Joy” hymn edition,
not Beethoven’s entire symphony. Its notes and rhythms are retained, with octave shifts,
AI-written instrumentation and original procedural drum patterns. All instrument sounds
come from code. These are designed synthesis models, not recordings or calibrated replicas.</p>
<p class="intro">Listening copies target −18 LUFS when built with the loudness extra,
bounded by a −1.5 dBFS sample-peak ceiling. Some quiet or transient clips cannot reach that
target. Exact gains and measurements are in <a href="measurements.json">the render report</a>.
Numerical checks do not establish perceived quality.</p></details><section class="grid">"""
    source = source_piece()
    page += (
        "\n".join(rows)
        + '</section><footer>Source score: <a href="'
        + html.escape(source["source_url"], quote=True)
        + '">Mutopia edition</a>. '
    )
    page += (
        html.escape(source["credit"])
        + ", Public Domain. MIDI keeps notes and tempo; external instruments "
        "and effects differ.</footer></main>"
    )
    page += """<script>
for(const button of document.querySelectorAll('[data-play]')){
 const a=button.parentElement.querySelector('audio');
 function update(){button.textContent=a.paused?'Play':'Pause';
 button.setAttribute('aria-pressed',String(!a.paused));
 const title=button.parentElement.querySelector('h2').textContent;
 button.setAttribute('aria-label',`${a.paused?'Play':'Pause'} ${title}`)}
 for(const event of ['play','pause','ended'])a.addEventListener(event,update);
 button.addEventListener('click',async()=>{try{if(a.paused)await a.play();else a.pause()}
 catch{button.textContent='Download WAV to listen'}});
}
document.addEventListener('play',e=>{for(const a of document.querySelectorAll('audio')){
if(a!==e.target)a.pause()}},true);
</script></html>"""
    (output / "index.html").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=ROOT / "output/electronic-music")
    parser.add_argument("--no-loudness", action="store_true", help="Use only the core dependencies")
    parser.add_argument("--only", help="Render one named style or voice into this output directory")
    parser.add_argument(
        "--html-only", action="store_true", help="Refresh the player from existing renders"
    )
    args = parser.parse_args()
    build(args.output, loudness=not args.no_loudness, only=args.only, html_only=args.html_only)
