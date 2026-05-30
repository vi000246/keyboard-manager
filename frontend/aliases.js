// aliases.js — shared store for user-defined key/action names ("describe").
//
// One source of truth (raw keycode → name) used by the Static Viewer,
// Interactive simulator, Cheatsheet, and the Key Name Map editor. Views call
// `ensure()` before rendering so `get(raw)` is synchronous inside renderers.
(function () {
  "use strict";

  let map = {};
  let loadPromise = null;
  const listeners = new Set();

  async function load() {
    const r = await fetch("/api/aliases");
    map = r.ok ? await r.json() : {};
    return map;
  }

  function ensure() {
    if (!loadPromise) loadPromise = load().catch(() => (map = {}));
    return loadPromise;
  }

  function reload() {
    loadPromise = load().catch(() => (map = {}));
    return loadPromise;
  }

  function get(raw) {
    if (!raw) return null;
    return Object.prototype.hasOwnProperty.call(map, raw) ? map[raw] : null;
  }

  function all() {
    return map;
  }

  // Persist one name (blank deletes), update the local map, and notify views.
  async function set(raw, name) {
    const r = await fetch("/api/aliases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw, name }),
    });
    if (!r.ok) throw new Error(`save failed: HTTP ${r.status}`);
    const trimmed = (name || "").trim();
    if (trimmed) map[raw] = trimmed;
    else delete map[raw];
    notify();
    return trimmed;
  }

  function onChange(fn) {
    listeners.add(fn);
  }

  function notify() {
    for (const fn of listeners) {
      try {
        fn();
      } catch (e) {
        /* a broken listener shouldn't stop the others */
      }
    }
  }

  window.keyAliases = { ensure, reload, get, all, set, onChange };
})();
