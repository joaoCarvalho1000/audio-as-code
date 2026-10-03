from audio_as_code import Pattern, Song, Track, export_midi, render

melody = Pattern.sequence(["C4", "E4", "G4", None], step=0.5).repeat(4)
kick = Pattern.sequence([36, None], step=1, gate=0.3).repeat(4)

song = Song(
    title="My first loop",
    bpm=110,
    beats=8,
    seed=42,
    tracks=[
        Track(name="Melody", instrument="pluck", notes=melody.notes, gain=0.5),
        Track(name="Kick", instrument="kick", notes=kick.notes, gain=0.7),
    ],
)

song.save("output/loop.json")
report = render(song, "output/loop.wav")
export_midi(song, "output/loop.mid")
print(report["wav"])
