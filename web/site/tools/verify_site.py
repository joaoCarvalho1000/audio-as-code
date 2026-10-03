"""Browser check of a built site: python web/site/tools/verify_site.py [site-folder] [shots-folder].

Serves the folder over HTTP with the repository preview handler (examples/serve_site.py,
byte ranges like a real static host), exercises navigation, playback, seeking, sections,
copy, the agent handoff (also from a subpath, with clipboard blocked, and without
JavaScript) and every page, collects console/page errors and failed requests, and saves
desktop (1440) and mobile (390) screenshots. Needs Playwright with a Chromium build.
"""

from __future__ import annotations

import functools
import http.server
import json
import os
import sys
import threading
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
SITE = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "output" / "site").resolve()
SHOTS = Path(sys.argv[2] if len(sys.argv) > 2 else ROOT / ".impeccable" / "review").resolve()
# Set AAC_CHROMIUM to use a specific Chromium build; otherwise Playwright picks its own.
CHROME = os.environ.get("AAC_CHROMIUM") or None


def _preview_handler() -> type[http.server.SimpleHTTPRequestHandler]:
    """The repository's Range-capable preview handler, or the stdlib one if it is absent."""
    sys.path.insert(0, str(ROOT / "examples"))
    try:
        from serve_site import SiteHandler
    except ImportError:
        return http.server.SimpleHTTPRequestHandler
    finally:
        sys.path.pop(0)
    return SiteHandler


class Quiet(_preview_handler()):
    prefix = ""

    def log_message(self, *args) -> None:
        pass

    def translate_path(self, path: str) -> str:
        # Mount the site under a subpath to test URL construction on subpath hosting.
        if self.prefix and path.startswith(self.prefix):
            path = "/" + path[len(self.prefix) :]
        return super().translate_path(path)


def serve(prefix: str = "") -> tuple[http.server.ThreadingHTTPServer, str]:
    handler_class = type("Mounted", (Quiet,), {"prefix": prefix})
    handler = functools.partial(handler_class, directory=str(SITE))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.handle_error = lambda request, address: None  # aborted media downloads are expected
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}{prefix or '/'}"


def resolves(url: str) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD")) as response:
            return response.status == 200
    except OSError:
        return False


