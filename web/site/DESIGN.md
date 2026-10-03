---
name: Audio as Code public site
description: Paste-Up. A fly-posted risograph gig poster printed from each piece's own data, in fluoro pink, blue, yellow and black on cool white stock, that hands the music job to your agent.
colors:
  riso-pink: "#ff48b0"
  riso-blue: "#0078bf"
  riso-yellow: "#ffe800"
  pink-deep: "#b8146f"
  ink: "#141413"
  paper: "#f9fbfd"
  rule: "#d8d6cc"
  muted: "#45443f"
  on-ink-soft: "#dddcd3"
  code-text: "#f2f1ea"
  code-caption: "#cfcec5"
  code-divider: "#4a4943"
  code-comment: "#b4b3aa"
  code-string: "#ff9ad2"
  code-number: "#7cc8ff"
typography:
  headliner:
    fontFamily: "Anybody, Archivo, sans-serif"
    fontSize: "clamp(64px, 12vw, 190px)"
    fontWeight: 900
    lineHeight: 0.82
    letterSpacing: "-0.02em"
    fontVariation: "\"wdth\" 100"
  presenter:
    fontFamily: "Anybody, Archivo, sans-serif"
    fontSize: "clamp(30px, 4.1vw, 60px)"
    fontWeight: 900
    lineHeight: 0.95
    letterSpacing: "-0.015em"
    fontVariation: "\"wdth\" 150"
  presenter-verb:
    fontFamily: "Anybody, Archivo, sans-serif"
    fontSize: "clamp(24px, 3vw, 44px)"
    fontWeight: 500
    lineHeight: 0.95
    letterSpacing: "0"
    fontVariation: "\"wdth\" 52"
  display-band:
    fontFamily: "Anybody, Archivo, sans-serif"
    fontSize: "clamp(40px, 6.2vw, 96px)"
    fontWeight: 900
    lineHeight: 0.95
    letterSpacing: "-0.01em"
    fontVariation: "\"wdth\" 112"
  footer-mark:
    fontFamily: "Anybody, Archivo, sans-serif"
    fontSize: "clamp(48px, 10.6vw, 190px)"
    fontWeight: 900
    lineHeight: 0.84
    letterSpacing: "-0.02em"
    fontVariation: "\"wdth\" 150"
  headline-doc:
    fontFamily: "Anybody, Archivo, sans-serif"
    fontSize: "clamp(40px, 5.6vw, 92px)"
    fontWeight: 900
    lineHeight: 0.88
    letterSpacing: "-0.01em"
    fontVariation: "\"wdth\" 104"
  title-step:
    fontFamily: "Anybody, Archivo, sans-serif"
    fontSize: "clamp(26px, 2.4vw, 36px)"
    fontWeight: 900
    lineHeight: 1.1
    letterSpacing: "-0.01em"
    fontVariation: "\"wdth\" 96"
  title:
    fontFamily: "Anybody, Archivo, sans-serif"
    fontSize: "22px"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.01em"
    fontVariation: "\"wdth\" 92"
  label-tag:
    fontFamily: "Anybody, Archivo, sans-serif"
    fontSize: "17px"
    fontWeight: 900
    lineHeight: 1
    letterSpacing: "0.02em"
    fontVariation: "\"wdth\" 92"
  label-nav:
    fontFamily: "Anybody, Archivo, sans-serif"
    fontSize: "15px"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "0.04em"
    fontVariation: "\"wdth\" 78"
  label-small:
    fontFamily: "Anybody, Archivo, sans-serif"
    fontSize: "11px"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "0.08em"
    fontVariation: "\"wdth\" 90"
  body:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.6
  body-lede:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "clamp(18px, 1.5vw, 21px)"
    fontWeight: 400
    lineHeight: 1.5
  body-prose:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 400
    lineHeight: 1.7
  mono-code:
    fontFamily: "JetBrains Mono, ui-monospace, Cascadia Mono, monospace"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.65
  mono-meta:
    fontFamily: "JetBrains Mono, ui-monospace, Cascadia Mono, monospace"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.2
    fontFeature: "\"tnum\" 1"
