from django.conf.urls import patterns, include, url
from django.conf.urls.i18n import i18n_patterns
from django.conf import settings
from django.contrib import admin
from django.contrib import auth

from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from cms.sitemaps import CMSSitemap

# admin.autodiscover

# urlpatterns = patterns('',
#     url(r'^jsi18n/(?P<packages>\S+?)/$', 'django.views.i18n.javascript_catalog'),
# )

urlpatterns = i18n_patterns('',
    url(r'^repanier/', include('repanier.urls')),
    url(r'^coordi/', include(admin.site.urls)),
    url(r'^sitemap\.xml$', 'django.contrib.sitemaps.views.sitemap', {'sitemaps': {'cmspages': CMSSitemap}}),
    # url(r'^', include('filer.server.urls')),
    # url(r'^', include('password_reset.urls')),
    url(r'^', include('cms.urls')),
)

urlpatterns += staticfiles_urlpatterns()