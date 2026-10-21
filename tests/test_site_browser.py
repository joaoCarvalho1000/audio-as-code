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


def test_groove_downloads_match_the_published_comparison(browser):
    import json
    import wave

    from audio_as_code import Song

    reports = json.loads((SITE / "groove/report.json").read_text(encoding="utf-8"))
    with wave.open(str(SITE / "groove/before.wav")) as before:
        before_params = before.getparams()
    with wave.open(str(SITE / "groove/after.wav")) as after:
        assert after.getparams() == before_params
    for label in ("before", "after"):
        report = reports[label]
        assert report["loudness"]["target_reached"]
        assert not report["loudness"]["peak_limited"]
        assert abs(report["loudness"]["achieved_lufs"] + 20) < 0.1
        assert report["wav"]["full_scale_samples"] == 0
        assert Song.load(SITE / f"groove/{label}.json").beats == 34
        assert (SITE / f"groove/{label}.mid").read_bytes().startswith(b"MThd")
    assert (SITE / "groove/groove_comparison.py").is_file()


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
            if route == "source.html":
                page.locator('nav [data-key="listen"]').click()
                page.wait_for_url(f"{site_url}/#listen")
                assert page.locator("[data-console]").count() == 1
            if route in {"index.html", "instruments/index.html", "electronic/index.html"}:
                page.screenshot(path=str(artifacts / f"{route.replace('/', '-')}-{width}.png"))
            if route == "index.html":
                page.locator("#groove").screenshot(path=str(artifacts / f"groove-{width}.png"))
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    finally:
        context.close()


@pytest.mark.parametrize("width", [390, 1440])
def test_groove_switches_at_same_position_and_retries_failed_audio(browser, site_url, width):
    context = browser.new_context(viewport={"width": width, "height": 900}, reduced_motion="reduce")
    context.route("https://**", lambda route: route.abort())
    context.add_init_script("""(() => {
      const play = HTMLMediaElement.prototype.play;
      HTMLMediaElement.prototype.play = function (...args) {
        window.lastPlayed = this;
        return play.apply(this, args);
      };
    })()""")
    page = context.new_page()
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    try:
        page.goto(f"{site_url}/", wait_until="networkidle")
        assert not any("/groove/" in url for url in requests)
        before = page.locator('[data-src="groove/before.wav"] button')
        after = page.locator('[data-src="groove/after.wav"] button')
        before.focus()
        before.press("Space")
        page.wait_for_function(
            "window.lastPlayed && !lastPlayed.paused && lastPlayed.currentTime > .05"
        )
        page.evaluate("lastPlayed.currentTime = 5")
        after.click()
        page.wait_for_function(
            "lastPlayed.currentSrc.endsWith('/after.wav') && !lastPlayed.paused "
            "&& lastPlayed.currentTime >= 5"
        )
        assert page.evaluate("lastPlayed.currentTime < 8")
        assert before.get_attribute("aria-pressed") == "false"
        assert after.get_attribute("aria-pressed") == "true"
        # A second selection before metadata arrives must retain the pending position.
        page.evaluate("""() => {
          document.querySelector('[data-src="groove/before.wav"] button').click();
          document.querySelector('[data-src="groove/after.wav"] button').click();
        }""")
        page.wait_for_function("lastPlayed.readyState >= 3 && !lastPlayed.paused")
        assert 5 <= page.evaluate("lastPlayed.currentTime") < 9
        after.click()
        page.wait_for_function("lastPlayed.paused")
        # Fail the next selection, then recover without reloading the page.
        page.route("**/groove/before.wav", lambda route: route.abort())
        before.click()
        status = page.locator("#groove article").first.locator("[data-mini-status]")
        from playwright.sync_api import expect

        expect(status).to_contain_text("Try again")
        page.unroute("**/groove/before.wav")
        before.click()
        page.wait_for_function(
            "lastPlayed.currentSrc.endsWith('/before.wav') && !lastPlayed.paused "
            "&& lastPlayed.currentTime > .05"
        )
        # The main player takes ownership, leaving both comparison controls stopped.
        page.locator("[data-console] [data-play]").click()
        page.wait_for_function("!lastPlayed.currentSrc.includes('/groove/') && !lastPlayed.paused")
        assert before.get_attribute("aria-pressed") == "false"
        assert after.get_attribute("aria-pressed") == "false"
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
    context = browser.new_context(reduced_motion="reduce")
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
