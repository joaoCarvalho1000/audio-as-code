"""Hosting preparation must preserve assets and never overwrite an existing folder."""

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "prepare_cloudflare", Path(__file__).resolve().parents[1] / "examples/prepare_cloudflare.py"
)
assert SPEC is not None and SPEC.loader is not None
STAGING = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGING)
prepare = STAGING.prepare

ACCOUNT = "a" * 32


def website(root: Path) -> Path:
    site = root / "site"
    (site / "music").mkdir(parents=True)
    (site / "index.html").write_text("test site", encoding="utf-8")
    (site / "music/manifest.json").write_text('{"pieces": []}', encoding="utf-8")
    (site / "music/song.wav").write_bytes(b"RIFF" * 32)
    return site


def test_staging_separates_large_files_without_altering_source(tmp_path, monkeypatch):
    monkeypatch.setattr(STAGING, "ASSET_LIMIT", 100)
    site = website(tmp_path)
    output = tmp_path / "staged"
    report = prepare(site, output, account_id=ACCOUNT, domains=("example.com",))
    assert report["static_files"] == 2
    assert len(report["large_files"]) == 1
    assert (site / "music/song.wav").read_bytes() == b"RIFF" * 32
    assert not (output / "assets/music/song.wav").exists()
    assert (output / "assets/index.html").read_bytes() == (site / "index.html").read_bytes()
    manifest = json.loads((output / "media-manifest.json").read_text())
    assert manifest["/music/song.wav"]["bytes"] == 128
    config = json.loads((output / "wrangler.jsonc").read_text())
    assert config["routes"] == [{"pattern": "example.com", "custom_domain": True}]
    assert config["assets"]["directory"] == "./assets"
    with pytest.raises(ValueError, match="already exists"):
        prepare(site, output, account_id=ACCOUNT)
    assert (output / "assets/index.html").read_text() == "test site"


def test_preflight_rejects_overlap_and_invalid_target_before_writing(tmp_path):
    site = website(tmp_path)
    with pytest.raises(ValueError, match="overlap"):
        prepare(site, site / "nested", account_id=ACCOUNT)
    assert not (site / "nested").exists()
    with pytest.raises(ValueError, match="account_id"):
        prepare(site, tmp_path / "new", account_id="invalid")
    assert not (tmp_path / "new").exists()