rounded:
  none: "0px"
  sm: "2px"
  pill: "999px"
  disc: "50%"
spacing:
  gutter: "clamp(16px, 3.4vw, 56px)"
  strip: "64px"
  strip-phone: "56px"
  band: "clamp(72px, 9vw, 136px)"
  step-gap: "clamp(56px, 6vw, 88px)"
  step-top: "clamp(64px, 8vw, 104px)"
  tag-row: "28px 24px"
  lineup-row: "64px"
components:
  tag:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.label-tag}"
    rounded: "{rounded.none}"
    padding: "0 18px"
    height: "52px"
  tag-hover:
    backgroundColor: "{colors.riso-yellow}"
    textColor: "{colors.ink}"
  tag-ink:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.label-tag}"
    rounded: "{rounded.none}"
    padding: "0 18px"
    height: "52px"
  tag-ink-hover:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.riso-yellow}"
  tag-agent-cta:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.label-tag}"
    rounded: "{rounded.none}"
    padding: "0 22px"
    height: "60px"
  sticker-play:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.disc}"
    size: "clamp(124px, 12.6vw, 186px)"
  lineup-work:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0 10px"
    height: "64px"
  lineup-work-chosen:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  version-chip:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0 9px"
    height: "26px"
  version-chip-chosen:
    backgroundColor: "{colors.riso-yellow}"
    textColor: "{colors.ink}"
  brief-chip:
    backgroundColor: "transparent"
    textColor: "{colors.paper}"
    rounded: "{rounded.none}"
    padding: "0 14px"
    height: "44px"
  brief-chip-pressed:
    backgroundColor: "{colors.riso-yellow}"
    textColor: "{colors.ink}"
  brief-field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "16px 18px"
    height: "200px"
  code-panel:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.code-text}"
    typography: "{typography.mono-code}"
    rounded: "{rounded.sm}"
    padding: "18px"
  copy-button:
    backgroundColor: "{colors.riso-yellow}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0 14px"
    height: "34px"
  copy-button-done:
    backgroundColor: "{colors.riso-pink}"
    textColor: "{colors.ink}"
  ticket-download:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0 18px 0 20px"
    height: "54px"
  ticket-download-lead:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    height: "76px"
  ticket-download-hover:
    backgroundColor: "{colors.riso-pink}"
  section-tab:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "12px"
    height: "92px"
  section-tab-hover:
    backgroundColor: "{colors.riso-yellow}"
  mini-key:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.pill}"
    padding: "0 20px 0 16px"
    height: "52px"
  revision-note:
    backgroundColor: "{colors.riso-yellow}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "18px 22px"
  deliverable-slip:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "12px 16px"
  note-slip:
    backgroundColor: "{colors.riso-yellow}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "16px 20px"
---

# Design System: Audio as Code public site

Scope: the public website built from `web/site` into `output/site` (home, guides, examples, source, 404, shared strip and footer). The instrument audition desk keeps its own system in the root `DESIGN.md`; this file does not govern it. This file replaces the rejected Calibration Bench record; nothing of that world carries over.

## Overview

**Creative North Star: "The Paste-Up"**

Every piece gets a fly-posted gig poster, printed from its own data. The first viewport is a full-bleed risograph sheet. The real min/max envelope of the selected render is a fluoro silhouette across the middle. The real notes of its score run as a plate across the whole sheet. The work's name is overprinted in a huge tilted headliner. Three Riso drums (pink, blue, yellow) and black are the only inks. They overprint by `multiply` on a cool white stock, so overlaps make new colours the way a press does. Misregistration, halftone dot screens, torn paper edges, tape, stickers and tear-off tabs are the native materials. They are the world, not decoration on top of it.

Below the poster the page is a stack of torn paper stocks: blue, yellow, paper, pink, blue, paper, then black ink for the footer. Each stock carries one job. The flow is agent-first: the poster's ink "Give it to your agent" tag leads to the blue handoff band. There the visitor describes the music, copies one prompt built from that brief, and learns what comes back (WAV, MIDI, editable score, source, report) and how to ask for revisions. Density is loose and loud at the top and readable in the bands. Display type shouts in Anybody's variable width axis; Archivo reads; JetBrains Mono carries files, clocks and code.

