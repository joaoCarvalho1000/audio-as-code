"""Content-derived CSP for generated HTML, shared by staging and local browser checks."""

from __future__ import annotations

import base64
import hashlib
import json
from html.parser import HTMLParser


def digest(text: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode()).digest()).decode() + "'"


class PolicyParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.scripts = set()
        self.styles = set()
        self.attributes = set()
        self.analytics = None
        self.block = None
        self.parts = []
        self.attrs = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "style" in attrs:
            self.attributes.add(digest(attrs["style"]))
        if any(key.startswith("on") for key in attrs):
            raise ValueError("inline event handlers are not supported by the site CSP")
        if tag in {"script", "style"}:
            self.block, self.parts, self.attrs = tag, [], attrs

    def handle_data(self, data):
        if self.block:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag != self.block:
            return
        text = "".join(self.parts)
        if tag == "style":
            self.styles.add(digest(text))
        elif self.attrs.get("id") == "aac-analytics-config":
            self.analytics = json.loads(text)
        elif "src" not in self.attrs and self.attrs.get("type", "") not in {
            "application/json",
            "application/ld+json",
        }:
            self.scripts.add(digest(text))
        self.block = None


def content_security_policy(html: str) -> str:
    # HTML parsing normalizes CRLF before computing CSP hashes in the browser.
    parser = PolicyParser()
    parser.feed(html.replace("\r\n", "\n").replace("\r", "\n"))
    scripts = ["'self'", *sorted(parser.scripts)]
    connections = ["'self'"]  # fetch scores and decode audio for canvas visualizations.
    if parser.analytics:
        host = parser.analytics["apiHost"]
        if host not in {"https://us.i.posthog.com", "https://eu.i.posthog.com"}:
            raise ValueError("unsupported analytics host in CSP")
        scripts.append(host.replace(".i.posthog.com", "-assets.i.posthog.com") + "/static/array.js")
        connections.append(host)
    directives = {
        "default-src": ["'none'"],
        "base-uri": ["'none'"],
        "object-src": ["'none'"],
        "frame-ancestors": ["'self'"],
        "form-action": ["'none'"],
        "script-src": scripts,
        "script-src-attr": ["'none'"],
        "style-src": ["'self'", *sorted(parser.styles)],
        "style-src-attr": ["'unsafe-hashes'", *sorted(parser.attributes)]
        if parser.attributes
        else ["'none'"],
        "img-src": ["'self'", "data:"],  # generated gallery's decorative SVG background.
        "font-src": ["'self'"],
        "media-src": ["'self'"],
        "connect-src": connections,
    }
    return "; ".join(key + " " + " ".join(values) for key, values in directives.items())
