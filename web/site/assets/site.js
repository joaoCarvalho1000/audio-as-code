(() => {
  "use strict";
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const clock = (s) => {
    if (!isFinite(s)) return "–";
    s = Math.max(0, s);
    return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  };
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  /* The four Riso drums. Every plate is drawn in one of them and overlaps multiply. */
  const INK = { pink: "#ff48b0", blue: "#0078bf", yellow: "#ffe800", black: "#141413", paper: "#fbfaf6" };
  // Each piece is printed with its own plate assignment, so the four posters differ but share one system.
  const PRINTS = [
    { wave: "pink", notes: "yellow", title: "blue", tilt: -2.2 },
    { wave: "yellow", notes: "pink", title: "blue", tilt: 1.6 },
    { wave: "blue", notes: "yellow", title: "pink", tilt: -1.2 },
    { wave: "yellow", notes: "blue", title: "pink", tilt: 2.4 },
  ];

  /* ---------------------------------------------------------------- copy */
  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      const area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.append(area);
      area.select();
      let ok = false;
      try { ok = document.execCommand("copy"); } catch { ok = false; }
      area.remove();
      return ok;
    }
  }
  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-copy]");
    if (!button) return;
    const code = button.closest(".code")?.querySelector("pre code");
    if (!code) return;
    const ok = await copyText(code.textContent);
    button.textContent = ok ? "Copied" : "Select and copy";
    button.classList.toggle("ok", ok);
    if (!ok) {
      const range = document.createRange();
      range.selectNodeContents(code);
      getSelection().removeAllRanges();
      getSelection().addRange(range);
    }
    clearTimeout(button._t);
    button._t = setTimeout(() => { button.textContent = "Copy"; button.classList.remove("ok"); }, 1800);
  });

  /* ------------------------------------------------------- one audio out */
  // Every player on the page shares this element, so only one sound plays at a time.
  const audio = new Audio();
  audio.preload = "none";
  let owner = null;
  function claim(player, src) {
    if (owner && owner !== player) owner.release();
    owner = player;
    if (audio.dataset.src !== src) {
      audio.dataset.src = src;
      audio.src = src;
    }
  }

  /* ------------------------------------------------------------ drawing */
  // Canvas backing stores are sized here; callers invoke it on resize, never per frame.
  const surfaces = new WeakMap();
  function fit(canvas, maxRatio = 2) {
    const ratio = Math.min(window.devicePixelRatio || 1, maxRatio);
    const cached = surfaces.get(canvas);
    if (cached?.ratio === ratio) return cached;
    const w = Math.max(1, Math.round(canvas.clientWidth * ratio));
    const h = Math.max(1, Math.round(canvas.clientHeight * ratio));
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
    const result = { ctx: canvas.getContext("2d"), w, h, ratio };
    surfaces.set(canvas, result);
    return result;
  }
  // Halftone plates: the unprinted future of a piece is a dot screen in the same ink.
  const screensByCtx = new WeakMap();
  function screen(ctx, ink, ratio, kind = "dots") {
    if (!screensByCtx.has(ctx)) screensByCtx.set(ctx, new Map());
    const screens = screensByCtx.get(ctx);
    const key = `${ink}|${ratio}|${kind}`;
    if (!screens.has(key)) {
      const s = Math.round(6 * ratio);
      const tile = document.createElement("canvas");
      tile.width = tile.height = s;
      const t = tile.getContext("2d");
      t.fillStyle = ink;
      if (kind === "dots") {
        t.beginPath();
        t.arc(s / 2, s / 2, s * 0.3, 0, Math.PI * 2);
        t.fill();
      } else {
        t.fillRect(0, 0, s, s * 0.42);
      }
      screens.set(key, ctx.createPattern(tile, "repeat"));
    }
    return screens.get(key);
  }
  function peakOf(envelope) {
    let peak = 0;
    for (const [a, b] of envelope) peak = Math.max(peak, -a, b);
    return Math.max(peak, 0.05);
  }
  // A filled silhouette of the real min/max envelope, scaled to the piece's own peak.
  function silhouette(ctx, envelope, x0, x1, cy, amp, peak) {
    const n = envelope.length;
    const step = (x1 - x0) / n;
    ctx.beginPath();
    ctx.moveTo(x0, cy);
    for (let i = 0; i < n; i++) ctx.lineTo(x0 + (i + 0.5) * step, cy - (envelope[i][1] / peak) * amp);
    ctx.lineTo(x1, cy);
    for (let i = n - 1; i >= 0; i--) ctx.lineTo(x0 + (i + 0.5) * step, cy - (envelope[i][0] / peak) * amp);
    ctx.closePath();
  }
  function registration(ctx, x, y, r, ratio) {
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.moveTo(x - r * 1.6, y); ctx.lineTo(x + r * 1.6, y);
    ctx.moveTo(x, y - r * 1.6); ctx.lineTo(x, y + r * 1.6);
    ctx.lineWidth = 1.5 * ratio;
    ctx.stroke();
  }
  const miniLayers = new WeakMap();
  function miniTrace(canvas, envelope, progress) {
    const { ctx, w, h } = fit(canvas);
    ctx.clearRect(0, 0, w, h);
    if (!envelope.length) return;
    let cache = miniLayers.get(canvas);
    if (!cache || cache.w !== w || cache.h !== h || cache.envelope !== envelope) {
      const make = (played) => {
        const layer = document.createElement("canvas");
        layer.width = w; layer.height = h;
        const c = layer.getContext("2d");
        c.fillStyle = INK.pink;
        silhouette(c, envelope, 0, w, h / 2, h * 0.46, peakOf(envelope));
        c.fill();
        if (played) { c.globalCompositeOperation = "multiply"; c.fillStyle = INK.blue; c.fill(); }
        return layer;
      };
      cache = { w, h, envelope, base: make(false), played: make(true) };
      miniLayers.set(canvas, cache);
    }
    ctx.drawImage(cache.base, 0, 0);
    const x = Math.min(1, Math.max(0, progress)) * w;
    if (x > 0) ctx.drawImage(cache.played, 0, 0, x, h, 0, 0, x, h);
  }

  /* ------------------------------------------------------------- console */
  // Performance contract: layout is read only on resize, selection and font load; the
  // static plates are rendered once into cached canvases; playback composites them at
  // most 30 times a second, and nothing draws while the poster or roll is off screen.
  const FRAME_MS = 1000 / 24;
  const consoleEl = $("[data-console]");
  if (consoleEl) {
    let pieces = [];
    try { pieces = JSON.parse($("#pieces-data").textContent); } catch { pieces = []; }
    const ui = {
      plates: $("[data-trace]"), scope: $("[data-scope]"), msg: $("[data-scope-msg]"), scrub: $("[data-scrub]"),
      play: $("[data-play]"), label: $("[data-play-label]"), selector: $("[data-selector]"), headliner: $("[data-headliner]"),
      time: $("[data-time]"), length: $("[data-length]"), bpm: $("[data-bpm]"), tracks: $("[data-tracks]"), notes: $("[data-notes]"), seed: $("[data-seed]"),
      title: $("[data-piece-title]"), desc: $("[data-piece-desc]"), voices: $("[data-piece-voices]"),
      downloads: $("[data-downloads]"), frames: $("[data-frames]"), roll: $("[data-roll]"), rollMsg: $("[data-roll-msg]"),
      rollKey: $("[data-roll-key]"), code: $("[data-piece-code]"), codeSlot: $("[data-code-slot]"),
      ring: $("[data-ring-text]"), meta: $("[data-piece-meta]"), credit: $("[data-piece-credit]"),
      needs: $("[data-piece-needs]"), needsList: $("[data-needs-list]"),
    };
    // Public-domain excerpts and original pieces are labelled as what they are, everywhere they appear.
    const RING = {
      classic: "the classic · from the public-domain score · synthesized ·",
      reimagined: "reimagined by an AI agent · synthesized from code ·",
      excerpt: "public-domain excerpt · arranged & synthesized in code ·",
      original: "full piece · rendered offline · synthesized from code ·",
    };
    const VARIANT = { classic: "The classic", reimagined: "Reimagined" };
    const GROUPS = {
      classic: (n, paired) => (paired ? `Classics · ${n} works, two ways` : `Classics · ${n} public-domain pieces`),
      original: (n) => `Originals · ${n} composed in code`,
    };
    const isReimagined = (p) => p.variant === "reimagined";
    function ringText(p) {
      if (!isClassic(p)) return RING.original;
      if (isReimagined(p)) return RING.reimagined;
      return p.excerpt === true ? RING.excerpt : RING.classic;
    }
    function metaText(p) {
      if (!isClassic(p)) return "Original piece · composed in Python for Audio as Code";
      const work = p.work_title || p.title;
      // The source composer and the new arrangement are credited separately.
      if (isReimagined(p)) {
        return ["Reimagined by an AI agent", p.arrangement && `for ${p.arrangement}`, p.composer && (/^traditional$/i.test(p.composer) ? `from the traditional ${work}` : `from ${p.composer}'s ${work}`)].filter(Boolean).join(" · ");
      }
      if (p.excerpt === true) return [p.composer, p.arrangement ? `public-domain excerpt for ${p.arrangement}` : "public-domain excerpt"].filter(Boolean).join(" · ");
      return [p.composer, "The classic", p.arrangement && `complete arrangement for ${p.arrangement}`].filter(Boolean).join(" · ");
    }
    const isClassic = (p) => p.collection === "classic";
    const surname = (name) => String(name || "").trim().split(/\s+/).pop() || "";
    function creditHtml(p) {
      if (!isClassic(p)) return "Composed for this site in Python and rendered by Audio as Code's synthesized voices.";
      const c = p.credit || {};
      const source = c.url ? `<a href="${esc(c.url)}" rel="external">${esc(c.edition || "source edition")}</a>` : esc(c.edition || "the cited edition");
      const by = c.edition_credit ? `, edition by ${esc(c.edition_credit)}` : "";
      const license = c.license ? `, marked ${esc(c.license)} on its source page` : "";
      const scope = p.performance_scope ? ` Score scope: ${esc(p.performance_scope)}.` : "";
      const heard = isReimagined(p)
        ? "This version is a new arrangement written by an AI agent with Audio as Code, then synthesized like every sound here; it is not a recording."
        : "You hear the score synthesized by Audio as Code, not an archival recording.";
      return `Score source: ${source}${by}${license}.${scope} ${heard} <a href="#credits">All score credits</a>`;
    }
    // Keep the chosen bill line in view inside the bounded lineup. Layout is read only on selection.
    function reveal(button) {
      const box = ui.selector;
      if (box.scrollHeight <= box.clientHeight + 1) return;
      // Group labels pin to the top and bottom edges; 8px more clears the chosen slab's tilt.
      const pin = ($(".lineup-group", box)?.offsetHeight || 0) + 8;
      const line = button.closest(".work") || button;
      const top = line.offsetTop - pin;
      const bottom = line.offsetTop + line.offsetHeight + pin;
      if (top < box.scrollTop) box.scrollTop = top;
      else if (bottom > box.scrollTop + box.clientHeight) box.scrollTop = bottom - box.clientHeight;
    }
    const knockouts = $$("[data-knockout]", consoleEl);
    let current = null;
    let print = PRINTS[0];
    let peak = 1;
    let heard = false; // once a piece has sounded, unplayed notes fall back to the dot screen
    const rolls = new Map();
    let rollController = null;
    let pendingSeek = null;
    let geom = null; // cached layout of the poster, in canvas pixels
    let layers = null; // { solid, ghost, notes } pre-rendered plates for the current piece and size
    let tabs = [];
    let ink = null; // the breathing headliner layer
    const seen = { poster: true, roll: false };
    const last = { time: "", scrub: "", valuetext: "", tabs: "", breath: 1 };
    let raf = 0;
    let timer = 0;
    const player = { release() { cancelMedia(); setPlaying(false); } };
    const ours = () => owner === player && audio.dataset.src === current?.audio;
    const length = () => (ours() && isFinite(audio.duration) ? audio.duration : current?.duration_seconds || 0);
    const now = () => (ours() ? audio.currentTime : (pendingSeek ?? 0));
    const beatAt = (t) => (current ? (t * current.bpm) / 60 : 0);
    const playing = () => owner === player && !audio.paused;
    const ratioFor = () => Math.min(window.devicePixelRatio || 1, 1.5);

    /* Track inks for the program roll: three drums times three screens keeps nine voices apart without hue alone. */
    const TRACK_INKS = [["blue", "solid"], ["pink", "solid"], ["black", "solid"], ["blue", "dots"], ["pink", "dots"], ["black", "dots"], ["blue", "lines"], ["pink", "lines"], ["black", "lines"], ["blue", "solid"]];
    const swatchCss = ([inkName, kind]) => {
      const c = INK[inkName];
      if (kind === "dots") return `background:radial-gradient(circle, ${c} 38%, transparent 42%) 0 0 / 5px 5px`;
      if (kind === "lines") return `background:repeating-linear-gradient(0deg, ${c} 0 2px, transparent 2px 5px)`;
      return `background:${c}`;
    };

    // Read every rectangle the plates need, once.
    function measure() {
      const box = consoleEl.getBoundingClientRect();
      const scopeBox = ui.scope.getBoundingClientRect();
      const tabsBox = ui.frames.hidden ? null : ui.frames.getBoundingClientRect();
      const ratio = ratioFor();
      geom = {
        ratio,
        w: Math.max(1, Math.round(box.width * ratio)),
        h: Math.max(1, Math.round(box.height * ratio)),
        top: (scopeBox.top - box.top) * ratio,
        bandH: scopeBox.height * ratio,
        floor: (tabsBox ? tabsBox.top - box.top : box.height) * ratio,
        knock: knockouts.map((el) => el.getBoundingClientRect()).filter((r) => r.width)
          .map((r) => [(r.left - box.left - 10) * ratio, (r.top - box.top - 8) * ratio, (r.width + 20) * ratio, (r.height + 16) * ratio]),
      };
      const canvas = ui.plates;
      if (canvas.width !== geom.w || canvas.height !== geom.h) { canvas.width = geom.w; canvas.height = geom.h; }
      tabs = $$("button", ui.frames);
    }

    // Render the static plates (notes, knockouts, wave) into two cached canvases: as printed, and as a dot screen.
    function buildPlates() {
      if (!current || !geom) { layers = null; return; }
      const { w, h, ratio, top, bandH, floor, knock } = geom;
      const roll = rolls.get(current.id);
      const notes = [];
      const make = (ghosted) => {
        const c = document.createElement("canvas");
        c.width = w; c.height = h;
        const ctx = c.getContext("2d");
        ctx.globalCompositeOperation = "multiply";
        if (roll && roll.notes.length) {
          const span = Math.max(12, roll.hi - roll.lo + 1);
          const y0 = 10 * ratio;
          const y1 = floor - 12 * ratio;
          const rowH = (y1 - y0) / span;
          const px = w / current.beats;
          const barH = Math.max(3 * ratio, rowH * 0.78);
          ctx.fillStyle = ghosted ? screen(ctx, INK[print.notes], ratio) : INK[print.notes];
          for (const [, pitch, s, d] of roll.notes) {
            const x = s * px;
            const y = y1 - (pitch - roll.lo + 1) * rowH;
            const bw = Math.max(2 * ratio, d * px - ratio);
            ctx.fillRect(x, y, bw, barH);
            if (!ghosted) notes.push([x, y, bw, barH, s, s + d]);
          }
          // Knock the note plate out behind running text, as a printer would.
          ctx.globalCompositeOperation = "destination-out";
          ctx.fillStyle = "#000";
          for (const [x, y, rw, rh] of knock) ctx.fillRect(x, y, rw, rh);
          ctx.globalCompositeOperation = "multiply";
        }
        ctx.fillStyle = INK[print.wave];
        silhouette(ctx, current.envelope, 0, w, top + bandH / 2, bandH * 0.5, peak);
        ctx.fill();
        return c;
      };
      layers = { solid: make(false), ghost: make(true), notes };
    }

    function drawPlates(t, beat, p) {
      const ctx = ui.plates.getContext("2d");
      const { w, h, ratio, top, bandH, floor } = geom;
      ctx.globalCompositeOperation = "source-over";
      ctx.clearRect(0, 0, w, h);
      if (!layers) return;
      if (!heard) { ctx.drawImage(layers.solid, 0, 0); return; }
      const x = p * w;
      ctx.drawImage(layers.ghost, 0, 0);
      if (x > 0) {
        // Ink prints as the playhead passes.
        ctx.drawImage(layers.solid, 0, 0, x, h, 0, 0, x, h);
        ctx.strokeStyle = INK.black;
        ctx.lineWidth = 1.5 * ratio;
        for (const [nx, ny, nw, nh, s, e] of layers.notes) {
          if (beat >= s && beat < e) ctx.strokeRect(nx, ny, nw, nh);
        }
        ctx.fillStyle = INK.black;
        ctx.fillRect(x - ratio, 0, 2 * ratio, floor);
        registration(ctx, x, top + 10 * ratio, 6 * ratio, ratio);
        registration(ctx, x, top + bandH - 10 * ratio, 6 * ratio, ratio);
      }
    }

    function drawRoll(beat) {
      const canvas = ui.roll;
      const { ctx, w, h, ratio } = fit(canvas, 1.5);
      ctx.globalCompositeOperation = "source-over";
      ctx.fillStyle = INK.yellow;
      ctx.fillRect(0, 0, w, h);
      const roll = current && rolls.get(current.id);
      if (!roll || !roll.notes.length) return;
      const windowBeats = Math.min(current.beats, w / ratio < 560 ? 16 : 32);
      const start = Math.max(0, Math.min(current.beats - windowBeats, beat - windowBeats * 0.2));
      const end = start + windowBeats;
      const rowH = h / (roll.hi - roll.lo + 3);
      const px = w / windowBeats;
      ctx.globalCompositeOperation = "multiply";
      ctx.fillStyle = "rgba(20,20,19,.22)";
      for (let b = Math.ceil(start / 4) * 4; b < end; b += 4) ctx.fillRect(Math.round((b - start) * px), 0, ratio, h);
      // Notes are sorted by start, so the window is one contiguous run after a binary search.
      const sorted = roll.byStart;
      let i = 0, j = sorted.length;
      const from = start - roll.longest;
      while (i < j) { const m = (i + j) >> 1; if (sorted[m][2] < from) i = m + 1; else j = m; }
      for (; i < sorted.length; i++) {
        const [track, pitch, s, d] = sorted[i];
        if (s > end) break;
        if (s + d < start) continue;
        const [inkName, kind] = TRACK_INKS[track % TRACK_INKS.length];
        const x = (s - start) * px;
        const y = h - (pitch - roll.lo + 2) * rowH;
        const bw = Math.max(2 * ratio, d * px - ratio);
        const bh = Math.max(3 * ratio, rowH - ratio);
        const sounded = !heard || s <= beat;
        if (kind === "solid") ctx.fillStyle = sounded ? INK[inkName] : screen(ctx, INK[inkName], ratio);
        else ctx.fillStyle = screen(ctx, INK[inkName], ratio, kind);
        ctx.globalAlpha = sounded || kind === "solid" ? 1 : 0.55;
        ctx.fillRect(x, y, bw, bh);
        ctx.globalAlpha = 1;
        if (kind !== "solid") {
          ctx.strokeStyle = INK[inkName];
          ctx.lineWidth = ratio;
          ctx.strokeRect(x + ratio / 2, y + ratio / 2, bw - ratio, bh - ratio);
        }
      }
      if (heard && beat > 0) {
        ctx.globalCompositeOperation = "source-over";
        ctx.fillStyle = INK.black;
        ctx.fillRect((beat - start) * px - ratio, 0, 2 * ratio, h);
      }
    }

    // One frame: draw only what is on screen and write to the DOM only when a value changed.
    function frame() {
      if (!current || document.hidden) return;
      const t = now();
      const len = length();
      const p = len ? Math.min(1, t / len) : 0;
      const beat = beatAt(t);
      if (seen.poster && geom) {
        drawPlates(t, beat, p);
        const time = clock(t);
        if (time !== last.time) {
          last.time = time;
          ui.time.textContent = time;
          const vt = `${time} of ${clock(len)}`;
          if (vt !== last.valuetext) { last.valuetext = vt; ui.scrub.setAttribute("aria-valuetext", vt); }
        }
        const sv = String(Math.round(p * 1000));
        if (sv !== last.scrub && document.activeElement !== ui.scrub) { last.scrub = sv; ui.scrub.value = sv; }
        let here = -1, past = 0;
        current.sections.forEach((s, i) => {
          if (beat >= s.start_beat && beat < s.end_beat && (t > 0 || i === 0)) here = i;
          if (heard && beat >= s.end_beat) past = i + 1;
        });
        const key = `${here}|${past}`;
        if (key !== last.tabs) {
          last.tabs = key;
          tabs.forEach((b, i) => {
            b.classList.toggle("is-current", i === here);
            b.classList.toggle("is-past", i < past);
            if (i === here) b.setAttribute("aria-current", "true"); else b.removeAttribute("aria-current");
          });
        }
        if (playing()) breathe(p);
      }
      if (seen.roll) drawRoll(beat);
    }
    const render = () => frame();

    // The headliner breathes: a compositor-only horizontal scale that follows the envelope at the playhead.
    function breathe(p) {
      if (!current || reduced.matches || !ink) return;
      const env = current.envelope;
      const i = Math.min(env.length - 1, Math.max(0, Math.floor(p * env.length)));
      const level = Math.min(1, (env[i][1] - env[i][0]) / (2 * peak));
      const target = 0.86 + level * 0.28;
      const next = last.breath + (target - last.breath) * 0.35;
      if (Math.abs(next - last.breath) > 0.003) {
        last.breath = next;
        ink.style.transform = `scaleX(${next.toFixed(3)})`;
      }
    }
    function rest() {
      last.breath = 1;
      if (ink) ink.style.transform = "";
    }

    function loop() {
      raf = 0;
      if (!playing() || document.hidden || !(seen.poster || seen.roll)) return;
      frame();
      schedule();
    }
    function stopFrames() {
      clearTimeout(timer);
      cancelAnimationFrame(raf);
      timer = raf = 0;
    }
    function schedule() {
      if (!timer && !raf && playing() && !document.hidden && (seen.poster || seen.roll)) {
        timer = setTimeout(() => { timer = 0; raf = requestAnimationFrame(loop); }, reduced.matches ? 250 : FRAME_MS);
      }
    }
    function visibilityChanged() {
      stopFrames();
      consoleEl.classList.toggle("is-away", document.hidden || !seen.poster);
      if (!document.hidden) { render(); schedule(); }
    }
    document.addEventListener("visibilitychange", visibilityChanged);
    reduced.addEventListener("change", () => {
      rest();
      ui.headliner.classList.toggle("is-live", playing() && !reduced.matches);
      visibilityChanged();
    });
    if ("IntersectionObserver" in window) {
      const io = new IntersectionObserver((entries) => {
        for (const entry of entries) {
          if (entry.target === consoleEl) {
            seen.poster = entry.isIntersecting;
          } else seen.roll = entry.isIntersecting;
        }
        visibilityChanged();
      });
      io.observe(consoleEl);
      io.observe(ui.roll);
    } else seen.roll = true;

    function setPlaying(on) {
      stopFrames();
      ui.play.classList.toggle("is-playing", on);
      ui.label.textContent = on ? "Pause" : "Play";
      ui.play.setAttribute("aria-label", `${on ? "Pause" : "Play"} ${current ? current.title : ""}`);
      ui.headliner.classList.toggle("is-live", on && !reduced.matches);
      if (on) heard = true;
      else rest();
      render();
      if (on) schedule();
    }

    // Servers without HTTP Range support (python -m http.server) make streamed audio
    // unseekable; then the file is fetched once into memory, where seeking always works.
    // The conversion includes metadata readiness, so overlapping scrubs await the
    // same complete operation. The newest requested position wins.
    const canSeek = () => audio.seekable.length > 0 && audio.seekable.end(0) > 1;
    let blob = null;
    let job = null;
    let mediaController = new AbortController();
    let wantPlayback = false;
    function cancelMedia() {
      wantPlayback = false;
      pendingSeek = null;
      mediaController.abort();
      mediaController = new AbortController();
      job = null;
      if (owner === player) {
        audio.pause();
        audio.removeAttribute("src");
        delete audio.dataset.src;
        audio.load(); // Cancel the native stream as well as the fallback fetch.
      }
      if (blob) { URL.revokeObjectURL(blob); blob = null; }
    }
    function metadata(signal) {
      if (signal.aborted) return Promise.reject(new DOMException("Cancelled", "AbortError"));
      if (audio.readyState >= 1) return Promise.resolve();
      return new Promise((resolve, reject) => {
        const cleanup = () => {
          audio.removeEventListener("loadedmetadata", ready);
          audio.removeEventListener("error", failed);
          signal.removeEventListener("abort", aborted);
        };
        const ready = () => { cleanup(); resolve(); };
        const failed = () => { cleanup(); reject(new Error("Audio metadata unavailable")); };
        const aborted = () => { cleanup(); reject(new DOMException("Cancelled", "AbortError")); };
        audio.addEventListener("loadedmetadata", ready);
        audio.addEventListener("error", failed);
        signal.addEventListener("abort", aborted, { once: true });
      });
    }
    function makeSeekable() {
      if (job) return job;
      const piece = current;
      const signal = mediaController.signal;
      const valid = () => !signal.aborted && current === piece && owner === player;
      ui.msg.textContent = "Loading the full recording to enable seeking…";
      const conversion = (async () => {
        try {
          const response = await fetch(piece.audio, { signal });
          if (!response.ok) throw new Error(String(response.status));
          const data = await response.blob();
          if (!valid()) return false;
          blob = URL.createObjectURL(data);
          audio.src = blob;
          await metadata(signal);
          if (!valid()) return false;
          ui.msg.textContent = "";
          if (wantPlayback) audio.play().catch(() => {});
          return true;
        } catch (error) {
          if (valid() && error.name !== "AbortError") {
            if (blob) {
              const failedURL = blob;
              blob = null;
              audio.src = piece.audio;
              URL.revokeObjectURL(failedURL);
            }
            ui.msg.textContent = "Seeking isn't available from this server. Use the WAV download below.";
          }
          return false;
        }
      })();
      job = conversion;
      conversion.finally(() => { if (job === conversion) job = null; });
      return conversion;
    }
    async function applySeek() {
      const piece = current;
      const signal = mediaController.signal;
      try {
        await metadata(signal);
        if (signal.aborted || current !== piece || !ours() || pendingSeek == null) return;
        if (pendingSeek > 0 && !canSeek() && !(await makeSeekable())) return;
        if (signal.aborted || current !== piece || !ours() || pendingSeek == null) return;
        const target = pendingSeek;
        pendingSeek = null;
        audio.currentTime = target;
        render();
      } catch (error) {
        if (!signal.aborted && current === piece && error.name !== "AbortError") ui.msg.textContent = "The requested section couldn't be loaded. Try Play again.";
      }
    }
    async function seek(seconds) {
      if (!current) return;
      heard = true;
      pendingSeek = Math.max(0, Math.min(seconds, length() - 0.05));
      if (ours()) applySeek();
      render();
    }
    async function play() {
      if (!current) return;
      wantPlayback = true;
      const piece = current;
      const signal = mediaController.signal;
      claim(player, current.audio);
      if (pendingSeek != null) applySeek();
      ui.msg.textContent = audio.readyState < 3 ? "Loading audio…" : "";
      try { await audio.play(); } catch (error) {
        if (signal.aborted || current !== piece || owner !== player || error.name === "AbortError") return;
        wantPlayback = false;
        setPlaying(false);
        ui.msg.textContent = audio.error || error.name === "NotSupportedError"
          ? "This recording couldn't be loaded. Use the WAV download below instead."
          : "Playback was blocked. Press Play again.";
      }
    }
    audio.addEventListener("playing", () => { if (owner === player) { ui.msg.textContent = ""; setPlaying(true); } });
    audio.addEventListener("waiting", () => { if (owner === player) ui.msg.textContent = "Loading audio…"; });
    audio.addEventListener("pause", () => { if (owner === player) setPlaying(false); });
    audio.addEventListener("seeked", () => { if (owner === player) render(); });
    audio.addEventListener("ended", () => { if (owner === player) { wantPlayback = false; setPlaying(false); audio.currentTime = 0; render(); } });
    audio.addEventListener("loadedmetadata", () => { if (owner === player) { ui.length.textContent = clock(audio.duration); render(); } });
    audio.addEventListener("error", () => {
      if (owner !== player || !audio.getAttribute("src")) return;
      wantPlayback = false;
      setPlaying(false);
      ui.msg.textContent = "This recording couldn't be loaded. Use the WAV download below instead.";
    });

    ui.play.addEventListener("click", () => {
      if (playing() || wantPlayback) { wantPlayback = false; audio.pause(); setPlaying(false); }
      else play();
    });
    ui.scrub.addEventListener("input", () => seek((ui.scrub.value / 1000) * length()));

    async function loadRoll(piece) {
      if (!rolls.has(piece.id)) {
        const controller = new AbortController();
        rollController = controller;
        ui.rollMsg.textContent = "Reading the score…";
        try {
          const response = await fetch(piece.roll, { signal: controller.signal });
          if (!response.ok) throw new Error(response.status);
          const roll = await response.json();
          let lo = Infinity, hi = -Infinity, longest = 0;
          for (const n of roll.notes) { lo = Math.min(lo, n[1]); hi = Math.max(hi, n[1]); longest = Math.max(longest, n[3]); }
          Object.assign(roll, { lo, hi, longest, byStart: roll.notes.slice().sort((a, b) => a[2] - b[2]) });
          rolls.set(piece.id, roll);
        } catch (error) {
          if (current === piece && error.name !== "AbortError") ui.rollMsg.textContent = "The note data couldn't be loaded. The JSON score download has the same notes.";
        } finally {
          if (rollController === controller) rollController = null;
        }
      }
      if (current === piece) {
        const roll = rolls.get(piece.id);
        if (roll) {
          ui.rollMsg.textContent = "";
          ui.rollKey.innerHTML = roll.tracks.map((t, i) => `<span class="swatch-item"><i class="swatch" style="${swatchCss(TRACK_INKS[i % TRACK_INKS.length])}"></i>${esc(t.name)}</span>`).join("");
        }
        buildPlates();
        render();
      }
    }

    // Break the title into poster lines: short words ride together, long words get a line each.
    function posterLines(title) {
      const lines = [];
      for (const word of title.split(/\s+/)) {
        const prev = lines[lines.length - 1];
        if (prev && (word.length <= 3 || prev.length <= 3) && (prev + " " + word).length <= 8) lines[lines.length - 1] = `${prev} ${word}`;
        else lines.push(word);
      }
      return lines;
    }
    function fitHeadliner() {
      const el = ui.headliner;
      const spans = $$(".hl-line", el);
      if (!spans.length) return;
      const wide = matchMedia("(min-width: 960px)").matches;
      const area = el.parentElement.getBoundingClientRect();
      const bill = $(".bill", consoleEl).getBoundingClientRect();
      const room = wide ? bill.left - area.left - 24 : area.width - 2 * parseFloat(getComputedStyle(el.parentElement).paddingLeft);
      el.style.setProperty("--hl", "100px");
      const widest = Math.max(...spans.map((s) => s.scrollWidth));
      const byWidth = (100 * room * (wide ? 0.86 : 0.94)) / Math.max(1, widest);
      const byHeight = (wide ? innerHeight * 0.52 : innerHeight * 0.3) / (spans.length * 0.82);
      const size = Math.max(48, Math.min(byWidth, byHeight, wide ? 250 : 120));
      el.style.setProperty("--hl", `${size.toFixed(1)}px`);
    }
    function relayout() {
      surfaces.delete(ui.roll);
      fitHeadliner();
      measure();
      buildPlates();
      render();
    }
    function paste(piece, index) {
      print = PRINTS[index % PRINTS.length];
      consoleEl.style.setProperty("--ink-title", INK[print.title]);
      consoleEl.style.setProperty("--tilt", `${print.tilt}deg`);
      ui.headliner.innerHTML = `<div class="hl-ink">${posterLines(piece.work_title || piece.title).map((l) => `<span class="hl-line">${esc(l)}</span>`).join("")}</div>`;
      ink = $(".hl-ink", ui.headliner);
      relayout();
      if (!reduced.matches) {
        // Paste: the title slaps down and the plates come back into register, both on the compositor.
        for (const el of [ui.headliner, ui.plates]) {
          el.classList.remove("is-slapping");
          void el.offsetWidth;
          el.classList.add("is-slapping");
        }
      }
    }

    function select(piece, focus = false) {
      if (current === piece) return;
      cancelMedia();
      rollController?.abort();
      current = piece;
      const index = pieces.indexOf(piece);
      peak = peakOf(piece.envelope);
      heard = false;
      pendingSeek = null;
      Object.assign(last, { time: "", scrub: "", valuetext: "", tabs: "" });
      $$("button", ui.selector).forEach((b) => {
        const on = b.dataset.id === piece.id;
        b.setAttribute("aria-checked", String(on));
        b.tabIndex = on ? 0 : -1;
        if (on) reveal(b);
        if (on && focus) b.focus();
      });
      ui.play.disabled = false;
      ui.scrub.disabled = false;
      ui.msg.textContent = "";
      ui.length.textContent = clock(piece.duration_seconds);
      ui.bpm.textContent = String(Math.round(piece.bpm));
      ui.tracks.textContent = String(piece.track_count);
      ui.notes.textContent = piece.note_count.toLocaleString("en");
      ui.seed.textContent = piece.seed == null ? "–" : String(piece.seed);
      ui.title.textContent = piece.title;
      ui.desc.textContent = piece.description;
      if (ui.ring) ui.ring.textContent = ringText(piece);
      if (ui.meta) ui.meta.textContent = metaText(piece);
      if (ui.credit) ui.credit.innerHTML = creditHtml(piece);
      if (ui.needs) {
        const needs = piece.source ? piece.requires || [] : [];
        ui.needs.hidden = !needs.length;
        ui.needsList.textContent = needs.join(", ");
      }
      ui.voices.innerHTML = piece.instruments.map((i) => `<li>${esc(i.replace(/_/g, " "))}</li>`).join("");
      const mb = (b) => `${(b / 1048576).toFixed(1)} MB`;
      const arrow = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m0 0-5-5m5 5 5-5M4 20h16" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="square"/></svg>';
      const links = [
        [piece.wav, "WAV, exact render", mb(piece.wav_bytes)],
        piece.audio !== piece.wav ? [piece.audio, "MP3 preview", ""] : null,
        [piece.midi, "MIDI", ""],
        [piece.score, "JSON score", ""],
        piece.source ? [piece.source, "Python source", ""] : null,
        piece.source_bundle ? [piece.source_bundle, "Runnable source bundle", piece.source_bundle_bytes ? mb(piece.source_bundle_bytes) : ""] : null,
      ].filter(Boolean);
      ui.downloads.innerHTML = links.map(([href, label, size]) => `<li><a href="${esc(href)}" download><span>${esc(label)}${size ? `<small>${esc(size)}</small>` : ""}</span>${arrow}</a></li>`).join("");
      ui.frames.innerHTML = piece.sections.map((s, i) => {
        const at = (s.start_beat * 60) / piece.bpm;
        return `<button type="button" data-at="${at}" style="--hang:${(i % 2 ? -1 : 1) * (1 + (i % 3) * 0.8)}deg" aria-label="Jump to ${esc(s.name)} at ${clock(at)}"><span>${clock(at)}</span><b>${esc(s.name)}</b></button>`;
      }).join("");
      $$("button", ui.frames).forEach((b) => b.addEventListener("click", () => {
        seek(Number(b.dataset.at));
        if (!playing()) play();
      }));
      ui.frames.hidden = !piece.sections.length;
      if (piece.code_excerpt) {
        ui.code.hidden = false;
        ui.codeSlot.innerHTML = `<figure class="code" data-lang="python"><figcaption><span>${esc(piece.source_label || "full_compositions.py")}</span><button type="button" class="copy" data-copy>Copy</button></figcaption><pre><code>${esc(piece.code_excerpt)}</code></pre></figure>`;
      } else ui.code.hidden = true;
      ui.rollKey.textContent = "";
      setPlaying(false);
      paste(piece, index);
      loadRoll(piece);
      if (focus || location.hash.startsWith("#piece-")) history.replaceState(null, "", `#piece-${piece.id}`);
    }

    if (!pieces.length) {
      ui.msg.textContent = "No pieces are included in this build yet.";
      ui.title.textContent = "The program";
      ui.desc.textContent = "This build doesn't include any rendered pieces yet. Until it does, the instrument library has short rendered clips you can play.";
      ui.frames.hidden = true;
    } else {
      // A paired work (The classic / Reimagined) is one bill line with adjacent variant controls;
      // anything unpaired (the optional originals) follows as a single line.
      const byId = new Map(pieces.map((p) => [p.id, p]));
      const works = [];
      for (const p of pieces) {
        const key = p.pair_id || p.id;
        let work = works.find((w) => w.key === key);
        if (!work) works.push((work = { key, items: [] }));
        work.items.push(p);
      }
      const paired = works.some((w) => w.items.length > 1);
      const grouped = pieces.some(isClassic) && !pieces.every(isClassic);
      let group = "";
      ui.selector.innerHTML = works.map((w) => {
        const first = w.items[0];
        const kind = isClassic(first) ? "classic" : "original";
        const count = works.filter((x) => isClassic(x.items[0]) === (kind === "classic")).length;
        const head = grouped && kind !== group ? `<p class="lineup-group lineup-${kind}" aria-hidden="true">${esc(GROUPS[kind](count, paired))}</p>` : "";
        group = kind;
        if (paired && first.variant) {
          const name = first.work_title || first.title;
          const picks = w.items.map((p) => {
            const label = VARIANT[p.variant] || p.title;
            return `<button type="button" role="radio" aria-checked="false" tabindex="-1" data-id="${esc(p.id)}" aria-label="${esc(`${name}: ${label === p.title ? label : label.toLowerCase()}, ${clock(p.duration_seconds)}`)}">${esc(label)}<small>${clock(p.duration_seconds)}</small></button>`;
          }).join("");
          return `${head}<div class="work"><p class="work-name" aria-hidden="true"><b>${esc(name)}</b><small>${esc(surname(first.composer))}</small></p><div class="work-pick">${picks}</div></div>`;
        }
        const line = isClassic(first)
          ? [surname(first.composer), first.arrangement, clock(first.duration_seconds)].filter(Boolean).join(" · ")
          : `${clock(first.duration_seconds)} · ${Math.round(first.bpm)} BPM · ${first.track_count} voices`;
        return `${head}<button type="button" role="radio" aria-checked="false" tabindex="-1" data-id="${esc(first.id)}">${esc(first.title)}<small>${esc(line)}</small><span class="vh">, ${esc(first.status || (isClassic(first) ? "public-domain piece" : "original piece"))}</span></button>`;
      }).join("");
      // The group labels stay pinned to the bill's edges; clicking one scrolls to that group.
      $$(".lineup-group", ui.selector).forEach((head) => head.addEventListener("click", () => {
        const first = head.nextElementSibling;
        ui.selector.scrollTo({ top: Math.max(0, first.offsetTop - head.offsetHeight), behavior: reduced.matches ? "auto" : "smooth" });
      }));
      // Left/Right switch versions of the same work; Up/Down move between works, keeping the version.
      const rows = works.map((w) => w.items);
      const locate = (id) => {
        for (let r = 0; r < rows.length; r++) {
          const c = rows[r].findIndex((p) => p.id === id);
          if (c >= 0) return [r, c];
        }
        return [0, 0];
      };
      $$("button[data-id]", ui.selector).forEach((b) => {
        const piece = byId.get(b.dataset.id);
        b.addEventListener("click", () => select(piece));
        b.addEventListener("keydown", (e) => {
          const [r, c] = locate(piece.id);
          const across = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
          const down = { ArrowDown: 1, ArrowUp: -1 }[e.key] || (across && rows[r].length === 1 ? across : 0);
          let next = null;
          if (across && rows[r].length > 1) next = rows[r][(c + across + rows[r].length) % rows[r].length];
          else if (down) {
            const target = rows[(r + down + rows.length) % rows.length];
            next = target[Math.min(c, target.length - 1)];
          }
          if (!next) return;
          e.preventDefault();
          select(next, true);
        });
      });
      const fromHash = pieces.find((p) => location.hash === `#piece-${p.id}`);
      select(fromHash || pieces[0]);
      if (fromHash) consoleEl.scrollIntoView();
      document.fonts?.ready.then(() => { if (current) relayout(); });
    }
    // Width changes re-measure; the poster's own height changes (fitting the title) do not loop.
    let resizeT = 0;
    let lastWidth = 0;
    new ResizeObserver((entries) => {
      const width = Math.round(entries[0].contentRect.width);
      const height = Math.round(entries[0].contentRect.height);
      const key = `${width}x${height}`;
      if (key === lastWidth) return;
      lastWidth = key;
      clearTimeout(resizeT);
      resizeT = setTimeout(() => { if (current) relayout(); }, 120);
    }).observe(consoleEl);
    new ResizeObserver(() => {
      surfaces.delete(ui.roll);
      if (seen.roll) render();
    }).observe(ui.roll);
  }

  /* --------------------------------------------------------- mini player */
  $$("[data-mini]").forEach((mini) => {
    const button = $("[data-mini-play]", mini);
    const canvas = $("[data-mini-trace]", mini);
    const label = $("span", button);
    const original = label.textContent;
    let envelope = [];
    try { envelope = JSON.parse(canvas.dataset.envelope); } catch { envelope = []; }
    let raf = 0;
    let timer = 0;
    let visible = false;
    const active = () => !document.hidden && visible && !audio.paused && owner === player;
    const draw = () => {
      if (!document.hidden && visible) miniTrace(canvas, envelope, owner === player && audio.duration ? audio.currentTime / audio.duration : 0);
    };
    const stop = () => { clearTimeout(timer); cancelAnimationFrame(raf); timer = raf = 0; };
    const loop = () => {
      raf = 0;
      if (!active()) return;
      draw();
      schedule();
    };
    const schedule = () => {
      if (!timer && !raf && active()) timer = setTimeout(() => { timer = 0; raf = requestAnimationFrame(loop); }, reduced.matches ? 250 : FRAME_MS);
    };
    const wake = () => { stop(); draw(); schedule(); };
    const set = (on) => { button.classList.toggle("is-playing", on); label.textContent = on ? "Pause" : original; wake(); };
    const player = { release() { audio.pause(); set(false); } };
    button.addEventListener("click", async () => {
      if (owner === player && !audio.paused) { audio.pause(); return; }
      claim(player, mini.dataset.src);
      try { await audio.play(); } catch (error) { if (owner === player && error.name !== "AbortError") label.textContent = "Couldn't play"; }
    });
    audio.addEventListener("playing", () => owner === player && set(true));
    audio.addEventListener("pause", () => owner === player && set(false));
    audio.addEventListener("ended", () => owner === player && set(false));
    audio.addEventListener("error", () => { if (owner === player) { set(false); label.textContent = "Couldn't load"; } });
    document.addEventListener("visibilitychange", wake);
    reduced.addEventListener("change", wake);
    new IntersectionObserver(entries => { visible = entries[0].isIntersecting; wake(); }).observe(mini);
    new ResizeObserver(() => { surfaces.delete(canvas); draw(); }).observe(canvas);
  });

  /* ----------------------------------------------------------- docs toc */
  const tocLinks = $$(".doc-toc a");
  if (tocLinks.length && "IntersectionObserver" in window) {
    const map = new Map(tocLinks.map((a) => [decodeURIComponent(a.hash.slice(1)), a]));
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        tocLinks.forEach((a) => a.classList.remove("is-here"));
        map.get(entry.target.id)?.classList.add("is-here");
      }
    }, { rootMargin: "-80px 0px -70% 0px" });
    map.forEach((_, id) => { const el = document.getElementById(id); if (el) observer.observe(el); });
  }
})();
