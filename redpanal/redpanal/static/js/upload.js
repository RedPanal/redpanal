/*
 * Uploading (project/upload.html): drop or choose files and folders, or record.
 * Each audio file goes up on its own with its progress (/crear/archivo/). Then, only if needed:
 * same project? same length → stems? Session files travel with the project.
 */
(function () {
  "use strict";
  window.rpPage(function () {
    var root = document.querySelector("[data-upload]");
    if (!root) return;
    var audioExt = root.dataset.audioExt.split(","), attachExt = root.dataset.attachmentExt.split(",");
    var list = root.querySelector("[data-list]"), errorEl = root.querySelector("[data-error]");
    var ask = root.querySelector("[data-ask]"), ctxForm = root.querySelector("[data-context]");
    var uploaded = [], attachments = [], pending = 0, folderName = "", together = null;

    function ext(name) { var i = name.lastIndexOf("."); return i < 0 ? "" : name.slice(i + 1).toLowerCase(); }
    function csrf() { return ctxForm.querySelector("[name=csrfmiddlewaretoken]").value; }
    function show(step) { root.querySelectorAll("[data-step]").forEach(function (s) { s.hidden = s.dataset.step !== step; }); }

    // -- collecting files: inputs, drops (folders included) -------------------------------------
    function take(files) {
      files = files.filter(function (f) { return f && f.name && f.name.charAt(0) !== "."; });
      if (!files.length) return;
      show("files");
      files.forEach(function (f) {
        var e = ext(f.name);
        if (audioExt.indexOf(e) !== -1) send(f);
        else if (attachExt.indexOf(e) !== -1) attachments.push(f);
        else row(f.name).note(root.dataset.skipped);
      });
      if (!pending) settle();
    }

    function walk(entry, path) {
      return new Promise(function (resolve) {
        if (entry.isFile) { entry.file(function (f) { resolve([f]); }, function () { resolve([]); }); return; }
        if (!entry.isDirectory) { resolve([]); return; }
        if (!folderName) folderName = entry.name;
        var reader = entry.createReader(), all = [];
        (function more() {
          reader.readEntries(function (entries) {
            if (!entries.length) { Promise.all(all).then(function (r) { resolve([].concat.apply([], r)); }); return; }
            entries.forEach(function (en) { all.push(walk(en, path + entry.name + "/")); });
            more();
          }, function () { resolve([]); });
        })();
      });
    }

    var drop = root.querySelector("[data-drop]");
    ["dragenter", "dragover"].forEach(function (t) {
      drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.add("is-over"); });
    });
    ["dragleave", "drop"].forEach(function (t) {
      drop.addEventListener(t, function () { drop.classList.remove("is-over"); });
    });
    drop.addEventListener("drop", function (e) {
      e.preventDefault();
      var items = e.dataTransfer.items, entries = [];
      if (items && items.length && items[0].webkitGetAsEntry) {
        entries = Array.prototype.map.call(items, function (it) { return it.webkitGetAsEntry(); }).filter(Boolean);
      }
      if (entries.length) {
        Promise.all(entries.map(function (en) { return walk(en, ""); }))
          .then(function (r) { take([].concat.apply([], r)); });
      } else {
        take(Array.prototype.slice.call(e.dataTransfer.files));
      }
    });
    drop.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); root.querySelector("#up-files").click(); }
    });
    root.querySelectorAll("[data-files]").forEach(function (input) {
      input.addEventListener("change", function () {
        var files = Array.prototype.slice.call(input.files);
        if (input.hasAttribute("webkitdirectory") && files[0] && files[0].webkitRelativePath) {
          folderName = files[0].webkitRelativePath.split("/")[0];
        }
        take(files);
        input.value = "";
      });
    });

    // A recording is one more file. Coming from "Record" in the Crear panel, it's the one at hand.
    var rec = root.querySelector("[data-recorder]");
    if (/[?&]grabar=1/.test(location.search)) {
      var startBtn = rec.querySelector("[data-rec-start]");
      startBtn.scrollIntoView({ block: "center" });
      startBtn.focus();
      rec.classList.add("is-wanted");
    }
    rec.addEventListener("recorder:done", function (e) {
      var f = e.detail.file, when = new Date();
      var name = root.dataset.recordingName + " " + when.toLocaleDateString() + " " + when.toLocaleTimeString().slice(0, 5);
      take([new File([f], name.replace(/[\/:]/g, "-") + "." + ext(f.name), { type: f.type })]);
    });

    // -- sending, one by one with progress (two at a time) ------------------------------------
    function row(name) {
      var li = document.createElement("li"); li.className = "rp-upload";
      li.innerHTML = '<span class="rp-upload-name"></span><span class="rp-upload-bar"><span></span></span><span class="rp-upload-state small rp-muted"></span>';
      li.querySelector(".rp-upload-name").textContent = name;
      list.appendChild(li);
      return {
        el: li,
        progress: function (p) { li.querySelector(".rp-upload-bar span").style.width = Math.round(p * 100) + "%"; },
        done: function (text) { li.classList.add("is-done"); this.progress(1); li.querySelector(".rp-upload-state").innerHTML = '<i class="fa fa-check" aria-hidden="true"></i> '; li.querySelector(".rp-upload-state").appendChild(document.createTextNode(text || "")); },
        note: function (text) { li.classList.add("is-error"); li.querySelector(".rp-upload-state").textContent = text; }
      };
    }

    var queue = [], running = 0, order = 0;
    function send(f) { pending++; queue.push({ file: f, row: row(f.name), order: order++ }); pump(); }
    function pump() {
      while (running < 2 && queue.length) {
        running++;
        (function (job) {
          var data = new FormData(); data.append("audio", job.file);
          var xhr = new XMLHttpRequest();
          xhr.open("POST", root.dataset.fileUrl);
          xhr.setRequestHeader("X-CSRFToken", csrf());
          xhr.upload.onprogress = function (e) { if (e.lengthComputable) job.row.progress(e.loaded / e.total * 0.95); };
          xhr.onload = function () {
            var res = {}; try { res = JSON.parse(xhr.responseText); } catch (err) {}
            if (xhr.status === 200 && res.id) {
              res.order = job.order; uploaded.push(res); job.row.done(res.name);
              uploaded.sort(function (x, y) { return x.order - y.order; });  // as chosen, not as finished
            }
            else job.row.note(res.error || xhr.statusText);
            finish();
          };
          xhr.onerror = function () { job.row.note(xhr.statusText || "…"); finish(); };
          xhr.send(data);
        })(queue.shift());
      }
    }
    function finish() { running--; pending--; pump(); if (!pending) settle(); }

    // -- the only questions there are ---------------------------------------------------------
    function sameLength() {
      var d = uploaded.map(function (u) { return u.duration; });
      if (d.length < 2 || d.some(function (x) { return !x; })) return false;
      var max = Math.max.apply(null, d), min = Math.min.apply(null, d);
      return max - min <= max * 0.01;
    }

    function settle() {
      if (!uploaded.length) return;
      ask.hidden = false;
      var many = uploaded.length > 1;
      root.querySelector("[data-ask-group]").hidden = !many;
      root.querySelector("[data-ask-single]").hidden = many;
      var wrap = root.querySelector("[data-existing-wrap]");
      if (wrap) wrap.hidden = !many;  // with one file, "Is it part of a project?" already lists them
      root.querySelector("[data-name]").value = folderName || (many ? root.dataset.defaultName : uploaded[0].name);
      root.querySelector("[data-continue]").hidden = many && together === null;
      // Coming from a sound or a work: the files go into the project named above.
      var top = root.querySelector("[data-top-name]");
      if (top) {
        root.querySelector("[data-name]").value = top.value;
        if (many) root.querySelector('[data-together="1"]').click();
        else { into.value = "new"; root.querySelector("[data-ask-project]").hidden = false; }
      }
    }

    root.querySelectorAll("[data-together]").forEach(function (b) {
      b.addEventListener("click", function () {
        together = b.dataset.together === "1";
        root.querySelectorAll("[data-together]").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
        root.querySelector("[data-ask-project]").hidden = !together;
        root.querySelector("[data-ask-stems]").hidden = !(together && sameLength());
        root.querySelector("[data-continue]").hidden = false;
        if (!together) organize();
      });
    });
    var into = root.querySelector("[data-into]");
    if (into) into.addEventListener("change", function () {
      root.querySelector("[data-ask-project]").hidden = into.value !== "new";
      root.querySelector("[data-ask-stems]").hidden = true;
    });

    root.querySelector("[data-continue]").addEventListener("click", organize);

    function organize() {
      var data = new FormData(ctxForm);
      data.append("ids", uploaded.map(function (u) { return u.id; }).join(","));
      var single = uploaded.length === 1, existing = root.querySelector("[data-existing]");
      var group = single ? (into.value !== "") : together;
      data.append("together", group ? "1" : "0");
      if (group) {
        data.append("name", root.querySelector("[data-name]").value);
        var project = single ? (into.value !== "new" ? into.value : "") : (existing ? existing.value : "");
        if (project) data.append("project", project);
        var stems = root.querySelector("[data-stems]:checked");
        data.append("stems", !root.querySelector("[data-ask-stems]").hidden && stems && stems.value === "1" ? "1" : "0");
      }
      root.querySelector("[data-continue]").disabled = true;
      fetch(root.dataset.organizeUrl, { method: "POST", body: data, credentials: "same-origin" })
        .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.json(); })
        .then(function (res) {
          // Session files that came along travel with the project.
          var jobs = res.project ? attachments.map(function (f) {
            var d = new FormData(); d.append("file", f);
            return fetch(root.dataset.attachmentUrl.replace("SLUG", res.project), {
              method: "POST", body: d, credentials: "same-origin", headers: { "X-CSRFToken": csrf() }
            }).catch(function () {});
          }) : [];
          return Promise.all(jobs).then(function () { location.assign(res.next); });
        })
        .catch(function (e) { errorEl.textContent = e.message; root.querySelector("[data-continue]").disabled = false; });
    }
  });
})();
