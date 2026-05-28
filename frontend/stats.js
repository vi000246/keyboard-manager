// stats.js — Stats dashboard: per-app and global top-N tables.
// Heatmap overlay (M3) extends this with a grid view in heatmap.js.
(function () {
  "use strict";

  const root = document.getElementById("view-stats");
  let apps = [];
  let loaded = false;

  async function loadApps() {
    const r = await fetch("/api/apps");
    apps = r.ok ? await r.json() : [];
    apps.sort((a, b) => (a.bundle_id < b.bundle_id ? -1 : 1));
  }

  async function loadStats(app, kind) {
    const u = new URL("/api/stats", location.origin);
    if (app) u.searchParams.set("app", app);
    u.searchParams.set("kind", kind);
    u.searchParams.set("top", "30");
    const r = await fetch(u);
    return r.ok ? await r.json() : null;
  }

  function renderToolbar(currentApp, currentKind) {
    const opts = ['<option value="">All apps</option>']
      .concat(
        apps.map((a) => {
          const sel = a.bundle_id === currentApp ? "selected" : "";
          const label = `${a.bundle_id}${a.bucket ? ` (${a.bucket})` : ""}`;
          return `<option value="${escapeAttr(a.bundle_id)}" ${sel}>${escapeHtml(label)}</option>`;
        })
      )
      .join("");
    const kinds = [
      ["single", "Single keys"],
      ["mod", "Mod combos"],
      ["all", "All"],
    ]
      .map(([v, l]) => `<option value="${v}" ${v === currentKind ? "selected" : ""}>${l}</option>`)
      .join("");
    return `
      <div class="stats-toolbar">
        <label>App: <select id="stats-app">${opts}</select></label>
        <label>Kind: <select id="stats-kind">${kinds}</select></label>
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
        return `
          <tr>
            <td class="rank">${i + 1}</td>
            <td class="count">${r.count.toLocaleString()}</td>
            <td class="pct">${r.pct.toFixed(2)}%</td>
            <td><code>${escapeHtml(mods + r.key)}</code></td>
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

  async function refresh() {
    const sel = root.querySelector("#stats-app");
    const kindSel = root.querySelector("#stats-kind");
    const app = sel ? sel.value || null : null;
    const kind = kindSel ? kindSel.value : "single";
    const stats = await loadStats(app, kind);
    root.innerHTML = renderToolbar(app, kind) + renderTable(stats);
    wire();
  }

  function wire() {
    const sel = root.querySelector("#stats-app");
    const kindSel = root.querySelector("#stats-kind");
    if (sel) sel.addEventListener("change", refresh);
    if (kindSel) kindSel.addEventListener("change", refresh);
  }

  async function init() {
    await loadApps();
    const stats = await loadStats(null, "single");
    root.innerHTML = renderToolbar(null, "single") + renderTable(stats);
    wire();
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function escapeAttr(s) {
    return escapeHtml(s).replace(/"/g, "&quot;");
  }

  // Lazy-load: only fetch when Stats tab first activates.
  document.querySelector('nav button[data-view="stats"]').addEventListener("click", () => {
    if (!loaded) {
      loaded = true;
      init();
    }
  });

  // Expose for heatmap.js (M3.3 will read current scope).
  window.statsDashboard = {
    getScope: () => {
      const sel = root.querySelector("#stats-app");
      const kindSel = root.querySelector("#stats-kind");
      return {
        app: sel ? sel.value || null : null,
        kind: kindSel ? kindSel.value : "single",
      };
    },
    refresh,
  };
})();
