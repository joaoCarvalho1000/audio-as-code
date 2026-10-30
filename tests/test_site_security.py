"""CSP must authorize exact generated content and reject new executable content."""

import pytest

from examples.site_security import content_security_policy, digest


def test_content_hashes_and_narrow_sources():
    policy = content_security_policy(
        "<script>\r\nconst x = 1;\r\n</script><style>body { color:red }</style>"
        '<b style="color:red">x</b>'
        '<script id="aac-analytics-config" type="application/json">'
        '{"apiHost":"https://eu.i.posthog.com"}</script>'
    )
    assert digest("\nconst x = 1;\n") in policy
    assert digest("body { color:red }") in policy
    assert digest("color:red") in policy
    assert "https://eu-assets.i.posthog.com/static/array.js" in policy
    assert "connect-src 'self' https://eu.i.posthog.com" in policy
    assert "us.i.posthog.com" not in policy
    assert "unsafe-inline" not in policy and "unsafe-eval" not in policy and "*" not in policy
    assert "script-src-attr 'none'" in policy
    assert "https://" not in content_security_policy("<h1>No analytics</h1>")


def test_inline_handlers_and_unapproved_analytics_fail():
    with pytest.raises(ValueError, match="inline event"):
        content_security_policy('<body onload="alert(1)">')
    with pytest.raises(ValueError, match="analytics host"):
        content_security_policy(
            '<script id="aac-analytics-config">{"apiHost":"https://other.test"}</script>'
        )
