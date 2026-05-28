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
})();
