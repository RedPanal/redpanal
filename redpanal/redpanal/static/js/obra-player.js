/*
 * RedPanal player: one component for works and loose sounds.
 *
 * Full mixer (work page):
 *   <div data-mixer>
 *     <button data-play> <span data-time> <span data-duration> <input type="range" data-seek>
 *     <div data-track data-src data-peaks data-offset [data-candidate] [data-active="false"]>
 *       <div data-wave></div> <button data-mute> <button data-solo> <input type="range" data-volume>
 *     </div>
 *   </div>
 *
 * Compact (cards, lists): one combined waveform, click to seek.
 *   <div data-mixer data-compact> <button data-play> <div data-combined-wave></div> <span data-time> …
 *     <span data-track data-src data-peaks data-offset hidden></span> …
 *   </div>
 *
 * Several aligned parts play in sync with Web Audio (each shifted by its offset), on the page.
 * A single file in compact mode plays in the persistent player (rp-dock.js), so it keeps sounding
 * while browsing; the card shows the same state on its own waveform. It can change tempo keeping
 * the pitch (Explore › Sounds). Inside [data-queue] (a project's files), the others come after it.
 * Only one player sounds at a time.
 */
(function () {
  "use strict";
  if (window.RPMixer) return;  // loaded twice (base + page): keep the first

  function fmt(sec) {
    sec = Math.max(0, sec || 0);
    var m = Math.floor(sec / 60), s = Math.floor(sec % 60);
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function peaksFromBuffer(buffer, bars) {
    var data = buffer.getChannelData(0), step = Math.max(1, Math.floor(data.length / bars)), out = [];
    for (var i = 0; i < bars; i++) {
      var max = 0;
      for (var j = i * step; j < Math.min(data.length, (i + 1) * step); j += 16) {
        var v = Math.abs(data[j]); if (v > max) max = v;
      }
      out.push(max);
    }
    return out;
  }

  function makeCanvas(container) {
    var canvas = document.createElement("canvas"), width = container.clientWidth || 300, height = container.clientHeight || 40;
    var ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio; canvas.height = height * ratio;
    canvas.style.width = width + "px"; canvas.style.height = height + "px";
    canvas.setAttribute("aria-hidden", "true");
    var g = canvas.getContext("2d");
    g.scale(ratio, ratio);
    g.fillStyle = getComputedStyle(container).color || "#8a877f";
    return { canvas: canvas, g: g, width: width, height: height };
  }

  function Track(mixer, el) {
    this.mixer = mixer;
    this.el = el;
    this.src = el.dataset.src || null;
    this.offset = parseInt(el.dataset.offset || "0", 10) / 1000;
    this.candidate = el.hasAttribute("data-candidate");
    this.active = el.dataset.active !== "false";
    this.muted = false;
    this.solo = false;
    this.volume = 1;
    this.buffer = null;
    this.peaks = null;
    this.duration = parseInt(el.dataset.durationMs || "0", 10) / 1000;  // known before loading anything
    this.node = null;
    this.gain = null;
    this.wave = el.querySelector("[data-wave]");
    this.bind();
  }

  Track.prototype.bind = function () {
    var self = this, el = this.el;
    var mute = el.querySelector("[data-mute]"), solo = el.querySelector("[data-solo]"),
        vol = el.querySelector("[data-volume]");
    if (mute) mute.addEventListener("click", function () {
      self.muted = !self.muted; mute.setAttribute("aria-pressed", self.muted); self.mixer.updateGains();
    });
    if (solo) solo.addEventListener("click", function () {
      self.solo = !self.solo; solo.setAttribute("aria-pressed", self.solo); self.mixer.updateGains();
    });
    if (vol) vol.addEventListener("input", function () {
      self.volume = vol.value / 100; self.mixer.updateGains();
    });
  };

  Track.prototype.loadPeaks = function () {
    var self = this, url = this.el.dataset.peaks;
    if (!url || this.peaks) return Promise.resolve();
    return fetch(url).then(function (r) { return r.json(); }).then(function (d) {
      var peaks = (d && d.peaks) || d || [], max = Math.max.apply(null, peaks.concat([0.0001]));
      self.peaks = max > 1 ? peaks.map(function (p) { return p / max; }) : peaks;
      self.duration = (d && d.duration) || self.duration;
    }).catch(function () {});
  };

  Track.prototype.loadBuffer = function (ctx) {
    var self = this;
    if (this.buffer || !this.src) return Promise.resolve();
    return fetch(this.src).then(function (r) { return r.arrayBuffer(); })
      .then(function (ab) { return ctx.decodeAudioData(ab); })
      .then(function (buf) {
        self.buffer = buf;
        self.duration = buf.duration;
        if (!self.peaks) self.peaks = peaksFromBuffer(buf, 300);
      });
  };

  Track.prototype.setBuffer = function (buf) {
    this.buffer = buf;
    this.duration = buf.duration;
    this.peaks = peaksFromBuffer(buf, 300);
  };

  // Peak (0–1) of this track at a moment of the work's timeline.
  Track.prototype.peakAt = function (t) {
    if (!this.peaks || !this.peaks.length || !this.duration) return 0;
    var rel = (t - this.offset) / this.duration;
    if (rel < 0 || rel >= 1) return 0;
    return this.peaks[Math.floor(rel * this.peaks.length)] || 0;
  };

  Track.prototype.draw = function (total) {
    if (!this.wave) return;
    var w = this.wave, peaks = this.peaks;
    w.innerHTML = "";
    if (!peaks || !peaks.length || !total) return;
    var c = makeCanvas(w), origin = this.mixer.origin;
    var start = (this.offset - origin) / total * c.width,
        span = this.duration / total * c.width, bar = 2, gap = 1,
        n = Math.max(1, Math.floor(span / (bar + gap)));
    for (var i = 0; i < n; i++) {
      var p = peaks[Math.floor(i / n * peaks.length)] || 0, h = Math.max(2, p * (c.height - 4));
      c.g.fillRect(start + i * (bar + gap), (c.height - h) / 2, bar, h);
    }
    w.appendChild(c.canvas);
    var head = document.createElement("div");
    head.className = "rp-playhead";
    w.appendChild(head);
  };

  function Mixer(root) {
    var self = this;
    this.root = root;
    this.compact = root.hasAttribute("data-compact");
    this.ctx = null;
    this.master = null;
    this.playing = false;
    this.startedAt = 0;
    this.position = 0;
    this.origin = 0;  // earliest start, can be negative
    this.rate = 1;
    this.tracks = this.own("[data-track]").map(function (el) { return new Track(self, el); });
    // One file in a card or list: stream it with the browser's audio element.
    this.simple = this.compact && this.tracks.length === 1 && !this.tracks[0].offset;
    this.playBtn = this.own("[data-play]")[0];
    this.timeEl = this.own("[data-time]")[0];
    this.durEl = this.own("[data-duration]")[0];
    this.seekEl = this.own("[data-seek]")[0];
    this.statusEl = this.own("[data-status]")[0];
    this.combined = this.own("[data-combined-wave]")[0];
    this.bind();
    var start = function () {
      Promise.all(self.tracks.map(function (t) { return t.loadPeaks(); })).then(function () { self.layout(); });
    };
    if (this.compact && "IntersectionObserver" in window) {
      // Cards load their waveform only when they come into view.
      var io = this.io = new IntersectionObserver(function (entries) {
        if (entries.some(function (e) { return e.isIntersecting; })) { io.disconnect(); start(); }
      }, { rootMargin: "200px" });
      io.observe(root);
    } else {
      start();
    }
    var resizeTimer;
    this.onResize = function () { clearTimeout(resizeTimer); resizeTimer = setTimeout(function () { self.layout(); }, 150); };
    this.onOtherPlay = function (e) { if (!self.docked() && e.detail !== self && self.playing) self.pause(); };
    // A file playing in the persistent player: this card shows whether it's this one, and where it goes.
    this.onDock = function () {
      if (!self.simple) return;
      var was = self.playing;
      self.playing = self.isCurrent() && window.RPDock.playing;
      self.setButton();
      self.paint();
      if (self.playing && !was) self.tick();
    };
    window.addEventListener("resize", this.onResize);
    document.addEventListener("rp:play", this.onOtherPlay);
    document.addEventListener("rp:dock", this.onDock);
    if (this.simple && this.isCurrent()) this.onDock();
  }

  // Leaving the page (rp-nav.js): music in sync stops; a file in the persistent player keeps going.
  Mixer.prototype.destroy = function () {
    if (!this.docked()) this.pause();
    this.stopSources();
    if (this.ctx && this.ctx.close) { try { this.ctx.close(); } catch (e) {} this.ctx = null; }
    if (this.io) this.io.disconnect();
    window.removeEventListener("resize", this.onResize);
    document.removeEventListener("rp:play", this.onOtherPlay);
    document.removeEventListener("rp:dock", this.onDock);
    this.playing = false;
  };

  Mixer.prototype.docked = function () { return this.simple && !!window.RPDock; };
  Mixer.prototype.isCurrent = function () { return this.docked() && window.RPDock.isCurrent(this.tracks[0].src); };

  // What the persistent player shows for this file.
  Mixer.prototype.dockItem = function () {
    var d = this.root.dataset, t = this.tracks[0];
    return {
      id: d.itemId ? parseInt(d.itemId, 10) : null, title: d.itemTitle || "", artist: d.itemArtist || "",
      url: d.itemUrl || "", cover: d.itemCover || "", src: t.src, peaks: t.el.dataset.peaks || "",
      duration: t.duration || null
    };
  };

  // The other files of the same project come after it (then the ones before it).
  Mixer.prototype.dockGroup = function () {
    var box = this.root.closest("[data-queue]"), self = this;
    if (!box) return [];
    var players = Array.prototype.map.call(box.querySelectorAll("[data-mixer][data-compact]"), function (r) { return r.rpMixer; })
      .filter(function (m) { return m && m.simple; });
    var i = players.indexOf(self);
    return players.slice(i + 1).concat(players.slice(0, Math.max(0, i))).map(function (m) { return m.dockItem(); });
  };

  // Elements of this player, leaving out the ones of players nested inside it (mini players of loose parts).
  Mixer.prototype.own = function (selector) {
    var root = this.root;
    return Array.prototype.filter.call(root.querySelectorAll(selector), function (el) {
      return el.parentElement.closest("[data-mixer]") === root;
    });
  };

  Mixer.prototype.bind = function () {
    var self = this;
    if (this.playBtn) this.playBtn.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); self.toggle(); });
    if (this.seekEl) this.seekEl.addEventListener("input", function () {
      self.seek(self.origin + self.seekEl.value / 1000 * self.total());
    });
    if (this.combined) this.combined.addEventListener("click", function (e) {
      e.preventDefault(); e.stopPropagation();
      var box = self.combined.getBoundingClientRect(), frac = (e.clientX - box.left) / box.width;
      self.seek(self.origin + Math.max(0, Math.min(1, frac)) * self.total());
      if (!self.playing) self.play();
    });
    this.root.querySelectorAll("[data-toggle-candidate]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var track = self.trackById(btn.dataset.toggleCandidate);
        if (!track) return;
        self.setActive(track, btn.dataset.state === "on");
        self.root.querySelectorAll('[data-toggle-candidate="' + btn.dataset.toggleCandidate + '"]').forEach(function (b) {
          b.setAttribute("aria-pressed", b === btn);
        });
      });
    });
    this.root.querySelectorAll("[data-seek-to]").forEach(function (el) {
      el.addEventListener("click", function (e) {
        e.preventDefault();
        self.seek(parseInt(el.dataset.seekTo, 10) / 1000);
        if (!self.playing) self.play();
      });
    });
    if (!this.compact) this.root.addEventListener("keydown", function (e) {
      var tag = (e.target.tagName || "").toLowerCase();
      if (e.code === "Space" && ["input", "textarea", "select", "button", "a"].indexOf(tag) === -1) {
        e.preventDefault(); self.toggle();
      }
    });
  };

  Mixer.prototype.trackById = function (id) {
    return this.tracks.filter(function (t) { return t.el.id === id; })[0];
  };

  Mixer.prototype.total = function () {
    var end = 0, start = 0;
    this.tracks.forEach(function (t) {
      end = Math.max(end, t.offset + t.duration);
      start = Math.min(start, t.offset);
    });
    var a = this.isCurrent() ? window.RPDock.audio : this.audio;
    if (this.simple && a && isFinite(a.duration)) end = Math.max(end, a.duration);
    this.origin = start;
    return Math.max(0.001, end - start);
  };

  Mixer.prototype.layout = function () {
    var total = this.total();
    this.tracks.forEach(function (t) { t.draw(total); });
    if (this.combined) this.drawCombined(total);
    if (this.durEl) this.durEl.textContent = fmt(total);
    this.paint();
  };

  // Compact players: every track summed into one waveform along the work's timeline.
  Mixer.prototype.drawCombined = function (total) {
    var box = this.combined, self = this;
    box.querySelectorAll("canvas, .rp-playhead, .rp-progress").forEach(function (n) { n.remove(); });
    var has = this.tracks.some(function (t) { return t.peaks && t.peaks.length; });
    if (!has) { box.classList.add("is-empty"); return; }
    box.classList.remove("is-empty");
    var c = makeCanvas(box), bar = 2, gap = 1, n = Math.floor(c.width / (bar + gap));
    for (var i = 0; i < n; i++) {
      var t = self.origin + (i + 0.5) / n * total, p = 0;
      self.tracks.forEach(function (tr) { p = Math.max(p, tr.peakAt(t)); });
      var h = Math.max(1.5, p * (c.height - 2));
      c.g.fillRect(i * (bar + gap), (c.height - h) / 2, bar, h);
    }
    box.appendChild(c.canvas);
    var progress = document.createElement("div"); progress.className = "rp-progress"; box.appendChild(progress);
    var head = document.createElement("div"); head.className = "rp-playhead"; box.appendChild(head);
  };

  Mixer.prototype.ensureContext = function () {
    if (!this.ctx) {
      var AC = window.AudioContext || window.webkitAudioContext;
      this.ctx = new AC();
      this.master = this.ctx.createGain();
      this.master.connect(this.ctx.destination);
    }
    return this.ctx;
  };

  Mixer.prototype.load = function () {
    var ctx = this.ensureContext(), self = this;
    if (this.statusEl) this.statusEl.textContent = this.statusEl.dataset.loading || "…";
    this.root.classList.add("is-loading");
    return Promise.all(this.tracks.map(function (t) { return t.loadBuffer(ctx); })).then(function () {
      if (self.statusEl) self.statusEl.textContent = "";
      self.root.classList.remove("is-loading");
      self.layout();
    });
  };

  Mixer.prototype.effectiveGain = function (t) {
    var anySolo = this.tracks.some(function (x) { return x.solo; });
    if (t.candidate && !t.active) return 0;
    if (t.muted) return 0;
    if (anySolo && !t.solo) return 0;
    return t.volume;
  };

  Mixer.prototype.updateGains = function () {
    var self = this;
    this.tracks.forEach(function (t) {
      if (t.gain) t.gain.gain.setTargetAtTime(self.effectiveGain(t), self.ctx.currentTime, 0.015);
      t.el.classList.toggle("is-silent", self.effectiveGain(t) === 0);
    });
  };

  Mixer.prototype.currentTime = function () {
    if (this.docked()) return this.isCurrent() ? window.RPDock.audio.currentTime : 0;
    if (this.simple) return this.audio ? this.audio.currentTime : this.position;
    if (!this.playing) return this.position;
    return this.position + (this.ctx.currentTime - this.startedAt);
  };

  Mixer.prototype.currentMs = function () { return Math.round(this.currentTime() * 1000); };

  Mixer.prototype.startSources = function () {
    var ctx = this.ctx, self = this, at = ctx.currentTime + 0.05, from = this.position;
    this.tracks.forEach(function (t) {
      if (!t.buffer) return;
      var gain = ctx.createGain();
      gain.gain.value = self.effectiveGain(t);
      gain.connect(self.master);
      var src = ctx.createBufferSource();
      src.buffer = t.buffer;
      src.connect(gain);
      var rel = from - t.offset;
      if (rel < 0) src.start(at - rel, 0);
      else if (rel < t.buffer.duration) src.start(at, rel);
      else return;
      t.node = src; t.gain = gain;
    });
    this.startedAt = at;
    // Same moment on the page clock, to line up recordings made while listening.
    this.startedPerf = performance.now() + (at - ctx.currentTime) * 1000;
  };

  Mixer.prototype.stopSources = function () {
    this.tracks.forEach(function (t) {
      if (t.node) { try { t.node.stop(); } catch (e) {} t.node.disconnect(); t.node = null; }
      if (t.gain) { t.gain.disconnect(); t.gain = null; }
    });
  };

  Mixer.prototype.simpleAudio = function () {
    var self = this;
    if (!this.audio) {
      var a = this.audio = new Audio();
      a.preload = "none";
      a.preservesPitch = a.mozPreservesPitch = a.webkitPreservesPitch = true;
      a.src = this.tracks[0].src;
      a.addEventListener("ended", function () { self.playing = false; self.setButton(); self.paint(); });
      a.addEventListener("loadedmetadata", function () { self.layout(); });
    }
    return this.audio;
  };

  Mixer.prototype.play = function () {
    var self = this;
    if (this.docked()) {
      this.root.dispatchEvent(new CustomEvent("mixer:play"));
      return window.RPDock.play(this.dockItem(), { group: this.dockGroup(), rate: this.rate }) || Promise.resolve();
    }
    document.dispatchEvent(new CustomEvent("rp:play", { detail: this }));
    if (this.simple) {
      var a = this.simpleAudio();
      a.playbackRate = this.rate;
      this.root.classList.add("is-loading");
      return a.play().then(function () {
        self.root.classList.remove("is-loading");
        self.playing = true; self.setButton(); self.tick();
        self.root.dispatchEvent(new CustomEvent("mixer:play"));
      }).catch(function () { self.root.classList.remove("is-loading"); });
    }
    var ready = this.tracks.every(function (t) { return t.buffer || !t.src; }) ? Promise.resolve() : this.load();
    return ready.then(function () {
      self.ensureContext().resume();
      if (self.position >= self.total() + self.origin - 0.05) self.position = self.origin;
      self.startSources();
      self.playing = true;
      self.setButton();
      self.tick();
      self.root.dispatchEvent(new CustomEvent("mixer:play"));
    });
  };

  Mixer.prototype.pause = function () {
    if (this.docked()) { if (this.isCurrent()) window.RPDock.pause(); return; }
    if (!this.playing) return;
    if (this.simple) { this.audio.pause(); }
    else { this.position = this.currentTime(); this.stopSources(); }
    this.playing = false;
    this.setButton();
    this.root.dispatchEvent(new CustomEvent("mixer:pause"));
  };

  Mixer.prototype.toggle = function () { this.playing ? this.pause() : this.play(); };

  Mixer.prototype.seek = function (sec) {
    if (this.docked()) {
      if (this.isCurrent()) window.RPDock.seek(sec);
      else window.RPDock.play(this.dockItem(), { group: this.dockGroup(), rate: this.rate, start: sec });
      return;
    }
    if (this.simple) {
      var a = this.simpleAudio();
      try { a.currentTime = Math.max(0, sec); } catch (e) {}
      this.paint();
      return;
    }
    var was = this.playing;
    if (was) { this.stopSources(); this.playing = false; }
    this.position = Math.max(this.origin, sec);
    if (was) { this.startSources(); this.playing = true; }
    this.paint();
  };

  // Listen at another tempo (single files only: the audio element keeps the pitch).
  Mixer.prototype.setRate = function (rate) {
    this.rate = rate || 1;
    if (this.isCurrent()) window.RPDock.setRate(this.rate);
    if (this.audio) this.audio.playbackRate = this.rate;
  };

  Mixer.prototype.setActive = function (track, on) {
    track.active = on;
    track.el.dataset.active = on ? "true" : "false";
    if (this.ctx) this.updateGains(); else track.el.classList.toggle("is-silent", !on);
  };

  Mixer.prototype.setOffset = function (track, ms) {
    track.offset = ms / 1000;
    this.layout();
    if (this.playing) this.seek(this.currentTime());
  };

  Mixer.prototype.addTrack = function (el, buffer) {
    var t = new Track(this, el);
    if (buffer) t.setBuffer(buffer);
    this.tracks.push(t);
    this.layout();
    return t;
  };

  Mixer.prototype.removeTrack = function (track) {
    if (track.node) { try { track.node.stop(); } catch (e) {} }
    this.tracks = this.tracks.filter(function (t) { return t !== track; });
    this.layout();
  };

  Mixer.prototype.setButton = function () {
    if (!this.playBtn) return;
    var label = this.playing ? this.playBtn.dataset.labelPause : this.playBtn.dataset.labelPlay;
    if (label) this.playBtn.setAttribute("aria-label", label);
    this.playBtn.setAttribute("aria-pressed", this.playing ? "true" : "false");
    this.playBtn.innerHTML = this.playing ? '<i class="fa fa-pause" aria-hidden="true"></i>' : '<i class="fa fa-play" aria-hidden="true"></i>';
  };

  Mixer.prototype.paint = function () {
    var total = this.total(), now = this.currentTime(), pct = Math.min(100, Math.max(0, (now - this.origin) / total * 100));
    if (this.timeEl) this.timeEl.textContent = fmt(now);
    if (this.seekEl && document.activeElement !== this.seekEl) this.seekEl.value = Math.round(pct * 10);
    this.root.querySelectorAll(".rp-playhead").forEach(function (h) { h.style.left = pct + "%"; });
    this.root.querySelectorAll(".rp-progress").forEach(function (p) { p.style.width = pct + "%"; });
    this.root.dispatchEvent(new CustomEvent("mixer:time", { detail: { ms: Math.round(now * 1000), label: fmt(now) } }));
  };

  Mixer.prototype.tick = function () {
    var self = this;
    if (!this.playing) return;
    if (!this.simple && this.currentTime() >= this.total() + this.origin) {
      this.pause(); this.position = this.origin; this.paint(); return;
    }
    this.paint();
    requestAnimationFrame(function () { self.tick(); });
  };

  window.RPMixer = Mixer;
  window.rpFormatTime = fmt;
  window.rpInitPlayers = function (scope) {
    (scope || document).querySelectorAll("[data-mixer]").forEach(function (root) {
      if (!root.rpMixer) root.rpMixer = new Mixer(root);
    });
  };
  document.addEventListener("DOMContentLoaded", function () { window.rpInitPlayers(); });
})();
