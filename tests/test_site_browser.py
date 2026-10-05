"""Exercise the generated pages and real media decoding, without live analytics."""

from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from examples.serve_site import SiteHandler

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "output/site"


@pytest.fixture
def site_url(browser):
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SiteHandler, directory=str(SITE)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("width", [390, 1440])
def test_generated_pages_load_without_script_errors(browser, site_url, width):
    context = browser.new_context(viewport={"width": width, "height": 900})
    context.route("https://**", lambda route: route.abort())
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    artifacts = ROOT / "output/browser-checks"
    artifacts.mkdir(parents=True, exist_ok=True)
    try:
        pages = sorted(SITE.rglob("*.html"))
        assert len(pages) >= 5
        for file in pages:
            route = file.relative_to(SITE).as_posix()
            response = page.goto(f"{site_url}/{route}", wait_until="networkidle")
            assert response.status == 200, route
            assert page.title(), route
            assert not errors, f"{route}: {errors}"
            if route in {"index.html", "instruments/index.html", "electronic/index.html"}:
                page.screenshot(path=str(artifacts / f"{route.replace('/', '-')}-{width}.png"))
    finally:
        context.close()


@pytest.mark.parametrize(
    ("route", "selector"),
    [
        ("index.html", "[data-console] [data-play]"),
        ("instruments/index.html", ".row-play"),
        ("electronic/index.html", "[data-play]"),
    ],
)
def test_players_decode_and_pause_real_audio(browser, site_url, route, selector):
    context = browser.new_context()
    context.route("https://**", lambda route: route.abort())
    # Observe the actual media element, including the homepage's detached Audio.
    # Playback and decoding still use Chromium's unmodified implementation.
    context.add_init_script("""(() => {
      const play = HTMLMediaElement.prototype.play;
      HTMLMediaElement.prototype.play = function (...args) {
        window.lastPlayed = this;
        return play.apply(this, args);
      };
    })()""")
    page = context.new_page()
    try:
        page.goto(f"{site_url}/{route}")
        button = page.locator(selector).first
        button.click()
        page.wait_for_function(
            "window.lastPlayed && !lastPlayed.paused && lastPlayed.currentTime > 0.05",
            timeout=15000,
        )
        assert page.evaluate("lastPlayed.error === null && lastPlayed.duration > 0")
        button.click()
        page.wait_for_function("lastPlayed.paused")
    finally:
        context.close()
