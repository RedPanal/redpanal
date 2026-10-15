/*
 * Uploads that survive a bad connection.
 * Forms marked with data-offline-queue are sent in the background with progress;
 * if there is no signal, they wait in this device (IndexedDB) and go out by
 * themselves when the connection comes back.
 */
(function () {
  "use strict";
  var DB = "rp-uploads", STORE = "queue";

  function db() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB, 1);
      req.onupgradeneeded = function () { req.result.createObjectStore(STORE, { keyPath: "id", autoIncrement: true }); };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }
  function tx(mode, fn) {
    return db().then(function (d) {
      return new Promise(function (resolve, reject) {
        var t = d.transaction(STORE, mode), result = fn(t.objectStore(STORE));
        t.oncomplete = function () { resolve(result && result.result !== undefined ? result.result : result); };
        t.onerror = function () { reject(t.error); };
      });
    });
  }
  function queueAdd(item) { return tx("readwrite", function (s) { return s.add(item); }); }
  function queueAll() { return tx("readonly", function (s) { return s.getAll(); }); }
  function queueRemove(id) { return tx("readwrite", function (s) { return s.delete(id); }); }

  function toast(html) {
    var box = document.getElementById("rp-toasts");
    if (!box) {
      box = document.createElement("div");
      box.id = "rp-toasts"; box.className = "rp-toasts"; box.setAttribute("role", "status"); box.setAttribute("aria-live", "polite");
      document.body.appendChild(box);
    }
    var el = document.createElement("div");
    el.className = "rp-toast"; el.innerHTML = html;
    box.appendChild(el);
    setTimeout(function () { el.remove(); }, 9000);
  }
  function esc(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
  var T = window.RP_QUEUE_TEXT || {};

  function entriesOf(form) {
    var fd = new FormData(form), out = [];
    fd.forEach(function (value, key) { out.push([key, value]); });
    return out;
  }
  function formDataOf(entries) {
    var fd = new FormData();
    entries.forEach(function (e) { if (e[1] instanceof Blob) fd.append(e[0], e[1], e[1].name); else fd.append(e[0], e[1]); });
    return fd;
  }

  function save(form, url, title) {
    return queueAdd({ url: url, title: title, entries: entriesOf(form), created: Date.now() }).then(function () {
      var status = form.querySelector("[data-uploading]");
      if (status) { status.hidden = false; status.textContent = T.queued || "Sin conexión: se va a subir sola cuando vuelva la señal."; }
      var btn = form.querySelector("[data-submit]");
      if (btn) btn.disabled = false;
    });
  }

  // Send in the background, with progress; queue on network failure.
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form.hasAttribute || !form.hasAttribute("data-offline-queue") || e.defaultPrevented) return;
    if (!window.indexedDB || !window.FormData) return;  // plain submit still works
    e.preventDefault();
    var url = form.getAttribute("action") || window.location.href;
    var title = (form.querySelector("[name=name]") || {}).value || form.dataset.queueTitle || document.title;
    var status = form.querySelector("[data-uploading]");
    if (!navigator.onLine) { save(form, url, title); return; }

    var xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.upload.onprogress = function (ev) {
      if (status && ev.lengthComputable) {
        status.hidden = false;
        status.textContent = (T.progress || "Subiendo… %s").replace("%s", Math.round(ev.loaded * 100 / ev.total) + "%");
      }
    };
    xhr.onload = function () {
      if (xhr.responseURL && xhr.responseURL.split("#")[0] !== url.split("#")[0] && xhr.status < 400) {
        window.location.href = xhr.responseURL;
      } else {
        // Same page back: validation errors or a summary to show.
        document.open(); document.write(xhr.responseText); document.close();
      }
    };
    xhr.onerror = function () { save(form, url, title); };
    xhr.send(new FormData(form));
  });

  var flushing = false;
  function flush() {
    if (flushing || !navigator.onLine || !window.indexedDB) return;
    flushing = true;
    queueAll().then(function (items) {
      return items.reduce(function (chain, item) {
        return chain.then(function () {
          return fetch(item.url, { method: "POST", body: formDataOf(item.entries), credentials: "same-origin" })
            .then(function (res) {
              if (res.ok) {
                toast((T.sent || "Se subió «%s».").replace("%s", esc(item.title)) +
                      ' <a href="' + esc(res.url) + '">' + (T.see || "Ver") + "</a>");
                return queueRemove(item.id);
              }
              if (res.status >= 400 && res.status < 500) {
                toast((T.failed || "No se pudo subir «%s».").replace("%s", esc(item.title)));
                return queueRemove(item.id);
              }
            })
            .catch(function () { /* still offline: keep it for later */ });
        });
      }, Promise.resolve());
    }).then(function () { flushing = false; }, function () { flushing = false; });
  }
  window.addEventListener("online", flush);
  document.addEventListener("DOMContentLoaded", flush);
  window.rpUploadQueue = { all: queueAll, flush: flush };
})();
