(function ($) {
    $(document).ready(function ($) {
        if (location.pathname.indexOf('change') <= -1) {
            // List form
            $(".object-tools").append('<li><a href="./is_order_confirm_send/' + location.search + '">&nbsp;&nbsp;' + gettext('✓🔐') + '&nbsp;&nbsp;</a></li>');
        }
    });
})(django.jQuery);
