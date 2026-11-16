/* Steps of the "Create" screen: choose → review and trim → publish. */
(function () {
  "use strict";
  var form = document.getElementById("work-form");
  if (!form) return;

  var steps = {};
  form.querySelectorAll("[data-step]").forEach(function (s) { steps[s.dataset.step] = s; });
  var fileInput = document.getElementById("id_audio");
  var trimStart = form.querySelector("[data-trim-start]"), trimEnd = form.querySelector("[data-trim-end]");
  var hiddenStart = document.getElementById("id_trim_start_ms"), hiddenEnd = document.getElementById("id_trim_end_ms");
  var canvas = form.querySelector("[data-trim-wave]");
  var playBtn = form.querySelector("[data-trim-play]");
  var ctx = null, buffer = null, source = null, recordedSeconds = 0;
  var fmt = window.rpFormatTime;
  var hasErrors = !!form.querySelector(".text-danger:not(:empty)");

  form.classList.add("is-enhanced");
  fileInput.classList.add("visually-hidden");
  fileInput.removeAttribute("required");

  function show(name) {
    Object.keys(steps).forEach(function (k) { steps[k].hidden = k !== name; });
    var h = steps[name].querySelector("h2:not(.visually-hidden)") || steps[name].querySelector("button, input");
    if (h) { h.setAttribute("tabindex", "-1"); h.focus(); }
  }
  show("choose");
  // After a validation error the browser drops the file: show both steps so it can be chosen again.
  if (hasErrors) steps.details.hidden = false;

  function audioContext() {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    return ctx;
  }

  function review(file) {
    stopPreview();
    show("review");
    form.querySelector("[data-trim-unavailable]").hidden = true;
    file.arrayBuffer().then(function (ab) { return audioContext().decodeAudioData(ab); }).then(function (buf) {
      buffer = buf;
      var ms = Math.round(buf.duration * 1000);
      [trimStart, trimEnd].forEach(function (r) { r.max = ms; });
      trimStart.value = 0; trimEnd.value = ms;
      draw(); update();
      suggestTempo(buf);
    }).catch(function () {
      buffer = null;
      form.querySelector("[data-trim-unavailable]").hidden = false;
      hiddenStart.value = ""; hiddenEnd.value = "";
    });
  }

  // Prefill the tempo with an estimate the person can correct.
  function suggestTempo(buf) {
    var input = document.getElementById("id_tempo"), note = form.querySelector("[data-tempo-note]");
    if (!window.rpEstimateTempo || !input || input.value) return;
    var estimate = window.rpEstimateTempo(buf);
    // Measured: steady tones and noise score 6–9, rhythmic material 16 and up.
    if (!estimate || estimate.confidence < 12) return;
    input.value = estimate.bpm;
    input.dataset.estimated = "1";
    if (note) { note.textContent = note.dataset.template.replace("%s", estimate.bpm); note.hidden = false; }
  }

  function draw() {
    var w = canvas.clientWidth, h = canvas.clientHeight, ratio = window.devicePixelRatio || 1;
    canvas.width = w * ratio; canvas.height = h * ratio;
    var g = canvas.getContext("2d"); g.scale(ratio, ratio);
    var data = buffer.getChannelData(0), bars = Math.floor(w / 3), step = Math.floor(data.length / bars);
    g.fillStyle = getComputedStyle(canvas).color;
    for (var i = 0; i < bars; i++) {
      var max = 0;
      for (var j = i * step; j < (i + 1) * step; j += 32) max = Math.max(max, Math.abs(data[j]));
      var bh = Math.max(2, Math.min(1, max * 1.6) * (h - 6));
      g.fillRect(i * 3, (h - bh) / 2, 2, bh);
    }
  }

  function update() {
    var s = parseInt(trimStart.value, 10), e = parseInt(trimEnd.value, 10), max = parseInt(trimEnd.max, 10);
    if (s > e - 500) { if (document.activeElement === trimStart) { s = e - 500; trimStart.value = s; } else { e = s + 500; trimEnd.value = e; } }
    form.querySelector("[data-shade-start]").style.width = (s / max * 100) + "%";
    form.querySelector("[data-shade-end]").style.width = ((max - e) / max * 100) + "%";
    form.querySelector("[data-trim-from]").textContent = fmt(s / 1000);
    form.querySelector("[data-trim-to]").textContent = fmt(e / 1000);
    form.querySelector("[data-trim-length]").textContent = fmt((e - s) / 1000);
    hiddenStart.value = s > 0 ? s : "";
    hiddenEnd.value = e < max ? e : "";
  }

  function stopPreview() {
    if (source) { try { source.stop(); } catch (err) {} source = null; }
    playBtn.innerHTML = '<i class="fa fa-play" aria-hidden="true"></i>';
  }

  playBtn.addEventListener("click", function () {
    if (source) { stopPreview(); return; }
    if (!buffer) return;
    var s = trimStart.value / 1000, e = trimEnd.value / 1000;
    source = audioContext().createBufferSource();
    source.buffer = buffer;
    source.connect(audioContext().destination);
    source.onended = stopPreview;
    audioContext().resume();
    source.start(0, s, e - s);
    playBtn.innerHTML = '<i class="fa fa-pause" aria-hidden="true"></i>';
  });

  [trimStart, trimEnd].forEach(function (r) { r.addEventListener("input", update); });

  var recorderRoot = form.querySelector("[data-recorder]");
  recorderRoot.addEventListener("recorder:done", function (e) {
    recordedSeconds = e.detail.seconds;
    review(e.detail.file);
  });
  fileInput.addEventListener("change", function () {
    if (fileInput.files.length) review(fileInput.files[0]);
  });

  form.querySelector("[data-again]").addEventListener("click", function () {
    stopPreview();
    fileInput.value = "";
    show("choose");
  });
  form.querySelector("[data-continue]").addEventListener("click", function () {
    stopPreview();
    show("details");
    form.querySelector("#id_name").focus();
  });

  form.addEventListener("submit", function (e) {
    if (!fileInput.files.length) { e.preventDefault(); show("choose"); return; }
    form.querySelector("[data-submit]").disabled = true;
    form.querySelector("[data-uploading]").hidden = false;
  });

  // The license note depends on the stage: public now, or later.
  var note = form.querySelector("[data-license-note]");
  function syncLicense() {
    var checked = form.querySelector("input[name=visibility]:checked");
    var isPublic = checked && checked.value === "public";
    note.querySelector('[data-when="public"]').hidden = !isPublic;
    note.querySelector('[data-when="closed"]').hidden = isPublic;
  }
  form.querySelectorAll("input[name=visibility]").forEach(function (r) { r.addEventListener("change", syncLicense); });
  syncLicense();

  var cancel = document.querySelector("[data-cancel]");
  if (cancel) cancel.addEventListener("click", function (e) {
    var rec = recorderRoot.rpRecorder;
    var seconds = rec && (rec.state === "recording" || rec.state === "paused") ? rec.seconds : recordedSeconds;
    if (seconds > 10 && !window.confirm(cancel.dataset.confirm || "¿Descartar la grabación?")) e.preventDefault();
  });
})();
