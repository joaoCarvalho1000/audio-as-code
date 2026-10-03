# Put the music in your project

Make a reveal land, give the boss fight some nerve, or let the last slide take a
bow. Your agent composes with Audio as Code, brings the WAV into your creative
project, and keeps the score for revisions.

These recipes connect your tools through a portable skill, local commands and
ordinary audio files. Audio as Code supplies instrumental music and musical
cues. Use your project's other tools for narration and sound effects.

| Your creative workflow | Try this brief | What the next tool receives |
| --- | --- | --- |
| Video with Hyperframes | "A 12-second launch for a very serious moon-cheese company. Marimba curiosity, a bass entrance at second 4, a confident ending." | WAV on the video timeline; score/source retained for revisions |
| Game with a coding agent | "A tiny dragon thinks this is the final boss fight. Give me a 16-second battle cue and a separate 2-second victory sting." | Two WAV assets for the game's existing audio system, plus editable scores |
| Presentation with an agent | "A quarterly report with a villain arc: a 6-second ominous opening and a 4-second triumphant reveal." | Separate WAV cues placed on the relevant slides; playback configured by the presentation tool |

For looping game music, ask for a loop candidate and audition the join in the game.
Matching endpoints and managing release/effect tails need deliberate work; a render
is not automatically a seamless loop. For narration-heavy videos or presentations,
request sparse music and adjust its level in the consuming tool.

The source project includes an executable set of original creative briefs:

```sh
uv run --no-dev python examples/creative_workflows.py output/creative-workflows
```

Run it from the extracted source folder after setup. It delivers a 30-second
video cue with a reveal at 20 seconds, a 12-second game loop plus two-cycle
preview, and a nine-second presentation sting. Each has an initial version and
a revision that preserves specified material, with WAV/MIDI/JSON, composer,
inspection, reports and measured checks. Use a fresh output folder. Add
`--scores-only` for quick editing or `--brief game --version v2` for one candidate.
The loop uses short articulated rests and no effect tails; it is not a general
wet-loop exporter. Full rendering checks duration, finite stereo output, clipping,
reproducibility and the PCM join, and takes several minutes. Listening remains a
separate check. The source guide `docs/creative-workflows.md` explains the method.

## Start in your creative project

Use the website's **Copy agent prompt**, or download the full
[source project](../source.html) and give your agent the extracted folder. Ask it
to read [the portable skill](../skills/audio-as-code/SKILL.md), then describe the
music and where it will go. The agent needs a shell and Python 3.10+.

If setting it up directly, run these in the folder containing `pyproject.toml`:

```sh
uv sync --locked --no-dev
uv run --no-dev aac instruments
uv run --no-dev aac schema
```

Use the [quickstart](quickstart.md) for the pip/virtual-environment alternative.
Audio as Code is not published to a package registry. Its renderer needs no model
or provider key; your chosen agent has its own account and runtime requirements.

## Codex: keep the composer beside the project

