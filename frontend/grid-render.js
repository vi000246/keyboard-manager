// grid-render.js — shared keyboard grid HTML builder.
//
// Borne topology: 10 rows (5 left, 5 right) × 7 columns each. Rows 0..4 = left
// side, rows 5..9 = right side. The split is visual only; the data already
// arrives as a flat 10-row list.
(function () {
  "use strict";

  /**
   * Render a single layer's grid as side-by-side halves.
   *
   * `data-layer` on the .keyboard wrapper + `data-col` on each .key cell let
   * key-tooltip.js (and any future module that needs to look up a slot) reverse
   * the rendered DOM back to `layout.layers[layer].rows[row].keys[col]`. The
   * row index is already encoded in the `.row.row-N` class.
   *
   * `decorations` is layout-wide annotation derived once by the caller from
   * the full layout (which `renderLayer` itself doesn't see). Pulled out
   * into a single argument so the function stays pure and easy to test.
   *
   * @param {object} layer  Layout API layer: {index, rows: [{row, keys: [...]}]}
   * @param {{comboTriggers?: Set<string>, macroByRaw?: Map<string, number>}} [decorations]
   * @returns {string}
   */
  function isLiveKey(k) {
    if (!k) return false;
    const kind = k.resolved && k.resolved.expanded_kind;
    return kind && kind !== "transparent" && kind !== "empty";
  }

  function activeAt(layers, r, c) {
    for (const layer of layers) {
      const row = layer.rows[r];
      if (row && isLiveKey(row.keys[c])) return true;
    }
    return false;
  }

  // Work out which rows/columns to actually draw: a column (within a half) or a
  // row is shown only if SOME layer has a live key in it — so an unused outer
  // column or top row (e.g. a 3×5 board mapped onto this 10×7 grid) is dropped
  // entirely. Computed per-half because the two halves' empty edges differ.
  // Returns { left: {rows:[…], cols:[…]}, right: {rows:[…], cols:[…]} }.
  function usedGeometry(layout) {
    const layers = (layout && layout.layers) || [];
    const halves = [
      { key: "left", rows: [0, 1, 2, 3, 4] },
      { key: "right", rows: [5, 6, 7, 8, 9] },
    ];
    const geo = {};
    for (const h of halves) {
      const cols = [];
      for (let c = 0; c < 7; c++) {
        if (h.rows.some((r) => activeAt(layers, r, c))) cols.push(c);
      }
      const rows = h.rows.filter((r) => cols.some((c) => activeAt(layers, r, c)));
      geo[h.key] = { rows, cols };
    }
    return geo;
  }

  const FULL_GEOMETRY = {
    left: { rows: [0, 1, 2, 3, 4], cols: [0, 1, 2, 3, 4, 5, 6] },
    right: { rows: [5, 6, 7, 8, 9], cols: [0, 1, 2, 3, 4, 5, 6] },
  };

  function renderLayer(layer, decorations = {}, geometry = null) {
    if (!layer) return `<p class="error">no layer data</p>`;

    const comboTriggers = decorations.comboTriggers || new Set();
    const macroByRaw = decorations.macroByRaw || new Map();
    const geo = geometry || FULL_GEOMETRY;

    // Keep the real column index (data-col) so key-tooltip.js can still map the
    // DOM cell back to layout[layer].rows[row].keys[col].
    const renderRow = (cols, r) => {
      const row = layer.rows[r];
      return (
        `<div class="row row-${row.row}" style="grid-template-columns: repeat(${cols.length}, var(--key-w))">` +
        cols
          .map((c) => {
            const k = row.keys[c];
            const raw = k?.raw;
            const opts = raw
              ? {
                  isComboTrigger: comboTriggers.has(raw),
                  macroIndex: macroByRaw.has(raw) ? macroByRaw.get(raw) : null,
                }
              : undefined;
            return window.keycodeFormat.renderKey(k, c, opts);
          })
          .join("") +
        `</div>`
      );
    };

    return `
      <div class="keyboard" data-layer="${layer.index}">
        <div class="half half-left">
          ${geo.left.rows.map((r) => renderRow(geo.left.cols, r)).join("")}
        </div>
        <div class="half half-right">
          ${geo.right.rows.map((r) => renderRow(geo.right.cols, r)).join("")}
        </div>
      </div>`;
  }

  /**
   * Build the per-layout decoration bundle once so callers don't have to
   * repeat the (combo, macro) reduction on every re-render. Safe to call
   * with a missing layout.
   *
   * @param {object|null} layout  /api/layout response
   */
  function decorationsFor(layout) {
    const comboTriggers = new Set();
    if (layout && Array.isArray(layout.combo)) {
      for (const c of layout.combo) {
        if (!Array.isArray(c.triggers)) continue;
        for (const t of c.triggers) comboTriggers.add(t);
      }
    }
    const macroByRaw = new Map();
    if (layout && Array.isArray(layout.macro)) {
      for (const m of layout.macro) {
        // Each entry: { index, raw, actions: [...] } — raw is the keycode
        // ("MACRO0") that appears in the layer when this macro is mapped.
        if (m && m.raw) macroByRaw.set(m.raw, m.index);
      }
    }
    return { comboTriggers, macroByRaw };
  }

  window.gridRender = { renderLayer, decorationsFor, usedGeometry };
})();
