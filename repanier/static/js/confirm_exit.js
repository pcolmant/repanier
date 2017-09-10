(function($) {
    $(document).ready(function() {
        var formmodified = false;
        $('form *').change(function(){
            formmodified = true;
        });
        window.onbeforeunload = confirmExit;
        function confirmExit() {
            if (formmodified === true) {
                return gettext('New information not saved. Do you wish to leave the page?');
            }
        }
        $("input[name='_save']").click(function() {
            formmodified = false;
        });
    });

})(django.jQuery);
