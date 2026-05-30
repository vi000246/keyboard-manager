// app.js — Top-level navigation: switches between Static / Interactive / Stats.
// Layer dropdown is owned by static-viewer.js.
(function () {
  "use strict";

  const navButtons = document.querySelectorAll("nav button");
  const views = document.querySelectorAll(".view");

  navButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.view;
      navButtons.forEach((b) => b.classList.toggle("active", b === btn));
      views.forEach((v) => v.classList.toggle("hidden", v.id !== `view-${target}`));
    });
  });

  // Deep-link support for external launchers (e.g. the Hammerspoon HUD):
  //   ?view=cheatsheet   → open straight to that tab
  //   ?embed=1           → hide the app chrome (header/nav) for an overlay
  const params = new URLSearchParams(location.search);
  const wantView = params.get("view");
  if (wantView) {
    const btn = document.querySelector(`nav button[data-view="${wantView}"]`);
    if (btn) btn.click();
  }
  if (params.get("embed") === "1") document.body.classList.add("embed");
})();
