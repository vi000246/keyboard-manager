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
   * @param {object|null} key  Layout API key entry {col, raw, resolved} or null.
   * @param {number} col       Column index inside its row (passed by grid-render).
   * @returns {string}         HTML for a `.key` cell.
   */
  function renderKey(key, col = 0) {
    if (!key) {
      return `<div class="key gap" aria-hidden="true" data-col="${col}"></div>`;
    }

    const r = key.resolved || {};
    const kind = r.expanded_kind || "plain";
    const classes = ["key", `kind-${kind}`];

    const top = r.label_top ?? "";
    const bot = r.label_bottom ?? "";
    const labelTopHtml = top === "" ? "&nbsp;" : escapeHtml(top);
    const labelBotHtml = bot ? `<div class="label-bottom">${escapeHtml(bot)}</div>` : "";

    return `
      <div class="${classes.join(" ")}" data-raw="${escapeAttr(key.raw)}" data-col="${col}">
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
