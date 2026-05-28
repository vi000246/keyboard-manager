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

    const matches = [];
    for (let r = 0; r < base.rows.length; r++) {
      const row = base.rows[r];
      for (let c = 0; c < row.keys.length; c++) {
        const k = row.keys[c];
        if (!k) continue;
        const res = k.resolved;
        const kind = res.expanded_kind;

        // Direct label match (covers plain letters, layer-tap tap, mod-tap tap, etc.).
        if (label && res.label_top === label) {
          matches.push({ key: k, row: r, col: c, kind, reason: "label" });
          continue;
        }

        // Modifier-by-hold: holding "cmd" highlights any position whose hold
        // action sends Cmd — covers LGUI_T(...), ALL_T(...) (Hyper expands),
        // TD(N) whose hold branch is a modifier, etc.
        if (modName) {
          const hold = res.hold || "";
          const holdMatchesMod =
            hold === modName ||
            (hold === "Hyper" && ["Cmd", "Ctrl", "Alt", "Shift"].includes(modName)) ||
            (hold === "Meh"   && ["Ctrl", "Alt", "Shift"].includes(modName));
          if ((kind === "mod-tap" || kind === "tap-dance") && holdMatchesMod) {
            matches.push({ key: k, row: r, col: c, kind, reason: "hold-mod" });
            continue;
          }
          // Plain modifier keys (KC_LSHIFT label="LShift", KC_RSHIFT="RShift").
          if (kind === "plain" && res.label_top && res.label_top.endsWith(modName)) {
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
   * If any held key is a layer-tap on BASE, the displayed layer follows its
   * hold target. Last-held wins on conflict (rare in practice).
   */
  function computeActiveLayer() {
    let target = 0;
    for (const held of heldKeys) {
      const slot = findOnBaseLayer(held);
      if (!slot || slot.resolved.expanded_kind !== "layer-tap") continue;
      const m = (slot.resolved.label_bottom || "").match(/L(\d+)/);
      if (m) target = parseInt(m[1], 10);
    }
    return target;
  }

  // ── Layer-name lookup ──────────────────────────────────────────────
  // Friendly layer-index → name, for the status bar.
  const _LAYER_NAMES = ["BASE", "NAV", "", "", "MEDIA", ""];
  const layerName = (i) => _LAYER_NAMES[i] || "";

  function buildHeldChips() {
    if (heldKeys.size === 0) {
      return `<span class="chip chip-empty">none</span>`;
    }
    return [...heldKeys]
      .map((k) => {
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
        // Plain modifier (shift, cmd, ctrl, alt) — render as a tag without arrow.
        const isMod = ["shift", "ctrl", "alt", "cmd"].includes(k.toLowerCase());
        return `<span class="chip ${isMod ? "chip-bare-mod" : ""}">${escapeHtml(name)}</span>`;
      })
      .join("");
  }

  /**
   * Add `.pressed` to every BASE-layer slot that the held keys could be
   * coming from. Crucially we light up the SLOT position (via row/col),
   * which works regardless of which layer's content the grid is currently
   * rendering — so holding Tab on LT1 will glow even when the grid has
   * switched to NAV (where that position is TRN).
   */
  function applyPressed(gridRoot) {
    gridRoot.querySelectorAll(".key.pressed").forEach((k) =>
      k.classList.remove("pressed")
    );
    if (heldKeys.size === 0) return;

    const lit = new Set();
    for (const held of heldKeys) {
      const slots = findAllBaseSlots(held);
      for (const s of slots) {
        const cellKey = `${s.row}:${s.col}`;
        if (lit.has(cellKey)) continue;
        lit.add(cellKey);
        const rowEl = gridRoot.querySelector(`.row.row-${s.row}`);
        if (!rowEl) continue;
        const cellAtCol = rowEl.querySelectorAll(".key")[s.col];
        if (cellAtCol) cellAtCol.classList.add("pressed");
      }
    }
  }

  function render() {
    if (!layout) {
      root.innerHTML = `<p class="error">layout load failed</p>`;
      return;
    }
    const gridHtml = window.gridRender.renderLayer(layout.layers[activeLayer]);
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
      </div>`;
    const gridRoot = root.querySelector(".keyboard");
    if (gridRoot) applyPressed(gridRoot);
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
      const newLayer = computeActiveLayer();
      if (newLayer !== activeLayer) activeLayer = newLayer;
      render();
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
    render();
    connect();
    // One-time hover-tooltip wire-up. Delegation on the section means the
    // listener survives the frequent innerHTML re-renders triggered by WS.
    if (window.keyTooltip) {
      window.keyTooltip.setupKeyTooltips(root, () => layout);
    }
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
