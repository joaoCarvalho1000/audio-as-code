# Start a composition project

With Audio as Code installed, create an original editable sketch in a new directory:

```sh
aac init "my music"
cd "my music"
python -m audio_as_code doctor
python compose.py
```

Both `aac` and `python -m audio_as_code` expose `init` and `doctor`. The generated
composer uses the installed package; it works outside a source checkout. It writes
WAV, MIDI, the revised score and its render report under the project's `output/`.
The initial `score.json` lets you validate and render immediately without running
Python composition code.

The project includes `compose.py`, `score.json`, `README.md`, `AGENTS.md`,
`pyproject.toml` and `.gitignore`. Its README explains the first render and isolated
setup with either uv or Python venv and pip. The dependency pin uses the version
that created the project. `uv sync` creates the project environment and lock; init
does not install anything or replace a lock.

Init accepts a missing path or an empty directory, including a path with spaces.
It rejects nonempty directories, existing files, symlinks and directory junctions
before writing project files. It has no force option. All template files are loaded
and checked, then staged before exclusive publication; if a write fails, files
created by that attempt are removed. Use a dedicated directory with appropriate
permissions; initialization does not reserve it against other filesystem actors.

`aac doctor` emits JSON with an overall `ok` flag and individual checks for the
Python version, imported runtime dependencies, a short in-memory synthesis and
optional uv availability. Each failed or optional check includes a recovery hint.
Missing uv is a warning; it does not make a working runtime unhealthy. The check
does not install packages, run uv, write audio or access the network.

Doctor can only run once Audio as Code imports successfully. If a missing or broken
core dependency prevents that import, repair the local environment using `uv sync`
or the venv/pip instructions first. Its synthesis check establishes that one short
generated voice works in this environment, not that every score will render or
that an instrument sounds realistic. It does not check an audio device, ffmpeg,
deployment services or credentials, since the core workflow does not require them.

Keep the composer or JSON score as the source of truth for each revision. The
composer saves its score to `output/score.json`; editing the initial `score.json`
does not change the Python composer. Generated artifacts are replaced on subsequent
runs. Discover implemented instruments with `aac instruments`, inspect scores with
`aac inspect`, and review MIDI warnings before delivering the files.
