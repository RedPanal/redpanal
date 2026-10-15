/* Studio folder upload: gather files from a folder, a file picker or drag and drop into one input. */
(function () {
  "use strict";
  var form = document.getElementById("stems-form");
  if (!form) return;
  var input = document.getElementById("id_stems");
  var folder = document.getElementById("pick-folder");
  var zone = form.querySelector("[data-dropzone]");
  var rows = form.querySelector("[data-rows]");
  var template = form.querySelector("[data-row-template]");
  var listBox = form.querySelector("[data-file-list]");
  var files = [];

  function ext(name) { return (name.split(".").pop() || "").toLowerCase(); }
  function wanted(f) {
    if (f.name.charAt(0) === ".") return false;  // .DS_Store and friends
    var e = ext(f.name);
    return window.RP_AUDIO_EXT.indexOf(e) !== -1 || window.RP_ATTACH_EXT.indexOf(e) !== -1;
  }
  function mb(bytes) { return (bytes / 1048576).toFixed(1) + " MB"; }

  function add(list) {
    Array.prototype.forEach.call(list, function (f) {
      if (!wanted(f)) return;
      if (files.some(function (g) { return g.name === f.name && g.size === f.size; })) return;
      files.push(f);
    });
    sync();
  }

  function sync() {
    var dt = new DataTransfer();
    files.forEach(function (f) { dt.items.add(f); });
    input.files = dt.files;
    rows.innerHTML = "";
    files.forEach(function (f, i) {
      var row = template.content.firstElementChild.cloneNode(true);
      row.querySelector("[data-name]").textContent = f.webkitRelativePath || f.name;
      row.querySelector("[data-size]").textContent = mb(f.size);
      var select = row.querySelector("[data-instrument]");
      select.id = "instrument-" + i;
      row.querySelector("[data-select-label]").setAttribute("for", select.id);
      if (window.RP_AUDIO_EXT.indexOf(ext(f.name)) === -1) {
        // Session files keep the same position in the list, without an instrument.
        select.classList.add("visually-hidden");
        select.value = "";
        row.querySelector("[data-attachment-label]").hidden = false;
      }
      rows.appendChild(row);
    });
    listBox.hidden = files.length === 0;
  }

  // New work from a folder: the folder's name is a good first title.
  var title = document.getElementById("id_name"), titleEdited = false;
  if (title) title.addEventListener("input", function () { titleEdited = true; });
  function nameFromFolder(list) {
    var path = list.length && list[0].webkitRelativePath;
    if (title && !titleEdited && path && path.indexOf("/") > 0) title.value = path.split("/")[0];
  }

  input.addEventListener("change", function () { var picked = Array.from(input.files); files = []; add(picked); });
  folder.addEventListener("change", function () { nameFromFolder(folder.files); add(folder.files); folder.value = ""; });

  ["dragenter", "dragover"].forEach(function (t) {
    zone.addEventListener(t, function (e) { e.preventDefault(); zone.classList.add("is-over"); });
  });
  ["dragleave", "drop"].forEach(function (t) {
    zone.addEventListener(t, function (e) { e.preventDefault(); zone.classList.remove("is-over"); });
  });
  zone.addEventListener("drop", function (e) {
    var items = e.dataTransfer.items;
    if (items && items.length && items[0].webkitGetAsEntry) {
      var pending = [];
      Array.prototype.forEach.call(items, function (it) {
        var entry = it.webkitGetAsEntry();
        if (entry && entry.isDirectory && title && !titleEdited && items.length === 1) title.value = entry.name;
        if (entry) pending.push(walk(entry));
      });
      Promise.all(pending).then(function (lists) { add([].concat.apply([], lists)); });
    } else {
      add(e.dataTransfer.files);
    }
  });

  // Read dropped folders recursively.
  function walk(entry) {
    return new Promise(function (resolve) {
      if (entry.isFile) { entry.file(function (f) { resolve([f]); }, function () { resolve([]); }); return; }
      var reader = entry.createReader(), all = [];
      (function read() {
        reader.readEntries(function (batch) {
          if (!batch.length) {
            Promise.all(all.map(walk)).then(function (lists) { resolve([].concat.apply([], lists)); });
            return;
          }
          all = all.concat(Array.from(batch));
          read();
        }, function () { resolve([]); });
      })();
    });
  }

  form.addEventListener("submit", function () {
    form.querySelector("[data-submit]").disabled = true;
    form.querySelector("[data-uploading]").hidden = false;
  });
})();
