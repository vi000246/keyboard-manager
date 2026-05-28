// heatmap.js — overlay keystroke counts on the keyboard grid.
//
// The grid HTML is built by grid-render.js. This module just walks the rendered
// .row/.key cells and paints them according to the latest /api/stats/heatmap
// response.
(function () {
  "use strict";

  /**
   * Log-scaled red intensity. log() flattens the long tail so Space (28k+)
   * doesn't make every other key look black-on-black.
   */
  function colorFor(count, maxCount) {
    if (!count || !maxCount) return "transparent";
    const intensity = Math.log(1 + count) / Math.log(1 + maxCount);
    const r = Math.round(60 + 195 * intensity);
    const g = Math.round(60 * (1 - intensity));
    const b = Math.round(60 * (1 - intensity));
    return `rgba(${r}, ${g}, ${b}, 0.78)`;
  }

  async function loadHeatmap(app) {
    const u = new URL("/api/stats/heatmap", location.origin);
    if (app) u.searchParams.set("app", app);
    const r = await fetch(u);
    return r.ok ? await r.json() : null;
  }

  /**
   * Paint the grid in `rootEl` according to heatmap cells. Only cells whose
   * layer matches `layerIdx` are colored — others stay neutral.
   */
  function applyOverlay(rootEl, heatmap, layerIdx) {
    if (!heatmap) return;
    // Reset previous overlay
    rootEl.querySelectorAll(".key").forEach((k) => {
      k.style.backgroundColor = "";
      delete k.dataset.heatCount;
    });
    if (!heatmap.cells.length) return;

    const cellsByPos = new Map();
    for (const c of heatmap.cells) {
      if (c.layer !== layerIdx) continue;
      cellsByPos.set(`${c.row}:${c.col}`, c);
    }

    rootEl.querySelectorAll(".row").forEach((row) => {
      // Use the row-N class to find the actual row index in the data
      const rowIdx = parseInt(
        [...row.classList].find((c) => c.startsWith("row-"))?.slice(4) ?? "-1",
        10,
      );
      if (rowIdx < 0) return;
      row.querySelectorAll(".key").forEach((k, ci) => {
        const c = cellsByPos.get(`${rowIdx}:${ci}`);
        if (c) {
          k.style.backgroundColor = colorFor(c.count, heatmap.max_count);
          k.dataset.heatCount = String(c.count);
          const existing = k.getAttribute("title") || "";
          k.setAttribute(
            "title",
            existing.includes("count=") ? existing : `${existing} | count=${c.count}`,
          );
        }
      });
    });
  }

  window.heatmap = { loadHeatmap, applyOverlay, colorFor };
})();
