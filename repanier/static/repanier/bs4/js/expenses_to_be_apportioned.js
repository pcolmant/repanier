(function($) {
    $(document).ready(function($) {
        if(location.pathname.indexOf('change') <= -1) {
            $(".object-tools").prepend('<li><a href="./expenses_to_be_apportioned/' + location.search + '">' + gettext('Expenses to be apportioned')+ '</a></li>');
        }
    });
})(django.jQuery);
