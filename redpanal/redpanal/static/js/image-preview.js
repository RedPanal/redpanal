/* Show the picked picture right away, before uploading (project, sound and profile images). */
(function () {
  "use strict";
  document.addEventListener("change", function (e) {
    var input = e.target;
    if (!input.matches || !input.matches("input[type=file][data-image-preview]") || !input.files.length) return;
    var file = input.files[0];
    if (!/^image\//.test(file.type)) return;
    var url = URL.createObjectURL(file);
    document.querySelectorAll('[data-image-preview-of="' + input.id + '"]').forEach(function (img) {
      img.src = url;
      img.hidden = false;
    });
  });
})();
