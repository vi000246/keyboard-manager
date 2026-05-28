// keycode-format.js — pure functions: ResolvedKey → DOM HTML.
// IIFE with single window export so other modules can compose.
(function () {
  "use strict";

  /**
   * Render a single key cell. Smart mode: plain keys show a single label,
   * MT/LT/TD/wrapped keys stack tap on top and hold/layer below.
   *
   * @param {object|null} key  Layout API key entry: {col, raw, resolved} or null.
   * @returns {string} HTML for a `.key` cell.
   */
  function renderKey(key) {
    if (!key) return `<div class="key gap" aria-hidden="true"></div>`;

    const r = key.resolved || {};
    const kind = r.expanded_kind || "plain";
    const classes = ["key", `kind-${kind}`];

    const top = r.label_top ?? "";
    const bot = r.label_bottom ?? "";

    let tooltip;
    if (kind === "tap-dance" && Array.isArray(r.branches)) {
      const dt = r.double_tap ?? "—";
      const th = r.tap_hold ?? "—";
      tooltip = `tap=${r.tap} | hold=${r.hold} | 2tap=${dt} | tap+hold=${th} | term=${r.tap_term_ms}ms`;
    } else if (r.tap && r.hold) {
      tooltip = `tap=${r.tap} | hold=${r.hold}`;
    } else {
      tooltip = key.raw;
    }

    const labelTopHtml = top === "" ? "&nbsp;" : escapeHtml(top);
    const labelBotHtml = bot ? `<div class="label-bottom">${escapeHtml(bot)}</div>` : "";

    return `
      <div class="${classes.join(" ")}" title="${escapeAttr(tooltip)}" data-raw="${escapeAttr(key.raw)}">
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
