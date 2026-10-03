# Build and preview the website

The Audio as Code website is a static listening and documentation site. Its
canonical domain is **audioascode.com**. Building locally does not publish anything.

## Build from a checkout

Run these commands from the directory containing `pyproject.toml`, with Python
3.10+, uv and an installed FFmpeg:

```sh
uv sync --locked
uv run python examples/classic_showcase.py --ffmpeg ffmpeg
uv run python examples/classic_reimaginations.py --ffmpeg ffmpeg
uv run python examples/instrument_browser.py
uv run python examples/build_site.py --strict
```

The homepage compares five public-domain works, each in two complete versions
side by side: **The classic** and **Reimagined**. It opens on Für Elise, the
classic.

- `examples/classic_showcase.py` renders the classic versions (Für Elise, the
  Prelude from Bach's first cello suite, the Turkish March, Greensleeves and an
  Ode to Joy hymn arrangement) into `output/classic-showcase/`. The notes come
  from `examples/music/classics-full.json`, imported from the credited
  public-domain editions. "Complete" means the credited score's scope: the Ode
  to Joy edition is a sixteen-bar hymn arrangement, not Beethoven's Ninth
  Symphony. See [the score credits](classic-showcase.md).
- `examples/classic_reimaginations.py` renders an AI agent's new arrangement of
  each work into `output/classic-reimaginations/`. Its IDs are the classic IDs
  plus `-reimagined`. See [the reimagination notes](classic-reimaginations.md).

Both scripts write WAV, MIDI, editable JSON scores, render reports, 192 kbps MP3
previews and a `manifest.json`. The builder reads each manifest's `pair_id`,
`variant` (`classic` or `reimagined`), `work_title`, `complete` and source
credit fields (`source_url`, `edition_credit`, `source_license`). They travel
into the published `music/manifest.json`, the selected-piece credit line and
the homepage's score credits. A Reimagined version that omits a credit inherits
the one from its classic.

The instrument script renders 147 short audition clips: a music excerpt, a
phrase, and a single note or hit for each of the 49 playable voices. It writes
the listening library to `output/instruments/`. These clips are labelled there
as auditions; the homepage comparisons are the whole-work demos. Rendering steps
can take several minutes. They use procedural instrument sources and need no
sample downloads or network services.

For instrument work, render a subset or resume an interrupted batch:

```sh
uv run python examples/instrument_browser.py --instruments mandolin kalimba celesta recorder
uv run python examples/instrument_browser.py --resume
```

After editing the gallery template, use
`uv run python examples/instrument_browser.py --html-only` to rewrite the page from
its existing `catalog.json` without changing or rerendering any audio.

Resume reuses a clip only when its source, score, runtime fingerprint and all
output hashes match. A subset build can leave missing previews; finish the full
batch before building the website. A synthesis change invalidates cached clips.

The site builder reads those outputs, copies the documentation and web assets,
generates the downloadable source archive and machine-readable files, and
renders the small Python loop shown on the homepage. It writes the portable
site to `output/site/`. The JSON summary is also saved beside the site at
`output/site-build-report.json`.

`--strict` exits unsuccessfully on warnings or broken links. Warnings include a
missing Reimagined version, a classic without a source URL and licence, a
paired version not marked `complete: true`, a WAV whose length does not match
its score, and an MP3 preview older than its WAV. A stale or short render
therefore cannot pass a strict build.

