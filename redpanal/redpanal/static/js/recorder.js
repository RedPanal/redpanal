/*
 * Browser recorder. Fills a regular <input type="file"> with the recording,
 * so the form still posts as a normal multipart form.
 *
 *   <div data-recorder data-target-input="id_audio" [data-countdown="3"]>
 *     <button data-rec-start> <button data-rec-pause> <button data-rec-stop>
 *     <span data-rec-time> <div data-rec-level><span></span></div> <span data-rec-countdown>
 *   </div>
 *
 * Fires "recorder:start" and "recorder:done" ({ file, seconds }) on the root.
 */
(function () {
  "use strict";

  var MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];

  function pickMime() {
    if (!window.MediaRecorder || !MediaRecorder.isTypeSupported) return "";
    for (var i = 0; i < MIME_TYPES.length; i++) if (MediaRecorder.isTypeSupported(MIME_TYPES[i])) return MIME_TYPES[i];
    return "";
  }

  function extFor(mime) {
    if (mime.indexOf("mp4") !== -1) return "m4a";
    if (mime.indexOf("ogg") !== -1) return "ogg";
    return "webm";
  }

  function Recorder(root) {
    this.root = root;
    this.input = document.getElementById(root.dataset.targetInput);
    this.countdown = parseInt(root.dataset.countdown || "3", 10);
    this.q = function (sel) { return root.querySelector(sel); };
    this.state = "idle";
    this.seconds = 0;
    this.bind();
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      root.classList.add("is-unsupported");
    }
  }

  Recorder.prototype.bind = function () {
    var self = this, start = this.q("[data-rec-start]"), stop = this.q("[data-rec-stop]"),
        pause = this.q("[data-rec-pause]");
    if (start) start.addEventListener("click", function () { self.start(); });
    if (stop) stop.addEventListener("click", function () { self.stop(); });
    if (pause) pause.addEventListener("click", function () { self.togglePause(); });
  };

  Recorder.prototype.setState = function (s) {
    this.state = s;
    this.root.dataset.state = s;
  };

  Recorder.prototype.start = function () {
    var self = this;
    if (this.state !== "idle") return;
    this.setState("asking");
    navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false }
    }).then(function (stream) {
      self.stream = stream;
      return self.runCountdown();
    }).then(function () {
      self.begin();
    }).catch(function (err) {
      self.setState("idle");
      var msg = self.root.dataset.errorText || "No se pudo usar el micrófono.";
      self.root.dispatchEvent(new CustomEvent("recorder:error", { detail: { message: msg, error: err } }));
      var out = self.q("[data-rec-error]");
      if (out) out.textContent = msg;
    });
  };

  Recorder.prototype.runCountdown = function () {
    var self = this, el = this.q("[data-rec-countdown]"), n = this.countdown;
    if (!n) return Promise.resolve();
    this.setState("countdown");
    return new Promise(function (resolve) {
      (function step() {
        if (el) el.textContent = n;
        if (n === 0) { if (el) el.textContent = ""; resolve(); return; }
        n -= 1;
        setTimeout(step, 1000);
      })();
    });
  };

  Recorder.prototype.begin = function () {
    var self = this, mime = pickMime();
    this.mime = mime || "audio/webm";
    this.chunks = [];
    this.media = mime ? new MediaRecorder(this.stream, { mimeType: mime }) : new MediaRecorder(this.stream);
    this.media.ondataavailable = function (e) { if (e.data && e.data.size) self.chunks.push(e.data); };
    this.media.onstop = function () { self.finish(); };
    this.meter();
    this.keepAwake();
    this.media.start(1000);
    this.seconds = 0;
    this.lastTick = Date.now();
    this.setState("recording");
    this.timer = setInterval(function () {
      if (self.state === "recording") { self.seconds += (Date.now() - self.lastTick) / 1000; }
      self.lastTick = Date.now();
      var t = self.q("[data-rec-time]");
      if (t) t.textContent = window.rpFormatTime ? window.rpFormatTime(self.seconds) : Math.round(self.seconds);
    }, 200);
    this.root.dispatchEvent(new CustomEvent("recorder:start"));
  };

  Recorder.prototype.togglePause = function () {
    if (!this.media) return;
    if (this.state === "recording") { this.media.pause(); this.setState("paused"); }
    else if (this.state === "paused") { this.media.resume(); this.lastTick = Date.now(); this.setState("recording"); }
  };

  Recorder.prototype.stop = function () {
    if (this.media && (this.state === "recording" || this.state === "paused")) this.media.stop();
  };

  Recorder.prototype.finish = function () {
    clearInterval(this.timer);
    if (this.levelRaf) cancelAnimationFrame(this.levelRaf);
    if (this.audioCtx) this.audioCtx.close();
    this.stream.getTracks().forEach(function (t) { t.stop(); });
    if (this.wakeLock) { this.wakeLock.release().catch(function () {}); this.wakeLock = null; }
    var type = this.mime.split(";")[0];
    var file = new File([new Blob(this.chunks, { type: type })], "grabacion." + extFor(this.mime), { type: type });
    if (this.input && window.DataTransfer) {
      var dt = new DataTransfer();
      dt.items.add(file);
      this.input.files = dt.files;
    }
    this.setState("idle");
    this.root.dispatchEvent(new CustomEvent("recorder:done", { detail: { file: file, seconds: this.seconds } }));
  };

  Recorder.prototype.meter = function () {
    var self = this, bar = this.q("[data-rec-level] span");
    if (!bar) return;
    var AC = window.AudioContext || window.webkitAudioContext;
    this.audioCtx = new AC();
    var analyser = this.audioCtx.createAnalyser();
    analyser.fftSize = 1024;
    this.audioCtx.createMediaStreamSource(this.stream).connect(analyser);
    var data = new Float32Array(analyser.fftSize);
    (function loop() {
      analyser.getFloatTimeDomainData(data);
      var sum = 0;
      for (var i = 0; i < data.length; i++) sum += data[i] * data[i];
      var level = Math.min(1, Math.sqrt(sum / data.length) * 4);
      bar.style.width = Math.round(level * 100) + "%";
      self.levelRaf = requestAnimationFrame(loop);
    })();
  };

  Recorder.prototype.keepAwake = function () {
    var self = this;
    if (navigator.wakeLock && navigator.wakeLock.request) {
      navigator.wakeLock.request("screen").then(function (l) { self.wakeLock = l; }).catch(function () {});
    }
  };

  window.RPRecorder = Recorder;
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-recorder]").forEach(function (root) { root.rpRecorder = new Recorder(root); });
  });
})();
