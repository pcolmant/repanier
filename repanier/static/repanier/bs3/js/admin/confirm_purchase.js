(function ($) {
    $(document).ready(function ($) {
        if (location.pathname.indexOf('/change/') <= -1 && location.pathname.indexOf('/add/') <= -1 && location.pathname.indexOf('/history/') <= -1  && location.pathname.indexOf('/delete/') <= -1) {
            // List form
            $(".object-tools").append('<li><a href="./is_order_confirm_send/' + location.search + '">&nbsp;&nbsp;' + gettext('✓🔐') + '&nbsp;&nbsp;</a></li>');
        }
    });
})(django.jQuery);
