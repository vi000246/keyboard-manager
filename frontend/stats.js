// stats.js — Stats dashboard: heatmap on layout + per-app/kind Top-N table.
(function () {
  "use strict";

  const root = document.getElementById("view-stats");
  // Layer dropdown now lives inside this view (used to be a global element
  // in the header — only Stats really needed it).
  const LAYER_NAMES = ["BASE", "NAV", "NUM", "SYM", "FUNC", ""];
  let apps = [];
  let layout = null;
  let loaded = false;
  let lastHeatmap = null;
  let lastStats = null;
  let currentLayer = 0;

  function getLayerSelect() {
    return root.querySelector("#stats-layer");
  }

  async function loadApps() {
    const r = await fetch("/api/apps");
    apps = r.ok ? await r.json() : [];
    apps.sort((a, b) => (a.bundle_id < b.bundle_id ? -1 : 1));
  }

  async function loadLayout() {
    if (layout) return layout;
    const r = await fetch("/api/layout");
    layout = r.ok ? await r.json() : null;
    return layout;
  }

  async function loadStats(app, kind, keyQuery) {
    const u = new URL("/api/stats", location.origin);
    if (app) u.searchParams.set("app", app);
    u.searchParams.set("kind", kind);
    u.searchParams.set("top", "30");
    // When the user enters a key filter, send it through — backend lifts
    // the top cap so even rare matches (count=1) show up.
    if (keyQuery) u.searchParams.set("key", keyQuery);
    const r = await fetch(u);
    return r.ok ? await r.json() : null;
  }

  // ── Render fragments ────────────────────────────────────────────────

  // Last user-entered search query — preserved across re-renders.
  let appFilter = "";
  // Free-text filter on key/modifiers — e.g. "cmd" surfaces every Cmd combo
  // regardless of count rank (backend bypasses top-N cap when this is set).
  let keyFilter = "";
  // Debounce + focus-restore plumbing: typing fires a refresh that wipes
  // the toolbar, so we set a flag to put focus + caret back on the input.
  let _keyFilterTimer = null;
  let _focusKeyFilter = false;

  function filteredApps() {
    if (!appFilter) return apps;
    const q = appFilter.toLowerCase();
    return apps.filter(
      (a) =>
        (a.display_name || "").toLowerCase().includes(q) ||
        a.bundle_id.toLowerCase().includes(q) ||
        (a.bucket || "").toLowerCase().includes(q)
    );
  }

  function renderToolbar(currentApp, currentKind) {
    const opts = ['<option value="">All apps</option>'].concat(
      filteredApps().map((a) => {
        const sel = a.bundle_id === currentApp ? "selected" : "";
        const count = (a.total_count || 0).toLocaleString();
        const bucket = a.bucket ? ` · ${a.bucket}` : "";
        const label = `${a.display_name}${bucket}  (${count})`;
        return `<option value="${escapeAttr(a.bundle_id)}" ${sel}>${escapeHtml(label)}</option>`;
      })
    ).join("");
    const kinds = [
      ["single", "Single keys"],
      ["mod", "Mod combos"],
      ["all", "All"],
    ]
      .map(([v, l]) => `<option value="${v}" ${v === currentKind ? "selected" : ""}>${l}</option>`)
      .join("");
    const layerOpts = LAYER_NAMES.map((name, i) => {
      const label = name ? `${i} — ${name}` : `${i}`;
      const sel = i === currentLayer ? "selected" : "";
      return `<option value="${i}" ${sel}>${label}</option>`;
    }).join("");
    return `
      <div class="stats-toolbar">
        <label class="app-picker">
          App:
          <input id="stats-app-search" type="search" placeholder="filter…"
                 value="${escapeAttr(appFilter)}" autocomplete="off">
          <select id="stats-app">${opts}</select>
        </label>
        <label>Kind: <select id="stats-kind">${kinds}</select></label>
        <label>Key:
          <input id="stats-key-filter" type="search"
                 placeholder="cmd / c / shift…"
                 value="${escapeAttr(keyFilter)}" autocomplete="off">
        </label>
        <label>Layer: <select id="stats-layer">${layerOpts}</select></label>
        <span id="helper-status-slot"></span>
      </div>`;
  }

  // ── Helper status badge ────────────────────────────────────────────

  let helperPollTimer = null;
  let lastHelperStatus = null;

  async function pollHelperStatus() {
    try {
      const r = await fetch("/api/helper/status");
      if (!r.ok) return;
      lastHelperStatus = await r.json();
      renderHelperBadge();
    } catch {
      // Backend probably restarting — keep last state on screen
    }
  }

  function renderHelperBadge() {
    const slot = root.querySelector("#helper-status-slot");
    if (!slot) return;
    if (!lastHelperStatus) {
      slot.innerHTML = `<span class="helper-badge status-loading">helper: …</span>`;
      return;
    }
    const s = lastHelperStatus;
    let cls, label, detail;
    if (!s.process_running) {
      cls = "disconnected"; label = "disconnected";
      detail = "helper not reachable — check launchd";
    } else if (s.recently_captured) {
      cls = "active"; label = "active";
      detail = `last event ${s.seconds_since_last_event}s ago`;
    } else if (s.last_event_ts) {
      cls = "idle"; label = "idle";
      detail = `no events in ${s.seconds_since_last_event}s`;
    } else {
      cls = "idle"; label = "no events yet";
      detail = "helper reachable but DB empty for native_helper";
    }
    slot.innerHTML = `
      <span class="helper-badge status-${cls}" title="${escapeAttr(detail)}">
        helper: <strong>${label}</strong>
      </span>`;
  }

  // Whether polling has been requested (i.e. the Stats view was opened) —
  // lets the visibilitychange handler know to resume after a hidden tab.
  let helperPollWanted = false;

  function startHelperPolling() {
    helperPollWanted = true;
    if (helperPollTimer || document.hidden) return;
    pollHelperStatus();
    helperPollTimer = setInterval(pollHelperStatus, 5000);
  }

  // Don't poll /api/helper/status while the tab is hidden — a long-lived
  // background tab was probing the helper WS every 5s for nothing.
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (helperPollTimer) {
        clearInterval(helperPollTimer);
        helperPollTimer = null;
      }
    } else if (helperPollWanted) {
      startHelperPolling();
    }
  });

  function renderHeatmapSection(heatmap) {
    if (!heatmap) return `<p class="placeholder">heatmap unavailable</p>`;
    return `
      <div class="heatmap-section">
        <p class="meta">
          Shortcut heatmap — combos + functional keys (letters / digits /
          punctuation excluded so typing volume doesn't drown out hotkeys).
          Modifiers (Cmd/Shift/Ctrl/Alt) credit their physical key positions.
        </p>
        <p class="meta">
          Coverage:
          <strong>${heatmap.coverage_pct.toFixed(2)}%</strong>
          (cells: ${heatmap.cells.length}, unmapped: ${heatmap.unmapped.length},
           max: ${heatmap.max_count.toLocaleString()})
        </p>
        <div id="stats-grid"></div>
      </div>`;
  }

  function renderTable(stats) {
    if (!stats) return `<p class="error">stats unavailable</p>`;
    if (!stats.rows.length) {
      return `<p class="placeholder">no data for this scope (total ${stats.total_events})</p>`;
    }
    const rows = stats.rows
      .map((r, i) => {
        const mods = r.modifiers ? `${r.modifiers}+` : "";
        // User-defined name for this shortcut, set in the Key Name Map and
        // keyed identically via keyAliases.statKey (see aliases.js).
        const name = window.keyAliases
          ? window.keyAliases.get(window.keyAliases.statKey(r.key, r.modifiers))
          : null;
        const nameHtml = name
          ? ` <span class="stat-alias">${escapeHtml(name)}</span>`
          : "";
        return `
          <tr data-key="${escapeAttr(r.key)}" data-mods="${escapeAttr(r.modifiers)}">
            <td class="rank">${i + 1}</td>
            <td class="count">${r.count.toLocaleString()}</td>
            <td class="pct">${r.pct.toFixed(2)}%</td>
            <td><code>${escapeHtml(mods + r.key)}</code>${nameHtml}</td>
          </tr>`;
      })
      .join("");
    return `
      <p class="meta">Total in scope: <strong>${stats.total_events.toLocaleString()}</strong></p>
      <table class="stats-table">
        <thead><tr><th>#</th><th>Count</th><th>%</th><th>Key</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  // ── Wiring ─────────────────────────────────────────────────────────

  async function refresh() {
    const sel = root.querySelector("#stats-app");
    const kindSel = root.querySelector("#stats-kind");
    const app = sel ? sel.value || null : null;
    const kind = kindSel ? kindSel.value : "single";

    const [stats, heatmap, lay] = await Promise.all([
      loadStats(app, kind, keyFilter),
      window.heatmap ? window.heatmap.loadHeatmap(app) : Promise.resolve(null),
      loadLayout(),
      // Names are looked up synchronously while building the table rows.
      window.keyAliases ? window.keyAliases.ensure() : Promise.resolve(),
    ]);
    lastStats = stats;
    lastHeatmap = heatmap;

    root.innerHTML =
      renderToolbar(app, kind) +
      renderHeatmapSection(heatmap) +
      renderTable(stats);

    // Render the keyboard grid for the currently-selected layer, then overlay
    const gridSlot = root.querySelector("#stats-grid");
    if (gridSlot && lay) {
      gridSlot.innerHTML = window.gridRender.renderLayer(lay.layers[currentLayer]);
      if (window.heatmap && heatmap) {
        window.heatmap.applyOverlay(gridSlot, heatmap, currentLayer);
      }
    }
    wire();
    renderHelperBadge();
    startHelperPolling();
    // Refresh wiped the toolbar; put focus + caret back on the key filter
    // if it was the trigger, so the user's typing flow stays uninterrupted.
    if (_focusKeyFilter) {
      const inp = root.querySelector("#stats-key-filter");
      if (inp) {
        inp.focus();
        const v = inp.value;
        inp.value = "";
        inp.value = v;
      }
      _focusKeyFilter = false;
    }
  }

  function reapplyOverlayForLayer() {
    const gridSlot = root.querySelector("#stats-grid");
    const sel = getLayerSelect();
    currentLayer = sel ? parseInt(sel.value, 10) || 0 : currentLayer;
    if (gridSlot && layout) {
      gridSlot.innerHTML = window.gridRender.renderLayer(layout.layers[currentLayer]);
      if (window.heatmap && lastHeatmap) {
        window.heatmap.applyOverlay(gridSlot, lastHeatmap, currentLayer);
      }
    }
  }

  function wire() {
    const sel = root.querySelector("#stats-app");
    const kindSel = root.querySelector("#stats-kind");
    const layerSel = root.querySelector("#stats-layer");
    const searchInput = root.querySelector("#stats-app-search");
    const keyFilterInput = root.querySelector("#stats-key-filter");
    if (sel) sel.addEventListener("change", refresh);
    if (kindSel) kindSel.addEventListener("change", refresh);
    if (layerSel) {
      layerSel.addEventListener("change", () => {
        currentLayer = parseInt(layerSel.value, 10) || 0;
        reapplyOverlayForLayer();
      });
    }
    if (searchInput) {
      searchInput.addEventListener("input", (e) => {
        appFilter = e.target.value;
        // Only re-render the dropdown — don't re-fetch stats while the user types.
        rerenderToolbarOnly(sel ? sel.value || null : null, kindSel ? kindSel.value : "single");
      });
    }
    if (keyFilterInput) {
      keyFilterInput.addEventListener("input", (e) => {
        const v = e.target.value;
        if (_keyFilterTimer) clearTimeout(_keyFilterTimer);
        _keyFilterTimer = setTimeout(() => {
          keyFilter = v;
          _focusKeyFilter = true;
          refresh();
        }, 300);
      });
    }

    // Bidirectional highlight
    const table = root.querySelector(".stats-table");
    const grid = root.querySelector("#stats-grid");
    if (grid && table) wireBidirectional(grid, table);
  }

  function rerenderToolbarOnly(currentApp, currentKind) {
    const toolbar = root.querySelector(".stats-toolbar");
    if (!toolbar) return;
    toolbar.outerHTML = renderToolbar(currentApp, currentKind);
    // Restore focus + caret position to the search input so typing isn't interrupted
    const restored = root.querySelector("#stats-app-search");
    if (restored) {
      restored.focus();
      // Put caret at end
      const v = restored.value;
      restored.value = "";
      restored.value = v;
    }
    // Re-wire just the new toolbar inputs
    const sel = root.querySelector("#stats-app");
    const kindSel = root.querySelector("#stats-kind");
    const layerSel = root.querySelector("#stats-layer");
    const searchInput = root.querySelector("#stats-app-search");
    const keyFilterInput = root.querySelector("#stats-key-filter");
    if (sel) sel.addEventListener("change", refresh);
    if (kindSel) kindSel.addEventListener("change", refresh);
    if (layerSel) {
      layerSel.addEventListener("change", () => {
        currentLayer = parseInt(layerSel.value, 10) || 0;
        reapplyOverlayForLayer();
      });
    }
    if (searchInput) {
      searchInput.addEventListener("input", (e) => {
        appFilter = e.target.value;
        rerenderToolbarOnly(sel ? sel.value || null : null, kindSel ? kindSel.value : "single");
      });
    }
    if (keyFilterInput) {
      keyFilterInput.addEventListener("input", (e) => {
        const v = e.target.value;
        if (_keyFilterTimer) clearTimeout(_keyFilterTimer);
        _keyFilterTimer = setTimeout(() => {
          keyFilter = v;
          _focusKeyFilter = true;
          refresh();
        }, 300);
      });
    }
    // The badge lives inside the toolbar — restore it after the re-render
    renderHelperBadge();
  }

  function wireBidirectional(gridEl, tableEl) {
    gridEl.addEventListener("click", (e) => {
      const k = e.target.closest(".key");
      if (!k) return;
      const top = k.querySelector(".label-top")?.textContent?.trim();
      if (!top) return;
      tableEl.querySelectorAll("tr.highlighted").forEach((r) => r.classList.remove("highlighted"));
      const match = [...tableEl.querySelectorAll("tbody tr")].find(
        (r) => r.dataset.key && normalizeForCompare(r.dataset.key) === normalizeForCompare(top),
      );
      if (match) {
        match.classList.add("highlighted");
        match.scrollIntoView({ block: "center", behavior: "smooth" });
      }
    });

    tableEl.addEventListener("click", (e) => {
      const tr = e.target.closest("tr[data-key]");
      if (!tr) return;
      const key = tr.dataset.key;
      gridEl.querySelectorAll(".key.flash").forEach((k) => k.classList.remove("flash"));
      const target = [...gridEl.querySelectorAll(".key")].find(
        (k) =>
          normalizeForCompare(k.querySelector(".label-top")?.textContent?.trim() ?? "") ===
          normalizeForCompare(key),
      );
      if (target) {
        target.classList.add("flash");
        setTimeout(() => target.classList.remove("flash"), 1200);
      }
    });
  }

  // macOS event keys are lowercase / abbreviated; keyboard grid labels use
  // uppercase + symbols. Normalize both to a comparable form.
  const _CMP_ALIASES = {
    space: "space",
    return: "enter",
    enter: "enter",
    delete: "bksp",
    bksp: "bksp",
    forwarddelete: "del",
    del: "del",
    escape: "esc",
    esc: "esc",
    tab: "tab",
    left: "←",
    right: "→",
    up: "↑",
    down: "↓",
    pageup: "pgup",
    pgup: "pgup",
    pagedown: "pgdn",
    pgdn: "pgdn",
  };

  function normalizeForCompare(s) {
    const v = String(s).toLowerCase();
    return _CMP_ALIASES[v] ?? v;
  }

  async function init() {
    await Promise.all([loadApps(), loadLayout()]);
    refresh();
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function escapeAttr(s) {
    return escapeHtml(s).replace(/"/g, "&quot;");
  }

  // Lazy load
  document.querySelector('nav button[data-view="stats"]').addEventListener("click", () => {
    if (!loaded) {
      loaded = true;
      init();
    }
  });

  // (The Stats-page layer dropdown is wired inside `wire()` now — it lives
  //  in the toolbar, not the global header.)

  // Public surface for cross-module coordination (vial-upload.js).
  window.statsDashboard = {
    refresh: async () => {
      if (!loaded) return;
      // Invalidate the cached layout so the new .vil is picked up.
      layout = null;
      await refresh();
    },
  };
})();