The user explicitly rejected Calibration Bench (beige enamel rack panels, amber CRT scopes) and approved this look. Keep it as approved.

**Key Characteristics:**
- Four inks only (fluoro pink, blue, yellow, black) on cool white stock, overprinted by `multiply`.
- The poster is drawn from shipped data: envelope silhouette, note plate and section tabs come from the selected render, not illustration.
- Anybody's width axis is the main typographic voice, from 50% condensed to 150% extended in the same family.
- Hand-placed angles (−9° to +2.5°) on stickers, tags, slips and the chosen bill line, over a plain grid.
- Flat print: depth comes from ink overlap, misregistration offsets and torn edges. There are no blurred shadows.
- An agent-first handoff: describe, copy one prompt, paste, listen, revise.

## Colors

A three-drum risograph palette with black, printed on a cool white stock. All pink, blue and yellow surfaces that overlap other ink use `mix-blend-mode: multiply` (canvas plates use `globalCompositeOperation = "multiply"`).

### Primary
- **Fluoro Pink** (riso-pink): the hand-drawn marker ring (`ring.svg`) around the current nav item, section tab and docs page. It is the misregistration plate under the Play sticker and behind display heads (`text-shadow` offset). It inks the oversized step numerals, the dots between voices and families, the limit bullets, the Ko-fi heart, the link hover underline and the copied state of code Copy buttons. It is the first plate of the poster rotation (envelope on piece 1).

### Secondary
- **Riso Blue** (riso-blue): the headliner ink on the first two poster prints, the handoff and instruments stocks, docs and source H1s, docs link colour, and the textarea caret. On blue stock, text is paper.

### Tertiary
- **Process Yellow** (riso-yellow): the highlighter. It marks text selection, chosen version chips and pressed brief chips, hover fills on tags, tabs and lineup chips, tape on tags, the revision note and note slips, family count chips, inline code (60% alpha on paper) and the focus halo. It is the program stock and the default note plate.
- **Deep Pink** (pink-deep): pink that must read as text on paper. Used for the "presents" verb, the nav Ko-fi link, list markers, the current docs TOC entry, heading anchors and the caret.

### Neutral
- **Press Black** (ink): all body text, 3px rules and borders, the Play sticker disc, inverse slabs (chosen bill line, prompt and code panels, primary download ticket), the playhead and registration marks, and the footer stock.
- **Cool White Stock** (paper): the page and poster ground, paper bands, tags, tickets and slips, and text on ink and blue.
- **Pale Rule** (rule): quiet docs-table row rules and the docs TOC dots.
- **Graphite** (muted): composer surnames and durations in the lineup.
- **Soft White on Ink** (on-ink-soft): footer note and the disabled opt-out label on the black footer.
- **Code panel set** (code-text, code-caption, code-divider, code-comment, code-string, code-number): text, figcaption, dashed divider and syntax tints inside ink code panels only. Keywords use Process Yellow.

### Named Rules
**The Three Drums Rule.** Pink, blue, yellow and black are the only inks. A new surface is one of these stocks or an overprint of them. The code-panel syntax tints stay inside code panels.

**The Overprint Rule.** Coloured ink that crosses other ink multiplies. Coloured flat fills are never stacked opaquely on top of each other.

**The Ink-on-Stock Rule.** Text colour follows the stock: ink on paper, yellow and pink; paper on blue and black. Counts on blue sit as ink on a yellow chip.

## Typography

**Display Font:** Anybody (variable weight 100–900, width 50–150%), fallback Archivo, sans-serif
**Body Font:** Archivo (variable weight 100–900, width 62–125%), fallback system-ui, sans-serif
**Label/Mono Font:** JetBrains Mono (400–700), fallback ui-monospace, Cascadia Mono, monospace

All three are self-hosted latin WOFF2 subsets under the SIL Open Font License 1.1, with licences in `web/site/assets/fonts/`. They use `font-display: swap`. Anybody and Archivo are preloaded.

