# Website analytics

The public Audio as Code website uses PostHog to understand visits, acquisition,
demo use, downloads, and agent handoff interest. Analytics are separate from the
Python package: the CLI, synthesis engine, and generated music send no telemetry.

## Visitor privacy and controls

The site records selected interaction categories and public demo/instrument IDs.
It does **not** record music briefs, prompts, notes, clipboard contents, form
inputs, search text, or session replay. Automatic DOM capture, heatmaps, exception
capture, performance capture, surveys, and feature flags are disabled.

Page addresses omit query strings and fragments. Referrers retain only their
origin/domain. The five standard `utm_source`, `utm_medium`, `utm_campaign`,
`utm_content`, and `utm_term` campaign parameters are allowed, limited to 100 ASCII
letters, numbers, spaces, underscores, periods, and hyphens. Never put personal
data in campaign parameters. Other query parameters and ad click IDs are excluded.

Do Not Track and Global Privacy Control prevent SDK loading and collection.
Use **Opt out of analytics** in the footer to stop future capture on this browser.
The preference is saved locally; clearing site storage clears it. This cannot
recall requests already sent. If browser storage is unavailable, the choice lasts
for the current page. To re-enable explicitly, run `aacAnalytics.optIn()` in the
browser console; browser privacy signals still take precedence.

PostHog receives the network request and can enrich events with approximate
country information using the connection IP. There is no browser geolocation
permission or GPS lookup. VPNs, proxies, and agent infrastructure can make country
inaccurate. The project operator should enable **Settings → Project → IP data
capture configuration → Discard client IP data**; PostHog documents that normal
GeoIP enrichment can run before the IP is discarded. That project setting is not
changed by this repository and must be checked in the dashboard.

Identity uses `sessionStorage`, with no person profiles, login identity, or
persistent analytics cookies. Counts describe anonymous browser sessions/tabs,
not unique humans or a reliable cross-device audience. Browsers may copy a tab's
session storage when duplicating it. No visitor is identified by name or email.

## What gets measured

| Event | Additional properties | Meaning |
| --- | --- | --- |
| `$pageview` | sanitized page/referrer, allowed UTMs | A page reached deferred SDK initialization. |
| `demo_selected` | `piece_id` or `instrument_id` | A visitor chose a public demo/voice. |
| `demo_play_requested` | `player`, public ID | A play control was clicked. |
| `demo_play_started` | `player`, public ID | The player entered its playing state; resuming can repeat it. |
| `download_clicked` | `asset_type`, optional `piece_id` | A download link was clicked, not proof it completed. |
| `agent_handoff_copy_clicked` | none | Copy was requested; no prompt or clipboard text is captured. |
| `agent_resource_clicked` | `resource`: skill, llms, source_zip, source_page, guide | A browser clicked an agent/developer resource. |
| `support_clicked` | `placement`: nav/footer/other | A Ko-fi support link was clicked. |
| `analytics_verification` | `verification: true` | One explicitly authorized local installation test; exclude from product reporting. |

All events carry `analytics_schema: 1`. Basic SDK browser, OS, device, anonymous
session, and library metadata are allowlisted; arbitrary SDK properties and
automatic initial URL/person properties are removed before sending. Attribution
is recorded on the arrival page; UTMs are not silently propagated to later URLs.

Suggested dashboard views: pageviews by referring domain/UTM source and campaign;
pageviews by `$geoip_country_name`; play starts by piece/instrument; handoff-copy
clicks → skill/source clicks; downloads by format; support clicks by placement.
Copy and resource clicks indicate interest in an agent workflow, not proof that
an agent ran it. Treat copy clicks and completed clipboard writes separately.

## Build and configuration

The browser-visible project token and US ingestion host are committed in
`web/site/analytics-config.json`. This is a **public project token**, not a personal
API key or secret. Normal production builds preserve it automatically:

```sh
uv run python examples/build_site.py --strict
```

