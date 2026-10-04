# Contributing

Audio as Code is an early open-source prototype. Contributions should make composition,
validation, synthesis, or integration easier while keeping the engine small and
headless. For the module map, read [architecture](docs/architecture.md); for
release preparation, read [releasing](docs/releasing.md).

## Start with a reproducible change

For a bug, include the smallest original or public-domain score, the command or
Python call, expected/actual behavior, and your environment. For an API or
instrument proposal, describe the musical workflow it enables. The issue and PR
templates are available in [the repository](https://github.com/joaoCarvalho1000/audio-as-code).
Suspected vulnerabilities follow [SECURITY.md](SECURITY.md).

## Set up a checkout

Fork [the repository](https://github.com/joaoCarvalho1000/audio-as-code) on GitHub,
clone your fork with Git, and create a topic branch with `git switch -c your-change`.
Push your changes to that branch and open a pull request against this repository's
`main` branch when they are ready for review.

Install Python 3.10+ and [uv](https://docs.astral.sh/uv/), then run these commands
from the directory containing `pyproject.toml`:

```sh
uv sync --locked
uv run aac --version
uv run aac --help
uv run python -m audio_as_code --help
```

This installs the project in editable mode with development tools. No activation
is needed, including in PowerShell; source edits take effect immediately. First
installation needs dependency downloads. With dependencies cached, use
`uv sync --locked --offline`. Quote paths with spaces.

## Validate your change

Add a focused regression test for new musical behavior or a reproduced bug. Run
the relevant tests while developing, then the full project checks:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python .github/scripts/check_schema.py
uv build --no-sources
uv run python .github/scripts/check_distribution.py dist
uv run python .github/scripts/smoke_distribution.py dist
```

Use a fresh build output directory if `dist/` contains artifacts from other versions.
The archive checker expects exactly one wheel and one sdist. The smoke check
rebuilds the sdist and installs both wheels outside the checkout; it can need
network access for build/runtime dependencies. It tests the Python API and both
CLI entry points, including the normal error path. These checks do not publish.

CI runs the tests and schema check on Python 3.10 and 3.13 on Linux/Windows, and
3.13 on macOS. A separate job checks lint, formatting, and installed artifacts.
The Linux Python 3.13 job also tests the optional loudness backend. For changes
to that path, run `uv run --extra loudness pytest tests/test_loudness.py -W error`.
Report checks you could not run; do not label an unrun audition or CI job as passed.

For website hosting changes, install Node.js 24 and run the hosting checks from
the repository root. These install the locked tools and check Wrangler without
deploying:

```sh
npm ci --prefix web/cloudflare
npm exec --prefix web/cloudflare --no -- wrangler --version
node --test web/cloudflare/media-handler.test.js
```

For CLI changes, exercise both help entry points and the [README first run](README.md#try-it),
including an invalid score and paths containing spaces. Keep successful output
parseable as one JSON object on stdout and failures as structured JSON on stderr
with exit status 2. Help remains text. Preserve issue paths, export diagnostics,
and existing files when preflight fails. Focused checks include
`tests/test_cli_dx.py`, `tests/test_midi_cli.py`, and `tests/test_score_inspection.py`.

For audio changes, render `uv run python examples/first_light.py` and listen when
possible. Validate tuning, finite/stable output, controls, clipping, releases and
timing as appropriate. State what you actually heard and which checks were only
numerical. Signal measurements do not establish perceptual realism.

## Preserve the musical contract

- Generate instrument sounds from code using procedural, physical/modal or
  source/filter models. Do not introduce recorded samples, SoundFonts, sample
  libraries, or measured impulse responses as instrument sources.
- Follow [the instrument foundation](docs/instrument-foundation.md). Register
  capabilities centrally in `src/audio_as_code/instruments.py`; planned voices
  stay separate from playable IDs. Expose only implemented controls.
- Preserve existing score IDs and seeded rendering in a fixed environment.
  Explain any intentional output change and retain coverage for unchanged defaults.
- Treat JSON scores as data. Keep network services, credentials, audio-device
  access, and proprietary assets out of the engine.

When changing score models, regenerate the schema:

```sh
uv run aac schema -o schemas/song-v1.schema.json
```

Breaking score-format changes need a new schema version and migration guidance.
Update examples, the agent guide and the changelog for user-facing changes. Package
and score-schema versions are independent.

## Keep contributions portable

Dependencies and `uv.lock` change only for a dependency-related reason. Include
the reason and test results when updating them. A metadata-only change should not
silently regenerate the lock.

The wheel contains the importable package and CLI. The sdist uses an explicit
portable-file allowlist in `pyproject.toml`; the website source ZIP has its own
allowlist in `examples/build_site.py`. Keep both current when adding source files.
Keep the archive checker requirements current when the required portable contents
change. Inspect actual built files rather than relying on `.gitignore` alone.

Write generated WAV/MIDI/MP3, reports, screenshots and local experiments under
ignored `output/`. Do not commit environment files, credentials, logs, build output,
or agent/workstation state. Only contribute code and assets you have the right to
distribute; retain source-score credits and licenses.

Keep private planning, design briefs and session handoffs under `.internal/` or
`docs/internal/`. These directories and local planning filenames are excluded from
Git, source distributions and website downloads. Public documentation should explain
the API, musical models, examples or contributor workflows; omit session transcripts,
machine-specific results and links to local-only review artifacts. Keep `AGENTS.md`
and `skills/audio-as-code/SKILL.md` public so contributors and composing agents can
use them.

A PR should explain the problem, resulting behavior, compatibility impact and
validation. Keep unrelated cleanup separate. CI validates changes; publishing is a
separate, manually dispatched maintainer action described in [releasing](docs/releasing.md).
