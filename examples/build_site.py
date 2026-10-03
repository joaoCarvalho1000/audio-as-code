"""Build the static public website: python examples/build_site.py [--out output/site].

Inputs are files other steps produce; nothing here synthesizes audio:

- web/site/                         page templates, CSS, JS, fonts
- output/classic-showcase/          manifest.json + WAV/MIDI/JSON written by classic_showcase.py
- output/classic-reimaginations/    the agent-written Reimagined version of each classic
- output/full-compositions/         four original pieces; listed only with --with-originals
- docs/site/                        tutorial Markdown, runnable examples, llms.txt
- output/instruments/               the instrument audition library (instrument_browser.py)
- schemas/, src/audio_as_code       score schema and live instrument catalog
- skills/                           portable agent skills, published at the same path
- web/site/analytics-config.json    public PostHog key and host (absent, or --no-analytics: none)

The output folder is portable: every link is relative, no server code. The only network
requests a page makes are its optional analytics (see docs/analytics.md).
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import stat
import subprocess
import sys
import wave
import zipfile
from pathlib import Path

import numpy as np

from audio_as_code import __version__, analyze_wav, instrument_catalog

if __name__ == "__main__":
    from _site_discovery import canonical_url, metadata, write_discovery
else:
    from examples._site_discovery import canonical_url, metadata, write_discovery

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "site"
COMPOSITIONS = ROOT / "output" / "full-compositions"
CLASSICS = ROOT / "output" / "classic-showcase"
REIMAGINATIONS = ROOT / "output" / "classic-reimaginations"
# Notation and edition credits for the public-domain excerpts, used when a manifest omits them.
EXCERPTS = ROOT / "examples" / "music" / "excerpts.json"
# The home page opens on this piece when it is in the build.
DEFAULT_PIECE = "classic-fur-elise"
# Repository docs published verbatim beside the guides: classic credits, the reimagining notes
# and the analytics notice.
RAW_DOCS = {
    "classic-showcase.md": "docs/classic-showcase.md",
    "classic-reimaginations.md": "docs/classic-reimaginations.md",
    "analytics.md": "docs/analytics.md",
    "piano-sustain.md": "docs/piano-sustain.md",
    "creative-workflows.md": "docs/creative-workflows.md",
}
ANALYTICS_CONFIG = WEB / "analytics-config.json"
POSTHOG_HOSTS = ("https://us.i.posthog.com", "https://eu.i.posthog.com")
KOFI = "https://ko-fi.com/joaothecarvalho"
# Input fields an agent may need exactly as written, published beside the normalized credit.
PROVENANCE = (
    "pair_id",
    "variant",
    "work_title",
    "complete",
    "excerpt",
    "composer",
    "source_url",
    "edition_credit",
    "source_license",
    "source_piece",
    "source_beats",
    "source_bpm",
    "source_mapping",
    "source_verified_date",
    "performance_scope",
    "repeat_policy",
    "source_dataset",
    "arrangement_notes",
)
LOOP_SNIPPET = WEB / "snippets" / "loop.py"
DOCS = ROOT / "docs" / "site"
INSTRUMENTS = ROOT / "output" / "instruments"
SKILLS = ROOT / "skills"
IDENTITY = json.loads((WEB / "identity.json").read_text(encoding="utf-8"))

# Guide pages, in reading order: (slug, Markdown file, short nav label).
GUIDES = [
    ("quickstart", "quickstart.md", "Quickstart"),
    ("composition", "composition.md", "Composing"),
    ("agents", "agents.md", "For agents"),
    ("integrations", "integrations.md", "Integrations"),
    ("reference", "reference.md", "Reference"),
]

GUIDE_DESCRIPTIONS = {
    "quickstart": (
        "Create your first soundtrack with Audio as Code. Give the instructions to your AI agent, "
        "install the Python toolkit, and render editable music to WAV and MIDI."
    ),
    "composition": (
        "Compose music in Python with notes, chords, motifs, song forms and instrument controls. "
        "Build an editable arrangement and render it offline with Audio as Code."
    ),
    "agents": (
        "Give a coding agent the tools to compose, validate, render and revise music. Discover "
        "instruments, inspect export readiness, and deliver WAV, MIDI and editable scores."
    ),
    "integrations": (
        "Add music to creative agent workflows with Codex, Claude Code and Hyperframes. "
        "Create soundtracks for video timelines, game audio folders and presentations."
    ),
    "reference": (
        "Audio as Code API and CLI reference: Python composition, JSON score fields, procedural "
        "instruments, tempo, automation, effects, WAV rendering and MIDI export."
    ),
}

# Only these repository paths enter the downloadable source archive.
SOURCE_ALLOW = [
    "src/audio_as_code",
    "examples",
    "docs",
    "schemas",
    "tests",
    "web",
    "skills",
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "pyproject.toml",
    "uv.lock",
    ".gitignore",
    "AGENTS.md",
    ".github",
]
SOURCE_DENY = re.compile(
    r"(^|/)(\.claude|\.orca|\.cursor|\.idea|\.vscode|\.internal|\.mypy_cache|\.hypothesis|\.tox|\.nox|playwright-report|test-results|htmlcov|build|dist)(/|$)|"
    r"^docs/internal(/|$)|"
    r"(^|/)(DESIGN|PRODUCT|PLAN|HANDOFF|SESSION|NOTES|PROGRESS|CHECKPOINT|TASKS)\.md$|"
    r"(^|/)(instrument-browser-brief|instrument-refinement)\.md$|"
    r"(^|/)(\.dev\.vars[^/]*|\.coverage[^/]*|[^/]*\.egg-info|%SystemDrive%)(/|$)|"
    r"\.(wav|mp3|mid|midi|prof|p12|pfx)$|"
    r"(^|/)\.wrangler(/|$)|"
    r"(^|/)(\.git|\.env[^/]*|__pycache__|\.venv|output|node_modules|\.pytest_cache|\.ruff_cache|\.impeccable|\.agents|\.codex)(/|$)"
    r"|\.py[cod]$|(^|/)(.*\.log|.*\.key|.*\.pem|credentials[^/]*)$",
    re.IGNORECASE,
)


def _source_files() -> list[Path]:
    """Collect portable regular files without following links or Windows junctions."""
    files = []
    for entry in SOURCE_ALLOW:
        pending = [ROOT / entry]
        while pending:
            path = pending.pop()
            relative = path.relative_to(ROOT).as_posix()
            if SOURCE_DENY.search(relative):
                continue
            try:
                attributes = path.lstat()
            except FileNotFoundError:
                continue
            linked = stat.S_ISLNK(attributes.st_mode) or (
                getattr(attributes, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            )
            if linked or path.resolve() != path.absolute():
                raise ValueError(f"source downloads cannot include linked paths: {relative}")
            if stat.S_ISDIR(attributes.st_mode):
                pending.extend(sorted(path.iterdir(), reverse=True))
            elif stat.S_ISREG(attributes.st_mode):
                files.append(path)
    return files


# ----------------------------------------------------------------------------- Markdown


def _inline(text: str) -> str:
    """Escape text, then apply code spans, links, bold and italic."""
    codes: list[str] = []

    def keep(match: re.Match) -> str:
        codes.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", keep, text)
    text = html.escape(text, quote=False)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        lambda m: f'<a href="{html.escape(_rewrite_link(m.group(2)))}">{m.group(1)}</a>',
        text,
    )
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?![\w*])", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


def _rewrite_link(target: str) -> str:
    """Point Markdown links (written relative to docs/) at the built pages and files."""
    if re.match(r"^[a-z]+:", target) or target.startswith("#"):
        return target
    raw_doc = _raw_doc_link(target)
    if raw_doc is not None:
        return raw_doc
    path, _, anchor = target.partition("#")
    name = Path(path).name
    suffix = f"#{anchor}" if anchor else ""
    for slug, source, _ in GUIDES:
        if name == source:
            return f"{slug}.html{suffix}"
    if path.rstrip("/") == "examples":
        return "examples.html"
    if path.startswith("examples/") and name.endswith(".py"):
        return f"examples.html#{_slug(Path(path).stem)}"
    # Raw files the site publishes at the same relative location (examples/*.json,
    # ../schemas/, ../instruments.json, ../llms.txt) keep their link; check_links verifies them.
    if path.startswith(("examples/", "../")):
        return target
    return "../source.html"


def _raw_doc_link(target: str) -> str | None:
    """Flatten only known repository documents published beside the guides."""
    path, separator, anchor = target.partition("#")
    name = path.removeprefix("../")
    if name in RAW_DOCS:
        return name + separator + anchor
    return None


def _guide_markdown(text: str) -> str:
    """Adjust raw-document links for copied guides while retaining Markdown links."""
    return re.sub(
        r"(\[[^\]]+\]\()([^)\s]+)(\))",
        lambda match: match[1] + (_raw_doc_link(match[2]) or match[2]) + match[3],
        text,
    )


def _slug(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "section"


def markdown(text: str) -> tuple[str, list[tuple[int, str, str]], str]:
    """Convert the subset of Markdown the guides use. Returns (html, headings, title)."""
    out: list[str] = []
    headings: list[tuple[int, str, str]] = []
    title = ""
    lines = text.replace("\r\n", "\n").split("\n")
    i = 0
    seen: dict[str, int] = {}

    def para(buffer: list[str]) -> None:
        if buffer:
            out.append(f"<p>{_inline(' '.join(s.strip() for s in buffer))}</p>")
            buffer.clear()

    buffer: list[str] = []
    while i < len(lines):
        line = lines[i]
        fence = re.match(r"^```\s*([\w+-]*)", line)
        if fence:
            para(buffer)
            lang = fence.group(1) or "text"
            body = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                body.append(lines[i])
                i += 1
            out.append(code_block("\n".join(body), lang))
            i += 1
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading:
            para(buffer)
            level = len(heading.group(1))
            content = _inline(heading.group(2).strip())
            if level == 1 and not title:
                title = re.sub(r"<[^>]+>", "", content)
                i += 1
                continue
            anchor = _slug(content)
            seen[anchor] = seen.get(anchor, 0) + 1
            if seen[anchor] > 1:
                anchor = f"{anchor}-{seen[anchor]}"
            headings.append((level, anchor, re.sub(r"<[^>]+>", "", content)))
            out.append(
                f'<h{level} id="{anchor}">{content}'
                f'<a class="anchor" href="#{anchor}" aria-label="Link to this section">#</a>'
                f"</h{level}>"
            )
            i += 1
            continue
        if (
            line.startswith("|")
            and i + 1 < len(lines)
            and re.match(r"^\|[\s:|-]+\|$", lines[i + 1])
        ):
            para(buffer)
            head = [c.strip() for c in line.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            cells = "".join(f"<th>{_inline(c)}</th>" for c in head)
            body = "".join(
                "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>" for row in rows
            )
            out.append(
                f'<div class="table-wrap"><table><thead><tr>{cells}</tr></thead>'
                f"<tbody>{body}</tbody></table></div>"
            )
            continue
        bullet = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if bullet:
            para(buffer)
            ordered = bullet.group(2)[0].isdigit()
            items: list[str] = []
            while i < len(lines):
                item = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if item:
                    items.append(item.group(3))
                elif lines[i].startswith("  ") and lines[i].strip() and items:
                    items[-1] += " " + lines[i].strip()
                else:
                    break
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        if line.startswith(">"):
            para(buffer)
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i].lstrip("> "))
                i += 1
            out.append(f'<aside class="note"><p>{_inline(" ".join(quote))}</p></aside>')
            continue
        if not line.strip():
            para(buffer)
        elif re.match(r"^(-{3,}|\*{3,})$", line.strip()):
            para(buffer)
            out.append("<hr>")
        else:
            buffer.append(line)
        i += 1
    para(buffer)
    return "\n".join(out), headings, title


# ------------------------------------------------------------------------- code blocks

PY_KEYWORDS = (
    "False|None|True|and|as|assert|break|class|continue|def|del|elif|else|except|finally|for|"
    "from|global|if|import|in|is|lambda|not|or|pass|raise|return|try|while|with|yield"
)
TOKEN = re.compile(
    r"(?P<comment>#[^\n]*)"
    r'|(?P<string>"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\')'
    rf"|(?P<keyword>\b(?:{PY_KEYWORDS})\b)"
    r"|(?P<number>\b\d+(?:\.\d+)?\b)"
)


def highlight(code: str, lang: str) -> str:
    """Token-level colouring for Python, shell, and JSON; everything else stays plain."""
    if lang in {"json"}:
        pattern = re.compile(
            r'(?P<key>"(?:\\.|[^"\\])*"(?=\s*:))|(?P<string>"(?:\\.|[^"\\])*")'
            r"|(?P<number>-?\b\d+(?:\.\d+)?\b)|(?P<keyword>\b(?:true|false|null)\b)"
        )
    elif lang in {"python", "py"}:
        pattern = TOKEN
    elif lang in {"sh", "bash", "shell", "console", "powershell"}:
        pattern = re.compile(
            r"(?P<comment>#[^\n]*)|(?P<keyword>^\s*(?:uv|python|aac|pip|cd)\b)", re.M
        )
    else:
        return html.escape(code)
    out, last = [], 0
    for match in pattern.finditer(code):
        out.append(html.escape(code[last : match.start()]))
        out.append(f'<span class="t-{match.lastgroup}">{html.escape(match.group())}</span>')
        last = match.end()
    out.append(html.escape(code[last:]))
    return "".join(out)


def code_block(code: str, lang: str, label: str | None = None) -> str:
    label = label or {"sh": "shell", "bash": "shell", "py": "python"}.get(lang, lang)
    return (
        f'<figure class="code" data-lang="{html.escape(lang)}">'
        f"<figcaption><span>{html.escape(label)}</span>"
        f'<button type="button" class="copy" data-copy>Copy</button></figcaption>'
        f"<pre><code>{highlight(code, lang)}</code></pre></figure>"
    )


# ----------------------------------------------------------------------------- audio data


def wav_envelope(path: Path, bins: int = 720) -> tuple[list[list[float]], float]:
    """Min/max envelope of the actual WAV samples, plus its real duration in seconds."""
    with wave.open(str(path), "rb") as handle:
        if handle.getsampwidth() != 2:
            raise ValueError(f"{path} is not 16-bit PCM")
        channels, rate, frames = handle.getnchannels(), handle.getframerate(), handle.getnframes()
        data = np.frombuffer(handle.readframes(frames), dtype="<i2").astype(np.float32) / 32768
    mono = data.reshape(-1, channels).mean(axis=1)
    edges = np.linspace(0, len(mono), bins + 1).astype(int)
    envelope = [
        [round(float(mono[a:b].min()), 3), round(float(mono[a:b].max()), 3)] if b > a else [0, 0]
        for a, b in zip(edges[:-1], edges[1:], strict=False)
    ]
    return envelope, frames / rate


def score_notes(score: dict) -> dict:
    """Compact note list for the browser roll: [track, midi pitch, start beat, beats, velocity]."""
    from audio_as_code import midi_pitch

    tracks, notes = [], []
    for index, track in enumerate(score.get("tracks", [])):
        tracks.append({"name": track["name"], "instrument": track["instrument"]})
        for note in track.get("notes", []):
            notes.append(
                [
                    index,
                    midi_pitch(note["pitch"]),
                    round(float(note["start"]), 4),
                    round(float(note["duration"]), 4),
                    round(float(note.get("velocity", 0.8)), 3),
                ]
            )
    return {"tracks": tracks, "notes": notes}


# ---------------------------------------------------------------------------- analytics


def analytics_config(
    project_key: str | None = None,
    api_host: str | None = None,
    allow_local: bool = False,
    allowed_hosts: list[str] | None = None,
) -> dict | None:
    """Validate a PostHog key and host as a pair; None when neither is given (no analytics).

    allowed_hosts, when given, limits sending to those DNS hosts, so a fork of the source
    never reports into this project. allow_local only lifts the block on local addresses.
    """
    if not project_key and not api_host:
        return None
    if not (project_key and api_host):
        raise SystemExit("analytics needs both a PostHog project key and a host")
    if not re.fullmatch(r"phc_[A-Za-z0-9]{20,}", project_key):
        raise SystemExit("the PostHog project key must be a public phc_ token")
    if api_host.rstrip("/") not in POSTHOG_HOSTS:
        raise SystemExit(f"the PostHog host must be one of {', '.join(POSTHOG_HOSTS)}")
    config = {
        "projectKey": project_key,
        "apiHost": api_host.rstrip("/"),
        "allowLocal": bool(allow_local),
    }
    if allowed_hosts is not None:
        label = r"(?!-)[a-z0-9-]{1,63}(?<!-)"
        hosts = [str(h).strip().lower() for h in allowed_hosts]
        if not hosts or not all(re.fullmatch(rf"{label}(\.{label})+", h) for h in hosts):
            raise SystemExit("allowedHosts must be a non-empty list of DNS host names")
        config["allowedHosts"] = hosts
    return config


def analytics_from_file(path: Path = ANALYTICS_CONFIG) -> dict | None:
    """The committed production defaults; a missing file means no analytics."""
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return analytics_config(
        data.get("projectKey"),
        data.get("apiHost"),
        data.get("allowLocal") is True,
        data.get("allowedHosts"),
    )


def analytics_html(config: dict | None, prefix: str) -> str:
    """The config block and the deferred script, or nothing. The JSON is safe inside a script."""
    if not config:
        return ""
    data = json.dumps(config, separators=(",", ":"))
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return (
        f'<script id="aac-analytics-config" type="application/json">{data}</script>\n'
        f'<script src="{prefix}assets/analytics.js" defer></script>'
    )


# ------------------------------------------------------------------------------ pieces


def _display(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _find_source(name: str | None, folder: Path) -> Path | None:
    """A manifest's source script, beside the manifest or in examples/."""
    if not name:
        return None
    for candidate in (folder / name, ROOT / "examples" / Path(name).name):
        candidate = candidate.resolve()
        if candidate.is_file() and candidate.suffix == ".py":
            return candidate
    return None


