sagenb.settings = {};

sagenb.settings.setup_manage_users_page = function() {
	$("#add_user_button").click(function(e) {
		$("#add_user_modal input").val("");
		$("#add_user_modal input").focus();
	});
	var cb = sagenb.generic_callback(function(status, response) {
		var X = decode_response(response);

		var alert_class = "alert fade in";
		if(X.error) alert_class += " alert-error";
		else alert_class += " alert-success";

		var msg = "";
		if(X.error) msg = X.error;
		else msg = X.message;

		$('<div class="' + alert_class + '">' +
			'<button class="close" data-dismiss="alert">×</button>' +
			msg +
		'</div>').appendTo(".alert_container_inner");
	});
	$("#do_add_user_button").click(function(e) {
		sagenb.async_request("/add_user", cb, {
			username: $("#add_user_modal input").val()
		});
	});
	$(".reset_user_password_button").click(function(e) {
		// TODO gettext
    var username = $(this).parent().parent().data('username');
		if(!confirm("Are you sure you want to reset " + username + "'s password?"))
      {
        return;
      }
		window.open($(this).data('redirect'), '_self');
	});
	$(".suspend_user_button").click(function(e) {
		// TODO gettext
		if(!confirm("Are you sure you want to suspend/unsuspend " + 
			$(this).parent().parent().data("username") + 
			"'s account?")) return;
		sagenb.async_request("/suspend_user", sagenb.generic_callback(function(status, response) {
			window.location.reload();
		}), {
			username: $(this).parent().parent().data("username")
		});
	});
};
