// grid-render.js — shared keyboard grid HTML builder.
//
// Topology is NOT hardcoded here: it arrives on the layout as `layout.topology`
// (see backend/parsers/topology.py), which supplies the row count, the split
// point between halves, whether the right half is stored mirrored, and the
// cosmetic stagger. Swapping the .vil to a different keyboard therefore
// redraws the correct shape with no change in this file.
(function () {
  "use strict";

  /**
   * Last-resort topology for a layout served without one.
   *
   * Derived from the layout's own shape — never a hardcoded board. An earlier
   * version defaulted to the borne's 10×7/split-5 constants, which silently
   * drew a plausible but completely wrong board for any other keyboard
   * (wrong half boundary, missing rows) instead of failing visibly. The
   * backend always sends `topology`, so this only guards against a stale
   * cached response.
   */
  function inferTopo(layout) {
    const rows = (layout && layout.layers && layout.layers[0] && layout.layers[0].rows) || [];
    const rowCount = rows.length;
    const colCount = rows.reduce((m, r) => Math.max(m, r.keys.length), 0);
    return {
      rows: rowCount,
      cols: colCount,
      split: Math.floor(rowCount / 2),
      mirror_right: false,
      thumb_rows: [],
      slug: "unknown",
      geometry: { col_offsets: [], thumb_rotate: [], thumb_shift: [] },
    };
  }

  /**
   * Does the board have a physical key at (r, c)?
   *
   * Keyed off the matrix skeleton (`null` == no key) rather than off whether
   * anything is *assigned* there. An unassigned key (KC_NO) is still a key you
   * can press, so it must be drawn — trimming on assignment would delete a key
   * that happens to be blank on every layer.
   */
  function physicalAt(layers, r, c) {
    for (const layer of layers) {
      const row = layer.rows[r];
      if (row && row.keys[c] != null) return true;
    }
    return false;
  }

  /**
   * Work out which rows/columns to actually draw, per half.
   *
   * A column or row is drawn if the board has a physical key anywhere in it, so
   * matrix positions the board simply doesn't populate (a 3×5 board mapped onto
   * a wider matrix) are dropped, while every real key survives — assigned or
   * not. Computed per-half because the two halves' empty edges differ.
   *
   * The resolved topology rides along on the returned object so `renderLayer`
   * gets it without every caller having to thread it through separately.
   *
   * @returns {{left: {rows: number[], cols: number[]}, right: {...}, topo: object}}
   */
  function usedGeometry(layout) {
    const layers = (layout && layout.layers) || [];
    const topo = (layout && layout.topology) || inferTopo(layout);

    const allRows = [...Array(topo.rows).keys()];
    const halves = [
      { key: "left", rows: allRows.slice(0, topo.split) },
      { key: "right", rows: allRows.slice(topo.split) },
    ];

    const geo = { topo };
    for (const h of halves) {
      const cols = [];
      for (let c = 0; c < topo.cols; c++) {
        if (h.rows.some((r) => physicalAt(layers, r, c))) cols.push(c);
      }
      const rows = h.rows.filter((r) => cols.some((c) => physicalAt(layers, r, c)));
      geo[h.key] = { rows, cols };
    }
    return geo;
  }

  /**
   * Per-half drawing plan: the column order to draw in, plus the stagger
   * lookups keyed by that order.
   *
   * The right half is the left half seen in a mirror. When the board stores it
   * outer→inner we reverse the columns to put the index finger back in the
   * middle; the cosmetic arrays are reversed to match, and thumb rotation is
   * negated so the two clusters splay away from each other rather than both
   * leaning the same way.
   */
  function halfPlan(topo, half, side) {
    const g = topo.geometry || {};
    const mirrored = side === "right" && topo.mirror_right;

    const cols = mirrored ? [...half.cols].reverse() : half.cols;
    const offsets = [...(g.col_offsets || [])];
    const rotate = [...(g.thumb_rotate || [])];
    const shift = [...(g.thumb_shift || [])];
    if (side === "right") {
      offsets.reverse();
      rotate.reverse();
      shift.reverse();
    }
    const rotateSign = side === "right" ? -1 : 1;

    return { cols, offsets, rotate, shift, rotateSign };
  }

  /**
   * @param {object} layer       one entry from layout.layers
   * @param {object} decorations from decorationsFor(layout)
   * @param {object} geometry    REQUIRED — from usedGeometry(layout). Passing
   *   the geometry (rather than defaulting) is what keeps every view drawing
   *   the board the user actually owns; there is deliberately no default,
   *   because guessing produced a wrong-but-believable board.
   */
  function renderLayer(layer, decorations = {}, geometry = null) {
    if (!layer) return `<p class="error">no layer data</p>`;
    if (!geometry || !geometry.topo) {
      return `<p class="error">renderLayer: missing geometry — pass gridRender.usedGeometry(layout)</p>`;
    }

    const comboTriggers = decorations.comboTriggers || new Set();
    const macroByRaw = decorations.macroByRaw || new Map();
    const geo = geometry;
    const topo = geo.topo;
    const thumbRows = new Set(topo.thumb_rows || []);

    const renderRow = (plan, r) => {
      const row = layer.rows[r];
      if (!row) return "";
      const isThumb = thumbRows.has(r);

      // Thumb offsets are indexed by position among the row's *live* keys, not
      // by column — a thumb row starts with dead slots, and the cluster should
      // be numbered from its own first real key outward.
      let thumbSeen = 0;

      const cells = plan.cols.map((c, displayIndex) => {
        const k = row.keys[c];
        const styles = [];

        // Offsets ride on custom properties that style.css folds into a single
        // composed transform, so they cost no layout space (rows stay tightly
        // stacked, exactly as a real staggered board looks) and don't collide
        // with the transform used by the .pressed highlight.
        if (isThumb) {
          if (k) {
            const rot = plan.rotate[thumbSeen];
            const dy = plan.shift[thumbSeen];
            if (rot != null) styles.push(`--key-rot: ${rot * plan.rotateSign}deg`);
            if (dy != null) styles.push(`--key-dy: ${dy}rem`);
            thumbSeen += 1;
          }
        } else {
          const dy = plan.offsets[displayIndex];
          if (dy != null) styles.push(`--key-dy: ${dy}rem`);
        }

        const raw = k?.raw;
        const opts = { style: styles.join("; ") };
        if (raw) {
          opts.isComboTrigger = comboTriggers.has(raw);
          opts.macroIndex = macroByRaw.has(raw) ? macroByRaw.get(raw) : null;
        }
        return window.keycodeFormat.renderKey(k, c, opts);
      });

      return (
        `<div class="row row-${row.row}${isThumb ? " row-thumb" : ""}" ` +
        `style="grid-template-columns: repeat(${plan.cols.length}, var(--key-w))">` +
        cells.join("") +
        `</div>`
      );
    };

    const leftPlan = halfPlan(topo, geo.left, "left");
    const rightPlan = halfPlan(topo, geo.right, "right");

    return `
      <div class="keyboard" data-layer="${layer.index}" data-board="${escapeAttr(topo.slug || "unknown")}">
        <div class="half half-left">
          ${geo.left.rows.map((r) => renderRow(leftPlan, r)).join("")}
        </div>
        <div class="half half-right">
          ${geo.right.rows.map((r) => renderRow(rightPlan, r)).join("")}
        </div>
      </div>`;
  }

  /**
   * Column indices for one half, in the order they should be DRAWN.
   *
   * For a board whose right half is stored outer→inner this is the reversed
   * column list; otherwise it is the list unchanged. Views that build their
   * own rows (the cheatsheet) must go through this instead of using
   * `geo.<side>.cols` directly, or their right hand comes out backwards.
   * The values are still real matrix column indices, so `data-col` and any
   * (row, col) lookup keyed off them stays correct.
   *
   * @param {object} geo   from usedGeometry(layout)
   * @param {"left"|"right"} side
   */
  function displayCols(geo, side) {
    if (!geo || !geo[side]) return [];
    const topo = geo.topo || {};
    const cols = geo[side].cols;
    return side === "right" && topo.mirror_right ? [...cols].reverse() : cols;
  }

  function escapeAttr(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
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

  window.gridRender = { renderLayer, decorationsFor, usedGeometry, displayCols };
})();
