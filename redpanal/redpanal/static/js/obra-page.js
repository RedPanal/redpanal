/* Work page: share, unfold what a link points to, and comments at the moment of the stems heard together. */
(function () {
  "use strict";
  window.rpPage(function () {
    var page = document.querySelector("#main .rp-obra");
    if (!page) return;

    var share = page.querySelector("[data-share]");
    if (share) share.addEventListener("click", function () {
      var url = window.location.href.split("?")[0].split("#")[0];
      if (navigator.share) { navigator.share({ title: document.title, url: url }).catch(function () {}); return; }
      if (navigator.clipboard) navigator.clipboard.writeText(url).then(function () {
        var old = share.innerHTML;
        share.textContent = share.dataset.copied;
        setTimeout(function () { share.innerHTML = old; }, 2000);
      });
    });

    // A link to something inside a folded section (history and files) unfolds it.
    function unfold(hash) {
      var id = (typeof hash === "string" ? hash : window.location.hash).slice(1);
      var target = id && document.getElementById(id);
      for (var el = target; el; el = el.parentElement) {
        if (el.tagName === "DETAILS") el.open = true;
      }
      return target;
    }
    window.addEventListener("hashchange", unfold);
    unfold();
    // A link to the same place again (the ⋯ menu's "Listen together"): open it anyway.
    page.addEventListener("click", function (e) {
      var a = e.target.closest('a[href^="#"]');
      if (!a || a.getAttribute("href").length < 2) return;
      var target = document.getElementById(a.getAttribute("href").slice(1));
      if (!target || !target.closest("details")) return;  // plain anchors (and :target forms) as usual
      unfold(a.getAttribute("href"));
      e.preventDefault();
      history.replaceState(history.state, "", a.getAttribute("href"));
      target.scrollIntoView({ block: "start" });
    });

    // Listening to the stems together, a comment can say at which moment.
    var together = page.querySelector(".rp-together-body[data-mixer]");
    var mixer = together && together.rpMixer;
    var form = page.querySelector("[data-comment-form]");
    if (form && mixer) {
      var input = form.querySelector("[name=msg]"), at = form.querySelector("[name=at_ms]");
      var template = input.dataset.placeholderAt, touched = false;
      together.addEventListener("mixer:play", function () { touched = true; });
      together.addEventListener("mixer:time", function (e) {
        if (touched) input.placeholder = template.replace("%s", e.detail.label);
      });
      form.addEventListener("submit", function () {
        at.value = touched ? mixer.currentMs() : "";
      });
    }
    return function () { window.removeEventListener("hashchange", unfold); };
  });
})();
