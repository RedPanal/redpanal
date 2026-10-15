/*
 * The persistent player: a bar at the bottom that keeps playing while you browse (see rp-nav.js).
 *
 * What plays is always the file someone clicks. After it comes its group (the other files of the
 * same project, when the click was inside one) and then sounds like the last one, fetched from
 * /reproductor/siguientes/<id>/. From the expanded panel: the queue, favorites, downloads, playlists.
 *
 * Page players (obra-player.js) hand single files over with RPDock.play(item, {group, rate, start})
 * and follow the "rp:dock" event to show the same state on their own waveform.
 */
(function () {
  "use strict";
  if (window.RPDock) return;

  var STORE = "rp-dock";
  var audio = new Audio();
  audio.preload = "none";
  audio.preservesPitch = audio.mozPreservesPitch = audio.webkitPreservesPitch = true;

  var state = { queue: [], index: -1, played: [], loading: false };
  var el = {}, labels = {}, pendingStart = null, fetchingMore = null, saveTimer = null;

  function fmt(sec) { return window.rpFormatTime ? window.rpFormatTime(sec) : Math.floor(sec || 0) + "s"; }
  function current() { return state.queue[state.index] || null; }
  function same(a, b) { return a && b && a.src === b.src; }
  function csrf() { var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/); return m ? decodeURIComponent(m[1]) : ""; }

  function emit() {
    document.dispatchEvent(new CustomEvent("rp:dock", { detail: { item: current(), playing: Dock.playing } }));
  }

  // -- playback ------------------------------------------------------------------------------

  function load(item, start) {
    if (!item) return;
    state.loading = true;
    audio.src = item.src;
    audio.playbackRate = item.rate || 1;
    pendingStart = start || null;
    if (item.id && state.played.indexOf(item.id) === -1) state.played.push(item.id);
    render();
    return play();
  }

  function play() {
    if (!current()) return Promise.resolve();
    if (!audio.src) return load(current(), pendingStart);
    document.dispatchEvent(new CustomEvent("rp:play", { detail: "dock" }));  // page mixers stop
    return audio.play().catch(function () { state.loading = false; render(); });
  }

  var Dock = {
    audio: audio,
    playing: false,

    isCurrent: function (src) { var c = current(); return !!(c && c.src === src); },
    upcoming: function () { return state.queue.slice(state.index); },

    // Play one file; `group` comes after it, then similar sounds.
    play: function (item, opts) {
      opts = opts || {};
      item.rate = opts.rate || 1;
      if (same(current(), item)) {
        if (opts.rate) Dock.setRate(opts.rate);
        if (opts.start != null) Dock.seek(opts.start);
        return play();
      }
      state.queue = [item].concat((opts.group || []).filter(function (g) { return !same(g, item); }));
      state.index = 0;
      open(true);
      return load(item, opts.start);
    },

    // Play a collection (favorites, downloads, a playlist) from one of its items.
    playList: function (items, index) {
      state.queue = items.slice();
      state.index = index || 0;
      return load(current());
    },

    pause: function () { audio.pause(); },
    toggle: function () { Dock.playing ? Dock.pause() : play(); },
    seek: function (sec) {
      if (!audio.src) { pendingStart = sec; return; }
      try { audio.currentTime = Math.max(0, sec); } catch (e) {}
      render();
    },
    setRate: function (rate) {
      var c = current(); if (c) c.rate = rate || 1;
      audio.playbackRate = rate || 1;
    },

    next: function () {
      if (state.index < state.queue.length - 1) { state.index++; return load(current()); }
      return more().then(function (added) {
        if (added) { state.index++; load(current()); }
        else { Dock.pause(); audio.currentTime = 0; render(); }
      });
    },

    prev: function () {
      if (audio.currentTime > 3 || state.index === 0) { Dock.seek(0); return; }
      state.index--; load(current());
    },

    close: function () {
      audio.pause(); audio.removeAttribute("src"); audio.load();
      state = { queue: [], index: -1, played: [], loading: false };
      try { sessionStorage.removeItem(STORE); } catch (e) {}
      render(); emit();
    }
  };
  window.RPDock = Dock;

  // Similar sounds after the last one that has an id (sounds, not previews).
  function more() {
    if (fetchingMore) return fetchingMore;
    var seed = null;
    for (var i = state.queue.length - 1; i >= 0; i--) { if (state.queue[i].id) { seed = state.queue[i]; break; } }
    if (!seed) return Promise.resolve(0);
    var exclude = state.played.concat(state.queue.map(function (q) { return q.id; })).filter(Boolean);
    fetchingMore = fetch("/reproductor/siguientes/" + seed.id + "/?excluir=" + exclude.join(","), { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : { tracks: [] }; })
      .then(function (d) {
        var fresh = (d.tracks || []).filter(function (t) { return !state.queue.some(function (q) { return same(q, t); }); });
        state.queue = state.queue.concat(fresh);
        render();
        return fresh.length;
      })
      .catch(function () { return 0; })
      .then(function (n) { fetchingMore = null; return n; });
    return fetchingMore;
  }

  audio.addEventListener("loadedmetadata", function () {
    if (pendingStart != null) { try { audio.currentTime = pendingStart; } catch (e) {} pendingStart = null; }
    render();
  });
  audio.addEventListener("playing", function () {
    state.loading = false; Dock.playing = true; render(); emit(); session();
    // Know what comes next before getting there.
    if (state.index >= state.queue.length - 1) more();
  });
  audio.addEventListener("pause", function () { Dock.playing = false; render(); emit(); save(); });
  audio.addEventListener("ended", function () { Dock.playing = false; emit(); Dock.next(); });
  audio.addEventListener("timeupdate", function () { paintTime(); if (!saveTimer) saveTimer = setTimeout(function () { saveTimer = null; save(); }, 2000); });
  audio.addEventListener("error", function () { state.loading = false; render(); });

  // A page mixer (several parts in sync) started: this one stops.
  document.addEventListener("rp:play", function (e) { if (e.detail !== "dock" && Dock.playing) Dock.pause(); });

  // -- lock screen, headphones, keyboard media keys ---------------------------------------------

  function session() {
    if (!("mediaSession" in navigator)) return;
    var c = current(); if (!c) return;
    try {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: c.title || "", artist: c.artist || "", album: "RedPanal",
        artwork: c.cover ? [{ src: c.cover, sizes: "112x112" }] : []
      });
    } catch (e) {}
  }
  if ("mediaSession" in navigator) {
    var handlers = {
      play: function () { play(); }, pause: function () { Dock.pause(); },
      previoustrack: function () { Dock.prev(); }, nexttrack: function () { Dock.next(); },
      seekto: function (d) { Dock.seek(d.seekTime); }
    };
    Object.keys(handlers).forEach(function (k) { try { navigator.mediaSession.setActionHandler(k, handlers[k]); } catch (e) {} });
  }

  // -- surviving a full page load (pages that reload, refreshing): paused where it was ------------

  function save() {
    if (!current()) return;
    try {
      sessionStorage.setItem(STORE, JSON.stringify({
        queue: state.queue.slice(Math.max(0, state.index - 20), state.index + 30),
        index: Math.min(state.index, 20), played: state.played.slice(-200), time: audio.currentTime || pendingStart || 0
      }));
    } catch (e) {}
  }
  function restore() {
    try {
      var s = JSON.parse(sessionStorage.getItem(STORE) || "null");
      if (!s || !s.queue || !s.queue.length) return;
      state.queue = s.queue; state.index = s.index || 0; state.played = s.played || [];
      pendingStart = s.time || 0;
    } catch (e) {}
  }
  window.addEventListener("pagehide", save);

  // -- the bar and the panel ------------------------------------------------------------------

  function open(visible) { if (el.root) { el.root.hidden = !visible; document.body.classList.toggle("has-dock", visible); } }

  function paintTime() {
    if (!el.root) return;
    var d = isFinite(audio.duration) ? audio.duration : (current() && current().duration) || 0;
    var t = audio.src ? audio.currentTime : (pendingStart || 0);
    var pct = (d ? t / d * 100 : 0) + "%";
    el.time.textContent = fmt(t) + " / " + (d ? fmt(d) : "–");
    if (document.activeElement !== el.seek) el.seek.value = d ? Math.round(t / d * 1000) : 0;
    el.seek.style.setProperty("--pct", pct);
    el.line.style.width = pct;
    el.s_wave.querySelector(".rp-sheet-progress").style.width = pct;
  }

  function render() {
    if (!el.root) return;
    var c = current();
    open(!!c);
    if (!c) return;
    el.title.textContent = el.s_title.textContent = c.title || "";
    el.s_title.href = el.s_page.href = c.url || "#";
    el.artist.textContent = el.s_artist.textContent = c.artist || "";
    [el.cover, el.s_cover].forEach(function (box) {
      box.innerHTML = "";
      if (c.cover) { var img = document.createElement("img"); img.src = c.cover; img.alt = ""; box.appendChild(img); }
      else box.innerHTML = '<i class="fa fa-wave-square" aria-hidden="true"></i>';
      box.classList.toggle("is-empty", !c.cover);
    });
    el.plays.forEach(function (b) {
      b.innerHTML = state.loading ? '<i class="fa fa-circle-notch fa-spin" aria-hidden="true"></i>'
        : '<i class="fa fa-' + (Dock.playing ? "pause" : "play") + '" aria-hidden="true"></i>';
      b.setAttribute("aria-label", Dock.playing ? labels.pause : labels.play);
      b.setAttribute("aria-pressed", Dock.playing ? "true" : "false");
    });
    paintTime();
    if (!el.sheet.hidden) {
      sheetFor(c);
      if (el.root.dataset.tab === "queue") showQueue();
    }
  }

  // Panel lists ---------------------------------------------------------------------------------

  function row(item, i, onPlay, extra) {
    var li = document.createElement("li");
    li.className = "rp-dock-row" + (same(item, current()) ? " is-current" : "");
    var btn = document.createElement("button");
    btn.type = "button"; btn.className = "rp-dock-row-play";
    btn.setAttribute("aria-label", labels.play + ": " + (item.title || ""));
    btn.innerHTML = '<i class="fa fa-' + (same(item, current()) && Dock.playing ? "volume-up" : "play") + '" aria-hidden="true"></i>';
    btn.addEventListener("click", function () { onPlay(i); });
    var text = document.createElement("span");
    text.className = "rp-dock-row-text";
    var a = document.createElement("a"); a.href = item.url || "#"; a.textContent = item.title || "";
    var who = document.createElement("span"); who.className = "rp-muted small d-block"; who.textContent = item.artist || "";
    text.appendChild(a); text.appendChild(who);
    li.appendChild(btn); li.appendChild(text);
    if (extra) li.appendChild(extra);
    return li;
  }

  function list(items, onPlay, empty) {
    el.list.innerHTML = "";
    if (!items.length) { el.list.innerHTML = '<p class="rp-muted small px-2">' + empty + "</p>"; return; }
    var ul = document.createElement("ul"); ul.className = "rp-dock-rows";
    items.forEach(function (item, i) { ul.appendChild(row(item, i, onPlay)); });
    el.list.appendChild(ul);
  }

  function showQueue() {
    var upcoming = state.queue.slice(state.index);
    list(upcoming, function (i) { state.index += i; load(current()); }, labels.emptyQueue);
  }

  function getJSON(url) {
    return fetch(url, { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : {}; });
  }

  function showCollection(url, empty) {
    el.list.innerHTML = '<p class="rp-muted small px-2">…</p>';
    getJSON(url).then(function (d) {
      var tracks = d.tracks || [];
      list(tracks, function (i) { Dock.playList(tracks, i); }, empty);
    });
  }

  function showPlaylists() {
    el.list.innerHTML = '<p class="rp-muted small px-2">…</p>';
    getJSON("/reproductor/listas/").then(function (d) {
      el.list.innerHTML = "";
      var ul = document.createElement("ul"); ul.className = "rp-dock-rows";
      (d.playlists || []).forEach(function (p) {
        var li = document.createElement("li"); li.className = "rp-dock-row";
        var b = document.createElement("button"); b.type = "button"; b.className = "rp-dock-row-open";
        b.innerHTML = '<i class="fa fa-list" aria-hidden="true"></i> <span></span> <span class="rp-muted small"></span>';
        b.children[1].textContent = p.name; b.children[2].textContent = p.count;
        b.addEventListener("click", function () { showPlaylist(p.id); });
        li.appendChild(b); ul.appendChild(li);
      });
      if (!ul.children.length) el.list.innerHTML = '<p class="rp-muted small px-2">' + labels.emptyPlaylists + "</p>";
      else el.list.appendChild(ul);
    });
  }

  function showPlaylist(id) {
    getJSON("/reproductor/listas/" + id + "/").then(function (d) {
      var tracks = d.tracks || [];
      list(tracks, function (i) { Dock.playList(tracks, i); }, labels.emptyPlaylist);
      var head = document.createElement("div"); head.className = "rp-dock-listhead";
      var back = document.createElement("button"); back.type = "button"; back.className = "btn btn-link btn-sm p-0";
      back.innerHTML = '<i class="fa fa-arrow-left" aria-hidden="true"></i> ';
      back.appendChild(document.createTextNode(d.name || ""));
      back.addEventListener("click", showPlaylists);
      head.appendChild(back);
      el.list.insertBefore(head, el.list.firstChild);
    });
  }

  function tab(name) {
    el.root.dataset.tab = name;
    el.tabs.forEach(function (t) { t.setAttribute("aria-selected", t.dataset.dockTab === name ? "true" : "false"); });
    if (name === "queue") showQueue();
    else if (name === "favorites") showCollection("/reproductor/favoritos/", labels.emptyFavorites);
    else if (name === "downloads") showCollection("/reproductor/descargados/", labels.emptyDownloads);
    else if (name === "playlists") showPlaylists();
  }

  // Add what's playing to a playlist (or a new one).
  function addToPlaylist() {
    var c = current(); if (!c || !c.id) return;
    getJSON("/reproductor/listas/").then(function (d) {
      el.list.innerHTML = "";
      var ul = document.createElement("ul"); ul.className = "rp-dock-rows";
      (d.playlists || []).forEach(function (p) {
        var li = document.createElement("li"); li.className = "rp-dock-row";
        var b = document.createElement("button"); b.type = "button"; b.className = "rp-dock-row-open";
        b.innerHTML = '<i class="fa fa-plus" aria-hidden="true"></i> <span></span>';
        b.children[1].textContent = p.name;
        b.addEventListener("click", function () {
          post("/reproductor/listas/" + p.id + "/agregar/", { audio: c.id }).then(function () { flash(labels.added); });
        });
        li.appendChild(b); ul.appendChild(li);
      });
      el.list.appendChild(ul);
      var form = document.createElement("form"); form.className = "rp-dock-newlist";
      form.innerHTML = '<label class="visually-hidden" for="rp-dock-newname"></label>' +
        '<input class="form-control form-control-sm" id="rp-dock-newname" maxlength="100" required>' +
        '<button class="btn btn-outline-dark btn-sm"></button>';
      form.querySelector("label").textContent = labels.newList;
      form.querySelector("input").placeholder = labels.newList;
      form.querySelector("button").textContent = labels.create;
      form.setAttribute("data-full-load", "");  // handled here, not by page navigation
      form.addEventListener("submit", function (e) {
        e.preventDefault(); e.stopPropagation();
        post("/reproductor/listas/nueva/", { name: form.querySelector("input").value, audio: c.id })
          .then(function () { flash(labels.added); });
      });
      el.list.appendChild(form);
    });
  }

  function post(url, data) {
    var body = new FormData();
    Object.keys(data).forEach(function (k) { body.append(k, data[k]); });
    return fetch(url, { method: "POST", body: body, credentials: "same-origin", headers: { "X-CSRFToken": csrf() } })
      .then(function (r) { return r.json(); });
  }

  function flash(text) {
    el.list.innerHTML = '<p class="small px-2" role="status"><i class="fa fa-check" aria-hidden="true"></i> ' + text + "</p>";
    setTimeout(function () { tab("playlists"); }, 1200);
  }

  // -- "Escuchando": the expanded view -----------------------------------------------------------

  var detailFor = null, waveFor = null, wavePeaks = null;

  function expand(opening) {
    el.sheet.hidden = !opening;
    el.expand.setAttribute("aria-expanded", opening ? "true" : "false");
    el.root.classList.toggle("is-expanded", opening);
    document.body.classList.toggle("dock-expanded", opening);
    if (opening) { tab(el.root.dataset.tab || "queue"); sheetFor(current()); el.collapse.focus(); }
    else el.expand.focus();
  }

  // What changes with each sound: the details from the server and its waveform.
  function sheetFor(c) {
    if (!c || el.sheet.hidden) return;
    if (c.id && detailFor !== c.id) {
      detailFor = c.id;
      ["favorite", "amplify", "download"].forEach(function (k) { el["s_" + k].hidden = true; });
      el.s_labels.innerHTML = ""; el.s_project.textContent = "";
      getJSON("/reproductor/pista/" + c.id + "/").then(function (d) {
        if (detailFor !== c.id || !d.id) return;
        (d.labels || []).forEach(function (text) {
          var s = document.createElement("span"); s.className = "rp-label"; s.textContent = text; el.s_labels.appendChild(s);
        });
        if (d.project) {
          el.s_project.textContent = labels.trackOf + " ";
          var a = document.createElement("a"); a.href = d.project.url; a.textContent = "«" + d.project.name + "»";
          el.s_project.appendChild(a);
        }
        if (d.download) { el.s_download.href = d.download; el.s_download.hidden = false; }
        if (d.can_react) {
          setReaction(el.s_favorite, d.favorite, "fa-heart"); el.s_favorite.dataset.url = d.favorite_url; el.s_favorite.hidden = false;
          setReaction(el.s_amplify, d.amplified, "fa-retweet"); el.s_amplify.dataset.url = d.amplify_url; el.s_amplify.hidden = false;
        }
      });
    }
    if (waveFor !== c.src) {
      waveFor = c.src; wavePeaks = null; drawWave();
      if (c.peaks) getJSON(c.peaks).then(function (d) {
        if (waveFor !== c.src) return;
        var raw = (d && d.peaks) || [], p = Array.isArray(raw) ? raw : (raw.data || []), max = 0.0001;
        p = p.map(function (x) { x = Math.abs(+x || 0); if (x > max) max = x; return x; });
        wavePeaks = p.map(function (x) { return x / max; });
        drawWave();
      });
    }
  }

  function setReaction(btn, on, icon) {
    btn.classList.toggle("is-on", !!on);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    var i = btn.querySelector("i");
    if (icon === "fa-heart") i.className = (on ? "fas" : "far") + " fa-heart";
  }

  function react(btn, icon) {
    var on = btn.getAttribute("aria-pressed") !== "true";
    setReaction(btn, on, icon);  // right away; the server confirms in the background
    var body = new FormData(); body.append("next", "/");
    fetch(btn.dataset.url, { method: "POST", body: body, credentials: "same-origin", headers: { "X-CSRFToken": csrf() } })
      .catch(function () { setReaction(btn, !on, icon); });
  }

  function drawWave() {
    var box = el.s_wave, canvas = box.querySelector("canvas");
    var w = box.clientWidth || 300, h = box.clientHeight || 64, ratio = window.devicePixelRatio || 1;
    canvas.width = w * ratio; canvas.height = h * ratio; canvas.style.width = w + "px"; canvas.style.height = h + "px";
    var g = canvas.getContext("2d"); g.scale(ratio, ratio); g.clearRect(0, 0, w, h);
    if (!wavePeaks || !wavePeaks.length) return;
    g.fillStyle = getComputedStyle(box).color;
    var bar = 2, gap = 1, n = Math.floor(w / (bar + gap));
    for (var i = 0; i < n; i++) {
      var p = wavePeaks[Math.floor(i / n * wavePeaks.length)] || 0, bh = Math.max(2, p * (h - 4));
      g.fillRect(i * (bar + gap), (h - bh) / 2, bar, bh);
    }
  }

  function setup() {
    var root = document.getElementById("rp-dock");
    if (!root) return;
    var q = function (s) { return root.querySelector(s); }, qa = function (s) { return Array.prototype.slice.call(root.querySelectorAll(s)); };
    el = {
      root: root, title: q("[data-dock-title]"), artist: q("[data-dock-artist]"), cover: q("[data-dock-cover]"),
      plays: qa("[data-dock-play]"), nexts: qa("[data-dock-next]"), prev: q("[data-dock-prev]"),
      line: q("[data-dock-line]"), time: q("[data-dock-time]"), seek: q("[data-dock-seek]"),
      expand: q("[data-dock-expand]"), collapse: q("[data-dock-collapse]"), sheet: q("[data-dock-sheet]"),
      list: q("[data-dock-list]"), tabs: qa("[data-dock-tab]"), add: q("[data-dock-add]"), close: q("[data-dock-close]"),
      s_cover: q("[data-sheet-cover]"), s_title: q("[data-sheet-title]"), s_artist: q("[data-sheet-artist]"),
      s_project: q("[data-sheet-project]"), s_labels: q("[data-sheet-labels]"), s_wave: q("[data-sheet-wave]"),
      s_favorite: q("[data-sheet-favorite]"), s_amplify: q("[data-sheet-amplify]"), s_download: q("[data-sheet-download]"),
      s_page: q("[data-sheet-page]")
    };
    labels = root.dataset;
    el.plays.forEach(function (b) { b.addEventListener("click", function () { Dock.toggle(); }); });
    el.nexts.forEach(function (b) { b.addEventListener("click", function () { Dock.next(); }); });
    qa("[data-dock-prev]").forEach(function (b) { b.addEventListener("click", function () { Dock.prev(); }); });
    qa("[data-dock-close]").forEach(function (b) { b.addEventListener("click", function () { expand(false); Dock.close(); }); });
    el.seek.addEventListener("input", function () {
      var d = isFinite(audio.duration) ? audio.duration : (current() && current().duration) || 0;
      Dock.seek(el.seek.value / 1000 * d);
    });
    el.s_wave.addEventListener("click", function (e) {
      var d = isFinite(audio.duration) ? audio.duration : (current() && current().duration) || 0, box = el.s_wave.getBoundingClientRect();
      Dock.seek(Math.max(0, Math.min(1, (e.clientX - box.left) / box.width)) * d);
      if (!Dock.playing) Dock.toggle();
    });
    el.expand.addEventListener("click", function () { expand(true); });
    el.collapse.addEventListener("click", function () { expand(false); });
    // Leaving for a page closes the view; the music goes on.
    el.sheet.addEventListener("click", function (e) { if (e.target.closest("a[href]") && !e.target.closest("[data-sheet-download]")) expand(false); });
    el.s_favorite.addEventListener("click", function () { react(el.s_favorite, "fa-heart"); });
    el.s_amplify.addEventListener("click", function () { react(el.s_amplify, "fa-retweet"); });
    el.tabs.forEach(function (t) { t.addEventListener("click", function () { tab(t.dataset.dockTab); }); });
    if (el.add) el.add.addEventListener("click", addToPlaylist);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !el.sheet.hidden) expand(false);
    });
    // On a phone, sliding the view down closes it.
    var y0 = null;
    el.sheet.addEventListener("touchstart", function (e) { y0 = el.sheet.scrollTop <= 0 ? e.touches[0].clientY : null; }, { passive: true });
    el.sheet.addEventListener("touchend", function (e) {
      if (y0 !== null && e.changedTouches[0].clientY - y0 > 90) expand(false);
      y0 = null;
    });
    window.addEventListener("resize", function () { if (!el.sheet.hidden) drawWave(); });
    restore();
    render();
    emit();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", setup); else setup();
})();
