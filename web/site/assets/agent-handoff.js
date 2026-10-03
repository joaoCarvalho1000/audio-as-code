/* Agent handoff: builds the prompt from the brief and copies it. Kept apart from site.js. */
(() => {
  "use strict";
  const root = document.querySelector("[data-handoff]");
  if (!root) return;
  const input = root.querySelector("[data-brief-input]");
  const out = root.querySelector("[data-prompt]");
  const status = root.querySelector("[data-handoff-status]");
  const copy = root.querySelector("[data-handoff-copy]");
  const chips = Array.from(root.querySelectorAll("[data-brief]"));
  // An anchor's href property is already absolute, resolved against the page as served:
  // root or subpath hosting and localhost all produce the right address.
  const href = (sel) => root.querySelector(sel)?.href || "";
  const fromFile = location.protocol === "file:";

  function prompt() {
    const brief = input.value.trim() || "(Describe the music here: what it is for, length, mood, instruments, tempo.)";
    const setup = fromFile
      ? [
          "1. Use the Audio as Code source folder or source ZIP I give you. If it is zipped, extract it into a new project folder.",
          "2. Read skills/audio-as-code/SKILL.md in that folder and follow it.",
        ]
      : [
          `1. Read the skill at ${href("[data-handoff-skill]")} and the guide index at ${href("[data-handoff-llms]")}.`,
          `2. If you don't already have an Audio as Code checkout, download ${href("[data-handoff-zip]")} and extract it into a new project folder. Then follow its bundled skills/audio-as-code/SKILL.md.`,
        ];
    return [
      "Use Audio as Code to create the music in the brief below.",
      ...setup,
      "3. Install its Python dependencies, compose an original score (Audio as Code makes instrumental music and cues, not speech or sound effects), then validate and render it locally.",
      "4. Deliver the WAV, the MIDI file, the editable score JSON, the Python source you wrote and the render report. If I'm working in a video, game or presentation project, put the WAV where that project expects audio and keep the score and source beside it for revisions. Then tell me what you would try next.",
      "",
      "Music brief:",
      brief,
    ].join("\n");
  }
  const update = () => { out.textContent = prompt(); };

  chips.forEach((chip) => chip.addEventListener("click", () => {
    input.value = chip.dataset.brief;
    chips.forEach((c) => c.setAttribute("aria-pressed", String(c === chip)));
    update();
  }));
  input.addEventListener("input", () => {
    chips.forEach((c) => c.setAttribute("aria-pressed", String(c.dataset.brief === input.value)));
    update();
  });

  async function write(text) {
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
  let reset = 0;
  copy.addEventListener("click", async () => {
    update();
    const ok = await write(out.textContent);
    clearTimeout(reset);
    if (ok) {
      copy.classList.add("ok");
      copy.firstChild.textContent = "Copied";
      status.textContent = "Copied. Paste it into your coding agent.";
      reset = setTimeout(() => { copy.classList.remove("ok"); copy.firstChild.textContent = "Copy agent prompt"; }, 2000);
    } else {
      const range = document.createRange();
      range.selectNodeContents(out);
      getSelection().removeAllRanges();
      getSelection().addRange(range);
      status.textContent = "Copying was blocked, so the prompt is selected. Press Ctrl+C (⌘C on a Mac) to copy it.";
    }
  });

  if (fromFile) root.querySelector("[data-handoff-file]").hidden = false;
  copy.hidden = false;
  update();
})();
