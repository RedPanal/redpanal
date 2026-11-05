/* Sumar una pista: record while the work plays (compensating the delay), or choose a file. */
(function () {
  "use strict";
  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("contribute-form");
    if (!form) return;
    var mixer = form.rpMixer;
    var fileInput = document.getElementById("id_audio");
    var offsetInput = form.querySelector("[data-offset]");
    var alignedFlag = form.querySelector("[data-aligned-by-ear]");
    var recorder = form.querySelector("[data-recorder]");
    var ready = form.querySelector("[data-ready]");
    var recStartedPerf = null;

    function chosen(name) {
      form.querySelector("[data-file-name]").textContent = name;
      ready.hidden = false;
    }

    // A chosen file: no offset, its alignment is guessed on the server.
    fileInput.addEventListener("change", function () {
      if (!fileInput.files.length) return;
      offsetInput.value = 0;
      alignedFlag.value = "";
      chosen(fileInput.files[0].name);
    });

    // Recorded over the work: in sync by construction, with the playback delay compensated.
    recorder.querySelector("[data-rec-start]").addEventListener("click", function () { if (mixer) mixer.load(); });
    recorder.addEventListener("recorder:start", function () {
      recStartedPerf = performance.now();
      if (mixer && mixer.tracks.length) { mixer.seek(0); mixer.play(); }
    });
    recorder.addEventListener("recorder:done", function (e) {
      var lead = 0, outLatency = 0;
      if (mixer && mixer.tracks.length) {
        mixer.pause();
        if (recStartedPerf && mixer.startedPerf) lead = mixer.startedPerf - recStartedPerf;
        if (mixer.ctx) outLatency = ((mixer.ctx.outputLatency || 0) + (mixer.ctx.baseLatency || 0)) * 1000;
        offsetInput.value = -Math.round(lead + outLatency + 10);
        alignedFlag.value = "1";
      }
      chosen(e.detail.file.name);
    });

    form.addEventListener("submit", function () { form.querySelector("[data-submit]").disabled = true; });
  });
})();
