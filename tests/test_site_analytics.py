"""Optional browser regression tests; SDK requests are stubbed, never sent to PostHog.

Run with Playwright installed and AAC_CHROMIUM set if its browser is outside the cache.
The fixture uses built HTML, but serves it entirely through browser routes.
"""

from __future__ import annotations

import json
import re
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "output/site"
JS = ROOT / "web/site/assets/analytics.js"
CONFIG = {"projectKey": "phc_testonly", "apiHost": "https://us.i.posthog.com"}
SDK = """
window.__sdkOptions = posthog._i[0][1];
window.__events = [];
const instance = {
  capture(name, props, options) {
    const event = __sdkOptions.before_send({event:name,properties:{
      ...props, distinct_id:'test-anonymous', $current_url:location.href,
      $initial_current_url:location.href, $set:{email:'private@example.test'},
      arbitrary_secret:'PRIVATE', $referrer:'https://search.test/private?secret=PRIVATE'
    }});
    if (event) __events.push(event);
  },
  opt_out_capturing() { window.__sdkOptedOut = true; }
};
window.posthog = instance;
__sdkOptions.loaded(instance);
"""


def page_for(browser, *, config=None, init="", sdk=SDK, host="site.example", path="index.html"):
    # These tests assert event semantics. Keep the pulsing playback buttons
    # stable so an animation cannot block Playwright's pointer actionability.
    context = browser.new_context(reduced_motion="reduce")
    if init:
        context.add_init_script(init)
    requests = []
    context.on("request", lambda request: requests.append(request.url))

    def route(request):
        url = request.request.url
        if ".posthog.com/" in url:
            assert url.endswith("/static/array.js"), "No live ingestion is allowed in tests"
            request.fulfill(body=sdk, content_type="application/javascript")
            return
        from urllib.parse import unquote, urlsplit

        path = unquote(urlsplit(url).path).lstrip("/") or "index.html"
        file = (SITE / path).resolve()
        if path == "assets/analytics.js":
            request.fulfill(body=JS.read_text(encoding="utf-8"), content_type="text/javascript")
            return
        if not file.is_relative_to(SITE.resolve()) or not file.is_file():
            request.fulfill(status=404, body="missing")
            return
        if file.suffix == ".html":
            html = file.read_text(encoding="utf-8")
            html = re.sub(r'<script id="aac-analytics-config".*?</script>', "", html, flags=re.S)
            html = re.sub(r'<script[^>]*src="[^"]*analytics.js"[^>]*></script>', "", html)
            injected = (
                '<script id="aac-analytics-config" type="application/json">'
                + json.dumps(config if config is not None else CONFIG)
                + '</script><script src="/assets/analytics.js" defer></script>'
            )
            request.fulfill(
                body=html.replace("</body>", injected + "</body>"), content_type="text/html"
            )
        else:
            request.fulfill(path=str(file))

    context.route("**/*", route)
    page = context.new_page()
    page.goto(f"https://{host}/{path}?utm_source=agent_test&secret=PRIVATE#PRIVATE")
    return context, page, requests


@pytest.mark.parametrize(
    ("host", "init", "config"),
    [
        ("localhost", "", CONFIG),
        ("127.0.0.1", "", CONFIG),
        ("site.example", "Object.defineProperty(navigator,'doNotTrack',{value:'1'})", CONFIG),
        (
            "site.example",
            "Object.defineProperty(navigator,'globalPrivacyControl',{value:true})",
            CONFIG,
        ),
        ("site.example", "localStorage.setItem('aac.analytics.optout','1')", CONFIG),
        ("site.example", "", {**CONFIG, "apiHost": "https://wrong.example"}),
        ("site.example", "", {**CONFIG, "projectKey": "personal-secret"}),
        ("fork.example", "", {**CONFIG, "allowedHosts": ["audioascode.com"]}),
    ],
)
def test_disabled_never_requests_sdk_or_media(browser, host, init, config):
    context, page, requests = page_for(browser, host=host, init=init, config=config)
    page.wait_for_timeout(350)
    assert not any("posthog.com" in url for url in requests)
    assert not any(re.search(r"\.(mp3|wav)(\?|$)", url) for url in requests)
    context.close()


