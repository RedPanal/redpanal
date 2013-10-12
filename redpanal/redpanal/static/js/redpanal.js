
$(function() {

  /* Comments */
  // Add reply action
  $("body").on("click", "button.comment-reply", function () {
        console.log("asd")
        var username = $(this).data("username");
        $('html,body').animate({scrollTop: 0}, 500);
        var input = $("#comment-form-small input#id_msg");
        input.focus();
        input.val("@"+username + " ");
    });
});

