// keyname-map.js — "Key Name Map" editor. Lists every nameable action / combo
// detected in the current .vil and lets you type a human name for each. Names
// are keyed by raw keycode, so one entry surfaces in every view that shows that
// action (Cheatsheet / Static Viewer / Interactive).
(function () {
  "use strict";

  const container = document.getElementById("view-keyname");
  if (!container) return;

  const LAYER_NAMES = ["BASE", "NAV", "SYM", "FN", "MEDIA", "ADJ"];
  let layoutCache = null;
  let entries = []; // [{raw, label, where}]

  // Plain typing keys that aren't worth naming: letters, digits, punctuation,
  // and basic whitespace/editing. EVERYTHING else on the keymap is included —
  // F-keys (incl. F13+), media keys, macros, arrows/nav, modifiers, and any
  // wrapped combo / tap-dance / layer-tap — regardless of whether you ever
  // press it. (The list is built from the .vil, not from your keystroke stats.)
  const PLAIN_TYPING = new Set([
    "KC_GRAVE", "KC_GRV", "KC_MINUS", "KC_MINS", "KC_EQUAL", "KC_EQL",
    "KC_LBRACKET", "KC_LBRC", "KC_RBRACKET", "KC_RBRC", "KC_BSLASH", "KC_BSLS",
    "KC_SCOLON", "KC_SCLN", "KC_QUOTE", "KC_QUOT", "KC_COMMA", "KC_COMM",
    "KC_DOT", "KC_SLASH", "KC_SLSH",
    "KC_SPACE", "KC_SPC", "KC_ENTER", "KC_ENT", "KC_BSPACE", "KC_BSPC",
    "KC_TAB", "KC_ESCAPE", "KC_ESC", "KC_DELETE", "KC_DEL", "KC_CAPS",
  ]);

  function isNameable(raw, kind) {
    if (!raw || raw === "KC_NO" || raw === "XXXXXXX") return false;
    if (kind === "transparent" || kind === "empty") return false;
    if (raw.includes("(")) return true; // wrapped combo / tap / layer-tap
    if (/^KC_[A-Z]$/.test(raw) || /^KC_[0-9]$/.test(raw)) return false; // letters/digits
    if (PLAIN_TYPING.has(raw)) return false;
    return true; // F-keys, media, macros, nav, mods, etc.
  }

  async function ensureLayout() {
    if (layoutCache) return layoutCache;
    const r = await fetch("/api/layout");
    if (!r.ok) throw new Error(`layout HTTP ${r.status}`);
    layoutCache = await r.json();
    return layoutCache;
  }

  function collect(layout) {
    const byRaw = new Map(); // raw -> {raw, label, where:Set}
    const add = (raw, label, where) => {
      if (!raw) return;
      let e = byRaw.get(raw);
      if (!e) {
        e = { raw, label: label || raw, where: new Set() };
        byRaw.set(raw, e);
      }
      if (where) e.where.add(where);
      if (!e.label && label) e.label = label;
    };

    for (const layer of layout.layers || []) {
      const lname = LAYER_NAMES[layer.index] || `L${layer.index}`;
      for (const row of layer.rows) {
        for (const k of row.keys) {
          if (!k) continue;
          const kind = k.resolved?.expanded_kind;
          if (!isNameable(k.raw, kind)) continue;
          add(k.raw, k.resolved?.label_top, lname);
        }
      }
    }
    for (const co of layout.combo || []) {
      const trig = (co.trigger_labels || []).filter(Boolean);
      if (trig.length === 0) continue;
      add(co.output, co.output_label, `combo ${trig.join("+")}`);
    }

    return [...byRaw.values()].sort((a, b) =>
      (a.label || "").localeCompare(b.label || "")
    );
  }

  function rowHtml(e) {
    const name = window.keyAliases.get(e.raw) || "";
    const where = [...e.where].join("、");
    return `
      <tr data-raw="${escapeAttr(e.raw)}" data-search="${escapeAttr(
        (e.label + " " + e.raw + " " + name).toLowerCase()
      )}">
        <td class="kn-action">${escapeHtml(e.label)}</td>
        <td class="kn-where">${escapeHtml(where)}</td>
        <td class="kn-name">
          <input type="text" value="${escapeAttr(name)}"
                 placeholder="輸入名稱…" aria-label="名稱" />
          <span class="kn-saved" hidden>已存</span>
        </td>
      </tr>`;
  }

  async function show() {
    let layout;
    try {
      [layout] = await Promise.all([ensureLayout(), window.keyAliases.ensure()]);
    } catch (e) {
      container.innerHTML = `<p class="error">load failed: ${e.message}</p>`;
      return;
    }
    entries = collect(layout);

    container.innerHTML =
      `<div class="kn-toolbar">` +
      `<input id="kn-search" type="search" placeholder="搜尋動作 / 名稱…" />` +
      `<span class="kn-hint">填入名稱即自動儲存；清空＝刪除。名稱會顯示在 Cheatsheet（取代按鍵）、Static Viewer、Interactive。</span>` +
      `</div>` +
      `<table class="kn-table"><thead><tr>` +
      `<th>動作</th><th>出現在</th><th>名稱 (describe)</th>` +
      `</tr></thead><tbody>${entries.map(rowHtml).join("")}</tbody></table>`;

    wire();
  }

  function wire() {
    const search = container.querySelector("#kn-search");
    const rows = [...container.querySelectorAll("tbody tr")];
    search.addEventListener("input", () => {
      const q = search.value.trim().toLowerCase();
      for (const tr of rows) {
        tr.hidden = q && !tr.dataset.search.includes(q);
      }
    });

    container.querySelectorAll("tbody tr").forEach((tr) => {
      const raw = tr.dataset.raw;
      const input = tr.querySelector("input");
      const saved = tr.querySelector(".kn-saved");
      let timer = null;
      const persist = async () => {
        try {
          await window.keyAliases.set(raw, input.value);
          tr.dataset.search =
            (input.value + " " + raw).toLowerCase();
          saved.hidden = false;
          setTimeout(() => (saved.hidden = true), 1200);
        } catch (e) {
          alert(`儲存失敗：${e.message}`);
        }
      };
      input.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(persist, 500);
      });
      input.addEventListener("blur", () => {
        clearTimeout(timer);
        persist();
      });
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function escapeAttr(s) {
    return escapeHtml(s).replace(/"/g, "&quot;");
  }

  function refresh() {
    layoutCache = null;
    window.keyAliases.reload().then(show);
  }

  show();
  window.keynameMap = { show, refresh };
})();
