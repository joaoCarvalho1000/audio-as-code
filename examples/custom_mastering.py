"""Render repeatable custom-patch and mastering auditions under output/custom-mastering."""

import json
from pathlib import Path

from audio_as_code import (
    BusCompressor,
    CustomInstrument,
    Delay,
    Envelope,
    FMLayer,
    Mastering,
    ModalLayer,
    ModalPartial,
    NoiseLayer,
    Note,
    OscillatorLayer,
    PatchFilter,
    Reverb,
    Song,
    Track,
    TruePeakLimiter,
    export_midi,
    render,
)


def example_song() -> Song:
    return Song(
        title="Glass and sparks",
        bpm=120,
        beats=8,
        seed=37,
        custom_instruments={
            "custom:glass": CustomInstrument(
                name="Glass",
                midi_program=89,
                layers=[
                    OscillatorLayer(waveform="triangle", gain=0.3),
                    FMLayer(gain=0.15, ratio=2.01, index=2.5),
                ],
                filter=PatchFilter(cutoff_hz=5000),
            ),
            "custom:spark": CustomInstrument(
                name="Spark",
                midi_program=14,
                layers=[
                    ModalLayer(
                        gain=0.5,
                        partials=[
                            ModalPartial(decay_seconds=0.2),
                            ModalPartial(ratio=2.7, amplitude=0.3, decay_seconds=0.08),
                        ],
                    ),
                    NoiseLayer(
                        gain=0.06,
                        envelope=Envelope(
                            attack_seconds=0.001,
                            decay_seconds=0.03,
                            sustain=0,
                            release_seconds=0.02,
                        ),
                    ),
                ],
            ),
        },
        tracks=[
            Track(
                name="Glass",
                instrument="custom:glass",
                gain=0.45,
                pan=-0.2,
                notes=[
                    Note(pitch=pitch, start=i * 2, duration=1.8)
                    for i, pitch in enumerate([60, 64, 67, 71])
                ],
            ),
            Track(
                name="Spark",
                instrument="custom:spark",
                gain=0.8,
                pan=0.25,
                notes=[
                    Note(pitch=81, start=beat, duration=0.2, velocity=1)
                    for beat in (0.5, 2.5, 4.5, 6.5)
                ],
            ),
        ],
    )


def main() -> None:
    out = Path("output/custom-mastering")
    dry = example_song()
    wet = dry.model_copy(
        update={
            "tracks": tuple(
                track.model_copy(update={"effects": (Delay(mix=0.15),)}) for track in dry.tracks
            ),
            "effects": (Reverb(mix=0.15),),
        }
    )
    mastered = wet.model_copy(
        update={
            "mastering": Mastering(
                compressor=BusCompressor(),
                limiter=TruePeakLimiter(),
                target_lufs=-14,
            )
        }
    )
    reports = {}
    for name, song in (("dry", dry), ("wet", wet), ("mastered", mastered)):
        song.save(out / f"{name}.json")
        export_midi(song, out / f"{name}.mid")
        reports[name] = render(song, out / f"{name}.wav", wav_format="pcm24")
    (out / "measurements.json").write_text(json.dumps(reports, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                name: {
                    "audio": report["audio"],
                    "true_peak": report["true_peak"],
                    "loudness": report.get("loudness"),
                }
                for name, report in reports.items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
