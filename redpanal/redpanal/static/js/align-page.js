/* Align a part: load the work's aligned parts and this one, suggest an offset, let the ear decide. */
(function () {
  "use strict";
  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("align-form");
    if (!form || !form.rpMixer) return;
    var mixer = form.rpMixer;
    var input = document.getElementById("id_offset_ms");
    var box = form.querySelector("[data-suggestion]");
    var target = mixer.tracks.filter(function (t) { return t.el.hasAttribute("data-align-target"); })[0];

    function setOffset(ms) {
      input.value = Math.round(ms);
      mixer.setOffset(target, Math.round(ms));
    }
    input.addEventListener("input", function () { mixer.setOffset(target, parseInt(input.value || "0", 10)); });
    form.querySelectorAll("[data-nudge]").forEach(function (b) {
      b.addEventListener("click", function () { setOffset(parseInt(input.value || "0", 10) + parseInt(b.dataset.nudge, 10)); });
    });

    var refs = mixer.tracks.filter(function (t) { return t !== target; });
    if (!refs.length || !window.rpSuggestOffset) { box.hidden = true; return; }
    box.textContent = box.dataset.analysing;
    mixer.load().then(function () {
      var result = window.rpSuggestOffset(refs.map(function (t) { return { buffer: t.buffer, offsetMs: t.offset * 1000 }; }),
                                          target.buffer);
      if (!result) { box.textContent = box.dataset.unclear; return; }
      var confidence = result.confidence >= 9 ? box.dataset.high : box.dataset.medium;
      if (result.verdict === "aligned") {
        box.textContent = box.dataset.aligned.replace("%c", confidence);
        setOffset(result.offsetMs);
      } else if (result.verdict === "shifted") {
        box.textContent = box.dataset.shifted.replace("%s", (result.offsetMs > 0 ? "+" : "") + result.offsetMs).replace("%c", confidence);
        setOffset(result.offsetMs);
      } else {
        box.textContent = box.dataset.unclear;
      }
    }).catch(function () { box.textContent = box.dataset.failed; });
  });
})();
