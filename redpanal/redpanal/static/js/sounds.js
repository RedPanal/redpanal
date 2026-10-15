/* Sounds list: each row has the shared player; listen at my tempo (pitch kept), keyboard navigation, quick download. */
(function () {
  "use strict";
  window.rpPage(function () {
    var box = document.querySelector("[data-sounds]");
    if (!box) return;
    var items = Array.prototype.slice.call(box.querySelectorAll("[data-sound]"));
    var atMyTempo = box.querySelector("[data-at-my-tempo]");
    var myTempo = box.querySelector("[data-my-tempo]");
    var hidden = document.querySelector("[data-my-tempo-hidden]");

    function playerOf(item) {
      var root = item.querySelector("[data-mixer]");
      return root && root.rpMixer ? { root: root, mixer: root.rpMixer } : null;
    }

    function rate(root) {
      var tempo = parseFloat(root.dataset.tempo);
      if (!atMyTempo.checked || !tempo) return 1;
      return Math.min(4, Math.max(0.25, parseFloat(myTempo.value || "100") / tempo));
    }

    function select(item) {
      items.forEach(function (i) { i.setAttribute("aria-selected", i === item); i.tabIndex = i === item ? 0 : -1; });
      item.focus();
    }

    items.forEach(function (item) {
      item.addEventListener("click", function (e) { if (!e.target.closest("a, button")) select(item); });
      item.addEventListener("keydown", function (e) {
        var i = items.indexOf(item), p = playerOf(item);
        if (e.key === "ArrowDown" && items[i + 1]) { e.preventDefault(); select(items[i + 1]); }
        else if (e.key === "ArrowUp" && items[i - 1]) { e.preventDefault(); select(items[i - 1]); }
        else if (e.code === "Space" && e.target === item && p) { e.preventDefault(); p.mixer.toggle(); }
        else if ((e.key === "d" || e.key === "D") && e.target === item) { window.location = item.dataset.download; }
      });
    });

    // Dragging the download button onto a folder or a DAW drops the file (Chromium browsers).
    box.querySelectorAll("[data-download-link]").forEach(function (link) {
      link.addEventListener("dragstart", function (e) {
        var name = link.closest("[data-sound]").querySelector(".rp-sound-name b").textContent.trim();
        e.dataTransfer.setData("DownloadURL", "audio/*:" + name + ":" + new URL(link.href, location.href).href);
      });
    });

    function syncTempo() {
      if (hidden) hidden.value = atMyTempo.checked ? myTempo.value : "";
      items.forEach(function (item) {
        var p = playerOf(item);
        if (p) p.mixer.setRate(rate(p.root));
      });
    }
    atMyTempo.addEventListener("change", syncTempo);
    myTempo.addEventListener("input", syncTempo);
    syncTempo();
  });
})();
