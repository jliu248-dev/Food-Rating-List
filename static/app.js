// Tooltip for the ratings breakdown rows (hover or keyboard focus).
(function () {
  const rows = document.querySelectorAll(".dist-row[data-tip]");
  if (!rows.length) return;
  const tip = document.createElement("div");
  tip.className = "tooltip";
  tip.setAttribute("role", "tooltip");
  document.body.appendChild(tip);

  function show(row, x, y) {
    const value = document.createElement("strong");
    value.textContent = row.dataset.tipValue;
    tip.replaceChildren(value, document.createTextNode(" · " + row.dataset.tip));
    tip.classList.add("show");
    const box = tip.getBoundingClientRect();
    const left = Math.min(Math.max(8, x - box.width / 2), window.innerWidth - box.width - 8);
    tip.style.left = left + "px";
    tip.style.top = (y - box.height - 10) + "px";
  }
  function hide() { tip.classList.remove("show"); }

  rows.forEach(function (row) {
    row.addEventListener("pointermove", function (e) { show(row, e.clientX, e.clientY); });
    row.addEventListener("pointerleave", hide);
    row.addEventListener("focus", function () {
      const r = row.getBoundingClientRect();
      show(row, r.left + r.width / 2, r.top);
    });
    row.addEventListener("blur", hide);
  });
})();

// Star picker: show a word for the chosen score.
(function () {
  const picker = document.querySelector(".star-inputs");
  const word = document.querySelector(".star-word");
  if (!picker || !word) return;
  const words = { 1: "Terrible", 2: "Not great", 3: "Okay", 4: "Good", 5: "Amazing" };
  function update(score) { word.textContent = score ? words[score] : ""; }
  const checked = picker.querySelector("input:checked");
  update(checked && checked.value);
  picker.addEventListener("change", function (e) { update(e.target.value); });
  picker.querySelectorAll("label").forEach(function (label) {
    const input = document.getElementById(label.htmlFor);
    label.addEventListener("mouseenter", function () { update(input.value); });
    label.addEventListener("mouseleave", function () {
      const c = picker.querySelector("input:checked");
      update(c && c.value);
    });
  });
})();

// Character counter for the review box.
(function () {
  const box = document.querySelector("textarea[data-counter]");
  const out = document.getElementById(box && box.dataset.counter);
  if (!box || !out) return;
  function update() { out.textContent = box.value.length + " / " + box.maxLength; }
  box.addEventListener("input", update);
  update();
})();
