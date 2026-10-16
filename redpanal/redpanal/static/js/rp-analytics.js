/*
 * Visit statistics with Umami, hosted by RedPanal (core/analytics.py, ESTADISTICAS.md).
 *
 * Umami's own automatic counting is off: the site moves between pages without reloading, and a page that must not
 * be counted (a private project, Estudio, a search) would be counted anyway. Here each page says whether it can be
 * counted (#rp-analytics, swapped with the page), and only the address is sent, never the search after "?".
 * Events: listening, downloading, and what the server queued (signing up, uploading, contributing, following,
 * posting). Never who: no user, no data about the person.
 */
(function () {
  "use strict";

  function page() {
    var el = document.getElementById("rp-analytics");
    return { el: el, track: !!el && el.dataset.track === "1" };
  }

  function send(name, data) {
    if (!window.umami || typeof window.umami.track !== "function") return;  // off, blocked or "do not track"
    var p = page();
    window.umami.track(function (props) {
      var out = {};
      for (var k in props) out[k] = props[k];
      // A page that can't be counted gives neither its address nor its title, only that something happened.
      out.url = p.track ? location.pathname : "/";
      if (!p.track) out.title = "";
      if (name) { out.name = name; out.data = data || {}; }
      return out;
    });
  }

  function onPage() {
    var p = page();
    if (!p.el) return;
    if (p.track) send();
    (p.el.dataset.events || "").split(",").forEach(function (name) { if (name) send(name); });
    p.el.dataset.events = "";  // sent once, even if the page is shown again
  }

  // Listening: once per sound in the player, once per "listen together" in a project.
  var lastId = null;
  document.addEventListener("rp:dock", function (e) {
    var item = e.detail && e.detail.item;
    if (!e.detail.playing || !item) return;
    var id = item.id || item.src;
    if (id === lastId) return;
    lastId = id;
    send("play", { kind: "sound" });
  });
  document.addEventListener("rp:play", function (e) {
    if (e.detail !== "dock") send("play", { kind: "project" });
  });

  // Downloading: a file, the parts of a project or its mix.
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a) return;
    var path = new URL(a.href, location.href).pathname;
    if (/\/bajar\/$|\/bajar-mezcla\/$|\/partes\.zip$|\/mezcla\.mp3$|\/archivos\/\d+\/$/.test(path)) send("download");
  }, true);

  document.addEventListener("rp:page", onPage);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", onPage);
  else onPage();
})();
