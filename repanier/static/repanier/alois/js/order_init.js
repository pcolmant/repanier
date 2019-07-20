jQuery(document).ready(function () {
    // Close card
    $(".card-close").click(function () {
        $(this).parent().slideUp(300);
        $("A").click(function () {
            // Stop displaying flash in next pages
            $(this).attr('href', $(this).attr('href') + "?flash=0");
            return true;
        });
    });
    /*
        Slide panel and filter
    */
    // $(".slide .slide-link").click(function () {
    //     $(this).parent().parent().find(".slide-body").toggle(300);
    // });

    // $("#filtersAccordion A.list-group-item").click(function () {
    //     $("#filtersAccordion A.list-group-item").removeClass("active");
    //     $(this).addClass("active");
    //     setTimeout(function () {
    //         $("#filtersSlidePanel .slide-body").hide(300);
    //     }, 300);
    // });
    /*
        Order screen
    */
    // Filter favorites product
    $("#filter_like").click(function () {
        $(".product-like-no").toggle();
    });
    // Filter dates
    $("[name='filter_date']").change(function () {
        dateId = $(this).val();
        if (dateId == "all") {
            $(".product-date").show();
        } else {
            $(".product-date").hide();
            $("." + dateId).show();
        }
    });
});
