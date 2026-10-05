"""Optional local browser checks, mandatory in the website CI job."""

import os
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1] / "output/site"


@pytest.fixture
def browser():
    if os.environ.get("AAC_REQUIRE_BROWSER") == "1":
        import playwright.sync_api  # noqa: F401

        assert (SITE / "index.html").is_file(), "CI must build the website before testing it"
    playwright = pytest.importorskip("playwright.sync_api")
    if not (SITE / "index.html").exists():
        pytest.skip("Build output/site first")
    with playwright.sync_playwright() as session:
        instance = session.chromium.launch(executable_path=os.environ.get("AAC_CHROMIUM") or None)
        yield instance
        instance.close()