**Character:** Anybody does the shouting and the width axis does the work. The same family runs 150% extended for the presenter and footer mark, 52% condensed for the pink "presents", and 62–78% condensed for numerals, bill lines and labels. Archivo is the plain reading voice. JetBrains Mono is for anything a machine would print: clocks, durations, file names, facts, meters and code. Width is set in CSS with `font-stretch` percentages; the frontmatter records it as the equivalent `wdth` axis value.

### Hierarchy
- **Headliner** (Anybody 900, width 100%, line-height 0.82, uppercase): the poster's work title, two lines, tilted by the print. Its size is fitted by script into a fixed box: 48–250px on desktop, at most 120px on narrow screens.
- **Presenter** (Anybody 900, width 150%, uppercase) with the **presenter verb** (Anybody 500, width 52%, lowercase, deep pink): the H1 "Audio as Code presents".
- **Display band** (Anybody 900, width 112%, uppercase): band H2s. Bands adjust width per stock: handoff 120%, program 104%, agents 128%.
- **Footer mark** (Anybody 900, width 150%; the middle word "as" drops to 50% in yellow).
- **Headline doc** (Anybody 900, width 104%, uppercase, blue with pink offset): guide H1s. Source and 404 sheet H1s use clamp(48px, 9vw, 150px) at 120% width.
- **Title step** (Anybody 900, width 96%, uppercase): numbered handoff and loop step heads.
- **Title** (Anybody 800, width 92%): default H3. In prose, H2 is clamp(28px, 2.6vw, 38px) at 96% width, sentence case.
- **Body** (Archivo 400, 17px/1.6); **lede** (clamp(18px, 1.5vw, 21px)/1.5, about 60–64ch); **prose** (18px/1.7, 72ch column).
- **Labels** (Anybody 800–900, 11–17px, width 74–92%, letter-spacing 0.02–0.08em, uppercase): tags, nav, tabs, facts and meters terms, figcaptions.
- **Mono** (JetBrains Mono): 14px/1.65 code, 12px durations and clocks, 17px facts and 24px meters with tabular numerals.

### Named Rules
**The Width Axis Rule.** Hierarchy comes from Anybody's width and weight, not from new families. Extended shouts, condensed labels, and mono for anything machine-printed.

**The Fixed Box Rule.** The headliner fills a fixed box (52vh desktop, clamp(140px, 23vh, 196px) below 960px) and is fitted after fonts load. Swapping fonts or titles never moves the poster around it. There is no font-visibility gate: text shows immediately with the fallback.

## Layout

**Strip.** A 64px header (56px under 760px) on paper holds the mark and an uppercase nav: Listen, Guides, Agents, Instruments, Source and a Ko-fi Support link. Under 760px the wordmark hides and Support collapses to its heart, keeping its accessible name.

**Poster grid (≥960px).** Two columns: `minmax(0, 1fr)` and a bill of clamp(290px, 25vw, 372px), with a column gap of clamp(24px, 3.4vw, 64px). Grid areas are "head bill / title bill / scope scope / tabs tabs". The minimum height is max(640px, 100svh − strip). The headliner sits bottom-left and overlaps down into the scope band by up to 120px. Play and the agent tag sit on the scope, right of centre. The section tabs run full-bleed along the bottom under a dashed rule.

**Poster (<960px).** One column: head, title, scope, bill, tabs. The Play sticker (118px) and the agent tag sit across the bottom of the scope band. The bill follows below the poster's first screen.

**Space is reserved before script fills it.** The lineup has `min-height` from `--pieces × --row + 3px`, with 5 works × 64px by default. Tabs keep 116px. The tagline keeps 5.6em on phones. The headliner box is fixed.

**Bands.** Each stock pads clamp(72px, 9vw, 136px) vertically and uses the gutter clamp(16px, 3.4vw, 56px) horizontally. Numbered steps (handoff, loop) use a two-column grid with gaps of clamp(56px, 6vw, 88px) by clamp(32px, 5vw, 72–80px), starting clamp(64px, 8vw, 104px) below the lede. Under 960px steps stack with 116px row gaps and a 112px top margin, so the oversized numerals never collide with text above them. Handoff step 3 spans both columns: deliverables on the left, the revision note on the right.

