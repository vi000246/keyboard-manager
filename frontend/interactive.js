// interactive.js — Interactive Simulator: real-time grid that responds to
// the user's physical keystrokes via the /api/live WebSocket.
//
// Behavior:
//   - On WS message {type: "down", key, ...}, add `key` to a heldKeys set.
//     If the BASE-layer position of that key has a layer-tap resolved kind,
//     switch the displayed layer to the hold target.
//   - On {type: "up", key, ...}, remove from heldKeys and recompute the
//     active layer (falls back to BASE when no layer-trigger is held).
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

  /**
   * Find which layer should be active given the currently held keys.
   * Looks at the BASE layer's resolved data: if any held key sits on a
   * layer-tap slot, the hold target wins. With multiple held layer keys,
   * the last one to arrive wins (it's last in the iteration order).
   */
  function computeActiveLayer() {
    if (!layout) return 0;
    let target = 0;
    const base = layout.layers[0];
    for (const held of heldKeys) {
      const label = labelFor(held);
      if (label === null) continue;
      for (const row of base.rows) {
        for (const k of row.keys) {
          if (!k) continue;
          const r = k.resolved;
          if (r.expanded_kind !== "layer-tap") continue;
          if (r.label_top !== label) continue;
          const m = (r.label_bottom || "").match(/L(\d+)/);
          if (m) target = parseInt(m[1], 10);
        }
      }
    }
    return target;
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
  };

  function labelFor(eventKey) {
    const k = eventKey.toLowerCase();
    if (k in _EVENT_TO_LABEL) return _EVENT_TO_LABEL[k];
    if (k.length === 1) return k.toUpperCase();
    return null;
  }

  function render() {
    if (!layout) {
      root.innerHTML = `<p class="error">layout load failed</p>`;
      return;
    }
    const gridHtml = window.gridRender.renderLayer(layout.layers[activeLayer]);
    const held = [...heldKeys].join(", ") || "(none)";
    root.innerHTML = `
      <div class="interactive-status">
        <span>helper:</span>
        <span class="status status-${helperStatus}">●</span>
        <span class="status-label">${helperStatus}</span>
        <span class="sep">·</span>
        <span>active layer: <strong>${activeLayer}</strong></span>
        <span class="sep">·</span>
        <span>held: <code>${escapeHtml(held)}</code></span>
      </div>
      ${gridHtml}`;
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
})();
