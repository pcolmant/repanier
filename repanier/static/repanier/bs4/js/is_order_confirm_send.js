(function($) {
    $(document).ready(function($) {
        if(location.pathname.indexOf('change') <= -1) {
            // $(".object-tools").append('<li><a href="./is_order_confirm_not_send/' + location.search + '">&nbsp;&nbsp;' + gettext('✗🔓')+ '&nbsp;&nbsp;</a></li>');
            $(".object-tools").append('<li><a href="./is_order_confirm_send/' + location.search + '">&nbsp;&nbsp;' + gettext('✓🔐')+ '&nbsp;&nbsp;</a></li>');
        }
    });
})(django.jQuery);
