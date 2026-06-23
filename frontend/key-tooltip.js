// key-tooltip.js — dark-theme floating popover that appears 100 ms after the
// mouse settles on any `.key` cell. Explains the keycode in detail according
// to its `expanded_kind`: TD branches, Hyper expansion, layer hold target,
// TRN fall-through, combo participation, media-key description, etc.
//
// Architecture
//   - One singleton `<div class="key-tooltip">` mounted on <body>.
//   - Event delegation on a *view container* (e.g. `#view-static`) so the
//     listeners survive frequent innerHTML re-renders (Interactive page
//     re-renders on every keystroke).
//   - Each `.key` carries `data-raw` + `data-col`; closest `.row` has class
//     `row-N`; closest `.keyboard` has `data-layer`. That's enough to
//     reverse-look-up `layout.layers[L].rows[R].keys[C]`.
//   - Smart-flip placement keeps the popover inside the viewport.
(function () {
  "use strict";

  // ─── singleton popover element ───────────────────────────────────────
  const tip = document.createElement("div");
  tip.className = "key-tooltip";
  tip.style.display = "none";
  // Block events on the tooltip itself so the cell's mouseout doesn't fire
  // when the cursor accidentally drifts over the popover edge.
  tip.style.pointerEvents = "none";
  document.body.appendChild(tip);

  let hoverTimer = null;
  let lastCell = null;

  // ─── public API ──────────────────────────────────────────────────────

  /**
   * Wire up hover-to-tooltip on a viewer container. Safe to call multiple
   * times for the same container — duplicate listeners are deduped via a
   * data-flag.
   *
   * @param {HTMLElement} viewRoot   e.g. document.getElementById("view-static")
   * @param {() => object|null} getLayout  returns the current cached /api/layout response
   */
  function setupKeyTooltips(viewRoot, getLayout) {
    if (!viewRoot || viewRoot.dataset.tooltipReady === "1") return;
    viewRoot.dataset.tooltipReady = "1";

    viewRoot.addEventListener("mouseover", (e) => {
      const cell = e.target.closest(".key");
      if (!cell || cell === lastCell) return;
      lastCell = cell;
      clearTimeout(hoverTimer);
      hoverTimer = setTimeout(() => {
        const layout = getLayout();
        if (!layout) return;
        const loc = locate(cell);
        if (!loc) return;
        showTooltipFor(cell, loc, layout);
      }, 100);
    });

    viewRoot.addEventListener("mouseout", (e) => {
      const cell = e.target.closest(".key");
      if (!cell) return;
      // mouseout fires when moving between child elements too; only hide when
      // truly leaving the cell (relatedTarget not inside same cell).
      const to = e.relatedTarget;
      if (to && cell.contains(to)) return;
      lastCell = null;
      clearTimeout(hoverTimer);
      hideTooltip();
    });
  }

  window.keyTooltip = { setupKeyTooltips };

  // ─── DOM reverse-lookup ─────────────────────────────────────────────

  function locate(cell) {
    const board = cell.closest(".keyboard");
    if (!board) return null;
    const layer = parseInt(board.dataset.layer, 10);
    const rowEl = cell.closest(".row");
    if (!rowEl) return null;
    const rowClass = [...rowEl.classList].find((c) => c.startsWith("row-"));
    if (!rowClass) return null;
    const row = parseInt(rowClass.slice(4), 10);
    const col = parseInt(cell.dataset.col ?? "-1", 10);
    if (Number.isNaN(layer) || Number.isNaN(row) || Number.isNaN(col)) return null;
    return { layer, row, col };
  }

  // ─── show / hide ─────────────────────────────────────────────────────

  function showTooltipFor(cell, loc, layout) {
    const layer = layout.layers[loc.layer];
    if (!layer) return;
    const key = layer.rows[loc.row]?.keys[loc.col];
    tip.innerHTML = buildTooltipHtml(key, loc, layout);
    tip.style.display = "block";
    place(tip, cell);
  }

  function hideTooltip() {
    tip.style.display = "none";
  }

  /**
   * Position the popover next to `anchor`. Default: below + slightly right.
   * Auto-flips when it would overflow viewport right/bottom.
   */
  function place(panel, anchor) {
    const margin = 8;
    const ar = anchor.getBoundingClientRect();
    // First measure with default placement to know natural width/height.
    panel.style.left = "0px";
    panel.style.top = "0px";
    const pr = panel.getBoundingClientRect();
    const pw = pr.width;
    const ph = pr.height;
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    let left = ar.left;
    if (left + pw + margin > vw) left = vw - pw - margin;
    if (left < margin) left = margin;

    // Prefer below the cell; flip above if it would overflow.
    let top = ar.bottom + margin;
    if (top + ph > vh - margin) {
      top = ar.top - ph - margin;
      if (top < margin) top = margin;
    }
    panel.style.left = `${Math.round(left)}px`;
    panel.style.top = `${Math.round(top)}px`;
  }

  // ─── tooltip HTML by kind ───────────────────────────────────────────

  // Layer-index → friendly name. Mirrors the dropdown in index.html.
  const LAYER_NAMES = ["BASE", "NAV", "NUM", "SYM", "FUNC", ""];

  // Plain keycodes whose system behavior is worth describing. Anything not
  // in here gets just "Output: <label>".
  const KEY_DESCRIPTIONS = {
    KC_MPLY: "HID media key — toggle play/pause in the active media app.",
    KC_MNXT: "HID media key — next track.",
    KC_MPRV: "HID media key — previous track.",
    KC_MSTP: "HID media key — stop.",
    KC_MUTE: "HID — toggle system mute.",
    KC_VOLU: "HID — volume up.",
    KC_VOLD: "HID — volume down.",
    KC_BRIU: "HID — display brightness up.",
    KC_BRID: "HID — display brightness down.",
    AU_TOG:  "Vial firmware — toggle keyboard audio (speaker beeps).",
  };

  function kindHeader(kind) {
    const labels = {
      "plain":         "Plain",
      "shift-wrapped": "Shift-wrapped",
      "mod-wrapped":   "Mod-wrapped",
      "layer-tap":     "Layer-tap",
      "mod-tap":       "Mod-tap",
      "tap-dance":     "Tap-dance",
      "transparent":   "Transparent",
      "empty":         "Empty",
      "unknown":       "Unknown",
      "macro":         "Macro",
    };
    return labels[kind] || kind || "Key";
  }

  function buildTooltipHtml(key, loc, layout) {
    if (!key) {
      return wrap("empty", "Empty", `<div class="kt-row"><span>No mapping at this slot.</span></div>`, "");
    }
    const r = key.resolved || {};
    const raw = key.raw || "";
    const kind = r.expanded_kind || "plain";

    let body = "";
    switch (kind) {
      case "plain":          body = renderPlain(r, raw); break;
      case "shift-wrapped":  body = renderShiftWrapped(r); break;
      case "mod-wrapped":    body = renderModWrapped(r); break;
      case "layer-tap":      body = renderLayerTap(r); break;
      case "mod-tap":        body = renderModTap(r); break;
      case "tap-dance":      body = renderTapDance(r, raw); break;
      case "transparent":    body = renderTransparent(loc, layout); break;
      case "empty":          body = `<div class="kt-row"><span>No mapping.</span></div>`; break;
      case "unknown":        body = renderUnknown(r); break;
      case "macro":          body = renderMacro(r, raw, layout); break;
      default:               body = `<div class="kt-row"><span>Output:</span><span>${escape(r.label_top || raw)}</span></div>`;
    }

    const combo = renderCombo(layout, raw);
    return wrap(kind, kindHeader(kind), body, raw, combo);
  }

  function wrap(kind, header, body, raw, combo = "") {
    const alias = window.keyAliases ? window.keyAliases.get(raw) : null;
    const nameRow = alias
      ? `<div class="kt-section"><div class="kt-row">
           <span class="kt-label">名稱</span><span><b>${escape(alias)}</b></span></div></div>
         <div class="kt-divider"></div>`
      : "";
    return `
      <div class="kt-header kt-kind-${escape(kind)}">${escape(header)}</div>
      ${nameRow}
      <div class="kt-section">${body}</div>
      ${combo ? `<div class="kt-divider"></div><div class="kt-section">${combo}</div>` : ""}
      ${raw ? `<div class="kt-divider"></div>
        <div class="kt-raw"><span class="kt-label">raw</span><code>${escape(raw)}</code></div>` : ""}`;
  }

  // ── per-kind body builders ──────────────────────────────────────────

  function renderPlain(r, raw) {
    const desc = KEY_DESCRIPTIONS[raw];
    return `
      <div class="kt-row"><span class="kt-label">Output</span><span>${escape(r.label_top || raw)}</span></div>
      ${desc ? `<div class="kt-note">${escape(desc)}</div>` : ""}`;
  }

  function renderShiftWrapped(r) {
    return `
      <div class="kt-row"><span class="kt-label">Output</span><span>${escape(r.label_top)}</span></div>
      <div class="kt-note">= Shift + (base key)</div>`;
  }

  function renderModWrapped(r) {
    return `
      <div class="kt-row"><span class="kt-label">Output</span><span>${escape(r.label_top)}</span></div>
      <div class="kt-note">single keypress sends the modifier combo above.</div>`;
  }

  function renderLayerTap(r) {
    const m = (r.label_bottom || "").match(/L(\d+)/);
    const lid = m ? parseInt(m[1], 10) : null;
    const lname = lid != null ? (LAYER_NAMES[lid] || "") : "";
    const target = lid != null
      ? `→ Layer ${lid}${lname ? ` (${lname})` : ""}`
      : (r.hold || "?");
    return `
      <div class="kt-row"><span class="kt-label">Tap</span><span>${escape(r.tap)}</span></div>
      <div class="kt-row"><span class="kt-label">Hold</span><span>${escape(target)}</span></div>`;
  }

  // Mapping for the Hyper expansion text. ALL_T / HYPR_T have a fixed
  // expansion that humans want to see.
  const HOLD_EXPANSIONS = {
    "Hyper": "Ctrl + Shift + Alt + Cmd",
    "Meh":   "Ctrl + Shift + Alt",
  };

  function renderModTap(r) {
    const expansion = HOLD_EXPANSIONS[r.hold];
    return `
      <div class="kt-row"><span class="kt-label">Tap</span><span>${escape(r.tap)}</span></div>
      <div class="kt-row"><span class="kt-label">Hold</span><span>${escape(r.hold)}</span></div>
      ${expansion ? `<div class="kt-sub">┗ ${escape(expansion)}</div>` : ""}`;
  }

  function renderTapDance(r, raw) {
    // Vial always serializes 4 branches per TD; the unused ones come back as
    // KC_NO → resolved label = null. Skip those rows entirely so the user
    // only sees branches they actually configured.
    const rows = [];
    if (r.tap)        rows.push(`<div class="kt-row"><span class="kt-label">Tap</span><span>${escape(r.tap)}</span></div>`);
    if (r.hold)       rows.push(`<div class="kt-row"><span class="kt-label">Hold</span><span>${escape(r.hold)}</span></div>`);
    if (r.double_tap) rows.push(`<div class="kt-row"><span class="kt-label">Double-tap</span><span>${escape(r.double_tap)}</span></div>`);
    if (r.tap_hold)   rows.push(`<div class="kt-row"><span class="kt-label">Tap+Hold</span><span>${escape(r.tap_hold)}</span></div>`);
    if (r.tap_term_ms != null) {
      rows.push(`<div class="kt-row"><span class="kt-label">Term</span><span>${r.tap_term_ms} ms</span></div>`);
    }
    return rows.join("");
  }

  function renderTransparent(loc, layout) {
    // Walk down to find the first non-TRN slot at the same (row, col).
    for (let L = loc.layer - 1; L >= 0; L--) {
      const k = layout.layers[L]?.rows[loc.row]?.keys[loc.col];
      if (!k) continue;
      const kind = k.resolved?.expanded_kind;
      if (!kind || kind === "transparent" || kind === "empty") continue;
      const lname = LAYER_NAMES[L] || "";
      return `
        <div class="kt-row"><span class="kt-label">Falls through to</span><span></span></div>
        <div class="kt-sub">Layer ${L}${lname ? ` ${lname}` : ""}: <strong>${escape(k.resolved.label_top || "")}</strong></div>
        <div class="kt-note">raw at that slot: <code>${escape(k.raw)}</code></div>`;
    }
    return `<div class="kt-row"><span>No lower layer defines this slot.</span></div>`;
  }

  function renderUnknown(r) {
    return `
      <div class="kt-row"><span class="kt-label">Output</span><span>${escape(r.label_top || "")}</span></div>
      <div class="kt-note">Not in label table — add it to <code>backend/parsers/keycode_labels.py</code>.</div>`;
  }

  // Vial macro actions vary in shape; we render them generically:
  //   ["tap", "KC_X"]    → tap KC_X
  //   ["down", "KC_X"]   → down KC_X
  //   ["up", "KC_X"]     → up KC_X
  //   ["text", "hello"]  → text "hello"
  //   ["delay", 200]     → delay 200ms
  //   anything else      → raw JSON of the action
  function _formatMacroAction(act) {
    if (!Array.isArray(act) || act.length === 0) return JSON.stringify(act);
    const verb = act[0];
    const arg = act[1];
    if (verb === "delay") return `delay ${arg}ms`;
    if (verb === "text")  return `text ${JSON.stringify(arg)}`;
    if (verb === "tap" || verb === "down" || verb === "up") {
      return `${verb} ${arg}`;
    }
    return JSON.stringify(act);
  }

  function renderMacro(r, raw, layout) {
    // Pull the action sequence for this macro index from the layout payload.
    const idx = (() => {
      const m = raw.match(/^MACRO?(\d+)$/);
      return m ? parseInt(m[1], 10) : null;
    })();
    let actions = null;
    if (idx != null && Array.isArray(layout.macro)) {
      const entry = layout.macro.find((m) => m.index === idx);
      if (entry) actions = entry.actions;
    }
    const header = `
      <div class="kt-row"><span class="kt-label">Label</span><span>${escape(r.label_top || raw)}</span></div>`;
    if (actions == null) {
      return `${header}<div class="kt-note">Macro slot ${idx ?? "?"} is not defined in this .vil.</div>`;
    }
    if (actions.length === 0) {
      return `${header}<div class="kt-note">Macro is empty (no actions configured).</div>`;
    }
    const rows = actions
      .map((a) => `<div class="kt-sub">• ${escape(_formatMacroAction(a))}</div>`)
      .join("");
    return `${header}
      <div class="kt-row"><span class="kt-label">Actions</span><span>${actions.length}</span></div>
      ${rows}`;
  }

  // ── Combo participation ─────────────────────────────────────────────

  function renderCombo(layout, raw) {
    if (!Array.isArray(layout.combo)) return "";
    const out = [];
    for (const c of layout.combo) {
      if (!Array.isArray(c.triggers) || !c.triggers.includes(raw)) continue;
      // Trigger labels were computed server-side; fall back to raw.
      const labels = (c.trigger_labels && c.trigger_labels.length === c.triggers.length)
        ? c.trigger_labels
        : c.triggers;
      const others = c.triggers
        .map((t, i) => ({ raw: t, lbl: labels[i] }))
        .filter((t) => t.raw !== raw)
        .map((t) => t.lbl);
      const output = c.output_label || c.output;
      out.push(`<div class="kt-row"><span class="kt-label">Combo</span><span>this + ${others.map(escape).join(" + ")} → ${escape(output)}</span></div>`);
    }
    return out.join("");
  }

  function escape(s) {
    return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
})();
