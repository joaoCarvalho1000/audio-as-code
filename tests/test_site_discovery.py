"""Published search and agent entry points agree with the site's actual routes."""

import json
import re
from xml.etree import ElementTree

import pytest

from examples._site_discovery import canonical_url, metadata, write_discovery
from examples.build_site import Site

ORIGIN = "https://audioascode.com"


@pytest.mark.parametrize(
    "relative,route",
    [
        ("index.html", "/"),
        ("source.html", "/source"),
        ("docs/quickstart.html", "/docs/quickstart"),
        ("instruments/index.html", "/instruments/"),
        ("docs/index.html-not-a-page.html", "/docs/index.html-not-a-page"),
    ],
)
def test_canonical_matches_hosting_routes(relative, route):
    assert canonical_url(ORIGIN, relative) == ORIGIN + route


def test_search_discovery_uses_shipped_pages_and_absolute_guide_links(tmp_path):
    site = Site(tmp_path)
    for relative in ("index.html", "docs/quickstart.html", "404.html"):
        site.page(
            relative,
            title="Music & agents",
            description="Create music.",
            body="<h1>Music</h1>",
            nav="docs",
        )
    site.write("llms.txt", "# Audio as Code\n\n[Quickstart](docs/quickstart.md)\n")
    site.write("docs/quickstart.md", "# Start\n\n[Schema](../schemas/song-v1.schema.json)\n")
    write_discovery(tmp_path, ORIGIN, ["docs/quickstart.md"])
    sitemap = ElementTree.parse(tmp_path / "sitemap.xml")
    urls = {node.text for node in sitemap.findall(".//{*}loc")}
    assert urls == {ORIGIN + "/", ORIGIN + "/docs/quickstart"}
    assert "Sitemap: " + ORIGIN + "/sitemap.xml" in (tmp_path / "robots.txt").read_text()
    full = (tmp_path / "llms-full.txt").read_text()
    assert f"]({ORIGIN}/docs/quickstart.md)" in full
    assert f"]({ORIGIN}/schemas/song-v1.schema.json)" in full
    assert "Source: " + ORIGIN + "/docs/quickstart.md" in full
    page = (tmp_path / "docs/quickstart.html").read_text(encoding="utf-8")
    assert f'rel="canonical" href="{ORIGIN}/docs/quickstart"' in page
    assert "{{METADATA}}" not in page
    graph = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', page)[1])[
        "@graph"
    ]
    assert graph[-1]["url"] in urls
    assert graph[1]["codeRepository"] == "https://github.com/joaoCarvalho1000/audio-as-code"
    assert not any("aggregateRating" in node or "review" in node for node in graph)
    assert 'content="noindex,follow"' in (tmp_path / "404.html").read_text()


def test_structured_metadata_escapes_script_delimiters():
    head = metadata(ORIGIN, "index.html", '</script><script>"&', "A & B", "0.1.0")
    assert head.count("</script>") == 1
    raw = re.search(r'<script type="application/ld\+json">(.*?)</script>', head)[1]
    assert json.loads(raw)["@graph"][-1]["name"] == '</script><script>"&'
