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

  /**
   * For a held event-key, find its BASE-layer slot. Used both for layer
   * resolution and for building the chip's "what does hold do" preview.
   */
  function findOnBaseLayer(eventKey) {
    if (!layout) return null;
    const label = labelFor(eventKey);
    if (label === null) return null;
    const base = layout.layers[0];
    for (const row of base.rows) {
      for (const k of row.keys) {
        if (k && k.resolved.label_top === label) return k;
      }
    }
    return null;
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
  // Mirrors the <option> labels in index.html for the global layer-select,
  // so the status bar can show "NAV" instead of just "1".
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

  /** Add `.pressed` to every grid cell whose label_top matches a held key. */
  function applyPressed(gridRoot) {
    gridRoot.querySelectorAll(".key.pressed").forEach((k) =>
      k.classList.remove("pressed")
    );
    if (heldKeys.size === 0) return;
    // Walk the cells once; build label→[elements] map.
    const cells = gridRoot.querySelectorAll(".key");
    for (const held of heldKeys) {
      const label = labelFor(held);
      if (label === null) continue;
      for (const k of cells) {
        if (k.querySelector(".label-top")?.textContent?.trim() === label) {
          k.classList.add("pressed");
        }
      }
      // If the layout switched to a layer where the trigger position renders
      // as TRN/empty, still light up the BASE slot's (row, col) for feedback.
      const slot = findOnBaseLayer(held);
      if (slot) {
        // BASE layer's flat (row, col) — walk rendered .row .key cells.
        const baseLayer = layout.layers[0];
        let baseRow = -1, baseCol = -1;
        for (let r = 0; r < baseLayer.rows.length; r++) {
          for (let c = 0; c < baseLayer.rows[r].keys.length; c++) {
            if (baseLayer.rows[r].keys[c] === slot) {
              baseRow = r;
              baseCol = c;
              break;
            }
          }
          if (baseRow !== -1) break;
        }
        if (baseRow !== -1) {
          const rowEl = gridRoot.querySelector(`.row.row-${baseRow}`);
          if (rowEl) {
            const cellAtCol = rowEl.querySelectorAll(".key")[baseCol];
            if (cellAtCol) cellAtCol.classList.add("pressed");
          }
        }
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
      <div class="held-chips" aria-label="currently held keys">
        ${buildHeldChips()}
      </div>
      ${gridHtml}`;
    // Paint the grid AFTER it's in the DOM.
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
