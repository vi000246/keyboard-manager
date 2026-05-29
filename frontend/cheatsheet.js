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
    "#1a9e4b", // 1 NAV   green
    "#0c8fb0", // 2 SYM   teal
    "#d11f1f", // 3 FN    red
    "#e6791b", // 4 MEDIA orange
    "#7d3fb3", // 5 ADJ   purple
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
    let mainHtml = `<span class="cs-base">${escapeHtml(top || "&nbsp;")}</span>`;
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

  function renderLegend(overlayIdx) {
    const chip = (color, label) =>
      `<span class="cs-li"><i style="background:${color}"></i>${escapeHtml(label)}</span>`;
    const items = [chip(LAYER_COLORS[0], LAYER_NAMES[0] || "BASE")];
    for (const idx of overlayIdx) {
      items.push(chip(LAYER_COLORS[idx] || "#555", LAYER_NAMES[idx] || `L${idx}`));
    }
    items.push(chip(HOLD_COLOR, "長按 hold"));
    return `<div class="cs-legend">${items.join("")}</div>`;
  }

  function renderCombos(layout) {
    if (!Array.isArray(layout.combo) || layout.combo.length === 0) return "";
    const rows = [];
    for (const co of layout.combo) {
      const trig = (co.trigger_labels || []).filter(Boolean);
      if (trig.length === 0) continue;
      const out = co.output_label || co.output || "";
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
      `<div class="combo-legend cs-combos"><div class="combo-legend-title">Combos</div>` +
      rows.join("") +
      `</div>`
    );
  }

  async function show() {
    const layout = await ensureLayout();
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
      renderLegend(built.overlayIdx) +
      built.board +
      renderCombos(layout) +
      `<div class="cs-foot">中央＝點按 · 下方洋紅＝長按 · 角落＝各 layer · ●＝參與 combo</div>`;

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
  window.cheatsheet = { show, refresh, getLayout: () => layoutCache };
})();
