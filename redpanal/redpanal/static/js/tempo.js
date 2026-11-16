/*
 * Rough tempo estimate from an AudioBuffer, in the browser.
 * Onset strength from the energy envelope, autocorrelation with fractional lags,
 * and a mild preference for tempos around 110 BPM to pick between octaves.
 * Good enough to prefill a field the person can correct; not a beat tracker.
 */
(function () {
  "use strict";

  function onsetEnvelope(buffer, hop, win) {
    var sr = buffer.sampleRate, length = Math.min(buffer.length, sr * 60);
    var channels = buffer.numberOfChannels, mono = new Float32Array(length);
    for (var c = 0; c < channels; c++) {
      var data = buffer.getChannelData(c);
      for (var i = 0; i < length; i++) mono[i] += data[i] / channels;
    }
    var frames = Math.floor((length - win) / hop);
    if (frames < 128) return null;
    // The low band (kick, bass) usually carries the pulse: follow it with a one-pole low-pass.
    var low = new Float32Array(length), alpha = 1 - Math.exp(-2 * Math.PI * 150 / sr), y = 0;
    for (i = 0; i < length; i++) { y += alpha * (mono[i] - y); low[i] = y; }
    function rmsEnvelope(signal) {
      var env = new Float32Array(frames);
      for (var f = 0; f < frames; f++) {
        var sum = 0, start = f * hop;
        for (var j = 0; j < win; j++) { var v = signal[start + j]; sum += v * v; }
        env[f] = Math.sqrt(sum / win);
      }
      return env;
    }
    function rise(env) {
      var out = new Float32Array(frames), max = 1e-9;
      for (var f = 1; f < frames; f++) { out[f] = Math.max(0, env[f] - env[f - 1]); if (out[f] > max) max = out[f]; }
      for (f = 0; f < frames; f++) out[f] /= max;
      return out;
    }
    var full = rise(rmsEnvelope(mono)), bass = rise(rmsEnvelope(low));
    var onset = new Float32Array(frames), mean = 0;
    for (var f = 0; f < frames; f++) { onset[f] = 0.7 * bass[f] + 0.3 * full[f]; mean += onset[f]; }
    mean /= frames;
    for (f = 0; f < frames; f++) onset[f] -= mean;
    return onset;
  }

  function estimateTempo(buffer) {
    var hop = 256, fps = buffer.sampleRate / hop;
    var onset = onsetEnvelope(buffer, hop, 1024);
    if (!onset) return null;  // shorter than ~1.5 s: nothing to measure
    var frames = onset.length, maxLag = Math.ceil(60 * fps / 50) * 2 + 2;
    var ac = new Float32Array(maxLag + 1);
    for (var lag = 1; lag <= maxLag && lag < frames; lag++) {
      var s = 0;
      for (var k = 0; k + lag < frames; k++) s += onset[k] * onset[k + lag];
      ac[lag] = s / (frames - lag);
    }
    function acf(x) {  // autocorrelation at a fractional lag
      var i = Math.floor(x), t = x - i;
      return i + 1 > maxLag ? 0 : ac[i] * (1 - t) + ac[i + 1] * t;
    }
    function score(bpm) {
      var lag = 60 * fps / bpm;
      return acf(lag) + 0.5 * acf(lag * 2);  // favour the pulse over its subdivisions
    }
    function prior(bpm) {
      var octaves = Math.log(bpm / 110) / Math.LN2;
      return Math.exp(-0.5 * octaves * octaves);
    }

    var best = 60, bestScore = -Infinity, total = 0, n = 0;
    for (var bpm = 60; bpm <= 180; bpm += 0.25) {
      var sc = score(bpm);
      total += Math.max(0, sc); n++;
      if (sc > bestScore) { bestScore = sc; best = bpm; }
    }
    if (bestScore <= 0) return null;

    // Between the found tempo and its usual confusions (double, half, 3:2), keep the most plausible.
    var chosen = best, chosenWeight = -Infinity;
    [best / 2, best * 2 / 3, best, best * 3 / 2, best * 2].forEach(function (b) {
      if (b < 55 || b > 200) return;
      var w = score(b) * prior(b);
      if (w > chosenWeight) { chosenWeight = w; chosen = b; }
    });
    return { bpm: Math.round(chosen), confidence: bestScore / (total / n) };
  }

  window.rpEstimateTempo = estimateTempo;
})();