def handoff(page, base: str, label: str, check) -> None:
    """Pick an example, edit the brief, copy, and check every URL in the prompt resolves."""
    chips = page.locator("[data-brief]")
    chips.nth(2).click()
    brief = chips.nth(2).get_attribute("data-brief")
    check(
        f"{label}: example brief fills the editor",
        page.locator("[data-brief-input]").input_value() == brief
        and chips.nth(2).get_attribute("aria-pressed") == "true",
    )
    page.locator("[data-handoff-copy]").click()
    page.wait_for_timeout(200)
    copied = page.evaluate("navigator.clipboard.readText()")
    urls = [w for w in copied.split() if w.startswith("http")]
    urls = [u.rstrip(".,") for u in urls]
    wanted = [
        base + "skills/audio-as-code/SKILL.md",
        base + "llms.txt",
    ]
    check(
        f"{label}: copied prompt names this site's skill, llms.txt and source ZIP",
        all(w in urls for w in wanted)
        and any(u.startswith(base + "download/") and u.endswith(".zip") for u in urls),
        str(urls),
    )
    check(f"{label}: every prompt URL resolves", bool(urls) and all(map(resolves, urls)), str(urls))
    check(f"{label}: copied prompt carries the chosen brief", brief in copied)
    status = page.locator("[data-handoff-status]").inner_text()
    check(f"{label}: copy reports success", status.lower().startswith("copied"), status)
    page.locator("[data-brief-input]").fill("A slow lullaby for harp and cello, about a minute.")
    page.locator("[data-handoff-copy]").click()
    page.wait_for_timeout(200)
    copied = page.evaluate("navigator.clipboard.readText()")
    check(
        f"{label}: edited brief is what gets copied",
        "A slow lullaby for harp and cello" in copied
        and page.locator("[data-brief][aria-pressed='true']").count() == 0,
    )
    chips.nth(0).click()


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    server, base = serve()
    results: dict = {"base": base, "checks": [], "errors": [], "failed_requests": []}

    def check(name: str, ok: bool, detail: str = "") -> None:
        results["checks"].append({"check": name, "ok": bool(ok), "detail": detail})

    pages = sorted(
        p.relative_to(SITE).as_posix()
        for p in SITE.rglob("*.html")
        if not p.is_relative_to(SITE / "instruments")
    )
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=CHROME,
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"],
        )
        for label, viewport, motion in [
            ("desktop", {"width": 1440, "height": 900}, "no-preference"),
            ("mobile", {"width": 390, "height": 844}, "reduce"),
        ]:
            context = browser.new_context(
                viewport=viewport,
                reduced_motion=motion,
                device_scale_factor=1 if label == "desktop" else 2,
                permissions=["clipboard-read", "clipboard-write"],
            )
            page = context.new_page()
            page.on("pageerror", lambda e, tag=label: results["errors"].append(f"{tag}: {e}"))
            page.on(
                "console",
                lambda m, tag=label: (
                    m.type == "error" and results["errors"].append(f"{tag}: {m.text}")
                ),
            )
            page.on(
                "requestfailed",
                lambda r, tag=label: results["failed_requests"].append(
                    f"{tag}: {r.url} {r.failure}"
                ),
            )
            page.on(
                "response",
                lambda r, tag=label: (
                    r.status >= 400
                    and results["failed_requests"].append(f"{tag}: {r.status} {r.url}")
                ),
            )
            page.goto(base + "index.html", wait_until="networkidle")
            requested_wav = page.evaluate(
                "performance.getEntriesByType('resource')"
                ".filter((e) => /[.](wav|mp3)$/.test(e.name)).length"
            )
            check(f"{label}: no audio fetched before Play", requested_wav == 0, str(requested_wav))
            overflow = page.evaluate(
                "document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            check(f"{label}: no horizontal overflow on home", overflow <= 0, f"{overflow}px")
            fold = page.evaluate(
                "() => ['[data-scope]', '[data-play]', '.key-agent'].map(s => "
                "document.querySelector(s).getBoundingClientRect().bottom)"
            )
            check(
                f"{label}: scope, Play and agent handoff inside first viewport",
                max(fold) <= viewport["height"],
                f"bottoms {[round(b) for b in fold]} / {viewport['height']}",
            )
            fonts = page.evaluate(
                "() => [getComputedStyle(document.querySelector('.nav a')).fontFamily,"
                " getComputedStyle(document.querySelector('[data-time]')).fontFamily]"
            )
            check(
                f"{label}: nav set in Anybody, clock mono",
                fonts[0].replace('"', "").startswith("Anybody") and "JetBrains" in fonts[1],
                str(fonts),
            )
            nav = page.evaluate(
                "() => { const l = document.querySelector('.nav'); const tops = new Set("
                "[...l.querySelectorAll('a')].map(a => Math.round(a.getBoundingClientRect().top)));"
                " return [tops.size, l.scrollWidth - l.clientWidth] }"
            )
            check(f"{label}: nav links on one row, none hidden", nav == [1, 0], str(nav))
            cells = page.evaluate(
                "() => [...document.querySelectorAll('.downloads li')].map(li => "
                "[Math.round(li.getBoundingClientRect().width),"
                " Math.round(li.firstElementChild.getBoundingClientRect().width)])"
            )
            check(
                f"{label}: download keys fill their grid cells",
                bool(cells)
                and all(abs(c - k) <= 1 for c, k in cells)
                and len({c for c, _ in cells[1:]}) == 1,
                str(cells),
            )
            pieces = page.locator("[data-selector] button").count()
            check(f"{label}: piece selector rendered", pieces > 0, str(pieces))
            if label == "desktop":
                page.screenshot(path=str(SHOTS / "desktop-first-viewport.png"))
            if pieces:
                page.locator("[data-play]").click()
                page.wait_for_function(
                    "() => document.querySelector('[data-play]').classList.contains('is-playing')",
                    timeout=15000,
                )
                page.wait_for_timeout(2300)
                t = page.locator("[data-time]").inner_text()
                check(f"{label}: Play advances the clock", t != "0:00", t)
                frames = page.locator("[data-frames] button")
                if frames.count() > 1:
                    frames.nth(1).click()
                    target = float(frames.nth(1).get_attribute("data-at"))
                    # Without HTTP Range support the player first downloads the whole WAV.
                    page.wait_for_function(
                        "t => { const [m, s] = document.querySelector('[data-time]')"
                        ".textContent.split(':'); return Math.abs(m * 60 + +s - t) <= 2 }",
                        arg=target,
                        timeout=30000,
                    )
                    m, s_ = page.locator("[data-time]").inner_text().split(":")
                    shown = int(m) * 60 + int(s_)
                    check(
                        f"{label}: section jump seeks to section start",
                        abs(shown - target) <= 2,
                        f"target {target:.1f}s, shows {shown}s",
                    )
                if pieces > 1:
                    page.locator("[data-selector] button").nth(1).click()
                    check(
                        f"{label}: switching piece stops playback",
                        not page.locator("[data-play]").evaluate(
                            "b => b.classList.contains('is-playing')"
                        ),
                    )
                mini = page.locator("[data-mini-play]")
                mini.click()
                page.wait_for_function(
                    "() => document.querySelector('[data-mini-play]')"
                    ".classList.contains('is-playing')",
                    timeout=10000,
                )
                check(
                    f"{label}: loop player plays; main player idle",
                    not page.locator("[data-play]").evaluate(
                        "b => b.classList.contains('is-playing')"
                    ),
                )
                mini.click()
                page.wait_for_timeout(300)
            page.locator(".loop [data-copy]").first.click()
            page.wait_for_timeout(200)
            check(
                f"{label}: copy button reports",
                page.locator(".loop [data-copy]").first.inner_text().lower()
                in {"copied", "select and copy"},
                page.locator(".loop [data-copy]").first.inner_text(),
            )
            page.locator(".key-agent").click()
            page.wait_for_timeout(400)
            top = page.evaluate("document.getElementById('handoff').getBoundingClientRect().top")
            check(f"{label}: agent action jumps to the handoff", abs(top) < 80, f"{top:.0f}px")
            handoff(page, base, label, check)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(300)
            page.screenshot(path=str(SHOTS / f"{label}.png"), full_page=True)
            for rel in pages:
                page.goto(base + rel, wait_until="networkidle")
                ow = page.evaluate(
                    "document.documentElement.scrollWidth - document.documentElement.clientWidth"
                )
                check(f"{label}: {rel} renders without overflow", ow <= 0, f"{ow}px")
                if label == "desktop" and rel == "docs/quickstart.html":
                    page.screenshot(path=str(SHOTS / "desktop-docs.png"), full_page=False)
                if label == "mobile" and rel == "docs/quickstart.html":
                    page.screenshot(path=str(SHOTS / "mobile-docs.png"), full_page=False)
            page.goto(base + "index.html")
            page.keyboard.press("Tab")
            check(
                f"{label}: first Tab reaches skip link",
                page.evaluate("document.activeElement.className") == "skip",
            )
            context.close()
        # Subpath hosting: every URL in the prompt is built from where the page is served.
        sub_server, sub_base = serve("/music/aac/")
        context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
        page = context.new_page()
        page.goto(sub_base + "index.html", wait_until="networkidle")
        handoff(page, sub_base, "subpath", check)
        context.close()
        sub_server.shutdown()
        # Clipboard refused: the prompt is selected and the visitor is told how to copy.
        context = browser.new_context()
        context.add_init_script(
            "Object.defineProperty(navigator, 'clipboard', { value: { writeText: () =>"
            " Promise.reject(new Error('denied')) } }); document.execCommand = () => false;"
        )
        page = context.new_page()
        page.goto(base + "index.html", wait_until="networkidle")
        page.locator("[data-handoff-copy]").click()
        page.wait_for_timeout(200)
        selected = page.evaluate("getSelection().toString()")
        prompt = page.locator("[data-prompt]").inner_text()
        check(
            "clipboard blocked: prompt selected with instructions",
            "blocked" in page.locator("[data-handoff-status]").inner_text()
            and selected.strip() == prompt.strip(),
        )
        context.close()
        # Without JavaScript the prompt is still readable and the resources are links.
        context = browser.new_context(java_script_enabled=False)
        page = context.new_page()
        page.goto(base + "index.html", wait_until="load")
        check(
            "no JavaScript: prompt readable, copy button hidden, links present",
            "skills/audio-as-code/SKILL.md" in page.locator("[data-prompt]").inner_text()
            and not page.locator("[data-handoff-copy]").is_visible()
            and page.locator("[data-handoff-zip]").get_attribute("href").endswith(".zip"),
        )
        context.close()
        browser.close()
    server.shutdown()
    results["ok"] = (
        all(c["ok"] for c in results["checks"])
        and not results["errors"]
        and not [f for f in results["failed_requests"] if "net::ERR_ABORTED" not in f]
    )
    print(json.dumps(results, indent=2))
    return 0 if results["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
