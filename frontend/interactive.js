// interactive.js — Interactive Simulator: real-time grid that responds to
// the user's physical keystrokes via the /api/live WebSocket.
//
// Behavior:
//   - On {type: "down", key, …}, add the key to a heldKeys set.
//   - If any held key is a layer-tap on BASE, switch the visible layer to
//     its hold target (so pressing Space shows the NAV layout immediately).
//   - Every held key paints `.pressed` on its grid cell — even when the new
//     layer renders that slot as TRN, you can still see WHERE you're holding.
//   - The status bar lists held keys as chips that spell out what each key
//     BECOMES when held (`Space → NAV`, `Caps → Hyper`, plain `Shift`, etc.)
//     so the modifier-combo case stays legible without overflowing.
//   - {type: "helper_disconnected"} flips a status badge; we reconnect with
//     exponential backoff so launchd restarts of the helper recover cleanly.
(function () {
  "use strict";

  const root = document.getElementById("view-interactive");
  let layout = null;
  let activeLayer = 0;
  const heldKeys = new Set();
  // Mouse-click simulated holds. QMK's standard LT(layer, kc) emits no
  // macOS event during the hold window — firmware swallows it. So we
  // can't observe a real hold via pynput. Clicking a layer-tap cell
  // (or any LT-style key) toggles a virtual hold here so the user can
  // still preview the layered layout without typing on it. Keys are
  // stored as "row:col" strings into BASE.
  const virtualHeld = new Set();
  let socket = null;
  let helperStatus = "connecting";
  let reconnectDelay = 1000;  // ms — grows up to 10s
  let initialized = false;

  async function ensureLayout() {
    if (layout) return layout;
    const r = await fetch("/api/layout");
    if (!r.ok) return null;
    layout = await r.json();
    return layout;
  }

  // macOS event-layer key names → BASE layer label_top text used in the grid.
  const _EVENT_TO_LABEL = {
    space: "Space",
    return: "Enter",
    enter: "Enter",
    delete: "Bksp",
    forwarddelete: "Del",
    escape: "Esc",
    tab: "Tab",
    left: "←", right: "→", up: "↑", down: "↓",
    pageup: "PgUp", pagedown: "PgDn",
    home: "Home", end: "End",
    shift: "Shift",  ctrl: "Ctrl",  alt: "Alt", cmd: "Cmd",
  };

  // Friendly display names for the chips (separate from layout labels — the
  // chips can use longer strings without breaking the grid).
  const _EVENT_TO_CHIP = {
    space: "Space", return: "Enter", enter: "Enter",
    delete: "Backspace", forwarddelete: "Delete", escape: "Esc", tab: "Tab",
    left: "←", right: "→", up: "↑", down: "↓",
    pageup: "PgUp", pagedown: "PgDn", home: "Home", end: "End",
    shift: "Shift", ctrl: "Ctrl", alt: "Alt", cmd: "Cmd",
    capslock: "Caps",
  };

  function labelFor(eventKey) {
    const k = eventKey.toLowerCase();
    if (k in _EVENT_TO_LABEL) return _EVENT_TO_LABEL[k];
    if (k.length === 1) return k.toUpperCase();
    return null;
  }

  function chipNameFor(eventKey) {
    const k = eventKey.toLowerCase();
    if (k in _EVENT_TO_CHIP) return _EVENT_TO_CHIP[k];
    if (k.length === 1) return k.toUpperCase();
    return k;
  }

  // Modifier event keys are pressed by physical positions whose label doesn't
  // necessarily equal the event-key name. We need a separate matcher for them.
  const MODIFIER_EVENT_KEYS = new Set(["shift", "ctrl", "alt", "cmd"]);
  const MOD_NAMES = {
    shift: "Shift",
    ctrl:  "Ctrl",
    alt:   "Alt",
    cmd:   "Cmd",
  };

  /**
   * Categorize the *set* of currently-held modifiers so we can attribute a
   * single "ctrl" event to the right physical source:
   *   - all 4 mods held → user is pressing a Hyper-source slot (ALL_T-style)
   *   - 3 of {ctrl,shift,alt} held (no cmd) → Meh-source slot
   *   - 1-2 mods → an "exact" source (plain mod key / mod-tap-hold / TD-hold)
   * Without this, holding TD(0) (hold=Ctrl) would also light up ALL_T
   * because Hyper contains Ctrl — visually confusing because ALL_T isn't
   * actually the source.
   */
  function _modContext() {
    const heldModSet = new Set();
    for (const h of heldKeys) {
      const n = MOD_NAMES[h.toLowerCase()];
      if (n) heldModSet.add(n);
    }
    if (heldModSet.size === 4) return "hyper";
    if (heldModSet.size === 3 && !heldModSet.has("Cmd")) return "meh";
    return "exact";
  }

  /**
   * Find every BASE-layer slot a held event-key could correspond to.
   *
   * Multiple positions can produce the same event (e.g. TD(3) tap=Tab AND
   * LT1(KC_TAB) tap=Tab both send "tab"). Returns the layer-tap match first
   * if any, then mod-tap, then plain — so callers can pick the most relevant.
   */
  function findAllBaseSlots(eventKey) {
    if (!layout) return [];
    const base = layout.layers[0];
    const label = labelFor(eventKey);
    const isMod = MODIFIER_EVENT_KEYS.has(eventKey.toLowerCase());
    const modName = isMod ? MOD_NAMES[eventKey.toLowerCase()] : null;
    const modCtx = isMod ? _modContext() : null;

    const matches = [];
    for (let r = 0; r < base.rows.length; r++) {
      const row = base.rows[r];
      for (let c = 0; c < row.keys.length; c++) {
        const k = row.keys[c];
        if (!k) continue;
        const res = k.resolved;
        const kind = res.expanded_kind;

        // Direct label match (plain letters, layer-tap tap, mod-tap tap, ...)
        if (label && res.label_top === label) {
          matches.push({ key: k, row: r, col: c, kind, reason: "label" });
          continue;
        }

        if (!modName) continue;
        const hold = res.hold || "";

        if (modCtx === "hyper") {
          // Only attribute the mod to a Hyper-source slot.
          if (hold === "Hyper" && (kind === "mod-tap" || kind === "tap-dance")) {
            matches.push({ key: k, row: r, col: c, kind, reason: "hyper" });
          }
        } else if (modCtx === "meh") {
          if (hold === "Meh" && (kind === "mod-tap" || kind === "tap-dance")) {
            matches.push({ key: k, row: r, col: c, kind, reason: "meh" });
          }
        } else {
          // Exact mode: plain mod key, or mod-tap / TD whose hold is exactly
          // this modifier. Critically we do NOT match Hyper/Meh here — they
          // only fire when the full set is held.
          if ((kind === "mod-tap" || kind === "tap-dance") && hold === modName) {
            matches.push({ key: k, row: r, col: c, kind, reason: "hold-mod" });
          } else if (kind === "plain" && res.label_top && res.label_top.endsWith(modName)) {
            matches.push({ key: k, row: r, col: c, kind, reason: "plain-mod" });
          }
        }
      }
    }

    // Sort: layer-tap > mod-tap > others (so the *first* result is the most
    // useful one for layer activation and pressed-highlight position).
    const rank = { "layer-tap": 0, "mod-tap": 1 };
    matches.sort((a, b) => (rank[a.kind] ?? 9) - (rank[b.kind] ?? 9));
    return matches;
  }

  function findOnBaseLayer(eventKey) {
    const matches = findAllBaseSlots(eventKey);
    return matches.length > 0 ? matches[0].key : null;
  }

  /**
   * The previewed layer is driven ONLY by virtual mouse-click holds.
   *
   * We deliberately do NOT switch layers from real key events: QMK swallows a
   * layer-tap's hold (no macOS event fires while it's held), so an observed
   * key event for a layer-tap key always means it was *tapped* — its tap
   * output was emitted, the layer was not entered. Inferring a layer from such
   * an event mis-fires whenever that same output arrives another way — e.g. a
   * C+V combo emitting Space would otherwise "hold" Space and jump to L2.
   * (Held keys still paint `.pressed` and list in the chips; they just don't
   * move the layer.)
   */
  function computeActiveLayer() {
    let target = 0;
    for (const pos of virtualHeld) {
      const slot = slotAt(pos);
      if (!slot) continue;
      const t = _layerTargetOf(slot.resolved);
      if (t !== null) target = t;
    }
    return target;
  }

  function slotAt(pos) {
    if (!layout) return null;
    const [r, c] = pos.split(":").map(Number);
    return layout.layers[0]?.rows[r]?.keys[c] || null;
  }

  // Layer-target extractor — returns the layer index N if this resolved cell
  // activates a layer when held, else null. Two kinds activate:
  //   - "layer-tap" (MO / LT): layer N is encoded in label_bottom as "L{N}"
  //   - "tap-dance" whose hold OR tap branch is MO(N): the branch label_top
  //     is "→L{N}" (set by the MO resolver). We prefer hold (the idiomatic
  //     place for layer activation in TD) and fall back to tap.
  // We don't try to dig LT(N, kc) out of a TD branch — that branch's
  // label_top is the inner key, not the layer arrow, so the layer info
  // doesn't reach this resolved struct. The MO-inside-TD case is the one
  // users hit in practice.
  function _layerTargetOf(resolved) {
    if (!resolved) return null;
    if (resolved.expanded_kind === "layer-tap") {
      const m = (resolved.label_bottom || "").match(/L(\d+)/);
      return m ? parseInt(m[1], 10) : null;
    }
    if (resolved.expanded_kind === "tap-dance") {
      const hold = resolved.hold || "";
      const tap = resolved.tap || "";
      const m = hold.match(/→L(\d+)/) || tap.match(/→L(\d+)/);
      return m ? parseInt(m[1], 10) : null;
    }
    return null;
  }

  // ── Layer-name lookup ──────────────────────────────────────────────
  // Friendly layer-index → name, for the status bar.
  const _LAYER_NAMES = ["BASE", "NAV", "NUM", "SYM", "FUNC", ""];
  const layerName = (i) => _LAYER_NAMES[i] || "";

  function buildHeldChips() {
    const physChips = [...heldKeys].map((k) => {
      const name = chipNameFor(k);
      const slot = findOnBaseLayer(k);
      const r = slot?.resolved;
      if (r?.expanded_kind === "layer-tap") {
        const m = (r.label_bottom || "").match(/L(\d+)/);
        const target = m ? parseInt(m[1], 10) : null;
        const nice = target !== null ? `L${target}${layerName(target) ? ` ${layerName(target)}` : ""}` : "?";
        return `<span class="chip chip-layer">${escapeHtml(name)} <span class="chip-arrow">→</span> ${escapeHtml(nice)}</span>`;
      }
      if (r?.expanded_kind === "mod-tap") {
        return `<span class="chip chip-mod">${escapeHtml(name)} <span class="chip-arrow">→</span> ${escapeHtml(r.hold || "")}</span>`;
      }
      const isMod = ["shift", "ctrl", "alt", "cmd"].includes(k.toLowerCase());
      return `<span class="chip ${isMod ? "chip-bare-mod" : ""}">${escapeHtml(name)}</span>`;
    });

    const virtChips = [...virtualHeld].map((pos) => {
      const slot = slotAt(pos);
      if (!slot) return "";
      const r = slot.resolved;
      const baseName = r.label_top || "?";
      const target = _layerTargetOf(r);
      if (target !== null) {
        const nice = `L${target}${layerName(target) ? ` ${layerName(target)}` : ""}`;
        return `<span class="chip chip-layer chip-virtual">${escapeHtml(baseName)} <span class="chip-arrow">→</span> ${escapeHtml(nice)} <span class="chip-virtual-tag">click</span></span>`;
      }
      return `<span class="chip chip-virtual">${escapeHtml(baseName)} <span class="chip-virtual-tag">click</span></span>`;
    });

    if (physChips.length === 0 && virtChips.length === 0) {
      return `<span class="chip chip-empty">none</span>`;
    }
    return [...physChips, ...virtChips].join("");
  }

  /**
   * Add `.pressed` to every BASE-layer slot that the held keys could be
   * coming from. Crucially we light up the SLOT position (via row/col),
   * which works regardless of which layer's content the grid is currently
   * rendering — so holding Tab on LT1 will glow even when the grid has
   * switched to NAV (where that position is TRN).
   */
  /**
   * When a combo with a MODIFIED output fires (e.g. C+V → Ctrl+Space), QMK
   * emits the modifier(s) + key, so heldKeys looks like {ctrl, space}. That is
   * the combo OUTPUT, not two separate physical presses — so we attribute it to
   * the combo instead of reverse-mapping ctrl/space onto unrelated base keys
   * (the Space cell + whatever holds Ctrl). Returns the matching combo or null.
   *
   * Scoped to modified outputs only: a plain single-key combo output (Esc, "{")
   * is genuinely indistinguishable from tapping that key, so we leave those to
   * the existing label-based highlight.
   */
  function comboFromHeldChord() {
    if (!layout || !Array.isArray(layout.combo) || heldKeys.size < 2) return null;
    const mods = new Set();
    const bases = [];
    for (const h of heldKeys) {
      const m = MOD_NAMES[h.toLowerCase()];
      if (m) mods.add(m);
      else bases.push(labelFor(h) || h);
    }
    if (mods.size === 0 || bases.length !== 1) return null;
    const baseLabel = bases[0];
    for (const c of layout.combo) {
      if (!Array.isArray(c.triggers) || c.triggers.length === 0) continue;
      const parts = (c.output_label || "").split("+");
      if (parts.length < 2) continue; // output has no modifier
      if (parts[parts.length - 1] !== baseLabel) continue;
      const cMods = new Set(parts.slice(0, -1));
      if (cMods.size !== mods.size) continue;
      let ok = true;
      for (const m of cMods) if (!mods.has(m)) { ok = false; break; }
      if (ok) return c;
    }
    return null;
  }

  // ── DOM cache + incremental updates ────────────────────────────────
  //
  // A full render() rebuilds the grid via innerHTML — far too expensive to
  // run per WS key event (fast typing fires 20+ events/sec, and each one
  // used to rebuild the entire grid then re-scan it with querySelectorAll).
  // Instead we cache cell references after every full render; key events
  // only touch classes and the chips strip, and consecutive events within
  // one frame are coalesced via requestAnimationFrame.
  let dom = null;          // { gridRoot, cells, labelCells, comboRows, chipsEl }
  let _pressedCells = [];  // elements currently carrying .pressed/.pressed-virtual
  let _comboLit = [];      // elements currently carrying .combo-highlight/.combo-active

  function buildDomCache() {
    const gridRoot = root.querySelector(".keyboard");
    if (!gridRoot) { dom = null; return; }
    // "r:c" → cell element. Positional col index, matching the previous
    // `rowEl.querySelectorAll(".key")[col]` lookup semantics.
    const cells = new Map();
    gridRoot.querySelectorAll(".row").forEach((rowEl) => {
      const rowCls = [...rowEl.classList].find((c) => /^row-\d+$/.test(c));
      if (!rowCls) return;
      const r = rowCls.slice(4);
      rowEl.querySelectorAll(".key").forEach((cell, i) => cells.set(`${r}:${i}`, cell));
    });
    // label_top text → [cells], for combo highlighting without re-reading
    // textContent on every event.
    const labelCells = new Map();
    gridRoot.querySelectorAll(".key").forEach((cell) => {
      const top = cell.querySelector(".label-top")?.textContent?.trim();
      if (!top) return;
      if (!labelCells.has(top)) labelCells.set(top, []);
      labelCells.get(top).push(cell);
    });
    const comboRows = new Map(); // combo index (string) → legend row element
    root.querySelectorAll(".combo-row").forEach((el) => {
      comboRows.set(el.dataset.comboIndex, el);
    });
    dom = {
      gridRoot,
      cells,
      labelCells,
      comboRows,
      chipsEl: root.querySelector(".held-chips"),
    };
    _pressedCells = [];
    _comboLit = [];
  }

  function applyPressed() {
    if (!dom) return;
    // Clear BOTH classes so the amber virtual marker disappears on release.
    for (const el of _pressedCells) {
      el.classList.remove("pressed");
      el.classList.remove("pressed-virtual");
    }
    _pressedCells = [];
    if (heldKeys.size === 0 && virtualHeld.size === 0) return;

    // If the held keys are actually a combo's modified output, don't paint the
    // reverse-mapped base cells — the combo highlight lights the trigger keys.
    const chordCombo = comboFromHeldChord();

    const lit = new Set();
    for (const held of chordCombo ? [] : heldKeys) {
      const slots = findAllBaseSlots(held);
      for (const s of slots) {
        const cellKey = `${s.row}:${s.col}`;
        if (lit.has(cellKey)) continue;
        lit.add(cellKey);
        const cell = dom.cells.get(cellKey);
        if (cell) {
          cell.classList.add("pressed");
          _pressedCells.push(cell);
        }
      }
    }
    // Virtual holds: ONLY add the dedicated `.pressed-virtual` class. Adding
    // `.pressed` too made the `.kind-transparent.pressed` rule (higher
    // specificity) clobber the amber styling on TRN slots — which is exactly
    // the case LT clicks hit, since the freshly-active layer renders that
    // slot as TRN.
    for (const pos of virtualHeld) {
      if (lit.has(pos)) continue;
      lit.add(pos);
      const cell = dom.cells.get(pos);
      if (cell) {
        cell.classList.add("pressed-virtual");
        _pressedCells.push(cell);
      }
    }
  }

  function render() {
    if (!layout) {
      root.innerHTML = `<p class="error">layout load failed</p>`;
      return;
    }
    const deco = window.gridRender.decorationsFor(layout);
    const gridHtml = window.gridRender.renderLayer(layout.layers[activeLayer], deco);
    const layerLbl = layerName(activeLayer);
    root.innerHTML = `
      <div class="interactive-status">
        <span>helper:</span>
        <span class="status status-${helperStatus}">●</span>
        <span class="status-label">${helperStatus}</span>
        <span class="sep">·</span>
        <span>layer: <strong>${activeLayer}${layerLbl ? ` ${layerLbl}` : ""}</strong></span>
      </div>
      ${gridHtml}
      <div class="held-chips held-chips-big" aria-label="currently held keys">
        ${buildHeldChips()}
      </div>
      ${buildComboLegend()}`;
    buildDomCache();
    if (dom) {
      applyPressed();
      applyComboHighlight();
      markLayerClickableCells(dom.gridRoot);
    }
  }

  /** Cheap per-key-event refresh: chips + pressed/combo classes only. */
  function updateDynamic() {
    if (!dom) {
      render();
      return;
    }
    if (dom.chipsEl) dom.chipsEl.innerHTML = buildHeldChips();
    applyPressed();
    applyComboHighlight();
  }

  // Coalesce bursts of WS events into one paint per animation frame.
  let _rafId = null;
  let _needFullRender = false;
  function scheduleUpdate(full) {
    if (full) _needFullRender = true;
    if (_rafId !== null) return;
    _rafId = requestAnimationFrame(() => {
      _rafId = null;
      const doFull = _needFullRender;
      _needFullRender = false;
      if (doFull) render();
      else updateDynamic();
    });
  }

  // Paint `.has-layer-target` on every cell whose BASE-layer slot is a
  // tap-dance with a layer-key branch, so CSS shows the pointer cursor
  // matching the existing MO/LT affordance. We key off BASE regardless
  // of which layer is currently visible — the click handler also reads
  // BASE — so the hint stays consistent when previewing other layers.
  function markLayerClickableCells(gridRoot) {
    gridRoot.querySelectorAll(".key.has-layer-target").forEach((el) =>
      el.classList.remove("has-layer-target")
    );
    const base = layout?.layers[0];
    if (!base) return;
    for (let r = 0; r < base.rows.length; r++) {
      const rowEl = gridRoot.querySelector(`.row.row-${r}`);
      if (!rowEl) continue;
      const cells = rowEl.querySelectorAll(".key");
      for (let c = 0; c < base.rows[r].keys.length; c++) {
        const k = base.rows[r].keys[c];
        if (!k || k.resolved.expanded_kind !== "tap-dance") continue;
        if (_layerTargetOf(k.resolved) === null) continue;
        if (cells[c]) cells[c].classList.add("has-layer-target");
      }
    }
  }

  // ── Combo legend ─────────────────────────────────────────────────────
  //
  // We render the legend as part of every full render() — re-rendering is
  // cheap and avoids dual sources of truth on which combos are active.
  // Each row carries `data-combo-index` so applyComboHighlight can light
  // it up without re-parsing the legend text.

  function buildComboLegend() {
    const combos = (layout?.combo || []).filter(
      (c) => Array.isArray(c.triggers) && c.triggers.length > 0
    );
    if (combos.length === 0) return "";
    const rows = combos
      .map((c) => {
        const triggers = (c.trigger_labels || c.triggers).map(escapeHtml).join(" + ");
        const output = escapeHtml(c.output_label || c.output || "?");
        return `
          <div class="combo-row" data-combo-index="${c.index}">
            <span class="combo-index">C${c.index}</span>
            <span class="combo-trigger">${triggers}</span>
            <span class="combo-arrow">→</span>
            <span class="combo-output">${output}</span>
          </div>`;
      })
      .join("");
    return `
      <section class="combo-legend" aria-label="configured combos">
        <h3 class="combo-legend-title">Combos</h3>
        ${rows}
      </section>`;
  }

  /**
   * Highlight combo rows + the participating cells in the grid whenever
   * any of the combo's triggers OR its output are currently held.
   *
   * QMK firmware fires the combo by swallowing the trigger keydowns and
   * only emitting the output, so when J+K → Esc fires, macOS sees just
   * "escape". We treat output-held as combo-active so the user can still
   * see WHICH combo fired by looking at the lit legend row.
   *
   * Output-held is necessarily ambiguous when the combo output is also a
   * key the user could press alone (e.g. Esc is reachable via TD(1) tap).
   * We accept that — over-highlighting is less confusing than silently
   * dropping the combo annotation.
   */
  function applyComboHighlight() {
    if (!dom) return;
    for (const el of _comboLit) {
      el.classList.remove("combo-highlight");
      el.classList.remove("combo-active");
    }
    _comboLit = [];
    if (!layout || !Array.isArray(layout.combo) || heldKeys.size === 0) return;

    const heldLabels = new Set();
    for (const h of heldKeys) {
      const l = labelFor(h);
      if (l) heldLabels.add(l);
    }
    // Combos whose output carries a modifier (e.g. Ctrl+Space) arrive as
    // {ctrl, space} — not a single "Ctrl+Space" label — so match them by chord.
    const chordCombo = comboFromHeldChord();

    for (const c of layout.combo) {
      if (!Array.isArray(c.triggers) || c.triggers.length === 0) continue;
      const triggerLabels = c.trigger_labels || c.triggers;
      const outputLabel = c.output_label || c.output;
      const triggerHit = triggerLabels.some((l) => heldLabels.has(l));
      const outputHit =
        (outputLabel && heldLabels.has(outputLabel)) ||
        (chordCombo && chordCombo.index === c.index);
      if (!triggerHit && !outputHit) continue;

      const row = dom.comboRows.get(String(c.index));
      if (row) {
        row.classList.add("combo-active");
        _comboLit.push(row);
      }

      // Light up every cell whose label_top matches a trigger or the output.
      // We match by the rendered top label rather than raw because the
      // output may live on a TD branch (e.g. KC_ESCAPE is TD(1).tap, so
      // its cell's raw is "TD(1)" — not directly comparable). Labels were
      // indexed once in buildDomCache instead of re-read per event.
      for (const label of [...triggerLabels, outputLabel]) {
        if (!label) continue;
        for (const cell of dom.labelCells.get(label) || []) {
          if (!cell.classList.contains("combo-highlight")) {
            cell.classList.add("combo-highlight");
            _comboLit.push(cell);
          }
        }
      }
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // ── WebSocket connection lifecycle ─────────────────────────────────

  function connect() {
    const url =
      (location.protocol === "https:" ? "wss://" : "ws://") +
      location.host +
      "/api/live";
    socket = new WebSocket(url);

    socket.onopen = () => {
      helperStatus = "connected";
      reconnectDelay = 1000;
      render();
    };

    socket.onmessage = (e) => {
      let msg;
      try {
        msg = JSON.parse(e.data);
      } catch {
        return;
      }
      if (msg.type === "helper_disconnected") {
        helperStatus = "disconnected";
        render();
        return;
      }
      if (msg.type === "down") {
        heldKeys.add(msg.key.toLowerCase());
      } else if (msg.type === "up") {
        heldKeys.delete(msg.key.toLowerCase());
      }
      // Layer only changes via virtual (click) holds, so key events almost
      // always take the cheap incremental path; keep the check as a guard.
      const newLayer = computeActiveLayer();
      const layerChanged = newLayer !== activeLayer;
      if (layerChanged) activeLayer = newLayer;
      scheduleUpdate(layerChanged);
    };

    socket.onerror = () => {
      helperStatus = "error";
      render();
    };

    socket.onclose = () => {
      helperStatus = "disconnected";
      render();
      // Reconnect with capped exponential backoff so launchd restarts pick up.
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 10000);
    };
  }

  async function init() {
    await ensureLayout();
    if (window.keyAliases) await window.keyAliases.ensure();
    render();
    connect();
    if (window.keyTooltip) {
      window.keyTooltip.setupKeyTooltips(root, () => layout);
    }
    wireClickToSimulate();
    // Re-render when a key name is added/edited on the Key Name Map page.
    if (window.keyAliases) window.keyAliases.onChange(render);
  }

  /**
   * Click a layer-activating cell to toggle a virtual hold. This exists
   * because QMK firmware emits no macOS event during a real LT / MO hold
   * — it swaps the active layer internally — so the only way to preview
   * a layered layout without typing on it is to click. We accept any cell
   * whose `_layerTargetOf` returns a layer index: plain layer-tap (LT, MO)
   * AND tap-dance cells whose hold (or tap) branch is a layer key. We
   * still reject mod-tap and plain-mod cells: those modifiers fire fine
   * via a physical press, and click-simulating them would be confusing
   * (e.g. "I clicked Hyper, does that block my real Shift?").
   */
  function wireClickToSimulate() {
    root.addEventListener("click", (e) => {
      const cell = e.target.closest(".key");
      if (!cell) return;
      const rowEl = cell.closest(".row");
      if (!rowEl) return;
      const rowMatch = [...rowEl.classList].find((c) => c.startsWith("row-"));
      if (!rowMatch) return;
      const row = parseInt(rowMatch.slice(4), 10);
      const col = parseInt(cell.dataset.col, 10);
      if (Number.isNaN(row) || Number.isNaN(col) || !layout) return;
      const baseSlot = layout.layers[0]?.rows[row]?.keys[col];
      if (!baseSlot) return;
      if (_layerTargetOf(baseSlot.resolved) === null) return;
      const pos = `${row}:${col}`;
      if (virtualHeld.has(pos)) virtualHeld.delete(pos);
      else virtualHeld.add(pos);
      const newLayer = computeActiveLayer();
      if (newLayer !== activeLayer) activeLayer = newLayer;
      render();
    });
  }

  // Lazy-load: only fetch + connect once the Interactive tab is opened.
  document
    .querySelector('nav button[data-view="interactive"]')
    .addEventListener("click", () => {
      if (!initialized) {
        initialized = true;
        init();
      }
    });

  // Public surface for cross-module coordination (vial-upload.js).
  window.interactiveSim = {
    refresh: async () => {
      if (!initialized) return;
      layout = null;
      await ensureLayout();
      render();
    },
  };
})();