def _requires(source: Path | None) -> list[str]:
    """Repository files a published source script needs beside it to run from a checkout."""
    if source is None:
        return []
    text = source.read_text(encoding="utf-8")
    needs = []
    for module in re.findall(r"^\s*(?:from|import)\s+([A-Za-z_]\w*)", text, re.M):
        if module != source.stem and (ROOT / "examples" / f"{module}.py").is_file():
            needs.append(f"examples/{module}.py")
    if "excerpts.json" in text:
        needs.append("examples/music/excerpts.json")
    return sorted(set(needs))


_ENSEMBLE = {1: "solo", 2: "duo", 3: "trio", 4: "quartet", 5: "quintet"}


def _status(piece: dict, collection: str, variant: str | None) -> str:
    if collection != "classic":
        return "original piece"
    if variant == "reimagined":
        return "Reimagined by an AI agent"
    if piece.get("excerpt") is True:
        return "public-domain excerpt"
    return "The classic"


def _declared(piece: dict, source: Path | None) -> list[str]:
    """Dependencies a manifest declares, as repository paths (they sit beside the source)."""
    declared = piece.get("requires") or piece.get("source_dependencies") or []
    if source is None or not declared:
        return []
    base = ROOT / "examples"
    return [(base / d).resolve().relative_to(ROOT).as_posix() for d in declared]


