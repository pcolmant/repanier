(function($) {
    $(document).ready(function($) {
        if(location.pathname.indexOf('change') <= -1) {
            $(".object-tools").prepend('<li><a href="./export_stock/' + location.search + '">' + gettext('Export stock')+ '</a></li>');
            $(".object-tools").prepend('<li><a href="./import_stock/' + location.search + '">' + gettext('Import stock')+ '</a></li>');
        }
    });
})(django.jQuery);
