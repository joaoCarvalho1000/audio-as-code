---
name: Audio as Code listening surfaces
description: A quiet cream and forest-green instrument audition desk.
colors:
  green: "#315c35"
  green-dark: "#24472a"
  paper: "#f6f4ef"
  surface: "#fffefa"
  ink: "#252d26"
  muted: "#62695d"
  line: "#d9ddd1"
  wash: "#e8eddf"
  error: "#993d31"
typography:
  display:
    fontSize: "clamp(32px, 3.2vw, 44px)"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-.035em"
  title:
    fontSize: "26px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-.025em"
  music-title:
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: '"Segoe UI", system-ui, sans-serif'
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: '"Segoe UI", system-ui, sans-serif'
    fontSize: "13px"
    fontWeight: 600
  identifier:
    fontFamily: "ui-monospace, Consolas, monospace"
    fontSize: "11px"
rounded:
  compact: "4px"
  control: "7px"
  panel: "12px"
  circular: "50%"
spacing:
  compact: "8px"
  small: "12px"
  medium: "16px"
  section: "24px"
components:
  button-primary:
    backgroundColor: "{colors.green}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "11px 15px"
    width: "100%"
  button-primary-hover:
    backgroundColor: "{colors.green-dark}"
  button-round:
    backgroundColor: "transparent"
    textColor: "{colors.green}"
    rounded: "{rounded.circular}"
    width: "38px"
    height: "38px"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.green}"
    padding: "3px 0"
  input-search:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "10px 12px 10px 38px"
  family-selected:
    backgroundColor: "{colors.wash}"
    textColor: "{colors.green-dark}"
    rounded: "{rounded.control}"
    padding: "10px 12px"
  availability-selected:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.green-dark}"
    padding: "8px 14px"
  status-playable:
    backgroundColor: "{colors.wash}"
    textColor: "{colors.green-dark}"
    rounded: "{rounded.compact}"
    padding: "4px 7px"
  detail-panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "22px"
  instrument-selected:
    backgroundColor: "{colors.wash}"
    textColor: "{colors.ink}"
    padding: "13px 12px"
  music-title:
    textColor: "{colors.ink}"
    typography: "{typography.music-title}"
  preview-mode:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.compact}"
    padding: "8px"
  preview-mode-selected:
    backgroundColor: "{colors.wash}"
    textColor: "{colors.green-dark}"
  sound-details:
    textColor: "{colors.ink}"
    padding: "16px 0 0"
---

# Design System: Audio as Code listening surfaces

## Overview

**Creative North Star: "The instrument audition desk"**

A quiet, practical listening surface: cream paper, dark ink, forest-green controls, and generous separation between dense catalog information. It extends the established local listening pages with flat instrument rows and a lightly enclosed detail panel.

Sound supplies the distinctive visual material. SVG envelopes come from the generated audio; availability, selection, and playback have separate visible states. This system is extracted from `web/instrument-browser.html` and the reviewed desktop and mobile output, with surface intent recorded in `docs/instrument-browser-brief.md`.

**Key Characteristics:**
- Cream surfaces and restrained forest-green emphasis.
- Flat, ruled catalog rows with readable metadata.
- Real waveform envelopes and one persistent audio transport.
- Explicit playable and planned states.

## Colors

A warm neutral foundation carries a single green accent; semantic status colors remain subordinate.

### Primary

- **Forest green** (`green`): preview actions, links, focus outlines, playback progress, and range controls.
- **Deep forest** (`green-dark`): primary hover state and selected-control text.

### Neutral

- **Cream paper** (`paper`): page canvas.
- **Warm white** (`surface`): detail panel, fields, selected availability segment, and player.
- **Dark ink** (`ink`): names, headings, and primary information.
- **Muted olive** (`muted`): supporting descriptions, families, counts, and timings.
- **Soft sage line** (`line`): row rules, panel outlines, and section dividers.
- **Sage wash** (`wash`): selected rows, active family and preview modes, and playable status.

Error messages use the `error` token. Planned status has a localized warm-brown treatment; it is a semantic exception rather than a second brand accent.

**The Selection Wash Rule.** Use the sage wash to mark the current choice across rows and controls; reserve solid green for the main playback action.

## Typography

**Body Font:** Segoe UI with system sans-serif fallbacks.
**Label/Mono Font:** UI monospace with Consolas fallback for score identifiers.

The current implementation uses the body stack for headings too. Its system display face is a carried craft limitation, not a display-family rule for future surfaces; the frontmatter records the observed heading sizes without canonizing that family choice.

The hierarchy is compact: responsive page heading, medium detail title, ordinary instrument names, and smaller metadata. Body copy uses the frontmatter body role; explanatory detail paragraphs reduce to (13px) with a more open line height (1.7). Instrument names use (15px, weight 600); supporting labels range from (11px) to (13px). The introductory sentence is limited to (65ch). Counts, timings, and control values use tabular numerals. Mobile detail titles reduce to (25px) and row names to (14px).

Music titles use the `music-title` role beneath the instrument heading, with balanced wrapping. Composer and arrangement copy uses muted text (12px, line height 1.6); source-credit links use (11px). These additions retain the existing body stack and compact metadata hierarchy.