def _arrangement(instruments: list[str]) -> str:
    """A short arrangement label for the bill: 'piano', 'flute and harp', 'brass quartet'."""
    names = [i.replace("_", " ") for i in instruments]
    if len(names) <= 2:
        return " and ".join(names)
    catalog = instrument_catalog()
    family_of = {i["id"]: i["family"] for i in catalog["instruments"]}
    family_name = {f["id"]: f["name"] for f in catalog["families"]}
    families = {family_of.get(i) for i in instruments}
    if len(families) == 1 and None not in families and len(names) in _ENSEMBLE:
        return f"{family_name[families.pop()].lower()} {_ENSEMBLE[len(names)]}"
    return f"{len(names)}-part ensemble"


def _excerpt_entry(piece: dict, pid: str) -> dict:
    keys = [piece.get(k) for k in ("source_piece", "excerpt_id", "excerpt")]
    key = next((k for k in keys if isinstance(k, str) and k), None)
    key = key or pid.removeprefix("classic-").replace("-", "_")
    if not EXCERPTS.is_file():
        return {}
    entry = json.loads(EXCERPTS.read_text(encoding="utf-8")).get(key, {})
    return entry if isinstance(entry, dict) else {}


def _credit(piece: dict, pid: str) -> dict | None:
    """A public-domain excerpt's source credit: its manifest entry first, then excerpts.json."""
    nested = {**(piece.get("source_credit") or {})}
    if isinstance(piece.get("credit"), dict):
        nested.update(piece["credit"])
    flat = {k: v for k, v in piece.items() if k != "title"}
    entry = _excerpt_entry(piece, pid)

    def pick(*keys: str) -> str:
        for where in (nested, flat, entry):
            for key in keys:
                value = where.get(key)
                if isinstance(value, (str, int)) and str(value).strip():
                    return str(value).strip()
        return ""

    credit = {
        "work": pick("work", "source_title") or str(entry.get("title", "")),
        "composer": pick("composer"),
        "edition_credit": pick("edition_credit", "editor", "typesetter", "credit"),
        "edition_id": pick("edition_id", "mutopia_id", "source_id"),
        "license": pick("license", "source_license", "licence"),
        "url": pick("edition_url", "source_url", "url"),
        "download_url": pick("download_url"),
        "verified": pick("source_verified_date", "verified"),
    }
    if not any(credit.values()):
        return None
    host = "Mutopia Project" if "mutopiaproject.org" in credit["url"] else "Source edition"
    credit["edition"] = f"{host} #{credit['edition_id']}" if credit["edition_id"] else host
    return credit


