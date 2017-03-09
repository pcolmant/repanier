(function($) {
    $(document).ready(function($) {
        if(location.pathname.indexOf('change') <= -1) {
            $(".object-tools").prepend('<li><a href="./export_stock/' + location.search + '">' + gettext('Export stock')+ '</a></li>');
            $(".object-tools").prepend('<li><a href="./import_stock/' + location.search + '">' + gettext('Import stock')+ '</a></li>');
        }
        // $(".object-tools").append('<li><a href="./is_order_confirm_send/' + location.search + '" class="addlink">&nbsp;&nbsp;🔐&nbsp;&nbsp;</a></li>');
    });
})(django.jQuery);
