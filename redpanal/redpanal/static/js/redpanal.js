
$(function() {

  /* Comments */
  // Add reply action
  $("body").on("click", "button.comment-reply", function () {
        var username = $(this).data("username");
        $('html,body').animate({scrollTop: 0}, 500);
        var input = $("#id_msg");
        input.focus();
        input.val("@"+username + " ");
    });
});

