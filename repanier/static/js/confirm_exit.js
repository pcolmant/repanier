(function($) {
    $(document).ready(function() {
        if(location.pathname.indexOf('change') <= -1) {
            var formmodified = false;
            $("input[type='number'] form").change(function () {
                formmodified = true;
            });
            window.onbeforeunload = confirmExit;

            function confirmExit() {
                if (formmodified === true) {
                    return gettext('New information not saved. Do you wish to leave the page?');
                }
            }

            $("input[name='_save']").click(function () {
                formmodified = false;
            });
        }
    });

})(django.jQuery);