**Docs.** Three columns: side nav 200px, prose `minmax(0, 72ch)`, and a sticky TOC of 210px. Under 1080px the TOC drops. Under 760px it is one column, with the side nav as a wrapping row.

**Breakpoints:** 1200px (tabs keep one-line labels and scroll), 1080px (docs TOC hides), 959/960px (poster and bands go single column), 760px (phone strip and type), 640px (tear-offs horizontal, compact tickets). There is no horizontal page scroll (`overflow-x: hidden` on body). Long strips (tabs, wide tables) scroll inside their own box.

## Elevation & Depth

The system is flat print. There are no blurred shadows. Depth is conveyed by ink overlap (`multiply`), by hard misregistration offsets of a second ink, by rotation, and by torn stock edges overlapping the band above.

### Shadow Vocabulary
- **Pink plate offset** (`text-shadow: .05em .035em 0 #ff48b0`): misregistered second plate behind the handoff H2, docs H1 and source/404 H1. The loop H2 and footer mark use `-.035em .03em 0` (pink). The footer's "as" uses blue.
- **Sticker plate** (pink disc `translate(7px, 6px)`, multiply, under the black disc): the Play sticker's misregistration.
- **Focus halo** (`outline: 3px solid ink; outline-offset: 3px; box-shadow: 0 0 0 7px yellow`): the only box-shadow, used for keyboard focus. On blue and ink surfaces the outline turns paper or yellow and the halo turns ink.
- **Torn edge** (20px `torn.svg` mask, 1200px repeat, 19px above each stock; footer offset 300px): each band tears over the one above.

### Named Rules
**The Flat Press Rule.** Surfaces are flat at rest. A second ink offset or a rotation is the only lift. There are no ambient or blurred drop shadows.

## Shapes

Corners are square (0) on tags, tickets, slips, tabs, lineup rows and chips. A 2px radius softens only code panels, the brief textarea, inline code and focus. Circles are reserved for the Play sticker, registration marks, dots and bullets. The loop's mini player key is the one pill (999px). Recurring silhouettes:
- the hand-drawn pink marker ring;
- ticket notches: radial-gradient masks, 8px on downloads, 11px on the lead ticket, 13px on the big source ticket;
- dashed perforation rules on tabs, tear-offs and credits;
- yellow tape strips (66×22px, rotated −5°) on tags;
- torn top edges on every band.

Borders are heavy: 3px ink on tags, 3px rules between lineup works, limits and meters, and 2px on chips and dashed rules.

## Components

### Buttons and tags
- **Tag (link button):** paper, 3px ink border, Anybody 900 17px uppercase, 52px tall, rotated 2.5° with yellow tape on top. **Hover:** straightens to 0°, lifts 2px, fills yellow, and its arrow nudges 4px.
- **Ink tag:** black fill, paper text, pink tape; hover turns the text yellow. The poster's **Give it to your agent** CTA is an ink tag at 60px, 20px text, with a down arrow to `#handoff`. On phones it wraps to two lines within 210px rather than squeezing the sticker.
- **Paper tag on colour:** the handoff Copy tag and footer Ko-fi tag. Normal-blend tape. It turns yellow when copied or hovered.

### Play sticker (signature)
A black disc (clamp(124px, 12.6vw, 186px), 118px on phones), rotated −9°, over a pink misregistration disc. It holds a play/pause glyph (inline SVG), "Play"/"Pause" and a mono clock `0:00 / 2:36`. A text ring runs round the rim; it names the selected version, e.g. "the classic · from the public-domain score · synthesized ·" or "reimagined by an AI agent · synthesized from code ·". The ring spins (16s linear) only while playing and pauses when the poster is off screen. Hover: −4° and ×1.04. Active: ×0.97. The sticker is disabled until a piece is selected. Its accessible name is "Play <title>" or "Pause <title>".

