// keycode-format.js — pure function: ResolvedKey → DOM HTML.
// Plain HTML strings, no innerHTML escape leaks. The richer hover description
// lives in key-tooltip.js (a singleton popover) instead of the native title="".
(function () {
  "use strict";

  /**
   * Render a single key cell.
   *
   * Smart mode:
   *   - plain keys      single label_top
   *   - MT / LT / TD    label_top stacked on top of label_bottom
   *   - empty slot      transparent placeholder (.gap)
   *
   * Each rendered cell carries `data-raw` and `data-col` so key-tooltip.js
   * can reverse-look-up the slot in the cached layout.
   *
   * `opts.isComboTrigger` adds a `.has-combo` class so CSS can render a
   * corner dot indicating the cell participates in one or more combos.
   * `opts.macroIndex` (when non-null) overrides label_bottom with "macro N"
   * so the cell visibly advertises that pressing it fires a macro instead
   * of the raw label_top.
   *
   * @param {object|null} key  Layout API key entry {col, raw, resolved} or null.
   * @param {number} col       Column index inside its row (passed by grid-render).
   * @param {{isComboTrigger?: boolean, macroIndex?: number|null}} [opts]
   * @returns {string}         HTML for a `.key` cell.
   */
  function renderKey(key, col = 0, opts = {}) {
    // Physical-geometry offsets (column stagger / thumb rotation) come from
    // grid-render as a ready-made style string — gaps get it too, so a
    // staggered column keeps its shape where the board has no key.
    const styleAttr = opts.style ? ` style="${escapeAttr(opts.style)}"` : "";

    if (!key) {
      return `<div class="key gap" aria-hidden="true" data-col="${col}"${styleAttr}></div>`;
    }

    const r = key.resolved || {};
    const kind = r.expanded_kind || "plain";
    const classes = ["key", `kind-${kind}`];
    if (opts.isComboTrigger) classes.push("has-combo");
    if (opts.macroIndex != null) classes.push("has-macro");

    const top = r.label_top ?? "";
    const bot = r.label_bottom ?? "";
    // User-given name (if any) replaces the keycode on the cell; the original
    // resolved output still shows in the hover tooltip (key-tooltip.js).
    const alias = window.keyAliases ? window.keyAliases.get(key.raw) : null;
    if (alias) classes.push("has-alias");
    const topText = alias || top;
    const labelTopHtml = topText === "" ? "&nbsp;" : escapeHtml(topText);
    // Macro override wins over the keycode's own label_bottom — the macro
    // identity (e.g. "macro 3") is more useful than the underlying raw,
    // which for a macro slot is just "MACRO3" and provides no extra info.
    const effectiveBot = opts.macroIndex != null ? `macro ${opts.macroIndex}` : bot;
    const labelBotHtml = effectiveBot
      ? `<div class="label-bottom">${escapeHtml(effectiveBot)}</div>`
      : "";

    return `
      <div class="${classes.join(" ")}" data-raw="${escapeAttr(key.raw)}" data-col="${col}"${styleAttr}>
        <div class="label-top">${labelTopHtml}</div>
        ${labelBotHtml}
      </div>`;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function escapeAttr(s) {
    return escapeHtml(s).replace(/"/g, "&quot;");
  }

  window.keycodeFormat = { renderKey };
})();
