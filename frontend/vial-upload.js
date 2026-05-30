// vial-upload.js — top-bar Vial loader: upload a .vil from disk or revert
// to the default. Notifies all three tabs (static / interactive / stats) so
// they reload their layout cache and re-render.
(function () {
  "use strict";

  const uploadBtn = document.getElementById("layout-upload-btn");
  const revertBtn = document.getElementById("layout-revert-btn");
  const fileInput = document.getElementById("layout-upload-input");
  const sourceLabel = document.getElementById("layout-source-label");

  async function refreshSourceLabel() {
    try {
      const r = await fetch("/api/layout/source");
      if (!r.ok) return;
      const s = await r.json();
      if (s.is_uploaded) {
        sourceLabel.textContent = "(uploaded)";
        sourceLabel.className = "source-uploaded";
        revertBtn.classList.remove("hidden");
      } else {
        sourceLabel.textContent = "";
        revertBtn.classList.add("hidden");
      }
    } catch {
      // Backend down — leave label as-is
    }
  }

  /**
   * Notify every tab that the layout has changed. Each module that caches
   * `/api/layout` exposes `_resetLayoutCache()` via window.* so this module
   * doesn't need to know their internals.
   */
  function notifyLayoutChanged() {
    if (window.staticViewer?.refresh) window.staticViewer.refresh();
    if (window.cheatsheet?.refresh) window.cheatsheet.refresh();
    if (window.statsDashboard?.refresh) window.statsDashboard.refresh();
    if (window.interactiveSim?.refresh) window.interactiveSim.refresh();
    if (window.keynameMap?.refresh) window.keynameMap.refresh();
  }

  uploadBtn.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", async () => {
    const f = fileInput.files?.[0];
    if (!f) return;
    uploadBtn.disabled = true;
    uploadBtn.textContent = "uploading…";
    try {
      const fd = new FormData();
      fd.append("file", f);
      const r = await fetch("/api/layout/upload", { method: "POST", body: fd });
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }));
        const msg = err?.detail?.message || err?.detail || r.statusText;
        alert(`Upload failed: ${msg}`);
        return;
      }
      await refreshSourceLabel();
      notifyLayoutChanged();
    } finally {
      uploadBtn.disabled = false;
      uploadBtn.textContent = "Load Vial…";
      fileInput.value = ""; // allow re-uploading the same filename
    }
  });

  revertBtn.addEventListener("click", async () => {
    revertBtn.disabled = true;
    try {
      const r = await fetch("/api/layout/upload", { method: "DELETE" });
      if (!r.ok) {
        alert(`Revert failed: ${r.statusText}`);
        return;
      }
      await refreshSourceLabel();
      notifyLayoutChanged();
    } finally {
      revertBtn.disabled = false;
    }
  });

  // Initial label
  refreshSourceLabel();
})();