### Lineup bill (paired works)
A `radiogroup` of five works: Für Elise, Cello Suite No. 1 · Prelude, Turkish March, Greensleeves and Ode to Joy. Each work is a 64px row: an Anybody 74% name, the composer surname in mono, then two adjacent version chips, **The classic** and **Reimagined**, each with its mono duration. Rows are divided by 3px ink rules.
- **Chosen work:** the row flips to an inverse black slab, rotated −1.6° and scaled ×1.03.
- **Chosen chip:** fills yellow, rotated 1.5°. The other chip on the chosen row is a paper outline.
- **Keyboard:** roving tabindex. Left/Right switch version within a work. Up/Down move between works and keep the version. Both wrap. Accessible names read "work: version, length".
- **Selection** updates title, credits, sticker ring, facts, downloads, tabs and roll. It stops any playback and resets to 0:00; the two arrangements are not time-mapped. The URL gets `#piece-<id>`, and deep links select on load. Für Elise, the classic, is the default.

### Section tabs
Tear-off tabs along the poster foot, separated by dashed rules. Each shows a mono start time and an Anybody label. The tab for the section under the playhead gets the marker ring. Passed tabs hang: 9px down, rotated ±1–2.6°. Clicking a tab seeks there and starts playback. Below 1200px tabs keep one-line labels and the strip scrolls.

### Scope and scrub
The envelope band carries an invisible full-size range input ("Seek within the piece"). Clicking or dragging seeks. Keyboard focus outlines the whole scope with the yellow halo inset. Status messages appear as a tilted black mono slip.

### Handoff band (agent-first, blue)
1. **Describe the music:** four brief chips ("Dragon boss fight", "Villain-arc report", "Launch video", "Just music") with `aria-pressed`. They are paper outlines on blue; pressed chips fill yellow and tilt −1.5°. A paper textarea (200px minimum, Archivo 17px, blue caret). Editing it unpresses chips that no longer match.
2. **Copy the prompt:** an ink code panel holds the prompt, rebuilt live from the brief, with links absolute to the page's origin. A paper **Copy agent prompt** tag is taped across the panel's foot, over an empty strip reserved for it. Copied: the tag turns yellow and a status line confirms. Blocked: the prompt is selected and the status explains how to copy.
3. **Paste it in, then listen:** paper deliverable slips (WAV, MIDI, score.json, source, report) in mono, alternately rotated −1° and 1.2°. A yellow **revision note** (Anybody 800, −0.6°) shows a plain-language change request.

Under the steps: an integrations sentence (Hyperframes, Codex, Claude Code), then a row of paper tags: Integrations guide, Agent skill · SKILL.md, Source ZIP, llms.txt, Agent guide, Developer quickstart. Even-numbered tags rotate −2°.

### Program band (yellow)
Piece title, an uppercase meta line (composer · version · arrangement), a description and a voices list with pink dots. Download **tickets** are notched paper tickets; the lead "WAV, exact render" ticket is black and 76px. They cover the MP3 preview, MIDI, JSON score, Python source and runnable bundle, and hover lifts them −1° with a pink fill. The **roll** is a yellow canvas with each track in an ink and screen (solid, dots, lines), plus a swatch key. There is a code excerpt panel, a credit line, and a **Score credits** list with dashed rows linking each Mutopia edition once.

### Code panels and copy
Ink panels, 2px corners, uppercase figcaption with a dashed divider, and a yellow **Copy** button rotated −1.5°. Hover straightens it and turns it paper; after copying it turns pink and reads "Copied" for 1.8s. If copying fails it reads "Select and copy" and selects the code. Selection inside code is yellow on ink.

### Loop band, mini player and meters
Numbered steps with giant condensed numerals (pink, blue, yellow; multiply, behind the text). A black pill mini key plays `loop.wav` beside a pink envelope trace that overprints blue as it plays. Meters are mono values over 3px rules.

### Tear-off sheet (pink band)
A paper sheet rotated 1.6°, with "Take one" in condensed blue. Below a dashed rule, vertical tear-off tabs link SKILL.md, llms.txt, the schema, instruments.json, the manifest and the docs. Hover drops a tab 10px and rotates it ±4°. Under 640px the tabs lie horizontal.