For an already installed checkout, `uv run python` can be replaced with
`.venv/Scripts/python.exe` in Windows PowerShell or `.venv/bin/python` on
macOS/Linux. Neither requires environment activation. See the
[README installation instructions](../README.md#try-it) for a pip-based local
installation. Dependency installation may require a network connection; the
build and rendering steps work offline once the environment is installed.

## Choose what the lineup includes

| Option | Effect |
| --- | --- |
| `--classics PATH` | Read the classic versions from another folder; `none` leaves them out |
| `--reimaginations PATH` | Read the Reimagined versions from another folder; `none` leaves them out |
| `--with-originals` | Also list the four original compositions after the classics |
| `--compositions PATH` | Folder holding those originals' `manifest.json` |

The four original compositions (`lanterns-on-the-water`, `copper-street`,
`night-signal`, `clockwork-garden`) stay in the repository with their IDs and
are rendered by `examples/full_compositions.py` into
`output/full-compositions/`. The default public lineup leaves them out.

## Analytics

`web/site/analytics-config.json` holds the public PostHog project key and host,
limited to `audioascode.com` and `www.audioascode.com` with `allowLocal: false`.
Every page, including the instrument library, then gets the config as inline
JSON and a deferred `assets/analytics.js`. The script sends nothing on other
hosts, on localhost, or when the browser signals Do Not Track or Global Privacy
Control. The footer links [the analytics notice](analytics.md) and shows an
opt-out button only where analytics would actually run.

| Option | Effect |
| --- | --- |
| `--no-analytics` | Build without analytics, even when the config file exists |
| `--posthog-project-key KEY --posthog-host HOST` | Use another public `phc_` key and the US or EU ingest host; both are required together. A fork must use its own project |
| `--analytics-allow-local` | Let analytics run on localhost, for an explicit verification build only |

The key and host are validated before the previous build is removed. A build
without the config file has no analytics.

## Preview locally

```sh
uv run python examples/serve_site.py --directory output/site --port 8765
```

Open `http://127.0.0.1:8765/` in a browser. Keep the terminal running and stop it
with Ctrl+C when finished. Use HTTP for the full site so browser requests for
JSON and audio work consistently. The server is a local file preview; the
browser does not execute Python or call a synthesis API.

The page loads no audio until a visitor presses Play, and it makes no
third-party requests on an ordinary local load: the Ko-fi support links are
plain external links, and analytics stays off on localhost.

This preview server supports HTTP byte ranges so the browser can jump to a
section without downloading a whole render again. It compresses text assets
and revalidates cached files so rebuilt pages appear on reload. It binds only to
localhost and serves files inside the chosen directory. Python's basic
`http.server` does not provide byte ranges in the supported Python versions;
seeking there can require a full-file fallback download. Static production
hosts should provide byte ranges, text compression, and appropriate caching too.

## Edit and rebuild

| Source | Purpose |
| --- | --- |
| `web/site/` | Page templates, styles, JavaScript, fonts, identity and analytics config |
| `docs/site/` | Public guides (including the integrations guide), runnable snippets, and agent index |
| `examples/classic_showcase.py` | The five classic versions, with source credits |
| `examples/classic_reimaginations.py` | The five Reimagined versions |
| `examples/full_compositions.py` | Four original compositions (listed only with `--with-originals`) |
| `web/instrument-browser.html` | Instrument listening-page template |
| `examples/instrument_browser.py` | Instrument library generator |
| `schemas/song-v1.schema.json` | Published score schema |

For page or guide edits, rerun only `examples/build_site.py --strict` using the
existing rendered inputs. After composition or instrument changes, regenerate
the affected audio inputs first. Generated assets live under `output/`, which
is ignored by Git; keep source changes in the files above.

Each site rebuild replaces its destination directory. `--out output/site-preview`
selects another destination. Preflight requires a folder strictly inside
`output/` and refuses the output root, symlinked paths, and overlap with source
inputs, rendered music/instrument inputs, or `output/site-work/`. Keep
personal files out of the generated destination.

## Portable output

A static host serves the contents of `output/site/`, including its media,
fonts, JSON, and downloads. It does not need Python, an application server, or
a server API. Preserve the relative directory structure; copying only the HTML
will break playback and downloads. Local build and preview commands do not
configure hosting or the domain. For the maintainer deployment workflow, see
[Cloudflare hosting](cloudflare-hosting.md).

Useful paths relative to the built site root:

| Path | Content |
| --- | --- |
| `index.html` | Listening homepage |
| `docs/quickstart.html` | Getting started guide |
| `docs/integrations.html` | Codex, Claude Code, Hyperframes, game and slide recipes |
| `instruments/index.html` | 147-clip instrument library |
| `source.html` | Source download, size, and SHA-256 |
| `download/audio-as-code-0.1.0-source.zip` | Portable source snapshot; version follows the package |
| `llms.txt` | Agent documentation index |
| `schemas/song-v1.schema.json` | Versioned score contract |
| `instruments.json` | Live catalog with explicit availability and controls |
| `music/manifest.json` | Every version in lineup order, with pair, credit and relative asset paths |
| `docs/classic-showcase.md` | Score credits for the five source editions |
| `docs/analytics.md` | Analytics and privacy notice |

The source archive excludes generated media and operational files through a
source allowlist and filters; it includes `.github/FUNDING.yml`. Its recipient
installs from the extracted checkout to run the complete examples and site tools.
For the engine and CLI in an existing project, install `audio-as-code==0.1.0`
from [PyPI](https://pypi.org/project/audio-as-code/0.1.0/). The website source ZIP is
a separately built snapshot; its published hash identifies its contents, which can
include documentation updates made after the registry release. The
public source repository is [joaoCarvalho1000/audio-as-code](https://github.com/joaoCarvalho1000/audio-as-code).
