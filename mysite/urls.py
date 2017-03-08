from cms.sitemaps import CMSSitemap
from django.conf.urls import include, url
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.i18n import JavaScriptCatalog

urlpatterns = i18n_patterns(
    url(r'^repanier/', include('repanier.urls')),
    url(r'^coordi/', include(admin.site.urls)),
    # url(r'^sitemap\.xml$', 'django.contrib.sitemaps.views.sitemap', {'sitemaps': {'cmspages': CMSSitemap}}),
    url(r'^sitemap\.xml$', sitemap, {'sitemaps': {'cmspages': CMSSitemap}},
        name='django.contrib.sitemaps.views.sitemap'),
    url(r'^jsi18n/$', JavaScriptCatalog.as_view(), name='javascript-catalog'),
    url(r'^', include('cms.urls')),
)

urlpatterns += staticfiles_urlpatterns()
