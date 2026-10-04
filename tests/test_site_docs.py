"""Published guide links resolve after repository documents are flattened."""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_site", ROOT / "examples/build_site.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def test_published_raw_document_links_in_html_and_markdown(tmp_path, monkeypatch):
    docs = tmp_path / "source-docs"
    docs.mkdir()
    links = "\n\n".join(f"[{name}](../{name}#details)" for name in builder.RAW_DOCS)
    text = (
        "# Quickstart\n\n"
        + links
        + "\n\n[Guide](composition.md)\n\n"
        + "[Schema](../schemas/song-v1.schema.json)\n\n"
        + "[Unknown](../private/piano-sustain.md)\n\n"
        + "[External](https://example.test/piano-sustain.md)\n"
    )
    source = docs / "quickstart.md"
    source.write_text(text, encoding="utf-8")
    before = source.read_bytes()
    monkeypatch.setattr(builder, "DOCS", docs)
    site = builder.Site(tmp_path / "published")
    site.guides()
    site.raw_docs(classics=0)
    copied = (site.out / "docs/quickstart.md").read_text(encoding="utf-8")
    html = (site.out / "docs/quickstart.html").read_text(encoding="utf-8")
    for name in builder.RAW_DOCS:
        assert f"]({name}#details)" in copied
        assert f'href="{name}#details"' in html
        assert (site.out / "docs" / name).is_file()
    for target in [
        "../schemas/song-v1.schema.json",
        "../private/piano-sustain.md",
        "https://example.test/piano-sustain.md",
    ]:
        assert f"]({target})" in copied
        assert f'href="{target}"' in html
    assert "](composition.md)" in copied
    assert 'href="composition.html"' in html
    assert source.read_bytes() == before


def test_repository_guides_publish_existing_pedal_targets_without_source_changes(tmp_path):
    sources = {builder.DOCS / filename for _, filename, _ in builder.GUIDES}
    before = {source: source.read_bytes() for source in sources}
    site = builder.Site(tmp_path / "published")
    site.guides()
    site.raw_docs(classics=0)
    linked_guides = 0
    for slug, filename, _ in builder.GUIDES:
        source = (builder.DOCS / filename).read_text(encoding="utf-8")
        targets = re.findall(r"\]\((?:\.\./)?(piano-sustain\.md|creative-workflows\.md)\)", source)
        copied = (site.out / "docs" / filename).read_text(encoding="utf-8")
        html = (site.out / "docs" / f"{slug}.html").read_text(encoding="utf-8")
        for target in targets:
            linked_guides += 1
            assert f"]({target})" in copied
            assert f'href="{target}"' in html
            assert (site.out / "docs" / target).is_file()
    assert linked_guides >= 3
    assert all(source.read_bytes() == contents for source, contents in before.items())
