from cms.sitemaps import CMSSitemap
from django.conf import settings
from django.conf.urls import include
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.i18n import JavaScriptCatalog

from django.urls import path

urlpatterns = i18n_patterns(
    path("repanier/", include("repanier.urls")),
    path("coordi/", admin.site.urls),
    path(
        "sitemap\.xml",
        sitemap,
        {"sitemaps": {"cmspages": CMSSitemap}},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path(
        "jsi18n/",
        JavaScriptCatalog.as_view(packages=["recurrence"]),
        name="javascript-catalog",
    ),
    path("", include("cms.urls")),
)

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns

urlpatterns += staticfiles_urlpatterns()