def test_events_exclude_content_and_auto_properties(browser):
    context, page, requests = page_for(browser)
    page.wait_for_function("window.__events?.length === 1")
    assert page.evaluate("__sdkOptions.autocapture") is False
    assert page.evaluate("__sdkOptions.disable_session_recording") is True
    assert not any(re.search(r"\.(mp3|wav)(\?|$)", url) for url in requests)
    page.locator("[data-brief-input]").fill("PRIVATE prompt and notes")
    page.locator("[data-handoff-copy]").click()
    page.locator("[data-selector] [data-id]").nth(1).click()
    page.evaluate("document.querySelector('[data-play]').classList.add('is-playing')")
    page.wait_for_function("__events.some(e=>e.event==='demo_play_started')")
    page.evaluate("""() => {
      const a=document.createElement('a');a.href='https://ko-fi.com/joaothecarvalho';
      a.dataset.kofi='footer';a.onclick=e=>e.preventDefault();document.body.append(a);a.click();
    }""")
    events = page.evaluate("__events")
    names = {event["event"] for event in events}
    assert {
        "$pageview",
        "agent_handoff_copy_clicked",
        "demo_selected",
        "demo_play_started",
        "support_clicked",
    } <= names
    assert "PRIVATE" not in json.dumps(events)
    assert "$set" not in json.dumps(events)
    assert events[0]["properties"]["utm_source"] == "agent_test"
    assert events[0]["properties"]["$current_url"] == "https://site.example/index.html"
    before = len(events)
    page.evaluate("aacAnalytics.optOut()")
    page.locator("[data-handoff-copy]").click()
    assert page.evaluate("__events.length") == before
    assert page.evaluate("__sdkOptedOut") is True
    context.close()


def test_verification_mode_is_one_labeled_event(browser):
    context, page, _ = page_for(
        browser,
        host="localhost",
        config={
            **CONFIG,
            "allowLocal": True,
            "verificationOnly": True,
            "allowedHosts": ["audioascode.com"],
        },
    )
    page.wait_for_function("window.__events?.length === 1")
    assert page.evaluate("__events[0].event") == "analytics_verification"
    page.locator("[data-handoff-copy]").click()
    assert page.evaluate("__events.length") == 1
    context.close()


def test_queued_events_drop_when_opted_out_before_sdk_load(browser):
    # Delay the SDK loaded callback, then opt out with a pageview still queued.
    context, page, _ = page_for(browser, sdk="window.__delayed = () => {" + SDK + "}")
    page.wait_for_function("typeof window.__delayed === 'function'")
    page.evaluate("aacAnalytics.optOut(); __delayed()")
    assert page.evaluate("__events.length") == 0
    assert page.evaluate("__sdkOptedOut") is True
    context.close()


def test_builder_config_and_safe_bootstrap():
    builder = runpy.run_path(str(ROOT / "examples/build_site.py"))
    validate = builder["analytics_config"]
    assert validate() is None
    for key, host in [
        ("phc_" + "a" * 24, None),
        ("personal-secret", CONFIG["apiHost"]),
        ("phc_" + "a" * 24, "https://wrong.example"),
    ]:
        with pytest.raises(SystemExit):
            validate(key, host)
    config = validate("phc_" + "a" * 24, CONFIG["apiHost"])
    assert config["allowLocal"] is False
    bootstrap = builder["analytics_html"](config, "../")
    assert 'src="../assets/analytics.js" defer' in bootstrap
    assert 'id="aac-analytics-config"' in bootstrap
    assert builder["analytics_html"](None, "") == ""


def test_gallery_playback_state_and_optout_control(browser):
    context, page, requests = page_for(browser, path="instruments/index.html")
    page.wait_for_function("window.__events?.length === 1")
    assert not any(re.search(r"\.(mp3|wav)(\?|$)", url) for url in requests)
    page.locator(".instrument-select").nth(1).click()
    page.evaluate("document.getElementById('audio').dispatchEvent(new Event('playing'))")
    page.wait_for_function("__events.some(e=>e.event==='demo_play_started')")
    assert (
        page.evaluate("__events.find(e=>e.event==='demo_play_started').properties.player")
        == "instrument"
    )
    assert page.locator('a[href$="analytics.md"]').count() >= 1
    page.locator("[data-analytics-optout]").click()
    assert page.evaluate("aacAnalytics.status()") == "opted-out"
    assert page.locator("[data-analytics-optout]").last.text_content() == "Analytics off"
    context.close()


def test_gallery_pause_is_not_counted_as_another_play_request(browser):
    context, page, _ = page_for(browser, path="instruments/index.html")
    page.wait_for_function("window.__events?.length === 1")
    page.evaluate("""() => {
      const audio = document.getElementById('audio');
      let paused = true;
      Object.defineProperty(audio, 'paused', {get: () => paused});
      audio.play = async () => { paused = false; audio.dispatchEvent(new Event('play')); };
      audio.pause = () => { paused = true; audio.dispatchEvent(new Event('pause')); };
    }""")
    button = page.locator(".row-play").first
    button.click()
    assert page.evaluate("__events.filter(e => e.event === 'demo_play_requested').length") == 1
    page.wait_for_function("document.querySelector('.instrument-row.is-playing') !== null")
    button.click()
    assert page.evaluate("__events.filter(e => e.event === 'demo_play_requested').length") == 1
    # Choosing a different row while something is playing is a new request.
    button.click()
    page.locator(".row-play").nth(1).click()
    assert page.evaluate("__events.filter(e => e.event === 'demo_play_requested').length") == 3
    context.close()