### Navigation and docs
Nav links are Anybody 800 uppercase. Hover fades the marker ring in at 45%; the current page shows it at full strength. In docs, the side nav is condensed 19px uppercase with a ring on `aria-current`. The TOC tracks the heading in view, using a deep-pink entry and an enlarged pink dot. Other docs elements:
- yellow note slips (−0.35°);
- tables with ink header cells;
- dashed `hr`;
- a black pager tag (−1.5°).

### Footer and visitor controls
A black torn stock with the giant mark, a paper Ko-fi tag (opens a new tab; nothing from Ko-fi loads with the page), a version note and yellow-underlined links. There is an **Analytics and privacy** link and an **Opt out of analytics** button underlined in pink. The button is hidden by default. The analytics script reveals it only on the allowed production hosts (`audioascode.com`, `www.audioascode.com`). After opting out, or under Global Privacy Control or Do Not Track, it reads "Analytics off" and is `aria-disabled`. Ordinary local previews load no analytics. There is one shared audio element (`preload="none"`), so no media loads before Play and only one sound plays at a time.

### Motion
- **Easing:** `--ease: cubic-bezier(.16, 1, .3, 1)` for every settle.
- **Slap:** choosing a piece pastes a new print. The headliner drops from −7%, rotated −5° and ×1.1, through a 1° overshoot, to rest over 0.62s. The plate canvas comes back into register from (12px, −8px) over 0.7s. Both animations are transform-only.
- **Breathe:** while playing, the headliner's ink line follows the envelope at the playhead as a compositor `scaleX` between 0.86 and 1.14.
- **Print as it plays:** unplayed plates show as a halftone dot screen. Solid ink prints left of the playhead, with a black playhead line and two registration marks. Sounding notes are outlined.
- **Frame budget:** playback draws at about 24 fps from cached plate canvases. Nothing draws while the tab is hidden or the poster and roll are off screen. Layout is read only on resize, selection and font load. The exact values are in the sidecar's `motion`.
- **Reduced motion:**
  - no slap and no register animation;
  - no breathing; the headliner's live class is never set;
  - the sticker ring does not spin;
  - CSS animations and transitions collapse to 0.001ms;
  - group scrolling is instant;
  - the playhead, clock and tabs still update, throttled to every 250ms.

## Do's and Don'ts

### Do:
- **Do** print every new surface in the three drums and black on cool white stock, and overprint coloured ink with `multiply`.
- **Do** draw poster plates from real data: the selected render's envelope, its score's notes and its sections.
- **Do** mark state with print devices: the inverse slab for the chosen bill line, the yellow chip for the chosen version, the pink marker ring for current, and a hanging tab for passed.
- **Do** keep hierarchy in Anybody's width axis and keep mono for files, clocks, counts and code.
- **Do** reserve space before script fills it (fixed headliner box, lineup min-height, tab strip, phone tagline) so nothing shifts.
- **Do** animate only transforms and opacity, stop drawing when off screen or hidden, and give every motion a reduced-motion path.
- **Do** keep the agent handoff as the primary call: the ink "Give it to your agent" tag in the first viewport, one copyable prompt, and the tag row of skill, llms.txt, ZIP and guides.
- **Do** put text on its matching stock (Ink-on-Stock Rule) and use the yellow focus halo for keyboard focus everywhere.

### Don't:
- **Don't** bring back Calibration Bench: rack panels, enamel, amber CRT scopes or a safety-orange commit colour.
- **Don't** add blurred or ambient drop shadows, gradients as decoration, or glass; depth is ink overlap, offset plates and torn edges.
- **Don't** introduce new hues outside the four inks, apart from the code-panel syntax tints inside code panels.
- **Don't** round tags, tickets, slips or tabs; circles belong to the sticker, dots and marks.
- **Don't** stage a fake live renderer or illustrated waveform; the site plays files rendered offline.
- **Don't** autoplay, load media before Play, or play two sources at once.
- **Don't** time-map or crossfade the two versions of a work; switching version stops and returns to 0:00.
- **Don't** load third-party scripts on ordinary local previews, or embed Ko-fi widgets.
