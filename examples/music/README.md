# Score sources

`excerpts.json` contains note events only: `[MIDI pitch, start beat, duration beats]`.
There is no audio, recorded excitation, SoundFont, or measured impulse response.
Normal demo generation is offline. The optional `build_excerpts.py` downloads the
listed Mutopia notation MIDI and rebuilds this small source dataset.

All five source editions are marked **Public Domain** by the Mutopia Project.
Each entry preserves the edition credit, source page, download URL, selected ZIP
member where applicable, and SHA-256 of the downloaded source. These credits
remain attached to the public-domain music; the framework code is MIT licensed.

| Excerpt | Composer | Edition credit | Source |
| --- | --- | --- | --- |
| Greensleeves | Traditional | Aaron Fontaine | [Mutopia 109](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=109) |
| Ode to Joy | Ludwig van Beethoven | Peter Chubb | [Mutopia 528](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=528) |
| Für Elise | Ludwig van Beethoven | Stelios Samelis | [Mutopia 931](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=931) |
| Turkish March, K. 331 | Wolfgang Amadeus Mozart | Rune Zedeler and Chris Sawer | [Mutopia 108](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=108) |
| Cello Suite No. 1, BWV 1007, Prelude | Johann Sebastian Bach | Andreas Scherer | [Mutopia 517](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=517) |

The first 24, 32, 12, 32, and 32 quarter-note beats respectively are retained.
The four Ode to Joy parts are transcribed separately from the edition's LilyPond
voices because the MIDI merges some unisons. Other excerpts use the upper
sounding melody and remaining accompaniment from the notation MIDI. This is a
small curated dataset, not a general-purpose MIDI importer.

`examples/famous_music.py` supplies the new arrangements: octave transpositions,
instrumentation, tempo, dynamic shaping, note gates, and original percussion
patterns. These are short adapted excerpts, not original orchestrations or
recorded performances. Generated WAV/MIDI outputs stay under `output/`.
