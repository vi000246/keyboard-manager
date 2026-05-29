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
  function renderLayer(layer, decorations = {}) {
    if (!layer) return `<p class="error">no layer data</p>`;

    const comboTriggers = decorations.comboTriggers || new Set();
    const macroByRaw = decorations.macroByRaw || new Map();

    const left = layer.rows.slice(0, 5);
    const right = layer.rows.slice(5, 10);
    const renderRow = (row) =>
      `<div class="row row-${row.row}">` +
      row.keys.map((k, col) => {
        const raw = k?.raw;
        const opts = raw
          ? {
              isComboTrigger: comboTriggers.has(raw),
              macroIndex: macroByRaw.has(raw) ? macroByRaw.get(raw) : null,
            }
          : undefined;
        return window.keycodeFormat.renderKey(k, col, opts);
      }).join("") +
      `</div>`;

    return `
      <div class="keyboard" data-layer="${layer.index}">
        <div class="half half-left">
          ${left.map(renderRow).join("")}
        </div>
        <div class="half half-right">
          ${right.map(renderRow).join("")}
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

  window.gridRender = { renderLayer, decorationsFor };
})();
