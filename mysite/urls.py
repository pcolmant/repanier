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
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.i18n import JavaScriptCatalog

from django.urls import path

admin.site.site_header = ""
admin.site.site_title = ""
admin.site.empty_value_display = "-"
# Disable new unwanted left admin menu :
admin.site.enable_nav_sidebar = False

urlpatterns = i18n_patterns(
    path("repanier/", include("repanier.urls", namespace="repanier")),
    path("coordi/", admin.site.urls),
    path('api-auth/', include('rest_framework.urls')),
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