Open the project in Codex and ask it to read `skills/audio-as-code/SKILL.md` from
the extracted Audio as Code folder. That direct instruction requires no skill
installation. For repeat use, copy the skill folder into your creative project's
`.agents/skills/audio-as-code/`. Codex discovers repository skills there; in Codex
CLI or the IDE extension, invoke it as `$audio-as-code`.
[Official Codex skill instructions](https://learn.chatgpt.com/docs/build-skills).

```text
Use the Audio as Code skill and the local source checkout. Compose an original
12-second moon-cheese launch cue: curious marimba, bass enters at second 4,
confident ending. Put v1 in output/moon-cheese/v1/. Deliver WAV, MIDI, score,
composer source and report. Check the actual WAV duration including tails.
```

Keep the source folder path in the brief if the creative project and framework
are separate. To revise: "Keep the motif and the 12-second cut. Make the opening
more suspicious, then brighten the final chord. Save v2."

## Claude Code: the same skill, another host

Claude Code can also read the portable file directly. For project discovery,
copy `skills/audio-as-code/` into `.claude/skills/audio-as-code/` in the creative
project, then invoke `/audio-as-code` with the same musical brief. Claude Code's
documented project skill directory and slash invocation support this layout.
[Official Claude Code skill instructions](https://code.claude.com/docs/en/skills).

The agent still composes and calls the local CLI. Copying the skill does not
install Python or the renderer. Preserve WAV, JSON and source files in the project
so either agent can continue the arrangement later.

## Hyperframes: music becomes a video asset

Make the score in Audio as Code and the visuals in Hyperframes. The connection is
a local WAV file: Hyperframes places it on its composition timeline and mixes it
into the rendered video. Its official example uses an `<audio>` element with a
WAV source. [Hyperframes repository](https://github.com/heygen-com/hyperframes).

1. Render the cue and inspect `report.json` or `aac analyze song.wav`. Use the
   measured WAV duration, including release/effect tails, to plan the video cut.
2. Create or open a Hyperframes project. For a new one, its documented local route
   is `npx hyperframes init my-video`, then work inside `my-video/`. Local video
   rendering requires Node.js 22+ and FFmpeg. The official skill installation is
   `npx skills add heygen-com/hyperframes` when you want agent authoring guidance.
   [Hyperframes quickstart](https://hyperframes.app/docs/1-startup/2-quickstart).
3. Copy your finished WAV to `my-video/assets/soundtrack.wav`. Keep its score,
   source and report in the music project; Hyperframes consumes the rendered audio,
   not the JSON score or MIDI.
4. Add this inside the existing root composition in `index.html`. Use an unused
   audio track index. This example assumes a confirmed 12-second cue:

```html
<audio id="soundtrack" src="./assets/soundtrack.wav"
       data-start="0" data-duration="12" data-track-index="8"
       data-volume="0.6"></audio>
```

`data-start` and `data-duration` are seconds. `data-media-start` can trim the
source start; omitting `data-duration` uses its remaining length. Audio elements
do not need `class="clip"`. Set the composition's visual timeline to cover the
intended cut; the audio tag does not author the visuals.
[Hyperframes HTML schema](https://hyperframes.app/docs/6-reference/html-schema).

Ask your video agent:

```text
Use the existing Hyperframes project. Build a 12-second moon-cheese launch video
around assets/soundtrack.wav. Place the reveal on the bass entrance at second 4.
Use this generated soundtrack, keep its ending audible, and preserve the editable
HTML project. Preview the full result and render an MP4.
```

From that project's folder, Hyperframes documents `npx hyperframes preview` and
`npx hyperframes render --output launch.mp4`.
[Hyperframes quickstart](https://hyperframes.app/docs/1-startup/2-quickstart).
When revising the music, render a new candidate, replace the copied WAV, and
preview again. Matching a filename does not guarantee the new duration matches
the video. The soundtrack remains procedural; this handoff adds no recorded
instrument sources.

## A small bridge for any shell-capable agent

The [runnable handoff example](examples/06_agent_handoff.py) accepts an existing
score, inspects WAV/MIDI readiness, renders WAV, analyzes the saved audio, exports MIDI, and
writes `handoff.json` with artifact paths, duration and warnings. Its subprocess
calls use the current environment's Python and argument lists, not shell strings.

To check the connection using the bundled demo, run from the source project:

```sh
uv run --no-dev aac demo -o output/integration-input.json
uv run --no-dev python docs/site/examples/06_agent_handoff.py output/integration-input.json output/integration-v1
```

Use a new output directory for each run. For actual work, replace the demo score
with the agent's original composition. A custom agent can call this script as a
local tool and read its JSON result; no provider SDK is required by the bridge.

| Artifact | Use |
| --- | --- |
| `song.wav` | Play in the game, place in a video, or attach to a slide |
| `score.json` and composer source | Revise notes, instrumentation, form and expression |
| `song.mid` | Continue in a DAW; its receiver determines the sound |
| `report.json`, `analysis.json` | Inspect duration, warnings, silence and levels |
| `inspection.json` | Read the score facts and export checks performed before rendering |
| `handoff.json` | Find the files programmatically; paths are local to this machine |

The bridge does not copy a separately authored composer script: retain that source
alongside the score. When transferring to another machine, copy the artifacts and
update paths rather than expecting absolute local paths to work remotely.

## Let errors guide the next edit

CLI success is JSON on stdout with exit 0. On exit 2, read the JSON on stderr:
`invalid_score` has `issues` with field `path` and `message`; `operation_failed`
has a `message` and recovery `hint`. Cross-field issues can have an empty path.
Fix the indicated score or file problem, validate again, then render and analyze
the new candidate. A process timeout or missing Python executable is a separate
execution problem, not a score diagnostic.

The bridge reports `score_not_exportable` and exits 2 for static WAV/MIDI blockers
before creating the output folder. It also forwards CLI errors and exits 2;
its own file/process errors use
`handoff_failed` and exit 1. It stops on failure, so check the exit code before
using any partial files. Successful signal checks cannot establish musical taste,
acoustic realism or a clean loop seam. Listen when available, and say when it was
not possible. See the [agent guide](agents.md) for the full command contract.

These recipes were checked against official tool documentation on 2026-10-02.
The local render/export bridge was executed; provider skill discovery and the
Hyperframes MP4 render were not exercised as part of this guide's validation.
