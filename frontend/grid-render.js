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
   * @param {object} layer  Layout API layer: {index, rows: [{row, keys: [...]}]}
   * @returns {string}
   */
  function renderLayer(layer) {
    if (!layer) return `<p class="error">no layer data</p>`;

    const left = layer.rows.slice(0, 5);
    const right = layer.rows.slice(5, 10);
    const renderRow = (row) =>
      `<div class="row row-${row.row}">` +
      row.keys.map((k) => window.keycodeFormat.renderKey(k)).join("") +
      `</div>`;

    return `
      <div class="keyboard">
        <div class="half half-left">
          ${left.map(renderRow).join("")}
        </div>
        <div class="half half-right">
          ${right.map(renderRow).join("")}
        </div>
      </div>`;
  }

  window.gridRender = { renderLayer };
})();