The production configuration restricts collection to `audioascode.com` and
`www.audioascode.com` using `allowedHosts`. A fork should use its own project token,
region, and host list, or remove the config. An absent config disables analytics.
Explicit CLI overrides require the key and host together:

```sh
uv run python examples/build_site.py --posthog-project-key phc_YOUR_PUBLIC_PROJECT_TOKEN --posthog-host https://us.i.posthog.com --strict
uv run python examples/build_site.py --no-analytics --strict
```

EU projects use `https://eu.i.posthog.com`. Never use a personal `phx_` API key.
Config validation happens before output cleanup. The builder embeds a JSON config
and deferred `assets/analytics.js` in generated pages, including the copied
instrument gallery. No Node package or Python analytics dependency is installed.
The wizard is unnecessary for this plain static site; integration uses the
official browser SDK and explicit settings instead of interactive scaffolding.

Ordinary localhost/private-address previews and `file:` pages never load PostHog.
`--analytics-allow-local` explicitly enables local capture for a dedicated testing
build; do not use it for ordinary preview. To verify without polluting product
events, the diagnostic harness adds `verificationOnly: true` to that isolated
local page's config; it sends exactly one `analytics_verification` event and
disables normal pageviews/clicks. This is not a production build option.

## Performance and verification

The small local event layer runs with `defer`. The SDK is requested asynchronously
after window load in an idle callback (2-second scheduling timeout), or a short
timer fallback. Hidden initial tabs wait until visible. A bounded queue preserves
early interactions once the SDK arrives. Very early bounces, blocked SDKs, and
ad blockers can result in missing events; navigation is never delayed for capture.
Analytics creates no audio element, audio preload, animation loop, or rendering
work. The SDK adds network/CPU work after load; it is not zero-cost.

Browser regression tests use the built site with a stubbed SDK and blocked live
ingestion. With Playwright and a Chromium installation available, run:

```sh
python -m pytest tests/test_site_analytics.py -q
```

Set `AAC_CHROMIUM` if needed. Browser tests skip without Playwright; the builder
contract test still runs. Checks cover DNT/GPC, durable opt-out, invalid config,
local/foreign-host blocking, sensitive text exclusion, safe events, queue opt-out,
single-event verification mode, and zero audio requests before Play.

After an installation check, find `analytics_verification` in PostHog's live
events, check GeoIP/project settings, and verify a visit from the deployed allowed
domain. An HTTP 200 from ingestion proves delivery was accepted; it does not prove
dashboard visibility, country enrichment or completeness of counts.

## Direct agent traffic requires the hosting layer

Agents that fetch `llms.txt`, `SKILL.md`, schema JSON, source ZIPs, or raw docs
usually do not execute browser JavaScript. This integration cannot count those
requests. JavaScript-executing automation may appear in browser events; bot/browser
classification is a heuristic, never proof of a human or agent.

Once the production host is known, add an opt-in server/edge request pipeline for
an allowlist of public resource paths. Emit a separate `public_resource_requested`
event with resource category, response status, cache outcome, method, coarse
country supplied by the host, and a coarse user-agent family/bot classification.
Do not forward URL queries, request bodies, authorization headers, full user-agent
strings, or raw IPs. Filter health checks, prefetches, local traffic, and internal
verification. Batch outside the response path; sample if necessary. Deduplicate
edge retries using a request ID rather than a permanent visitor identifier.

Choose aggregation or short-lived rotating anonymous IDs deliberately; request
counts are not unique agents. Forward trustworthy host country metadata instead
of geolocating the server's outgoing IP. Keep this server event stream separate
from browser pageviews to avoid double counting. No such pipeline is deployed or
silently added to the local preview server by this change.

## Official references

- [JavaScript SDK configuration](https://posthog.com/docs/libraries/js/config)
- [SDK usage and event filtering](https://posthog.com/docs/libraries/js/usage)
- [Data storage and IP discard](https://posthog.com/docs/privacy/data-storage)
- [Anonymous and identified events](https://posthog.com/docs/data/anonymous-vs-identified-events)