**The Numbers Stay Aligned Rule.** Use tabular numerals for counts, durations, progress, and numeric settings; reserve monospace for identifiers.

## Layout

Shared header, main content, and player align inside a centered container (1440px maximum) with desktop side padding (48px). Main content uses a family rail (174px), flexible list, and detail panel (294px), separated by gaps (28px). The family rail and detail panel stick (24px) below the viewport top. Rows are at least (80px) high. The repeated spacing vocabulary favors (8px), (12px), (16px), and (24px), with context-specific intermediate values.

At (1150px) and below, side padding becomes (28px), columns narrow to (150px / flexible / 265px), and gaps become (20px). At (920px), a native family selector replaces the rail, the catalog becomes two columns, and volume controls disappear. At (650px), the page uses (20px) gutters, search precedes availability filters, the detail panel sits above the list, and sticky panels return to normal flow. Selecting a row on mobile scrolls its details into view.

The fixed bottom transport persists across sizes. Its desktop three-column layout becomes two rows on mobile. Main content reserves bottom space (144px desktop; 155px mobile) so the final content remains reachable above the player.

## Elevation & Depth

Depth comes from warm-white surfaces, sage selection fills, and fine borders. Rows remain flat. The sole ambient shadow belongs to the active availability segment (`0 1px 3px #29302512`), which distinguishes the selected tab inside its muted track. The player is separated by a top rule, without a floating shadow.

## Shapes

Controls have modest curves; the detail panel uses the broader panel radius. Status labels use the compact radius. Playback buttons are circles, while catalog rows stay rectangular. Outlines and dividers are thin (1px). Icons are inline SVG strokes with rounded caps and joins; waveform envelopes use vertical strokes derived from audio peaks.

## Components

### Buttons

Primary preview buttons span the detail panel and have a minimum height (44px). Row preview actions are compact outlined circles that fill green on hover. Reset actions use a plain underlined text treatment. Disabled controls reduce opacity (.48) and use a not-allowed cursor. All interactive controls share a green focus outline (3px) with offset (4px).

Color and background transitions take (140ms, ease-out), enabled only when reduced motion is not requested. No movement is required to communicate a state change.

### Filters and navigation

Availability uses a compact segmented group with counts and a warm-white active segment. Family navigation uses full-width text rows with counts; active families use the selection wash. The family selector preserves the same filtering function at smaller widths. Search has a leading SVG magnifier, a warm-white fill, a subtle border, and a minimum height (44px).

Search includes repertoire titles and arrangement names alongside instrument, family, and engine metadata; its label and placeholder explicitly mention music.

### Status labels

Playable status combines a small dot with text on a sage fill. Planned status uses text and a warm neutral fill. Status never depends on color alone. Planned rows omit playback controls and show their state in words.

### Catalog and detail

Each catalog row combines a name, contextual caption, measured waveform, and a separate play action when available. Music mode captions show the piece title and arrangement; Phrase and Single note modes show the family. The waveform follows the selected mode. Selecting a name changes the detail panel; playing is a distinct control. The panel contains availability, identifier, preview modes, waveform, and expandable sound details. Technical values remain readable metadata; the page does not imply that displayed score defaults are editable controls.

Tone metadata lists only each instrument's catalog-supported controls, with per-instrument defaults overriding shared fallbacks. Use seconds for decay, cents for vibrato depth and detune, Hz for vibrato rate, and semitones for glide; brightness, pluck position, and breath are unitless.

### Music preview and sound details

Music is the default preview beside Phrase and Single note (Single hit for percussion). The three equal-width buttons share the existing bordered mode group, compact curves, and sage selected fill. Music mode shows the piece title, composer with a short-excerpt label, arrangement, performers, and a public-domain score and credits link. The link opens separately and carries edition credit and license information in its title. Other modes hide this repertoire block; downloads follow the selected clip.

The current library provides three clips for each of 45 instruments (135 total), with 31 solo and 14 combined music arrangements. These are generated demonstrations of the prototypes; repertoire presentation does not replace their model limitations.

About this sound is a native, initially collapsed disclosure below the preview. Its green summary (12px, weight 600) sits behind a fine top divider, with the existing section spacing; opening it adds space (12px) below the summary. The contents retain model descriptions, engine identity, supported defaults with units, and the explanation that tone edits belong in the JSON score. The existing mobile section spacing and focus treatment apply.

### Persistent player

A single transport mirrors the selected preview. It presents identity, play/pause, next available instrument, seek position, and desktop volume. Loading, failure, and completion have text or live announcements. Planned selections disable audio controls and hide preview and download content in the detail panel.

## Do's and Don'ts

### Do:

- **Do** carry cream, warm white, ink, and forest green into related listening surfaces.
- **Do** preserve visible keyboard focus and text labels for availability.
- **Do** keep waveform graphics tied to actual generated audio.
- **Do** adapt the catalog layout and reserve space for its persistent player.

### Don't:

- **Don't** give planned instruments a playback action or substitute audio.
- **Don't** hide status differences behind color alone.
- **Don't** present read-only preview defaults as editable synthesis controls.
