from django.conf import settings

from repanier.middleware import (
    get_query_preserved_filters,
    get_query_filters,
    get_query_params,
)


def repanier_settings(request):
    from repanier.globals import REPANIER_SETTINGS_HOME_SITE

    user = getattr(request, "user", None)
    if user is not None and user.is_staff:
        # Only in the admin

        # print("########## get_query_filters() : {}".format(get_query_filters()))
        # print("########## get_query_preserved_filters() : {}".format(get_query_preserved_filters()))
        # print("########## get_query_params() : {}".format(get_query_params()))

        return {
            "REPANIER_BOOTSTRAP_CSS": settings.REPANIER_SETTINGS_BOOTSTRAP_CSS_PATH,
            "REPANIER_CUSTOM_CSS": settings.REPANIER_SETTINGS_CUSTOM_CSS_PATH,
            "REPANIER_BRANDING_CSS": settings.REPANIER_SETTINGS_BRANDING_CSS_PATH,
            "REPANIER_GROUP_NAME": settings.REPANIER_SETTINGS_GROUP_NAME,
            "REPANIER_HOME_SITE": REPANIER_SETTINGS_HOME_SITE,
            "REPANIER_DISPLAY_LANGUAGE": settings.DJANGO_SETTINGS_MULTIPLE_LANGUAGE,
            "REPANIER_ADMIN_MANAGE_ACCOUNTING": settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING,
            "REPANIER_DISPLAY_PRODUCERS_ON_ORDER_FORM": settings.REPANIER_SETTINGS_SHOW_PRODUCER_ON_ORDER_FORM,
            "form_url": get_query_preserved_filters(),
            "change_list_filter": get_query_filters(),
        }
    else:
        # Only in the "not" admin
        return {
            "REPANIER_BOOTSTRAP_CSS": settings.REPANIER_SETTINGS_BOOTSTRAP_CSS_PATH,
            "REPANIER_CUSTOM_CSS": settings.REPANIER_SETTINGS_CUSTOM_CSS_PATH,
            "REPANIER_BRANDING_CSS": settings.REPANIER_SETTINGS_BRANDING_CSS_PATH,
            "REPANIER_GROUP_NAME": settings.REPANIER_SETTINGS_GROUP_NAME,
            "REPANIER_HOME_SITE": REPANIER_SETTINGS_HOME_SITE,
            "REPANIER_DISPLAY_LANGUAGE": settings.DJANGO_SETTINGS_MULTIPLE_LANGUAGE,
            "REPANIER_DISPLAY_PRODUCERS_ON_ORDER_FORM": settings.REPANIER_SETTINGS_SHOW_PRODUCER_ON_ORDER_FORM,
        }