def credits_html(pieces: list[dict]) -> str:
    """The plain score-credits list on the home page, one line per public-domain source."""
    items = []
    seen = set()
    for p in pieces:
        c = p.get("credit")
        if not c or p.get("pair_id") in seen:
            continue
        seen.add(p.get("pair_id"))
        who = f" Edition by {html.escape(c['edition_credit'])}," if c["edition_credit"] else ""
        edition = html.escape(c["edition"])
        link = (
            f'<a href="{html.escape(c["url"])}" rel="external">{edition}</a>'
            if c["url"]
            else edition
        )
        lic = f", marked {html.escape(c['license'])} on its source page" if c["license"] else ""
        items.append(
            f"<li><b>{html.escape(c['work'] or p['title'])}</b> "
            f"<span>{html.escape(c['composer'] or p['composer'])}.{who} {link}{lic}.</span></li>"
        )
    return "\n      ".join(items)


def credits_links(raw_docs: list[str]) -> str:
    """Links from the score credits to the published notes behind them."""
    links = [
        (doc, text)
        for doc, text in (
            ("docs/classic-showcase.md", "score credits and scope"),
            ("docs/classic-reimaginations.md", "what each reimagining changed"),
        )
        if doc in raw_docs
    ]
    if not links:
        return ""
    return (
        '<p class="credits-docs">Full notes: '
        + " · ".join(f'<a href="{doc}">{text}</a>' for doc, text in links)
        + "</p>"
    )


def program_copy(pieces: list[dict]) -> dict[str, str]:
    """Home-page lines that depend on which collections and versions this build includes."""
    classics = [p for p in pieces if p["collection"] == "classic"]
    originals = len(pieces) - len(classics)
    works = list(dict.fromkeys(p["pair_id"] for p in classics))
    paired = any(p["variant"] == "reimagined" for p in classics)
    if paired:
        intro = (
            "First, the classic. Then, a plot twist. Compare familiar music with an agent's new "
            "arrangement: different instruments, rhythms and moods. Both versions are synthesized "
            "from code, with editable scores."
        )
        note = (
            "The classic versions follow the credited public-domain scores. "
            "The reimagined versions are new arrangements by an AI agent. "
            "Audio as Code synthesizes every sound; "
            "both versions include editable scores and source."
        )
    elif classics:
        intro = "Hear familiar public-domain music, synthesized from code with editable scores."
        note = (
            "These versions follow the credited public-domain scores. Audio as Code synthesizes "
            "every sound, and each one includes an editable score and source."
        )
    else:
        intro, note = f"{originals} original pieces, composed in Python for this site.", ""
    if originals and classics:
        intro += f" {originals} original pieces, composed in Python for this site, follow them."
    if paired:
        label = "Choose a piece and compare its classic and reimagined arrangements"
    else:
        label = "Choose a classical piece" if classics and not originals else "Choose a piece"
    rows = len(works) + (originals if classics else 0) or originals
    style = f"--pieces:{rows}; --groups:{2 if classics and originals else 0}"
    if paired:
        style += "; --row:64px"
    headline = ("The classic,", "reimagined") if paired else (f"{len(pieces)} pieces", "to hear")
    return {
        "HEADLINE_1": html.escape(headline[0]),
        "HEADLINE_2": html.escape(headline[1]),
        "PROGRAM_INTRO": html.escape(intro),
        "CREDITS_NOTE": html.escape(note),
        "LINEUP_LABEL": html.escape(label),
        "LINEUP_STYLE": style,
        "HANDOFF_NOTE": html.escape(
            "Your agent needs a shell and Python 3.10+. You supply the brief; it handles the setup."
        ),
        "CREDITS_HIDDEN": "" if classics else " hidden",
    }


# ------------------------------------------------------------------------------ the build


