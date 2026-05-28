// static-viewer.js — Static Viewer page: GET /api/layout, render selected layer.
(function () {
  "use strict";

  const container = document.getElementById("view-static");
  const layerSelect = document.getElementById("layer-select");
  let layoutCache = null;

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

  async function show(layerIdx) {
    const layout = await ensureLayout();
    if (!layout) return;
    const layer = layout.layers[layerIdx];
    if (!layer) {
      container.innerHTML = renderError(`layer ${layerIdx} not present`);
      return;
    }
    container.innerHTML = window.gridRender.renderLayer(layer);
  }

  function renderError(msg) {
    return `<p class="error">${msg}</p>`;
  }

  layerSelect.addEventListener("change", () => {
    show(parseInt(layerSelect.value, 10));
  });

  // Initial render
  show(0);

  // Expose for debugging / Interactive module reuse
  window.staticViewer = { show, getLayout: () => layoutCache };
})();
