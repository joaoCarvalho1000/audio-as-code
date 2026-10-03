/* Explicit, content-free site analytics. No media, forms, or clipboard interception. */
(() => {
  "use strict";
  let config;
  try { config = JSON.parse(document.getElementById("aac-analytics-config")?.textContent || "null"); } catch { return; }
  if (!config || !/^phc_[A-Za-z0-9]+$/.test(config.projectKey || "") ||
      !["https://us.i.posthog.com", "https://eu.i.posthog.com"].includes(config.apiHost)) return;
  const host = location.hostname.toLowerCase();
  const local = !host.includes(".") || /^(localhost|127\.|0\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host) ||
    host.endsWith(".localhost") || host.endsWith(".local") || host.includes(":");
  if (!/^https?:$/.test(location.protocol) || (local && config.allowLocal !== true)) return;
  if (Array.isArray(config.allowedHosts) && !config.allowedHosts.includes(host) && !(local && config.allowLocal === true)) return;
  const verification = local && config.allowLocal === true && config.verificationOnly === true;
  const optKey = "aac.analytics.optout";
  let optedOut = false;
  try { optedOut = localStorage.getItem(optKey) === "1"; } catch { /* storage may be unavailable */ }
  const blocked = () => optedOut || navigator.globalPrivacyControl === true ||
    [navigator.doNotTrack, window.doNotTrack].some(value => value === "1" || value === "yes");
  let client = null;
  let scheduled = false;
  let queue = [];
  const observers = [];
  window.aacAnalytics = Object.freeze({
    optOut() {
      optedOut = true;
      queue = [];
      observers.forEach(observer => observer.disconnect());
      try { localStorage.setItem(optKey, "1"); } catch { /* still opted out in memory */ }
      client?.opt_out_capturing();
    },
    // Reload starts a fresh initialization; browser privacy signals still take precedence.
    optIn() { try { localStorage.removeItem(optKey); } catch { /* storage unavailable */ } location.reload(); },
    status() { return blocked() ? "opted-out" : client ? "ready" : "pending"; },
  });
  document.addEventListener("click", event => {
    const control = event.target instanceof Element && event.target.closest("[data-analytics-optout]");
    if (!control) return;
    event.preventDefault();
    window.aacAnalytics.optOut();
    control.textContent = "Analytics off";
    control.setAttribute("aria-disabled", "true");
  });
  document.querySelectorAll("[data-analytics-optout]").forEach(control => {
    control.hidden = false;
    if (blocked()) { control.textContent = "Analytics off"; control.setAttribute("aria-disabled", "true"); }
  });
  if (blocked()) return;

  const token = value => typeof value === "string" && /^[a-zA-Z0-9_. -]{1,100}$/.test(value) ? value : undefined;
  const slug = value => typeof value === "string" && /^[a-zA-Z0-9_-]{1,100}$/.test(value) ? value : undefined;
  const pageURL = location.origin + location.pathname;
  let referrer = "";
  try { const url = new URL(document.referrer); if (/^https?:$/.test(url.protocol)) referrer = url.origin; } catch { /* direct */ }
  const acquisition = { $current_url: pageURL, $pathname: location.pathname, $host: host,
    $referrer: referrer, $referring_domain: referrer ? new URL(referrer).hostname : "$direct", analytics_schema: 1 };
  const params = new URLSearchParams(location.search);
  for (const key of ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"]) {
    const value = token(params.get(key));
    if (value) acquisition[key] = value;
  }
  const events = new Set(["$pageview", "demo_selected", "demo_play_requested", "demo_play_started",
    "download_clicked", "agent_handoff_copy_clicked", "agent_resource_clicked", "support_clicked",
    "analytics_verification"]);
  const propertyNames = new Set(["distinct_id", "$device_id", "$session_id", "$window_id", "$lib", "$lib_version",
    "$browser", "$browser_version", "$browser_type", "$os", "$os_version", "$device_type",
    "$screen_height", "$screen_width", "$viewport_height", "$viewport_width", "$is_identified",
    "$process_person_profile", "token", "piece_id", "instrument_id", "player", "asset_type", "resource",
    "placement", "verification", ...Object.keys(acquisition)]);
  function sanitize(event) {
    if (blocked() || !events.has(event.event)) return null;
    const properties = {};
    for (const [key, value] of Object.entries(event.properties || {})) {
      if (propertyNames.has(key) && ["string", "number", "boolean"].includes(typeof value)) properties[key] = value;
    }
    // Override automatic SDK URL/referrer properties after SDK enrichment.
    event.properties = { ...properties, ...acquisition, $process_person_profile: false };
    return event;
  }
  function capture(name, properties = {}, immediate = false) {
    if (blocked()) return;
    if (client) client.capture(name, properties, immediate ? { transport: "sendBeacon", send_instantly: true } : undefined);
    else if (queue.length < 50) queue.push([name, properties, immediate]);
  }
  const selectedPiece = () => slug(document.querySelector('[data-selector] [aria-checked="true"]')?.dataset.id);
  function playerProperties(button) {
    if (button.matches("[data-play]")) return { player: "main", piece_id: selectedPiece() };
    if (button.matches("[data-mini-play]")) {
      const path = button.closest("[data-mini]")?.dataset.src || "";
      return { player: "mini", piece_id: slug(path.split("/").slice(-2, -1)[0]) };
    }
    return { player: "instrument", instrument_id: slug(button.dataset.id || document.querySelector(".instrument-row.selected")?.dataset.id) };
  }
  if (!verification) {
    capture("$pageview");
    document.addEventListener("click", event => {
      if (blocked() || !(event.target instanceof Element)) return;
      const button = event.target.closest("button,a");
      if (!button) return;
      if (button.matches("[data-selector] [data-id]")) capture("demo_selected", { piece_id: slug(button.dataset.id) });
      if (button.matches(".instrument-select[data-id]")) capture("demo_selected", { instrument_id: slug(button.dataset.id) });
      const galleryPause = document.getElementById("audio")?.paused === false &&
        (button.matches("#player-play,#detail-play") ||
          (button.matches(".row-play") && button.closest(".instrument-row")?.classList.contains("is-playing")));
      if (button.matches("[data-play],[data-mini-play],.row-play,#player-play,#detail-play") && !button.classList.contains("is-playing") && !galleryPause) capture("demo_play_requested", playerProperties(button));
      if (button.matches("[data-handoff-copy]")) capture("agent_handoff_copy_clicked");
      if (button.matches("[data-kofi]")) capture("support_clicked", { placement: ["nav", "footer"].includes(button.dataset.kofi) ? button.dataset.kofi : "other" }, true);
      if (button instanceof HTMLAnchorElement) {
        let url;
        try { url = new URL(button.href); } catch { return; }
        if (url.origin !== location.origin) return;
        const path = url.pathname;
        const extension = path.split(".").pop().toLowerCase();
        if (["wav", "mp3", "mid", "midi", "json", "py", "zip"].includes(extension) && (button.hasAttribute("download") || button.closest("[data-downloads]") || extension === "zip")) capture("download_clicked", { asset_type: extension, piece_id: button.closest("[data-downloads]") ? selectedPiece() : undefined }, true);
        const resource = /\/SKILL\.md$/.test(path) ? "skill" : /\/llms\.txt$/.test(path) ? "llms" : /\.zip$/.test(path) ? "source_zip" : /\/source\.html$/.test(path) ? "source_page" : /\/docs\//.test(path) ? "guide" : null;
        if (resource) capture("agent_resource_clicked", { resource }, true);
      }
    }, true);
    // Only watch two player state classes, never text, form values, or page mutations.
    document.querySelectorAll("[data-play],[data-mini-play]").forEach(button => {
      let playing = button.classList.contains("is-playing");
      const observer = new MutationObserver(() => {
        const next = button.classList.contains("is-playing");
        if (next && !playing) capture("demo_play_started", playerProperties(button));
        playing = next;
      });
      observer.observe(button, { attributes: true, attributeFilter: ["class"] });
      observers.push(observer);
    });
    document.getElementById("audio")?.addEventListener("playing", () => capture("demo_play_started", { player: "instrument", instrument_id: slug(document.querySelector(".instrument-row.selected")?.dataset.id) }));
  }
  function load() {
    if (blocked() || window.posthog) return; // Do not take over another integration/project.
    const options = {
      api_host: config.apiHost, persistence: "sessionStorage", person_profiles: "never",
      autocapture: false, capture_pageview: false, capture_pageleave: false, capture_dead_clicks: false,
      capture_exceptions: false, capture_heatmaps: false, capture_performance: false, rageclick: false,
      disable_session_recording: true, disable_surveys: true, disable_external_dependency_loading: true,
      advanced_disable_flags: true, advanced_disable_decide: true, advanced_disable_toolbar_metrics: true,
      save_referrer: false, save_campaign_params: false, respect_dnt: true,
      mask_all_text: true, mask_all_element_attributes: true, opt_out_useragent_filter: true,
      before_send: sanitize,
      loaded(instance) {
        client = instance;
        if (blocked()) { client.opt_out_capturing(); queue = []; return; }
        if (verification) capture("analytics_verification", { verification: true }, true);
        else { const pending = queue; queue = []; pending.forEach(args => capture(...args)); }
      },
    };
    // Official array.js queue contract; initialization happens when the async bundle arrives.
    const stub = [];
    stub._i = [[config.projectKey, options]];
    window.posthog = stub;
    const script = document.createElement("script");
    script.async = true;
    script.referrerPolicy = "no-referrer";
    script.src = config.apiHost.replace(".i.posthog.com", "-assets.i.posthog.com") + "/static/array.js";
    script.onerror = () => { queue = []; };
    document.head.append(script);
  }
  function schedule() {
    if (scheduled || blocked() || document.hidden) return;
    scheduled = true;
    if (window.requestIdleCallback) requestIdleCallback(load, { timeout: 2000 });
    else setTimeout(load, 200);
  }
  if (document.readyState === "complete") schedule();
  else window.addEventListener("load", schedule, { once: true });
  document.addEventListener("visibilitychange", () => { if (document.readyState === "complete") schedule(); });
})();
