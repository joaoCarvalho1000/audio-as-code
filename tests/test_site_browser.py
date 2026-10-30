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


def test_csp_blocks_unapproved_script_eval_style_and_connections(browser, site_url):
    context = browser.new_context()
    page = context.new_page()
    page.goto(site_url)
    page.route(
        "**/probe.js",
        lambda route: route.fulfill(
            content_type="text/javascript",
            body="""
        try { eval('window.evalRan = true'); } catch { window.evalBlocked = true; }
        try { new Function('window.functionRan = true')(); }
        catch { window.functionBlocked = true; }
        window.probeLoaded = true;""",
        ),
    )
    page.evaluate("""() => {
      const inline = document.createElement('script');
      inline.textContent = 'window.inlineRan = true'; document.body.append(inline);
      const probe = document.createElement('script');
      probe.src = '/probe.js'; document.body.append(probe);
      const style = document.createElement('style');
      style.textContent = 'body { --unapproved: 1 }'; document.head.append(style);
      const element = document.createElement('b'); element.id = 'csp-probe';
      element.setAttribute('style', '--unapproved: 1'); document.body.append(element);
      fetch('https://unapproved.invalid/test').then(() => window.fetchRan = true)
        .catch(() => window.fetchBlocked = true);
    }""")
    page.wait_for_function("() => window.probeLoaded && window.fetchBlocked")
    assert page.evaluate(
        "evalBlocked && functionBlocked && !window.inlineRan && "
        "!window.evalRan && !window.functionRan && !window.fetchRan"
    )
    assert page.evaluate("getComputedStyle(document.body).getPropertyValue('--unapproved')") == ""
    assert (
        page.locator("#csp-probe").evaluate(
            "el => getComputedStyle(el).getPropertyValue('--unapproved')"
        )
        == ""
    )
    context.close()


def test_original_review_pack_native_loops(browser, tmp_path):
    import json

    from examples.audio_review_pack import generate

    pack = tmp_path / "pack"
    generate(pack)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SiteHandler, directory=str(pack)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    context = browser.new_context()
    page = context.new_page()
    try:
        page.goto(f"http://127.0.0.1:{server.server_port}/")
        for name in ("dry", "wet"):
            audio = page.locator(f'audio[src="experiments/{name}-cycle.wav"]')
            audio.evaluate("el => el.play()")
            page.wait_for_function(
                "key => reviewObservations.files[key].wraps.length >= 3",
                arg=f"experiments/{name}-cycle.wav",
                timeout=20000,
            )
            audio.evaluate("el => el.pause()")
            assert audio.evaluate("el => el.readyState >= 2 && el.error === null")
        observed = page.evaluate("reviewObservations")
        for name in ("dry", "wet"):
            data = observed["files"][f"experiments/{name}-cycle.wav"]
            assert data["playing"] >= 1 and data["errors"] == []
        artifacts = ROOT / "output/browser-checks"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "review-pack-loops.json").write_text(
            json.dumps(observed, indent=2), encoding="utf-8"
        )
    finally:
        context.close()
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
    page.add_init_script("""window.cspViolations = [];
      document.addEventListener('securitypolicyviolation', e =>
        cspViolations.push({directive:e.effectiveDirective, blocked:e.blockedURI}));""")
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
            assert response.headers.get("content-security-policy"), route
            assert not page.evaluate("cspViolations"), route
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
            "() => window.lastPlayed && !lastPlayed.paused && lastPlayed.currentTime > .05"
        )
        page.evaluate("lastPlayed.currentTime = 5")
        after.click()
        page.wait_for_function(
            "() => lastPlayed.currentSrc.endsWith('/after.wav') && !lastPlayed.paused "
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
        page.wait_for_function("() => lastPlayed.readyState >= 3 && !lastPlayed.paused")
        assert 5 <= page.evaluate("lastPlayed.currentTime") < 9
        after.click()
        page.wait_for_function("() => lastPlayed.paused")
        # Fail the next selection, then recover without reloading the page.
        page.route("**/groove/before.wav", lambda route: route.abort())
        before.click()
        status = page.locator("#groove article").first.locator("[data-mini-status]")
        from playwright.sync_api import expect

        expect(status).to_contain_text("Try again")
        page.unroute("**/groove/before.wav")
        before.click()
        page.wait_for_function(
            "() => lastPlayed.currentSrc.endsWith('/before.wav') && !lastPlayed.paused "
            "&& lastPlayed.currentTime > .05"
        )
        # The main player takes ownership, leaving both comparison controls stopped.
        page.locator("[data-console] [data-play]").click()
        page.wait_for_function(
            "() => !lastPlayed.currentSrc.includes('/groove/') && !lastPlayed.paused"
        )
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
            "() => window.lastPlayed && !lastPlayed.paused && lastPlayed.currentTime > 0.05",
            timeout=15000,
        )
        assert page.evaluate("lastPlayed.error === null && lastPlayed.duration > 0")
        button.click()
        page.wait_for_function("() => lastPlayed.paused")
    finally:
        context.close()
