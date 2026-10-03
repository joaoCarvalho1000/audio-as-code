# Product

<!-- impeccable:product-schema 1 -->

## Identity

The project is **Audio as Code**. The owner selected this name and purchased **audioascode.com** on 2026-10-02. Use `https://audioascode.com` as the canonical public website address when building the site; domain ownership does not mean the site is already deployed. Keep the Python distribution `audio-as-code`, import `audio_as_code`, and CLI `aac`.

The public website should be playful, distinctive, and useful to developers and AI agents. It should demonstrate real generated audio, teach composition and rendering, and present complete classic/reimagined listening pairs with inspectable code, JSON scores, WAV, and MIDI. The public website is a separate surface from the existing instrument audition desk; its visual direction must preserve the latter's functionality.

The primary journey is agent-first: hear an example, copy one handoff prompt,
give the framework to a coding agent, and describe the music. The agent obtains
the source, reads the bundled portable skill, prepares a local environment, and
delivers an original WAV, MIDI, editable score, composer source and render report.
The person can request revisions in ordinary language. Learning Python is an
optional developer route. This promise requires a real source download and
public `skills/audio-as-code/SKILL.md`; it must not imply a hosted generation API,
browser Python execution, a published registry package or a bundled AI model.

The main use is sound inside creative agent workflows: an original soundtrack
for a video, music cues and stingers for a game, or an intro, background bed and
ending for a presentation. The agent composes and renders locally, then carries
the WAV into the active creative project while retaining the editable score.
Use playful, concrete briefs and show verified file handoffs to tools such as
Hyperframes, alongside Codex and Claude Code setup. These are CLI and file-based
recipes, not native connectors. Current support is procedural instrumental
music and musical cues; do not imply speech synthesis, arbitrary sound effects
or automatically seamless game loops.

The website listening program pairs five recognizable public-domain works with
new arrangements written by an AI agent: *Für Elise*, Bach's Cello Suite No. 1
Prelude, Mozart's *Turkish March*, *Greensleeves*, and *Ode to Joy*. Use **The
classic** and **Reimagined** as the two labels. The classic follows its credited
source score; the reimagining changes instrumentation, rhythm or mood. Both sides
must be complete within the credited source or standalone arrangement's scope,
synthesized by this engine, and available as editable scores. A complete *Ode to
Joy* hymn arrangement must not be presented as Beethoven's full symphonic movement.
Keep historical composer attribution separate from the agent's arrangement credit.

Preserve the five classic score IDs. Keep the four unrelated original full
compositions in the source repository, outside the website lineup. The paired
program replaces the previous short-excerpt collection only when its generated
artifacts are ready. No preview uses external audio or represents a recorded
acoustic performance. Describe the actual musical difference in each pair;
avoid inventing genres, instruments or production effects before hearing or
inspecting the new arrangement.

## Platform

web

## Stack

The framework is Python; listening pages use static HTML, CSS, and JavaScript with locally rendered WAV files. No server is required for the existing instrument audition surface. The requested public website should be portable to a static host and include human-readable tutorials and machine-readable agent resources.

## Users

The framework author is evaluating instrument sounds and their implementation status. Developers and AI agents use the Python API, JSON score, and CLI to compose and render music. Public website visitors need to hear what the framework actually produces and reproduce an example from source.

## Product Purpose

An open-source framework that lets creative agents compose editable music for videos, games and presentations. The public website demonstrates the music and hands the framework to an agent. A separate instrument library lets people audition every playable voice.

## Capabilities and Constraints

Optional score expression includes ordered step tempo changes, linear/step track
gain and pan automation, master-gain automation, note/track releases, and generated
delay/reverb chains. Renders include bounded tails within a 300-second total.
MIDI preserves tempo changes but omits audio effects, automation and releases;
stems omit master effects. These controls remain editable composition data.

Confirmed in the conversation: instrument sound must come from code and physical/procedural synthesis, without recorded samples or instrument libraries. The catalog has eight musical families and five engine groups. All 45 catalog entries now have playable prototypes, including a generated drum kit. The page states each approximation's scope; availability does not establish acoustic realism. Future planned entries must never receive a substitute sound that implies implementation.

Each instrument has Music, Phrase, and Single note or Single hit previews (135 clips total); the Music collection contains 31 solo and 14 combined arrangements with repertoire details and source credits. Search includes piece titles and arrangements, while About this sound preserves the synthesis limitations and supported score controls.

## Evidence on Hand

The catalog in `src/audio_as_code/instruments.py`, existing Python-generated audio, score and MIDI exports, and local listening pages in `examples/showcase.py` and `examples/physical_instruments.py`.

## Product Principles

- Let the user hear actual framework output.
- Clearly distinguish playable prototypes from planned instruments.
- Preserve the editable score behind each preview.
- Keep local listening immediate and usable without setup.