class Site:
    def __init__(
        self,
        out: Path,
        compositions: Path = COMPOSITIONS,
        classics: Path | None = CLASSICS,
        analytics: dict | None = None,
        reimaginations: Path | None = REIMAGINATIONS,
        originals: bool = False,
    ) -> None:
        self.out = out
        self.analytics = analytics
        self.reimaginations = reimaginations
        self.originals = originals
        self.compositions = compositions
        self.classics = classics
        self.warnings: list[str] = []
        self.pieces: list[dict] = []
        self.layout = (WEB / "layout.html").read_text(encoding="utf-8")

    # -- helpers
    def write(self, relative: str, text: str) -> None:
        path = self.out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def copy(self, source: Path, relative: str) -> None:
        path = self.out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, path)

    def page(
        self,
        relative: str,
        *,
        title: str,
        description: str,
        body: str,
        nav: str,
        extra_head: str = "",
        root: str | None = None,
    ) -> None:
        depth = relative.count("/")
        prefix = "../" * depth if root is None else root
        canonical = canonical_url(IDENTITY["canonical_origin"], relative)
        text = self.layout
        for key, value in {
            "TITLE": html.escape(title),
            "DESCRIPTION": html.escape(description),
            "CANONICAL": html.escape(canonical),
            "METADATA": metadata(
                IDENTITY["canonical_origin"], relative, title, description, __version__
            ),
            "ROOT": prefix,
            "NAV": nav,
            "BODY": body.replace("{{ROOT}}", prefix),
            "HEAD": extra_head.replace("{{ROOT}}", prefix),
            "ANALYTICS": analytics_html(self.analytics, prefix),
            "ANALYTICS_LINK": (
                f'<li><a href="{prefix}docs/analytics.md">Analytics and privacy</a></li>'
                # analytics.js reveals this only where it would actually send events.
                '<li><button type="button" class="foot-optout" data-analytics-optout hidden>'
                "Opt out of analytics</button></li>"
                if self.analytics and (ROOT / RAW_DOCS["analytics.md"]).is_file()
                else ""
            ),
            "KOFI": KOFI,
            "VERSION": __version__,
        }.items():
            text = text.replace("{{" + key + "}}", value)
        self.write(relative, text)

    # -- parts
    def assets(self) -> None:
        for source in (WEB / "assets").rglob("*"):
            if source.is_file():
                self.copy(source, "assets/" + source.relative_to(WEB / "assets").as_posix())

    def music(self) -> list[dict]:
        """The classics, each beside its Reimagined version; the originals only on request."""
        pieces: list[dict] = []
        collections = []
        if self.classics is not None:
            collections.append(("classic", self.classics, "classic"))
        if self.classics is not None and self.reimaginations is not None:
            collections.append(("classic", self.reimaginations, "Reimagined"))
        if self.originals:
            collections.append(("original", self.compositions, "original"))
        for collection, folder, label in collections:
            manifest_path = folder / "manifest.json"
            if not manifest_path.exists():
                self.warnings.append(f"{_display(manifest_path)} is missing; no {label} pieces")
                continue
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            for piece in manifest["pieces"]:
                pieces.append(self._piece(piece, manifest_path, collection))
        ids = [p["id"] for p in pieces]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate piece ids across manifests: {ids}")
        # Works keep the classics manifest's order; within a work the classic comes first.
        works = list(dict.fromkeys(p["pair_id"] for p in pieces))
        pieces.sort(
            key=lambda p: (
                p["collection"] != "classic",
                works.index(p["pair_id"]),
                p["variant"] == "reimagined",
            )
        )
        pieces.sort(key=lambda p: p["pair_id"] != DEFAULT_PIECE)  # stable: the default work leads
        classic_of = {p["pair_id"]: p for p in pieces if p["variant"] == "classic"}
        for p in pieces:
            # A Reimagined version arranges the same credited score; it inherits what it omits.
            source = classic_of.get(p["pair_id"]) if p["variant"] == "reimagined" else None
            if source and not (p["credit"] and p["credit"]["url"]):
                p["credit"] = source["credit"]
            if source:
                for key in ("composer", "work_title", "performance_scope"):
                    if not p.get(key) and source.get(key):
                        p[key] = source[key]
            if p["collection"] == "classic" and not (
                p["credit"] and p["credit"]["url"] and p["credit"]["license"]
            ):
                self.warnings.append(f"{p['id']}: no source edition URL and licence for its credit")
        paired = any(p["variant"] == "reimagined" for p in pieces)
        for work in works:
            versions = {p["variant"] for p in pieces if p["pair_id"] == work}
            if (
                self.reimaginations is not None
                and "classic" in versions
                and "reimagined" not in versions
            ):
                self.warnings.append(f"{work}: no Reimagined version found")
        for p in pieces:
            # The paired lineup compares whole works; a short excerpt there would mislead.
            if paired and p["collection"] == "classic" and p.get("complete") is not True:
                self.warnings.append(f"{p['id']}: not marked complete=true for the paired lineup")
        # The home page keeps site-root paths; the published manifest lives in music/,
        # so its asset paths are relative to that file, as a URL resolver expects.
        asset_keys = ("wav", "midi", "score", "source", "source_bundle", "audio", "roll")
        public = [
            {
                k: (v.removeprefix("music/") if k in asset_keys and isinstance(v, str) else v)
                for k, v in p.items()
                if k != "envelope"
            }
            for p in pieces
        ]
        self.write("music/manifest.json", json.dumps({"pieces": public}, indent=2) + "\n")
        self.pieces = pieces
        return pieces

    def _piece(self, piece: dict, manifest_path: Path, collection: str) -> dict:
        pid = re.sub(r"[^a-z0-9_-]", "-", piece["id"].lower())
        files = {}
        for kind in ("wav", "midi", "score"):
            source = (manifest_path.parent / piece[kind]).resolve()
            if not source.is_file():
                raise FileNotFoundError(f"{piece['id']}: {kind} file {source} is missing")
            name = f"{pid}{source.suffix}"
            self.copy(source, f"music/{pid}/{name}")
            files[kind] = f"music/{pid}/{name}"
        source_file = _find_source(piece.get("source"), manifest_path.parent)
        if source_file is not None:
            self.copy(source_file, f"music/{source_file.name}")
            files["source"] = f"music/{source_file.name}"
        elif piece.get("source"):
            self.warnings.append(f"{pid}: source {piece['source']} not found; no Python download")
        if piece.get("source_bundle"):
            bundle = (manifest_path.parent / piece["source_bundle"]).resolve()
            if bundle.is_file() and bundle.suffix == ".zip":
                self.copy(bundle, f"music/{bundle.name}")
                files["bundle"] = f"music/{bundle.name}"
            else:
                self.warnings.append(f"{pid}: source bundle {bundle.name} missing")
        files["audio"] = files["wav"]
        if piece.get("preview"):
            preview = (manifest_path.parent / piece["preview"]).resolve()
            if preview.is_file():
                self.copy(preview, f"music/{pid}/{pid}-preview{preview.suffix}")
                files["audio"] = f"music/{pid}/{pid}-preview{preview.suffix}"
            else:
                self.warnings.append(f"{pid}: preview {preview.name} missing; streaming the WAV")
        envelope, seconds = wav_envelope(manifest_path.parent / piece["wav"])
        score = json.loads((manifest_path.parent / piece["score"]).read_text(encoding="utf-8"))
        roll = score_notes(score)
        self.write(f"music/{pid}/roll.json", json.dumps(roll, separators=(",", ":")))
        bpm = float(score.get("bpm", piece["bpm"]))
        beats = float(score.get("beats", piece["beats"]))
        sections = [
            {"name": s["name"], "start_beat": s["start_beat"], "end_beat": s["end_beat"]}
            for s in piece.get("sections", [])
        ]
        if not sections:
            # One real seek point keeps the poster's section strip, and its reserved space, intact.
            whole = "Whole excerpt" if piece.get("excerpt") is True else "Whole piece"
            sections = [{"name": whole, "start_beat": 0.0, "end_beat": beats}]
        reimagined = piece.get("variant") == "reimagined" or pid.endswith("-reimagined")
        pair_id = piece.get("pair_id") or pid.removesuffix("-reimagined")
        variant = ("reimagined" if reimagined else "classic") if collection == "classic" else None
        credit = _credit(piece, pair_id) if collection == "classic" else None
        # A WAV or preview left over from an earlier render must not pass for this score.
        scored = beats * 60 / bpm
        if not scored - 0.5 <= seconds <= scored + 8:
            self.warnings.append(
                f"{pid}: WAV lasts {seconds:.1f} s but its score lasts {scored:.1f} s; rerender it"
            )
        if files["audio"] != files["wav"]:
            wav_time = (manifest_path.parent / piece["wav"]).stat().st_mtime
            if (manifest_path.parent / piece["preview"]).stat().st_mtime < wav_time - 120:
                self.warnings.append(f"{pid}: preview is older than its WAV; re-encode it")
        composer = piece.get("composer") or (credit or {}).get("composer") or ""
        return {
            "id": pid,
            "title": piece["title"],
            "description": piece.get("description", ""),
            "collection": collection,
            "pair_id": pair_id,
            "variant": variant,
            "work_title": piece.get("work_title") or (credit or {}).get("work") or piece["title"],
            "status": _status(piece, collection, variant),
            "composer": composer,
            # classic_showcase.py's "arrangement" is a sentence; the bill needs a short label.
            "arrangement": _arrangement(piece.get("instruments", [])),
            "credit": credit,
            # Machine-facing provenance, verbatim from the input manifest (absent for originals).
            **{k: piece[k] for k in PROVENANCE if k in piece},
            "arrangement_description": piece.get("arrangement", ""),
            "bpm": bpm,
            "beats": beats,
            "seed": score.get("seed"),
            "duration_seconds": round(seconds, 3),
            "instruments": piece.get("instruments", []),
            "sections": sections,
            "code_excerpt": piece.get("code_excerpt", ""),
            "wav": files["wav"],
            "midi": files["midi"],
            "score": files["score"],
            "source": files.get("source"),
            "source_label": (
                Path(files["source"]).name
                + (f" · {piece['source_function']}()" if piece.get("source_function") else "")
            )
            if files.get("source")
            else "",
            "requires": _declared(piece, source_file) or _requires(source_file),
            "source_bundle": files.get("bundle"),
            "source_bundle_bytes": (self.out / files["bundle"]).stat().st_size
            if files.get("bundle")
            else None,
            "audio": files["audio"],
            "roll": f"music/{pid}/roll.json",
            "envelope": envelope,
            "wav_bytes": (self.out / files["wav"]).stat().st_size,
            "note_count": len(roll["notes"]),
            "track_count": len(roll["tracks"]),
        }

    def guides(self) -> list[tuple[str, str, str]]:
        built = []
        for slug, source, label in GUIDES:
            path = DOCS / source
            if not path.exists():
                self.warnings.append(f"docs/site/{source} is missing; guide not built")
                continue
            text = path.read_text(encoding="utf-8")
            self.write(f"docs/{source}", _guide_markdown(text))
            body, headings, title = markdown(text)
            built.append((slug, title or label, label, body, headings))
        pages = []
        for slug, title, label, body, headings in built:
            toc = "".join(
                f'<li class="lv{level}"><a href="#{anchor}">{html.escape(text)}</a></li>'
                for level, anchor, text in headings
                if level <= 3
            )
            current = ' aria-current="page"'
            side = "".join(
                f'<li><a href="{s}.html"{current if s == slug else ""}>{html.escape(lb)}</a></li>'
                for s, _, lb, _, _ in built
            )
            side += '<li><a href="examples.html">Examples</a></li>'
            index = [s for s, *_ in built].index(slug)
            pager = ""
            if index + 1 < len(built):
                nxt = built[index + 1]
                pager = f'<a class="pager" href="{nxt[0]}.html">Next: {html.escape(nxt[2])}</a>'
            else:
                pager = '<a class="pager" href="examples.html">Next: Runnable examples</a>'
            content = (
                '<div class="doc">'
                f'<nav class="doc-side" aria-label="Guides"><ul>{side}</ul>'
                f'<a class="raw" href="{source_name(slug)}">Markdown source</a>'
                '<a class="side-agent" href="../index.html#handoff">Give it to your agent</a></nav>'
                f'<article class="prose"><h1>{html.escape(title)}</h1>{body}{pager}</article>'
                '<nav class="doc-toc" aria-label="On this page"><p>On this page</p>'
                f"<ul>{toc}</ul></nav>"
                "</div>"
            )
            self.page(
                f"docs/{slug}.html",
                title=f"{title} · {IDENTITY['name']}",
                description=GUIDE_DESCRIPTIONS[slug],
                body=content,
                nav="docs",
            )
            pages.append((slug, title, label))
        return pages

    def examples(self, guide_pages: list[tuple[str, str, str]]) -> list[str]:
        folder = DOCS / "examples"
        scripts = sorted(folder.glob("*.py")) if folder.exists() else []
        if not scripts:
            self.warnings.append("docs/site/examples/*.py is missing; examples page is empty")
        blocks = []
        for extra in sorted(folder.glob("*")) if folder.exists() else []:
            if extra.is_file() and extra.suffix in {".json", ".txt", ".md"}:
                self.copy(extra, f"docs/examples/{extra.name}")
        for script in scripts:
            code = script.read_text(encoding="utf-8")
            self.write(f"docs/examples/{script.name}", code)
            doc = re.match(r'^\s*"""([\s\S]*?)"""', code)
            summary = doc.group(1).strip().split("\n\n")[0] if doc else ""
            anchor = _slug(script.stem)
            blocks.append(
                f'<section class="example" id="{anchor}">'
                f"<header><h2>{html.escape(script.name)}</h2>"
                f'<a href="examples/{script.name}" download>Download .py</a></header>'
                f"<p>{_inline(' '.join(summary.split()))}</p>"
                + code_block(code, "python", f"docs/site/examples/{script.name}")
                + "</section>"
            )
        side = "".join(
            f'<li><a href="{s}.html">{html.escape(lb)}</a></li>' for s, _, lb in guide_pages
        )
        side += '<li><a href="examples.html" aria-current="page">Examples</a></li>'
        toc = "".join(
            f'<li class="lv2"><a href="#{_slug(s.stem)}">{html.escape(s.name)}</a></li>'
            for s in scripts
        )
        empty = (
            ""
            if blocks
            else '<p class="empty">The runnable examples have not been generated yet.</p>'
        )
        body = (
            '<div class="doc">'
            f'<nav class="doc-side" aria-label="Guides"><ul>{side}</ul>'
            '<a class="side-agent" href="../index.html#handoff">Give it to your agent</a></nav>'
            '<article class="prose"><h1>Runnable examples</h1>'
            "<p>Each script runs from a checkout with the local install "
            "(<code>uv sync</code>, then <code>uv run python &lt;script&gt;</code>). "
            "They write their WAV, MIDI and JSON under <code>output/</code>.</p>"
            + empty
            + "".join(blocks)
            + "</article>"
            f'<nav class="doc-toc" aria-label="On this page"><p>Scripts</p><ul>{toc}</ul></nav>'
            "</div>"
        )
        self.page(
            "docs/examples.html",
            title=f"Runnable examples · {IDENTITY['name']}",
            description="Copyable Python scripts that compose and render music with Audio as Code.",
            body=body,
            nav="docs",
        )
        return [s.name for s in scripts]

    def machine(self, scripts: list[str], guide_pages: list[tuple[str, str, str]]) -> None:
        catalog = instrument_catalog(include_planned=True)
        self.write("instruments.json", json.dumps(catalog, indent=2) + "\n")
        self.copy(ROOT / "schemas" / "song-v1.schema.json", "schemas/song-v1.schema.json")
        llms = DOCS / "llms.txt"
        if llms.exists():
            self.copy(llms, "llms.txt")
        else:
            self.warnings.append("docs/site/llms.txt is missing; wrote a minimal index")
            lines = [f"# {IDENTITY['name']}", "", f"> {IDENTITY['description']}", ""]
            lines += [f"- [{t}](docs/{s}.md)" for s, t, _ in guide_pages]
            self.write("llms.txt", "\n".join(lines) + "\n")

    def raw_docs(self, classics: int) -> list[str]:
        published = []
        for name, source in RAW_DOCS.items():
            path = ROOT / source
            if path.is_file():
                self.copy(path, f"docs/{name}")
                published.append(f"docs/{name}")
        reimagined = any(p["variant"] == "reimagined" for p in self.pieces)
        if reimagined and "docs/classic-reimaginations.md" not in published:
            self.warnings.append(
                "docs/classic-reimaginations.md is missing; the reimagining notes are unpublished"
            )
        if classics and "docs/classic-showcase.md" not in published:
            self.warnings.append(
                "docs/classic-showcase.md is missing; the credits guide is unpublished"
            )
        if self.analytics and "docs/analytics.md" not in published:
            self.warnings.append("docs/analytics.md is missing; analytics has no public notice")
        return published

    def skills(self) -> list[str]:
        """Publish the portable agent skills at the same relative path, for handoff prompts."""
        files = sorted(p for p in SKILLS.rglob("*") if p.is_file()) if SKILLS.exists() else []
        published = []
        for source in files:
            rel = source.relative_to(ROOT).as_posix()
            if SOURCE_DENY.search(rel):
                continue
            self.copy(source, rel)
            published.append(rel)
        if "skills/audio-as-code/SKILL.md" not in published:
            self.warnings.append("skills/audio-as-code/SKILL.md is missing; handoff links break")
        return published

    def instruments(self) -> int:
        if not (INSTRUMENTS / "index.html").exists():
            self.warnings.append(
                "output/instruments is missing; run examples/instrument_browser.py"
            )
            return 0
        count = 0
        for source in INSTRUMENTS.rglob("*"):
            if source.is_file() and source.suffix in {".html", ".json", ".wav", ".mid"}:
                relative = "instruments/" + source.relative_to(INSTRUMENTS).as_posix()
                self.copy(source, relative)
                count += source.suffix == ".wav"
                if source.suffix == ".html":
                    depth = relative.count("/")
                    text = (self.out / relative).read_text(encoding="utf-8")
                    block = analytics_html(self.analytics, "../" * depth)
                    title = "Listen to 49 code-generated instruments | Audio as Code"
                    description = (
                        "Compare piano, strings, brass, woodwinds and percussion synthesized "
                        "entirely from code. Listen to musical examples and download editable "
                        "scores, WAV and MIDI."
                    )
                    canonical = canonical_url(IDENTITY["canonical_origin"], relative)
                    text = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", text, count=1)
                    block += (
                        f'\n<meta name="description" content="{description}">'
                        f'\n<link rel="canonical" href="{canonical}">'
                        f'\n<meta property="og:title" content="{title}">'
                        f'\n<meta property="og:description" content="{description}">'
                        f'\n<meta property="og:url" content="{canonical}">'
                    )
                    block += "\n" + metadata(
                        IDENTITY["canonical_origin"], relative, title, description, __version__
                    )
                    block += (
                        '\n<link rel="alternate" type="text/plain" '
                        'href="../llms.txt" title="Agent instructions">'
                    )
                    if "</head>" in text:
                        self.write(relative, text.replace("</head>", block + "\n</head>", 1))
        return count

    def source_archive(self) -> dict:
        files = _source_files()
        target = self.out / "download" / f"audio-as-code-{__version__}-source.zip"
        target.parent.mkdir(parents=True, exist_ok=True)
        names = []
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in files:
                rel = file.relative_to(ROOT).as_posix()
                names.append(rel)
                info = zipfile.ZipInfo(f"audio-as-code/{rel}", date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, file.read_bytes())
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        return {
            "file": f"download/{target.name}",
            "bytes": target.stat().st_size,
            "sha256": digest,
            "files": len(names),
            "roots": SOURCE_ALLOW,
        }

    def loop(self) -> dict:
        """Run the README example exactly as shown and publish what it wrote."""
        work = ROOT / "output" / "site-work" / "loop"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        result = subprocess.run(
            [sys.executable, str(LOOP_SNIPPET)],
            cwd=work,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(f"README loop example failed: {result.stderr}")
        for name in ("loop.wav", "loop.mid", "loop.json"):
            self.copy(work / "output" / name, f"loop/{name}")
        wav = analyze_wav(work / "output" / "loop.wav")
        envelope, seconds = wav_envelope(work / "output" / "loop.wav", bins=240)
        score = json.loads((work / "output" / "loop.json").read_text(encoding="utf-8"))
        meters = [
            ("Duration", f"{seconds:.2f} s"),
            ("Peak", f"{wav['peak_dbfs']:.1f} dBFS"),
            ("RMS", f"{wav['rms_dbfs']:.1f} dBFS"),
            ("Silent", "no" if not wav["silent"] else "yes"),
            ("Tracks", str(len(score["tracks"]))),
            ("Notes", str(sum(len(t["notes"]) for t in score["tracks"]))),
        ]
        cli = (
            "uv run aac validate output/loop.json\n"
            "uv run aac render output/loop.json -o output/loop.wav --report output/report.json\n"
            "uv run aac analyze output/loop.wav"
        )
        return {
            "LOOP_CODE": code_block(
                LOOP_SNIPPET.read_text(encoding="utf-8").strip(), "python", "loop.py"
            ),
            "LOOP_CLI": code_block(cli, "sh"),
            "LOOP_WAV": "loop/loop.wav",
            "LOOP_MID": "loop/loop.mid",
            "LOOP_JSON": "loop/loop.json",
            "LOOP_ENVELOPE": html.escape(json.dumps(envelope, separators=(",", ":"))),
            "LOOP_METERS": "".join(
                f"<div><dt>{k}</dt><dd>{html.escape(v)}</dd></div>" for k, v in meters
            ),
        }

    def templated(self, name: str, relative: str, root: str | None = None, **data: str) -> None:
        text = (WEB / name).read_text(encoding="utf-8")
        meta = re.match(r"<!--\s*title:(.*?)\|\s*description:(.*?)-->\s*", text, re.S)
        title, description = (
            (meta.group(1).strip(), meta.group(2).strip()) if meta else (IDENTITY["name"], "")
        )
        body = text[meta.end() :] if meta else text
        for key, value in data.items():
            body = body.replace("{{" + key + "}}", value)
        self.page(
            relative,
            title=title,
            description=description,
            body=body,
            nav=relative.split("/")[0].replace(".html", ""),
            root=root,
        )


def source_name(slug: str) -> str:
    return dict((s, src) for s, src, _ in GUIDES)[slug]


def check_links(out: Path) -> list[str]:
    """Every relative href/src in built HTML must resolve inside the output folder."""
    problems = []
    for page in out.rglob("*.html"):
        if page.is_relative_to(out / "instruments"):
            continue
        text = page.read_text(encoding="utf-8")
        ids = set(re.findall(r'\sid="([^"]+)"', text))
        for target in re.findall(r'(?:href|src)="([^"]+)"', text):
            if re.match(r"^(?:[a-z]+:|//|\$\{|\{\{)", target) or (
                page.name == "404.html" and target.startswith("/")
            ):
                continue
            path, _, anchor = target.partition("#")
            if not path:
                if anchor and anchor not in ids:
                    problems.append(f"{page.relative_to(out)}: missing anchor #{anchor}")
                continue
            resolved = (page.parent / path).resolve()
            if not resolved.is_relative_to(out.resolve()):
                problems.append(f"{page.relative_to(out)}: {target} leaves the site")
            elif not (resolved.is_file() or (resolved / "index.html").is_file()):
                problems.append(f"{page.relative_to(out)}: {target} not found")
    return problems


def preflight(
    out: Path,
    compositions: Path,
    classics: Path | None = CLASSICS,
    reimaginations: Path | None = REIMAGINATIONS,
) -> Path:
    """Refuse destinations whose recursive removal could delete inputs or leave output/."""
    output_root = (ROOT / "output").resolve()
    if out.is_symlink() or any(parent.is_symlink() for parent in out.absolute().parents):
        raise SystemExit(f"refusing to build into a symlinked path: {out}")
    resolved = out.resolve()
    if resolved == output_root or not resolved.is_relative_to(output_root):
        raise SystemExit(f"refusing to build at {resolved}: choose a new folder inside output/")
    protected = [
        compositions,
        *([classics] if classics is not None else []),
        *([reimaginations] if reimaginations is not None else []),
        INSTRUMENTS,
        WEB,
        DOCS,
        ROOT / "src",
        ROOT / "schemas",
        ROOT / "output" / "site-work",
    ]
    for path in protected:
        path = path.resolve()
        if resolved == path or path.is_relative_to(resolved) or resolved.is_relative_to(path):
            raise SystemExit(f"refusing to build at {resolved}: it overlaps input {path}")
    return resolved


def build(
    out: Path,
    compositions: Path = COMPOSITIONS,
    classics: Path | None = CLASSICS,
    analytics: dict | None = None,
    reimaginations: Path | None = REIMAGINATIONS,
    originals: bool = False,
) -> dict:
    # Validated before anything is removed, so a bad key never costs the previous build.
    if analytics is not None:
        analytics = analytics_config(
            analytics.get("projectKey"),
            analytics.get("apiHost"),
            analytics.get("allowLocal"),
            analytics.get("allowedHosts"),
        )
    out = preflight(out, compositions, classics, reimaginations)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    site = Site(out, compositions, classics, analytics, reimaginations, originals)
    site.assets()
    pieces = site.music()
    guide_pages = site.guides()
    scripts = site.examples(guide_pages)
    site.machine(scripts, guide_pages)
    skills = site.skills()
    clips = site.instruments()
    archive = site.source_archive()
    catalog = instrument_catalog()
    playable = (
        catalog["counts"]["available"] if "counts" in catalog else len(catalog["instruments"])
    )
    classic_count = sum(p["collection"] == "classic" for p in pieces)
    raw_docs = site.raw_docs(classic_count)
    stats = {
        "pieces": len(pieces),
        "classics": classic_count,
        "originals": len(pieces) - classic_count,
        "playable": playable,
        "clips": clips,
        "version": __version__,
    }
    loop = site.loop()
    family_names = {f["id"]: f["name"] for f in catalog["families"]}
    family_counts: dict[str, int] = {}
    for item in catalog["instruments"]:
        family_counts[item["family"]] = family_counts.get(item["family"], 0) + 1
    families = "".join(
        f'<li style="--n:{n}"><b>{html.escape(family_names[f])}</b><span>{n}</span></li>'
        for f, n in family_counts.items()
    )
    first_guide = f"docs/{guide_pages[0][0]}.html" if guide_pages else "docs/examples.html"
    pieces_json = json.dumps(pieces, separators=(",", ":")).replace("</", "<\\/")
    site.templated(
        "index.html",
        "index.html",
        PIECES=pieces_json,
        STATS=json.dumps(stats),
        PLAYABLE=str(playable),
        CLIPS=str(clips),
        PIECE_COUNT=str(len(pieces)),
        CLASSIC_COUNT=str(classic_count),
        ORIGINAL_COUNT=str(len(pieces) - classic_count),
        CREDITS=credits_html(pieces),
        CREDITS_LINKS=credits_links(raw_docs),
        **program_copy(pieces),
        FIRST_GUIDE=first_guide,
        ARCHIVE=archive["file"],
        VERSION=__version__,
        FAMILIES=families,
        **loop,
    )
    site.templated(
        "source.html",
        "source.html",
        ARCHIVE=archive["file"],
        ARCHIVE_NAME=Path(archive["file"]).name,
        ARCHIVE_KB=f"{archive['bytes'] / 1024:,.0f}",
        ARCHIVE_SHA=archive["sha256"],
        ARCHIVE_FILES=str(archive["files"]),
        ARCHIVE_ROOTS=", ".join(f"<code>{html.escape(r)}</code>" for r in archive["roots"]),
        VERSION=__version__,
    )
    if (WEB / "404.html").exists():
        site.templated("404.html", "404.html", root="/")
    write_discovery(
        out, IDENTITY["canonical_origin"], [f"docs/{source_name(slug)}" for slug, *_ in guide_pages]
    )
    problems = check_links(out)
    summary = {
        "output": str(out),
        "pieces": [p["id"] for p in pieces],
        "guides": [s for s, *_ in guide_pages],
        "examples": scripts,
        "skills": skills,
        "raw_docs": raw_docs,
        "analytics": {"enabled": bool(analytics), **(analytics or {})},
        "instrument_clips": clips,
        "archive": archive,
        "warnings": site.warnings,
        "broken_links": problems,
    }
    # Kept beside, not inside, the deployable folder.
    report = out.parent / f"{out.name}-build-report.json"
    report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "output" / "site"))
    parser.add_argument(
        "--compositions",
        default=str(COMPOSITIONS),
        help="Folder holding the original compositions' manifest.json",
    )
    parser.add_argument(
        "--reimaginations",
        default=str(REIMAGINATIONS),
        help="Folder holding the Reimagined versions' manifest.json ('none' leaves them out)",
    )
    parser.add_argument(
        "--with-originals",
        action="store_true",
        help="Also list the four original compositions (left out of the public lineup by default)",
    )
    parser.add_argument(
        "--classics",
        default=str(CLASSICS),
        help="Folder holding the public-domain excerpts' manifest.json ('none' leaves them out)",
    )
    parser.add_argument("--posthog-project-key", help="Public phc_ key; overrides the config file")
    parser.add_argument(
        "--posthog-host", choices=POSTHOG_HOSTS, help="PostHog US or EU ingest host"
    )
    parser.add_argument(
        "--analytics-allow-local",
        action="store_true",
        help="Let analytics run on localhost, for an explicit verification build only",
    )
    parser.add_argument(
        "--no-analytics",
        action="store_true",
        help="Build without analytics even when web/site/analytics-config.json exists",
    )
    parser.add_argument("--strict", action="store_true", help="Fail on warnings or broken links")
    args = parser.parse_args()
    if args.no_analytics:
        analytics = None
    elif args.posthog_project_key or args.posthog_host:
        analytics = analytics_config(
            args.posthog_project_key, args.posthog_host, args.analytics_allow_local
        )
    else:
        analytics = analytics_from_file()
        if analytics and args.analytics_allow_local:
            analytics["allowLocal"] = True
    classics = None if args.classics.lower() == "none" else Path(args.classics)
    reimaginations = None if args.reimaginations.lower() == "none" else Path(args.reimaginations)
    summary = build(
        Path(args.out),
        Path(args.compositions),
        classics,
        analytics,
        reimaginations,
        args.with_originals,
    )
    print(json.dumps(summary, indent=2))
    if summary["broken_links"] or (args.strict and summary["warnings"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
