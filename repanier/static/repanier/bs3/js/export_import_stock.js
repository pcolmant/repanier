(function($) {
    $(document).ready(function($) {
        if(location.pathname.indexOf('change') <= -1) {
            $(".object-tools").prepend('<li><a href="./export_stock/' + location.search + '">' + gettext('Export the stock')+ '</a></li>');
            $(".object-tools").prepend('<li><a href="./import_stock/' + location.search + '">' + gettext('Import the stock')+ '</a></li>');
        }
    });
})(django.jQuery);
