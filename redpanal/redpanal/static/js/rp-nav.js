/*
 * Moving around without reloading, so the persistent player (rp-dock.js) keeps playing.
 *
 * Links and forms of the site fetch the next page and swap the parts of it that change
 * (header, messages, content, tab bar, page scripts). Pages for recording, uploading, aligning,
 * editing and accounts load in full, like files and downloads.
 *
 * Page scripts start with rpPage(fn): fn runs when the page is ready, on first load or after a swap,
 * and may return a function that undoes what it set up outside the page (window listeners…).
 */
(function () {
  "use strict";
  if (window.rpNav) return;

  var SWAP = ["header", "rp-toasts-slot", "main", "rp-tabbar", "rp-page-scripts"];
  var FULL = [
    /^\/(admin|accounts|ajustes|api|media|static|reproductor)\//,
    /^\/activity\/(un)?follow/,
    /^\/crear\/((carpeta|sonido)\/)?$/,  // recording and uploading pages; completing and sharing move softly
    /\/(aportar|carpeta|alinear|editar|borrar|bajar|escuchar|bajar-mezcla)\/$/,
    /\/archivos\/\d+\/$/,
    /\.(zip|txt|mp3|ogg|wav|flac|json|pdf)$/i,
    /^\/live\/iframe/
  ];
  var busy = null;

  function soft(url) {
    if (url.origin !== location.origin) return false;
    return !FULL.some(function (re) { return re.test(url.pathname); });
  }

  // Before leaving a page: stop its players and undo what its scripts set up.
  function leave() {
    document.querySelectorAll("#main [data-mixer]").forEach(function (root) {
      if (root.rpMixer && root.rpMixer.destroy) root.rpMixer.destroy();
    });
    window.rpPage.leave();
    document.querySelectorAll("dialog[open]").forEach(function (d) { d.close(); if (d.querySelector("form")) d.querySelector("form").reset(); });
  }

  function runScripts(container) {
    var scripts = Array.prototype.slice.call(container.querySelectorAll("script"));
    // One after the other, like on a full load: a page script may need the one before.
    return scripts.reduce(function (chain, old) {
      return chain.then(function () {
        return new Promise(function (resolve) {
          var s = document.createElement("script");
          Array.prototype.forEach.call(old.attributes, function (a) { s.setAttribute(a.name, a.value); });
          if (old.src) { s.onload = s.onerror = resolve; } else { s.textContent = old.textContent; }
          old.parentNode.replaceChild(s, old);
          if (!old.src) resolve();
        });
      });
    }, Promise.resolve());
  }

  function swap(doc, url, push) {
    if (!SWAP.every(function (id) { return doc.getElementById(id); })) { location.assign(url); return; }
    leave();
    document.title = doc.title;
    document.body.className = doc.body.className + (document.body.classList.contains("has-dock") ? " has-dock" : "");
    SWAP.forEach(function (id) {
      var now = document.getElementById(id), next = doc.getElementById(id);
      now.replaceWith(document.importNode(next, true));
    });
    if (push) history.pushState({ rp: true, scroll: 0 }, "", url);
    var u = new URL(url, location.href);
    if (u.hash && document.getElementById(u.hash.slice(1))) document.getElementById(u.hash.slice(1)).scrollIntoView();
    else if (push) window.scrollTo(0, 0);
    if (window.rpInitPlayers) window.rpInitPlayers(document.getElementById("main"));
    if (window.jQuery && window.follow_unfollow_button) {
      jQuery("#main .follow-unfollow").each(function (i, el) { window.follow_unfollow_button(el); });
    }
    return Promise.all(["header", "rp-toasts-slot", "main", "rp-page-scripts"].map(function (id) {
      return runScripts(document.getElementById(id));
    })).then(function () {
      var main = document.getElementById("main");
      main.setAttribute("tabindex", "-1");
      main.focus({ preventScroll: true });
      document.dispatchEvent(new CustomEvent("rp:page", { detail: { url: url } }));
    });
  }

  function go(url, opts) {
    opts = opts || {};
    var push = opts.push !== false;
    if (busy) busy.abort();
    var ctrl = window.AbortController ? new AbortController() : null;
    busy = ctrl;
    document.documentElement.classList.add("rp-navigating");
    var init = { credentials: "same-origin", headers: { "X-RP-Nav": "1" }, signal: ctrl && ctrl.signal };
    if (opts.method === "POST") { init.method = "POST"; init.body = opts.body; }
    return fetch(url, init).then(function (r) {
      var type = r.headers.get("Content-Type") || "";
      if (type.indexOf("text/html") === -1 || !soft(new URL(r.url))) { location.assign(r.url); return; }
      return r.text().then(function (html) {
        var doc = new DOMParser().parseFromString(html, "text/html");
        // A redirect after a form lands on another address: show that one.
        var finalUrl = r.redirected || opts.method === "POST" ? r.url : url;
        // Back on the same address (a favorite, a follow, a reply): no new history entry, no jump to the top.
        if (finalUrl === location.href) { history.replaceState({ rp: true, scroll: window.scrollY }, "", finalUrl); }
        return swap(doc, finalUrl, push && finalUrl !== location.href);
      });
    }).catch(function (e) {
      if (e && e.name === "AbortError") return;
      location.assign(url);
    }).then(function () {
      if (busy === ctrl) { busy = null; document.documentElement.classList.remove("rp-navigating"); }
    });
  }

  document.addEventListener("click", function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest("a[href]");
    if (!a || a.target || a.hasAttribute("download") || a.closest("[data-full-load]")) return;
    var url = new URL(a.href, location.href);
    if (!soft(url)) return;
    // Only the anchor changes on the same page: let the browser scroll.
    if (url.pathname === location.pathname && url.search === location.search && url.hash) return;
    e.preventDefault();
    go(url.href);
  });

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (e.defaultPrevented || form.closest("[data-full-load]") || form.target) return;
    var method = (form.getAttribute("method") || "get").toUpperCase();
    if (method === "DIALOG") return;
    var url = new URL(form.getAttribute("action") || location.href, location.href);
    if (!soft(url) || form.enctype === "multipart/form-data") return;
    e.preventDefault();
    var data;
    try { data = new FormData(form, e.submitter); } catch (err) {
      data = new FormData(form);
      if (e.submitter && e.submitter.name) data.append(e.submitter.name, e.submitter.value);
    }
    if (method === "GET") {
      url.search = new URLSearchParams(data).toString();
      go(url.href);
    } else {
      go(url.href, { method: "POST", body: data });
    }
  });

  window.addEventListener("popstate", function (e) {
    if (!e.state || !e.state.rp) return;
    go(location.href, { push: false }).then(function () { window.scrollTo(0, e.state.scroll || 0); });
  });

  // Remember where each page was scrolled, for the back button.
  var scrollTimer;
  window.addEventListener("scroll", function () {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(function () {
      if (history.state && history.state.rp) history.replaceState({ rp: true, scroll: window.scrollY }, "", location.href);
    }, 150);
  }, { passive: true });
  history.replaceState({ rp: true, scroll: window.scrollY }, "", location.href);
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";

  window.rpNav = { go: go };
})();
