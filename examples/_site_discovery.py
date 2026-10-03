"""Search metadata and plain-text discovery for the static website."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.parse import urljoin
from xml.etree import ElementTree

REPOSITORY = "https://github.com/joaoCarvalho1000/audio-as-code"


def canonical_url(origin: str, relative: str) -> str:
    """Match Cloudflare's extensionless pages and directory index redirects."""
    path = relative.removesuffix("index.html") if relative.endswith("/index.html") else relative
    if path == "index.html":
        path = ""
    return origin.rstrip("/") + "/" + path.removesuffix(".html")


def metadata(origin: str, relative: str, title: str, description: str, version: str) -> str:
    """Describe actual public content without invented reviews or search features."""
    canonical = canonical_url(origin, relative)
    origin = origin.rstrip("/")
    image = origin + "/assets/social.png"
    tags = {
        "og:type": "website",
        "og:site_name": "Audio as Code",
        "og:image": image,
        "og:image:width": "1200",
        "og:image:height": "630",
        "og:image:alt": (
            "Audio as Code. Your agent brings the music. Open-source, code-generated instruments."
        ),
    }
    lines = [
        f'<meta property="{key}" content="{html.escape(value, quote=True)}">'
        for key, value in tags.items()
    ]
    for key, value in {
        "twitter:card": "summary_large_image",
        "twitter:title": title,
        "twitter:description": description,
        "twitter:image": image,
        "twitter:image:alt": tags["og:image:alt"],
        "robots": "noindex,follow"
        if relative == "404.html"
        else "index,follow,max-image-preview:large",
    }.items():
        lines.append(f'<meta name="{key}" content="{html.escape(value, quote=True)}">')
    if relative == "404.html":
        return "\n".join(lines)
    graph = [
        {
            "@type": "WebSite",
            "@id": origin + "/#website",
            "name": "Audio as Code",
            "url": origin + "/",
            "inLanguage": "en",
        },
        {
            "@type": "SoftwareSourceCode",
            "@id": origin + "/#software",
            "name": "Audio as Code",
            "url": origin + "/",
            "description": (
                "Open-source Python framework for AI agents to compose editable music "
                "and synthesize instruments from code. Render WAV offline and export MIDI "
                "for videos, games and presentations."
            ),
            "codeRepository": REPOSITORY,
            "programmingLanguage": "Python",
            "runtimePlatform": "Python 3.10+",
            "version": version,
            "license": REPOSITORY + "/blob/main/LICENSE",
            "isAccessibleForFree": True,
        },
        {
            "@type": "WebPage",
            "@id": canonical + "#webpage",
            "url": canonical,
            "name": title,
            "description": description,
            "inLanguage": "en",
            "isPartOf": {"@id": origin + "/#website"},
            "about": {"@id": origin + "/#software"},
        },
    ]
    data = json.dumps(
        {"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False
    ).replace("<", "\\u003c")
    lines.append(f'<script type="application/ld+json">{data}</script>')
    return "\n".join(lines)


def absolute_markdown(text: str, source_url: str) -> str:
    """Keep copied excerpts usable without their original directory context."""
    return re.sub(
        r"(\[[^\]]+\]\()([^\s)]+)(\))",
        lambda match: match[1] + urljoin(source_url, match[2]) + match[3],
        text,
    )


def write_discovery(out: Path, origin: str, guides: list[str]) -> None:
    """Build the sitemap from shipped HTML, and full agent docs from shipped Markdown."""
    origin = origin.rstrip("/")
    namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ElementTree.register_namespace("", namespace)
    root = ElementTree.Element(f"{{{namespace}}}urlset")
    for path in sorted(out.rglob("*.html")):
        relative = path.relative_to(out).as_posix()
        if relative == "404.html":
            continue
        node = ElementTree.SubElement(root, f"{{{namespace}}}url")
        ElementTree.SubElement(node, f"{{{namespace}}}loc").text = canonical_url(origin, relative)
    ElementTree.indent(root)
    ElementTree.ElementTree(root).write(out / "sitemap.xml", encoding="utf-8", xml_declaration=True)
    (out / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {origin}/sitemap.xml\n",
        encoding="utf-8",
        newline="\n",
    )
    index = out / "llms.txt"
    text = absolute_markdown(index.read_text(encoding="utf-8"), origin + "/llms.txt")
    index.write_text(text, encoding="utf-8", newline="\n")
    sections = [text]
    for relative in guides:
        path = out / relative
        if path.is_file():
            url = origin + "/" + relative
            sections.append(
                f"\n---\n\nSource: {url}\n\n"
                + absolute_markdown(path.read_text(encoding="utf-8"), url)
            )
    (out / "llms-full.txt").write_text("\n".join(sections), encoding="utf-8", newline="\n")
