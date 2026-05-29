// static-viewer.js — Static Viewer page: render every USED layer in one
// scrollable stack. A layer is "used" if it has at least one slot that isn't
// transparent or empty — Vial always produces 6 layers in the .vil but most
// of them are TRN-only placeholders, and showing them all just adds noise.
(function () {
  "use strict";

  const container = document.getElementById("view-static");
  let layoutCache = null;

  // Mirrors the dropdown option text in index.html — keep in sync if a layer
  // gets renamed there.
  const LAYER_NAMES = ["BASE", "NAV", "", "", "MEDIA", ""];

  function isLayerUsed(layer) {
    for (const row of layer.rows) {
      for (const k of row.keys) {
        if (!k) continue;
        const kind = k.resolved?.expanded_kind;
        if (kind && kind !== "transparent" && kind !== "empty") {
          return true;
        }
      }
    }
    return false;
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

  async function show() {
    const layout = await ensureLayout();
    if (!layout) return;

    const usedLayers = layout.layers.filter(isLayerUsed);
    if (usedLayers.length === 0) {
      container.innerHTML = renderError("no populated layers found in .vil");
      return;
    }

    const deco = window.gridRender.decorationsFor(layout);
    container.innerHTML = usedLayers
      .map((layer) => {
        const name = LAYER_NAMES[layer.index] || "";
        const title = name ? `Layer ${layer.index} — ${name}` : `Layer ${layer.index}`;
        return `
          <section class="layer-block">
            <h2 class="layer-title">${escapeHtml(title)}</h2>
            ${window.gridRender.renderLayer(layer, deco)}
          </section>`;
      })
      .join("");
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function renderError(msg) {
    return `<p class="error">${msg}</p>`;
  }

  // Initial render — the global header picker no longer exists, so we just
  // show every used layer immediately.
  show();

  // One-time hover-tooltip wire-up. Event delegation on the section means
  // re-renders inside it don't drop the listener.
  if (window.keyTooltip) {
    window.keyTooltip.setupKeyTooltips(container, () => layoutCache);
  }

  // Public surface for cross-module coordination (vial-upload.js).
  function refresh() {
    layoutCache = null;
    show();
  }
  window.staticViewer = { show, refresh, getLayout: () => layoutCache };
})();
