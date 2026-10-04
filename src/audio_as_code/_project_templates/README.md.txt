# Small beginnings

This project contains an original eight-beat sketch for three procedural voices.
Edit `build_song()` in `compose.py` to change its melody, harmony, tempo or instruments.
`score.json` is the initial editable score; the composer writes revised scores to
`output/score.json`. Choose one as the source of truth for each revision.

If Audio as Code is already installed in your current environment, run:

```sh
python -m audio_as_code doctor
python compose.py
```

The composer creates `output/song.wav`, `output/song.mid`, `output/score.json` and
`output/report.json`. Repeated runs replace these generated artifacts. Listen to
the WAV and read the report; numerical measurements do not establish musical quality.

For an isolated project environment with uv, run these commands from this folder:

```sh
uv sync
uv run aac doctor
uv run python compose.py
```

This uses the dependency pin in `pyproject.toml` and creates a local `.venv` and
`uv.lock`. First installation downloads dependencies. Commit the lock when sharing
the project to keep those versions explicit.

Without uv, create and activate a Python virtual environment:

```sh
python -m venv .venv
```

In PowerShell, activate it with `.venv\Scripts\Activate.ps1`. On macOS or Linux,
use `source .venv/bin/activate`. Then install into that environment and compose:

```sh
python -m pip install "audio-as-code==__AAC_VERSION__"
python -m audio_as_code doctor
python compose.py
```

To work directly on the initial JSON score instead:

```sh
python -m audio_as_code validate score.json
python -m audio_as_code inspect score.json
python -m audio_as_code render score.json -o output/song.wav --report output/report.json
python -m audio_as_code midi score.json -o output/song.mid
```

Use `uv run` before these commands when using the project's uv environment.
Discover voices with `python -m audio_as_code instruments`; planned voices are
listed separately with `--all`. Rendering is local, seeded and limited to 300 seconds
per call. Instruments use generated synthesis, with no recordings or SoundFonts.
MIDI sounds depend on the receiving synthesizer; export warnings describe omitted
controls. Audio as Code is an early prototype, and its models have realism limits.

`doctor` checks an environment in which the package can already import. If import
fails before it runs, use the installation commands above to repair the environment.

`aac init` only creates files. It does not install dependencies, render audio,
send telemetry or change global settings.
