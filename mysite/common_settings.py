# -*- coding: utf-8 -*-
# http://www.doodle.com/srxt9yh5yutqgkp85y6nxczk/admin
# http://www.doodle.com/srxt9yh5yutqgkp8
from settings import *

import os
gettext = lambda s: s
PROJECT_PATH = os.path.abspath(os.path.dirname(__file__))

###################### Django
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2', # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': 'pi',                      # Or path to database file if using sqlite3.
        # The following settings are not used with sqlite3:
        'USER': 'pi',
        'PASSWORD': 'raspberry',
        'HOST': '127.0.0.1',                      # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
        'PORT': '5432',                      # Set to empty string for default.
    }
}

TIME_ZONE = 'Europe/Brussels'
LANGUAGE_CODE = 'fr-BE'
STATIC_ROOT = os.path.join(PROJECT_PATH, "static")
STATIC_URL = "/static/"
MEDIA_ROOT = os.path.join(PROJECT_PATH, "media")
MEDIA_URL = "/media/"
SOUTH_TESTS_MIGRATE = False

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.i18n',
    'django.core.context_processors.request',
    'django.core.context_processors.media',
    'django.core.context_processors.static',
)
INSTALLED_APPS += (
	# 'debug_toolbar',
	'django.contrib.admin',
	'south',
)

##################### Repanier
AUTHENTICATION_BACKENDS = ('repanier.auth_backend.RepanierCustomBackend',)
# ADMIN_LOGIN = 'pise'
# ADMIN_PASSWORD = 'raspberry'
INSTALLED_APPS += (
	'repanier',
)

##################### Django CMS
LANGUAGES = [
	('fr', 'French'),
	('nl', 'Dutch'),
	('en', 'English'),
]

TEMPLATE_DIRS = (
    # The docs say it should be absolute path: PROJECT_PATH is precisely one.
    # Life is wonderful!
    os.path.join(PROJECT_PATH, "templates"),
)
CMS_TEMPLATES = (
    ('template_1.html', 'Template One'),
    ('template_2.html', 'Template Two'),
)

THUMBNAIL_DEBUG = False

MIDDLEWARE_CLASSES += (
    'cms.middleware.multilingual.MultilingualURLMiddleware',
    'cms.middleware.user.CurrentUserMiddleware',
    'cms.middleware.page.CurrentPageMiddleware',
    'cms.middleware.toolbar.ToolbarMiddleware',
)

TEMPLATE_CONTEXT_PROCESSORS += (
    'cms.context_processors.media',
    'sekizai.context_processors.sekizai',
)

INSTALLED_APPS += (
	'djangocms_text_ckeditor',
	'easy_thumbnails',
	'cms',
	'mptt',
	'menus',
	'sekizai',
	'cms.plugins.file',
	'cms.plugins.flash',
	'cms.plugins.googlemap',
	'cms.plugins.link',
	'cms.plugins.picture',
	'cms.plugins.snippet',
	'cms.plugins.teaser',
#	'cms.plugins.text',
	'cms.plugins.video',
	'cms.plugins.twitter',
	'django.contrib.sitemaps',
)
CMS_MENU_TITLE_OVERWRITE = False
CMS_SOFTROOT = True
CMS_PERMISSION = True
CMS_PUBLIC_FOR = 'all'
CMS_MODERATOR = True
CMS_SHOW_START_DATE = False
CMS_SHOW_END_DATE = False
CMS_SEO_FIELDS = True

CKEDITOR_SETTINGS = {
		'language': '{{ language }}',
		'toolbar': 'CMS',
		'skin': 'moono'
}