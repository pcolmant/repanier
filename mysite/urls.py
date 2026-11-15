""" URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from cms.sitemaps import CMSSitemap
from django.conf import settings
from django.conf.urls import include
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path
from django.views.i18n import JavaScriptCatalog

from repanier.apps import REPANIER_SETTINGS_PERMANENCES_NAME
from repanier.sitemaps import PermamenceSitemap
from repanier.views.passport_door_view import (
    passport_arrive_view,
    passport_login_view,
    passport_request_view,
)
from repanier.views.passport_view import passport_profile_view, passport_verify_view

admin.site.site_header = ""
admin.site.site_title = ""
admin.site.empty_value_display = "-"
# Disable new unwanted left admin menu :
admin.site.enable_nav_sidebar = False


# Non i18n URLs
urlpatterns = [
    path(
        "sitemap.xml",
        sitemap,
        {
            "sitemaps": {
                REPANIER_SETTINGS_PERMANENCES_NAME: PermamenceSitemap,
                "cmspages": CMSSitemap,
            }
        },
        name="django.contrib.sitemaps.views.sitemap",
    ),
]

# i18n URLs
urlpatterns += i18n_patterns(
    # Server to server: the home site of a passport member answers
    # the profile the other family sites need to register him, and
    # tells the family routine whether a member is still one of its
    # active members. They live on the language prefixed side: a
    # plain 404 without a language prefix is redirected by the
    # locale middleware, and the family caller expects silent 404s.
    path("passport/profile/", passport_profile_view),
    path("passport/verify/", passport_verify_view),
    # The login door of the passport: a member logged out everywhere
    # still owns his password on his home site. The target sends the
    # browser to the home site, the home site vouches with a one
    # minute signed token, the target opens the door like a passport
    # arrival. The password never leaves the home site.
    path("passport/request/", passport_request_view, name="passport_request"),
    path("passport/login/", passport_login_view, name="passport_login"),
    path("passport/arrive/", passport_arrive_view, name="passport_arrive"),
    path("repanier/", include("repanier.urls", namespace="repanier")),
    path("coordi/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path(
        "jsi18n/",
        JavaScriptCatalog.as_view(packages=["recurrence"]),
        name="javascript-catalog",
    ),
    path("", include("cms.urls")),
)

if settings.DJANGO_SETTINGS_DEBUG_TOOLBAR:
    import debug_toolbar

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns

# urlpatterns += staticfiles_urlpatterns()
