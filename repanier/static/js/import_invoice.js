(function($) {
    $(document).ready(function($) {
        if(location.pathname.indexOf('change') <= -1) {
            $(".object-tools").append('<li><a href="./import_invoice/' + location.search + '">' + gettext('Import an invoice')+ '</a></li>');
        }
    });
})(django.jQuery);
