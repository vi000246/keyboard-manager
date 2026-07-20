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
  // null = combined overlay (all layers on one board); a number = show ONLY
  // that layer's keys (single-layer mode, toggled by the layer buttons or Tab).
  let selectedLayer = null;

  // Index-aligned with the .vil layer order. Keep in sync with
  // static-viewer.js LAYER_NAMES.
  const LAYER_NAMES = ["BASE", "NAV", "NUM", "SYM", "FUNC", "ADJ"];
  // Light tones — the board background is dark (#232323 keys on #1a1a1a), so
  // every layer colour must read as a light foreground.
  const LAYER_COLORS = [
    "#dcdcdc", // 0 BASE  light grey
    "#6ea8ff", // 1 NAV   light blue
    "#c79cff", // 2 SYM   light purple
    "#ff8a8a", // 3 FN    light red
    "#ffb15c", // 4 MEDIA light orange
    "#5fd3e6", // 5 ADJ   light teal
  ];
  const HOLD_COLOR = "#f061d4"; // base mod-tap / layer-tap hold action (light magenta)

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

    // Below: one coloured line per OTHER used layer, in a FIXED slot per layer
    // so the same layer always sits on the same row across every key (blank
    // where the layer is transparent) — makes columns easy to compare. Lines
    // ellipsis-truncate so long labels like "Cmd+KC_KP_PLUS" don't collide.
    const lines = [];
    for (const idx of overlayIdx) {
      const k = byIndex[idx].rows[r].keys[c];
      let txt = "";
      if (isLiveSlot(k)) {
        const lr = k.resolved || {};
        txt = lr.label_top ?? "";
        if (lr.label_bottom) txt += "/" + lr.label_bottom;
        txt = aliasOr(k.raw, txt); // named action → show only the name
      }
      if (txt) {
        const name = LAYER_NAMES[idx] || `L${idx}`;
        lines.push(
          `<span class="cs-ov" style="color:${LAYER_COLORS[idx] || "#555"}" ` +
            `title="${escapeHtml(name + ": " + txt)}">${escapeHtml(txt)}</span>`
        );
      } else {
        // Reserve this layer's row even when transparent, to keep alignment.
        lines.push(`<span class="cs-ov cs-ov-empty" aria-hidden="true"></span>`);
      }
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

    // Hide fully-empty rows/columns (shared with the static viewer).
    const geo = window.gridRender.usedGeometry(layout);
    const renderRow = (cols, r) =>
      `<div class="row row-${base.rows[r].row}" style="grid-template-columns: repeat(${cols.length}, var(--key-w))">` +
      cols
        .map((c) => cell(byIndex, base, overlayIdx, comboTriggers, r, c))
        .join("") +
      `</div>`;

    const board =
      `<div class="keyboard cs-board">` +
      `<div class="half half-left">${geo.left.rows.map((r) => renderRow(window.gridRender.displayCols(geo, "left"), r)).join("")}</div>` +
      `<div class="half half-right">${geo.right.rows.map((r) => renderRow(window.gridRender.displayCols(geo, "right"), r)).join("")}</div>` +
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

  // Layer selector: a button per USED layer plus "全部疊圖" (combined overlay).
  // Clicking one flips selectedLayer and re-renders just the board area.
  function renderLayerBar(usedIdx) {
    const btn = (val, label, color) =>
      `<button type="button" class="cs-layer-btn" data-layer="${val}" ` +
      `style="--c:${color}">${escapeHtml(label)}</button>`;
    // Button order mirrors the Tab cycle: non-BASE layers in index order, then
    // BASE, then the combined overlay last.
    const ordered = usedIdx.filter((i) => i !== 0);
    if (usedIdx.includes(0)) ordered.push(0); // BASE near the end
    const parts = [];
    for (const idx of ordered) {
      // Prefix each button with its layer index (NAV→1, NUM→2, SYM→3…) so the
      // number matches the LTn / MO(n) activator you press to reach the layer.
      const name = LAYER_NAMES[idx] || `L${idx}`;
      parts.push(btn(String(idx), `${idx} ${name}`, LAYER_COLORS[idx] || "#555"));
    }
    parts.push(btn("all", "全部疊圖", "#8a8a8a")); // combined overlay last
    return `<div class="cs-layer-bar">${parts.join("")}</div>`;
  }

  // One cell in single-layer mode: the selected layer's own legend, big and
  // centred. Transparent/empty slots on that layer fall through to BASE, so we
  // show the base legend dimmed (it tells you what the key still does there).
  function singleCell(byIndex, base, idx, r, c) {
    const baseKey = base.rows[r].keys[c];
    if (!baseKey) return `<div class="cs-key gap" aria-hidden="true"></div>`;
    const k = byIndex[idx].rows[r].keys[c];
    if (!isLiveSlot(k)) {
      const bres = baseKey.resolved || {};
      const btxt = aliasOr(baseKey.raw, bres.label_top ?? "");
      return (
        `<div class="cs-key cs-single trn">` +
        `<span class="cs-single-wrap"><span class="cs-single-main">${escapeHtml(btxt || "")}</span></span>` +
        `</div>`
      );
    }
    const res = k.resolved || {};
    const top = aliasOr(k.raw, res.label_top ?? "");
    const bot = res.label_bottom ?? "";
    const kind = res.expanded_kind || "plain";
    let inner = `<span class="cs-single-main">${escapeHtml(top || " ")}</span>`;
    if (bot) inner += `<span class="cs-single-sub">${escapeHtml(bot)}</span>`;
    return `<div class="cs-key cs-single kind-${kind}"><span class="cs-single-wrap">${inner}</span></div>`;
  }

  function renderSingleBoard(byIndex, base, idx, topology) {
    // Same trimmed shape as the combined view (computed across all layers).
    // `topology` must be threaded through from the layout — without it the
    // board falls back to inferred geometry and loses the board's mirroring.
    const geo = window.gridRender.usedGeometry({
      layers: Object.values(byIndex),
      topology,
    });
    const renderRow = (cols, r) =>
      `<div class="row row-${base.rows[r].row}" style="grid-template-columns: repeat(${cols.length}, var(--key-w))">` +
      cols.map((c) => singleCell(byIndex, base, idx, r, c)).join("") +
      `</div>`;
    const color = LAYER_COLORS[idx] || "#555";
    const name = LAYER_NAMES[idx] || `L${idx}`;
    return (
      `<div class="cs-single-cap" style="color:${color}">Layer ${idx} — ${escapeHtml(name)}（只顯示這層）</div>` +
      `<div class="keyboard cs-board cs-single-board" style="--layer-c:${color}">` +
      `<div class="half half-left">${geo.left.rows.map((r) => renderRow(window.gridRender.displayCols(geo, "left"), r)).join("")}</div>` +
      `<div class="half half-right">${geo.right.rows.map((r) => renderRow(window.gridRender.displayCols(geo, "right"), r)).join("")}</div>` +
      `</div>`
    );
  }

  const ROOT_PX = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;

  // Shrink one label's font until its full text fits its box width. The rem
  // value is the MAX (the CSS size); we only scale DOWN, stopping at minPx, so
  // long strings show in full instead of ellipsis-clipping. Resets to max first
  // so repeated calls (on resize) re-measure from scratch.
  function fitEl(el, maxRem, minPx) {
    const maxPx = maxRem * ROOT_PX;
    el.style.fontSize = maxPx + "px";
    // clientWidth 0 → board is hidden (not laid out yet); leave at max.
    if (!el.clientWidth || el.scrollWidth <= el.clientWidth) return;
    let size = Math.max(minPx, Math.floor((maxPx * el.clientWidth) / el.scrollWidth * 10) / 10);
    el.style.fontSize = size + "px";
    let guard = 0;
    while (el.scrollWidth > el.clientWidth && size > minPx && guard < 14) {
      size -= 0.5;
      el.style.fontSize = size + "px";
      guard += 1;
    }
  }

  // Auto-fit every label so its whole string shows: single-layer keys
  // (.cs-single-main), and the combined overlay's base legend (.cs-base) + each
  // per-layer line (.cs-ov). No-ops while hidden; the ResizeObserver re-runs it
  // once the tab/HUD becomes visible or the window width changes.
  function fitBoardText() {
    const wrap = document.getElementById("cs-board-wrap");
    if (!wrap) return;
    wrap.querySelectorAll(".cs-single-main").forEach((el) => fitEl(el, 1.35, 8));
    wrap.querySelectorAll(".cs-base").forEach((el) => fitEl(el, 0.95, 7));
    wrap.querySelectorAll(".cs-ov").forEach((el) => {
      if (!el.classList.contains("cs-ov-empty")) fitEl(el, 0.6, 5);
    });
  }

  // The board is first rendered while the tab is hidden (show() runs on load),
  // so fitBoardText() can't measure then. Observe the board wrapper and re-fit
  // when it gains/changes width (tab switch, HUD open, window resize). Width-
  // guarded so font tweaks — which don't change the wrapper width — never loop.
  let _lastFitWidth = -1;
  let _fitObserver = null;
  function watchBoardResize() {
    const wrap = document.getElementById("cs-board-wrap");
    if (!wrap || typeof ResizeObserver === "undefined") return;
    if (_fitObserver) _fitObserver.disconnect();
    _fitObserver = new ResizeObserver(() => {
      const w = wrap.clientWidth;
      if (!w || w === _lastFitWidth) return;
      _lastFitWidth = w;
      fitBoardText();
    });
    _fitObserver.observe(wrap);
  }

  // Re-render just the legend + board (no refetch) for the current selection.
  function renderBoardArea() {
    const layout = layoutCache;
    if (!layout) return;
    const byIndex = {};
    layout.layers.forEach((l) => (byIndex[l.index] = l));
    const base = byIndex[0];
    const legendWrap = document.getElementById("cs-legend-wrap");
    const boardWrap = document.getElementById("cs-board-wrap");
    if (!base || !legendWrap || !boardWrap) return;

    container.querySelectorAll(".cs-layer-btn").forEach((b) => {
      const v = b.dataset.layer;
      const on = (selectedLayer === null && v === "all") || String(selectedLayer) === v;
      b.classList.toggle("active", on);
    });

    if (selectedLayer === null) {
      const built = renderBoard(layout);
      if (typeof built === "string") {
        legendWrap.innerHTML = "";
        boardWrap.innerHTML = built;
        return;
      }
      legendWrap.innerHTML = renderLegend(built.overlayIdx, layout);
      boardWrap.innerHTML = built.board;
    } else {
      legendWrap.innerHTML = "";
      boardWrap.innerHTML = renderSingleBoard(byIndex, base, selectedLayer, layout.topology);
    }
    // Fit now (if visible) and force the observer to re-fit on next resize even
    // when the wrapper width is unchanged (content just changed under it).
    _lastFitWidth = -1;
    fitBoardText();
  }

  // Cheatsheet has no hover popup, so when a name exists we show ONLY the name
  // (it replaces the keycode/combo entirely).
  function aliasOr(raw, fallback) {
    const a = window.keyAliases?.get(raw);
    return a || fallback;
  }

  // Deep-link the opening layer via ?layer=… (the Hammerspoon HUD uses this to
  // land on SYM). Accepts a layer name ("sym", case-insensitive), an index
  // ("3"), or "all" for the combined overlay. Unknown → null (combined).
  function initialLayerFromUrl() {
    const raw = new URLSearchParams(location.search).get("layer");
    if (!raw) return null;
    const v = raw.trim();
    if (!v || v.toLowerCase() === "all") return null;
    const byName = LAYER_NAMES.findIndex((n) => n.toLowerCase() === v.toLowerCase());
    if (byName !== -1) return byName;
    const n = Number(v);
    return Number.isInteger(n) ? n : null;
  }

  // Tab / Shift+Tab cycles the displayed layer. Cycle order is every USED
  // non-BASE layer in .vil order, then BASE last, wrapping around. The combined
  // overlay (null) is NOT part of the cycle — reach it via the layer bar button.
  function cycleLayer(dir) {
    const layout = layoutCache;
    if (!layout) return;
    const usedIdx = layout.layers.filter(isLayerUsed).map((l) => l.index);
    if (!usedIdx.length) return;
    const cycle = usedIdx.filter((i) => i !== 0);
    if (usedIdx.includes(0)) cycle.push(0); // BASE goes last
    if (!cycle.length) return;
    let pos = cycle.findIndex((v) => v === selectedLayer);
    if (pos === -1) pos = 0;
    pos = (pos + dir + cycle.length) % cycle.length;
    selectedLayer = cycle[pos];
    renderBoardArea();
  }

  async function show() {
    const [layout] = await Promise.all([
      ensureLayout(),
      window.keyAliases ? window.keyAliases.ensure() : Promise.resolve(),
    ]);
    if (!layout) return;

    const base = layout.layers.find((l) => l.index === 0);
    if (!base) {
      container.innerHTML = renderError("no base layer (0) in .vil");
      return;
    }
    const usedIdx = layout.layers.filter(isLayerUsed).map((l) => l.index);
    // Drop a stale selection (e.g. after uploading a layout with fewer layers).
    if (selectedLayer !== null && !usedIdx.includes(selectedLayer)) selectedLayer = null;

    container.innerHTML =
      `<div class="cs-toolbar">` +
      `<button id="cs-print-btn" type="button">🖨 列印 / 存 PDF</button>` +
      `<span class="cs-hint">點上方 layer 按鈕只看單層；「全部疊圖」回到合併檢視。上傳新的 .vil 會自動更新。列印請選「橫向」。</span>` +
      `</div>` +
      renderLayerBar(usedIdx) +
      `<div id="cs-legend-wrap"></div>` +
      `<div id="cs-board-wrap"></div>` +
      `<div class="cs-refs">${renderCombos(layout)}${renderTapDance(layout)}</div>` +
      `<div class="cs-foot">中央＝點按 · 旁邊洋紅＝長按 · 下方彩色＝各 layer · ●＝參與 combo</div>`;

    const btn = document.getElementById("cs-print-btn");
    if (btn) btn.addEventListener("click", () => window.print());

    container.querySelectorAll(".cs-layer-btn").forEach((b) => {
      b.addEventListener("click", () => {
        const v = b.dataset.layer;
        selectedLayer = v === "all" ? null : Number(v);
        renderBoardArea();
      });
    });

    renderBoardArea();
    watchBoardResize();
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

  // Tab cycles layers while the cheatsheet view is on-screen. Registered once
  // (not per show()) so refresh()/alias reloads don't stack duplicate handlers.
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Tab") return;
    if (container.classList.contains("hidden")) return;
    e.preventDefault();
    cycleLayer(e.shiftKey ? -1 : 1);
  });

  selectedLayer = initialLayerFromUrl();
  show();
  if (window.keyAliases) window.keyAliases.onChange(refresh);
  window.cheatsheet = { show, refresh, getLayout: () => layoutCache };
})();
