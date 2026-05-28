// keyboard-manager frontend scaffold.
// M1: replace placeholders with actual keyboard grid rendering.

const navButtons = document.querySelectorAll("nav button");
const views = document.querySelectorAll(".view");

navButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = btn.dataset.view;
    navButtons.forEach((b) => b.classList.toggle("active", b === btn));
    views.forEach((v) => v.classList.toggle("hidden", v.id !== `view-${target}`));
  });
});

// M1 hook — fetch layout from backend.
// fetch("/api/layout").then((r) => r.json()).then((layout) => { ... });
