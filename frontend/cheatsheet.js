// cheatsheet.js — Cheatsheet page: overlay every USED layer onto a single
// board so the whole keymap fits on one printable sheet. Each physical key
// shows its BASE legend in the centre, the hold action below, and every other
// layer's legend in a coloured corner. Combos are listed underneath.
//
// Reuses the same /api/layout response (and its server-resolved label_top /
// label_bottom / combo labels) as the Static Viewer — no extra parsing here.
(function () {
  "use strict";

  const container = document.getElementById("view-cheatsheet");
  if (!container) return;

  let layoutCache = null;

  // Index-aligned with the .vil layer order. Keep in sync with
  // static-viewer.js LAYER_NAMES.
  const LAYER_NAMES = ["BASE", "NAV", "SYM", "FN", "MEDIA", "ADJ"];
  const LAYER_COLORS = [
    "#111111", // 0 BASE
    "#2454d6", // 1 NAV   dark blue
    "#9333ea", // 2 SYM   purple
    "#d11f1f", // 3 FN    red
    "#e6791b", // 4 MEDIA orange
    "#0c8fb0", // 5 ADJ   teal
  ];
  const HOLD_COLOR = "#c026a8"; // base mod-tap / layer-tap hold action

  function isLayerUsed(layer) {
    for (const row of layer.rows) {
      for (const k of row.keys) {
        if (!k) continue;
        const kind = k.resolved?.expanded_kind;
        if (kind && kind !== "transparent" && kind !== "empty") return true;
      }
    }
    return false;
  }

  function isLiveSlot(k) {
    if (!k) return false;
    const kind = k.resolved?.expanded_kind;
    return kind && kind !== "transparent" && kind !== "empty";
  }

  async function ensureLayout() {
    if (layoutCache) return layoutCache;
    try {
      const r = await fetch("/api/layout");
      if (!r.ok) {
        container.innerHTML = renderError(`layout error: HTTP ${r.status}`);
        return null;
      }
      layoutCache = await r.json();
      return layoutCache;
    } catch (e) {
      container.innerHTML = renderError(`layout fetch failed: ${e.message}`);
      return null;
    }
  }

  function cell(byIndex, base, overlayIdx, comboTriggers, r, c) {
    const baseKey = base.rows[r].keys[c];
    if (!baseKey || !isLiveSlot(baseKey)) {
      return `<div class="cs-key gap" aria-hidden="true"></div>`;
    }
    const res = baseKey.resolved || {};
    const top = res.label_top ?? "";
    const bot = res.label_bottom ?? "";
    const kind = res.expanded_kind || "plain";

    // Top block: base legend (big) + its hold action (small magenta tag).
    // A named action shows only its name.
    const baseText = aliasOr(baseKey.raw, top);
    let mainHtml = `<span class="cs-base">${escapeHtml(baseText || "&nbsp;")}</span>`;
    if (bot) mainHtml += `<span class="cs-hold">${escapeHtml(bot)}</span>`;

    // Below: one coloured line per OTHER used layer. Lines (not corners) so
    // long labels like "Cmd+KC_KP_PLUS" ellipsis-truncate instead of colliding.
    const lines = [];
    for (const idx of overlayIdx) {
      const k = byIndex[idx].rows[r].keys[c];
      if (!isLiveSlot(k)) continue;
      const lr = k.resolved || {};
      let txt = lr.label_top ?? "";
      if (lr.label_bottom) txt += "/" + lr.label_bottom;
      txt = aliasOr(k.raw, txt); // named action → show only the name
      if (!txt) continue;
      const name = LAYER_NAMES[idx] || `L${idx}`;
      lines.push(
        `<span class="cs-ov" style="color:${LAYER_COLORS[idx] || "#555"}" ` +
          `title="${escapeHtml(name + ": " + txt)}">${escapeHtml(txt)}</span>`
      );
    }

    const cls = ["cs-key", `kind-${kind}`];
    if (comboTriggers.has(baseKey.raw)) cls.push("has-combo");
    return (
      `<div class="${cls.join(" ")}">` +
      `<span class="cs-main">${mainHtml}</span>` +
      (lines.length ? `<span class="cs-ovs">${lines.join("")}</span>` : "") +
      `</div>`
    );
  }

  function renderBoard(layout) {
    const byIndex = {};
    layout.layers.forEach((l) => (byIndex[l.index] = l));
    const base = byIndex[0];
    if (!base) return renderError("no base layer (0) in .vil");

    const overlayIdx = layout.layers
      .filter((l) => l.index !== 0 && isLayerUsed(l))
      .map((l) => l.index);

    const comboTriggers = new Set();
    if (Array.isArray(layout.combo)) {
      for (const co of layout.combo) {
        for (const t of co.triggers || []) comboTriggers.add(t);
      }
    }

    const renderRow = (r) =>
      `<div class="row row-${base.rows[r].row}">` +
      base.rows[r].keys
        .map((_, c) => cell(byIndex, base, overlayIdx, comboTriggers, r, c))
        .join("") +
      `</div>`;

    const leftRows = [0, 1, 2, 3, 4];
    const rightRows = [5, 6, 7, 8, 9];
    const board =
      `<div class="keyboard cs-board">` +
      `<div class="half half-left">${leftRows.map(renderRow).join("")}</div>` +
      `<div class="half half-right">${rightRows.map(renderRow).join("")}</div>` +
      `</div>`;

    return { board, overlayIdx };
  }

  // For each non-base layer, work out HOW you reach it: scan every key for a
  // layer-switch action — LTn (hold layer-tap), MO/TT (momentary), TG/TO
  // (toggle) — and record the trigger tag (e.g. "LT1") plus the physical keys
  // it sits on (e.g. Tab / Del). Used to annotate the legend so the coloured
  // NAV/SYM lines say which key to hold.
  function activatorsByLayer(layout) {
    const map = {}; // idx -> { tags:Set, keys:Set, hold:bool }
    const add = (idx, tag, keyLabel, hold) => {
      if (!map[idx]) map[idx] = { tags: new Set(), keys: new Set(), hold };
      map[idx].tags.add(tag);
      if (keyLabel) map[idx].keys.add(keyLabel);
      if (hold) map[idx].hold = true;
    };
    const PATTERNS = [
      [/^LT(\d+)\(/, (n) => `LT${n}`, true],
      [/^MO\((\d+)\)/, () => "MO", true],
      [/^TT\((\d+)\)/, () => "TT", true],
      [/^TG\((\d+)\)/, () => "TG", false],
      [/^TO\((\d+)\)/, () => "TO", false],
    ];
    for (const layer of layout.layers || []) {
      for (const row of layer.rows) {
        for (const k of row.keys) {
          if (!k || !k.raw) continue;
          const keyLabel = (k.resolved && k.resolved.label_top) || "";
          for (const [re, tag, hold] of PATTERNS) {
            const m = k.raw.match(re);
            if (m) {
              add(+m[1], tag(m[1]), keyLabel, hold);
              break;
            }
          }
        }
      }
    }
    return map;
  }

  function renderLegend(overlayIdx, layout) {
    const act = activatorsByLayer(layout);
    const chip = (color, label, hint) =>
      `<span class="cs-li"><i style="background:${color}"></i>` +
      `<span>${escapeHtml(label)}</span>` +
      (hint ? `<span class="cs-li-act">${escapeHtml(hint)}</span>` : "") +
      `</span>`;
    const items = [chip(LAYER_COLORS[0], LAYER_NAMES[0] || "BASE")];
    for (const idx of overlayIdx) {
      const a = act[idx];
      let hint = "";
      if (a && a.tags.size) {
        const tags = [...a.tags].join("／");
        const keys = [...a.keys].join("／");
        const verb = a.hold ? "長按" : "切換";
        hint = keys ? `${verb} ${tags}（${keys}）` : `${verb} ${tags}`;
      }
      items.push(chip(LAYER_COLORS[idx] || "#555", LAYER_NAMES[idx] || `L${idx}`, hint));
    }
    items.push(chip(HOLD_COLOR, "長按 hold"));
    return `<div class="cs-legend">${items.join("")}</div>`;
  }

  function renderCombos(layout) {
    if (!Array.isArray(layout.combo)) return "";
    const rows = [];
    for (const co of layout.combo) {
      const trig = (co.trigger_labels || []).filter(Boolean);
      if (trig.length === 0) continue;
      const out = aliasOr(co.output, co.output_label || co.output || "");
      if (!out) continue;
      rows.push(
        `<div class="combo-row"><span class="combo-trigger">${escapeHtml(
          trig.join(" + ")
        )}</span><span class="combo-arrow">→</span><span class="combo-output">${escapeHtml(
          out
        )}</span></div>`
      );
    }
    if (rows.length === 0) return "";
    return (
      `<div class="combo-legend cs-ref-box"><div class="combo-legend-title">Combos</div>` +
      rows.join("") +
      `</div>`
    );
  }

  function renderTapDance(layout) {
    if (!Array.isArray(layout.tap_dance)) return "";
    // Only add the "tap+hold" column when some tap-dance actually uses it, so
    // layouts without it keep the table tight (TD / tap / hold / 2×).
    const hasTH = layout.tap_dance.some((td) => td.tap_hold_label);
    const cellHtml = (v) => (v ? escapeHtml(v) : `<span class="td-none">–</span>`);
    const rows = [];
    for (const td of layout.tap_dance) {
      const tap = td.tap_label ? aliasOr(td.tap, td.tap_label) : "";
      const hold = td.hold_label ? aliasOr(td.hold, td.hold_label) : "";
      const dbl = td.double_tap_label ? aliasOr(td.double_tap, td.double_tap_label) : "";
      const th = td.tap_hold_label ? aliasOr(td.tap_hold, td.tap_hold_label) : "";
      if (!tap && !hold && !dbl && !th) continue;
      rows.push(
        `<tr>` +
          `<td class="td-c-id">TD${td.index}</td>` +
          `<td>${cellHtml(tap)}</td>` +
          `<td>${cellHtml(hold)}</td>` +
          `<td>${cellHtml(dbl)}</td>` +
          (hasTH ? `<td>${cellHtml(th)}</td>` : "") +
          `</tr>`
      );
    }
    if (rows.length === 0) return "";
    const head =
      `<tr><th>TD</th><th>點按</th><th>長按</th><th>2×</th>` +
      (hasTH ? `<th>點+長</th>` : "") +
      `</tr>`;
    return (
      `<div class="combo-legend cs-ref-box"><div class="combo-legend-title">Tap Dance</div>` +
      `<table class="td-table"><thead>${head}</thead><tbody>${rows.join("")}</tbody></table>` +
      `</div>`
    );
  }

  // Cheatsheet has no hover popup, so when a name exists we show ONLY the name
  // (it replaces the keycode/combo entirely).
  function aliasOr(raw, fallback) {
    const a = window.keyAliases?.get(raw);
    return a || fallback;
  }

  async function show() {
    const [layout] = await Promise.all([
      ensureLayout(),
      window.keyAliases ? window.keyAliases.ensure() : Promise.resolve(),
    ]);
    if (!layout) return;

    const built = renderBoard(layout);
    if (typeof built === "string") {
      container.innerHTML = built; // error
      return;
    }

    container.innerHTML =
      `<div class="cs-toolbar">` +
      `<button id="cs-print-btn" type="button">🖨 列印 / 存 PDF</button>` +
      `<span class="cs-hint">上傳新的 .vil（上方 Load Vial…）即會自動更新此圖。列印請選「橫向」。</span>` +
      `</div>` +
      renderLegend(built.overlayIdx, layout) +
      built.board +
      `<div class="cs-refs">${renderCombos(layout)}${renderTapDance(layout)}</div>` +
      `<div class="cs-foot">中央＝點按 · 旁邊洋紅＝長按 · 下方彩色＝各 layer · ●＝參與 combo</div>`;

    const btn = document.getElementById("cs-print-btn");
    if (btn) btn.addEventListener("click", () => window.print());
  }

  function escapeHtml(s) {
    return String(s).replace(/&(?!nbsp;)/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function renderError(msg) {
    return `<p class="error">${msg}</p>`;
  }

  function refresh() {
    layoutCache = null;
    show();
  }

  show();
  if (window.keyAliases) window.keyAliases.onChange(refresh);
  window.cheatsheet = { show, refresh, getLayout: () => layoutCache };
})();
