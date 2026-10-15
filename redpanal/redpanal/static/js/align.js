/*
 * Does a part line up with the rest of the work? Compare onset envelopes at
 * different offsets (cross-correlation) and report the best one.
 *
 *   rpSuggestOffset([{buffer, offsetMs}, …], candidateBuffer) → {offsetMs, confidence, verdict}
 *
 * verdict: "aligned" (clear match near 0), "shifted" (clear match elsewhere: apply the offset),
 * "unclear" (no clear match: probably a loose part, or too little in common to tell).
 */
(function () {
  "use strict";
  var HOP = 256, WIN = 1024, MAX_SECONDS = 60, SEARCH_SECONDS = 20;

  function envelope(buffer) {
    var sr = buffer.sampleRate, length = Math.min(buffer.length, sr * MAX_SECONDS);
    var channels = buffer.numberOfChannels, mono = new Float32Array(length);
    for (var c = 0; c < channels; c++) {
      var d = buffer.getChannelData(c);
      for (var i = 0; i < length; i++) mono[i] += d[i] / channels;
    }
    var frames = Math.max(0, Math.floor((length - WIN) / HOP)), env = new Float32Array(frames), prev = 0;
    for (var f = 0; f < frames; f++) {
      var sum = 0, start = f * HOP;
      for (var j = 0; j < WIN; j++) { var v = mono[start + j]; sum += v * v; }
      var rms = Math.sqrt(sum / WIN);
      env[f] = Math.max(0, rms - prev);  // energy rises: attacks
      prev = rms;
    }
    // Every file "attacks" where it starts and stops where it ends: those edges would match
    // at offset 0 for any pair of files, so they don't count.
    var edge = Math.min(Math.round(0.5 * sr / HOP), Math.floor(frames / 4));
    for (f = 0; f < edge; f++) { env[f] = 0; env[frames - 1 - f] = 0; }
    return { env: env, fps: sr / HOP };
  }

  function normalise(a) {
    var mean = 0, i;
    for (i = 0; i < a.length; i++) mean += a[i];
    mean /= a.length || 1;
    var sd = 0;
    for (i = 0; i < a.length; i++) { a[i] -= mean; sd += a[i] * a[i]; }
    sd = Math.sqrt(sd / (a.length || 1)) || 1;
    for (i = 0; i < a.length; i++) a[i] /= sd;
    return a;
  }

  function suggestOffset(references, candidate) {
    if (!references.length || !candidate) return null;
    var cand = envelope(candidate), fps = cand.fps;
    // Reference: the aligned parts summed where they actually sound (their own offsets).
    var refLength = 0, envs = references.map(function (r) {
      var e = envelope(r.buffer), shift = Math.round((r.offsetMs || 0) / 1000 * fps);
      refLength = Math.max(refLength, shift + e.env.length);
      return { env: e.env, shift: shift };
    });
    if (refLength < 64 || cand.env.length < 64) return null;
    var ref = new Float32Array(refLength);
    envs.forEach(function (e) {
      for (var i = 0; i < e.env.length; i++) { var k = i + e.shift; if (k >= 0 && k < refLength) ref[k] += e.env[i]; }
    });
    normalise(ref);
    var c = normalise(Float32Array.from(cand.env));

    var maxLag = Math.round(SEARCH_SECONDS * fps), scores = new Float32Array(2 * maxLag + 1);
    var best = -Infinity, mean = 0, sq = 0, valid = 0;
    // Divide by the full length, not the overlap: tiny overlaps at the edges can't win by chance.
    var norm = Math.min(c.length, refLength), minOverlap = 0.3 * norm;
    for (var lag = -maxLag; lag <= maxLag; lag++) {
      // Candidate frame j sounds at reference frame j + lag.
      var s = 0, n = 0, j0 = Math.max(0, -lag), j1 = Math.min(c.length, refLength - lag);
      for (var j = j0; j < j1; j++) { s += c[j] * ref[j + lag]; n++; }
      var score = n >= minOverlap ? s / norm : NaN;
      scores[lag + maxLag] = score;
      if (score === score) {  // statistics only over lags with enough overlap
        mean += score; sq += score * score; valid++;
        if (score > best) best = score;
      }
    }
    var count = scores.length;
    if (valid < 16) return null;
    mean /= valid;
    var sd = Math.sqrt(Math.max(1e-12, sq / valid - mean * mean));

    // Music repeats every beat: among the near-best peaks, prefer the one closest to 0.
    var chosen = null;
    for (var k = 1; k < count - 1; k++) {
      var v = scores[k];
      if (v >= 0.85 * best && v >= scores[k - 1] && v >= scores[k + 1]) {
        if (chosen === null || Math.abs(k - maxLag) < Math.abs(chosen - maxLag)) chosen = k;
      }
    }
    if (chosen === null) return null;
    var a = scores[chosen - 1], b = scores[chosen], cc = scores[chosen + 1], shift = 0;
    if ((a - 2 * b + cc) !== 0) shift = 0.5 * (a - cc) / (a - 2 * b + cc);
    var offsetMs = Math.round(((chosen - maxLag) + shift) / fps * 1000);
    var confidence = (b - mean) / sd;  // how far the match stands out
    // Measured on test material: related parts score 9–11, unrelated ones and noise 3–5.
    var verdict = confidence < 7 ? "unclear" : (Math.abs(offsetMs) <= 30 ? "aligned" : "shifted");
    return { offsetMs: offsetMs, confidence: confidence, verdict: verdict };
  }

  window.rpSuggestOffset = suggestOffset;
})();
