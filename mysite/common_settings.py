# -*- coding: utf-8 -*-
import os

from settings import *

gettext = lambda s: s
PROJECT_PATH = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]
PROJECT_DIR = os.path.realpath(os.path.dirname(__file__))
os.sys.path.insert(0, os.path.dirname(PROJECT_DIR))

# ##################### DEBUG

# Defined into /etc/uwsgi/apps-available/*.ini
DEBUG = True if os.getenv('DJANGO_SETTINGS_MODULE_DEBUG', '') == 'True' else False
TEMPLATE_DEBUG = DEBUG
ADMINS = (
    (
        os.getenv('DJANGO_SETTINGS_MODULE_ADMIN_NAME', ''),
        os.getenv('DJANGO_SETTINGS_MODULE_ADMIN_EMAIL', '')
    ),
)
SERVER_EMAIL = os.getenv('DJANGO_SETTINGS_MODULE_ADMIN_EMAIL', '')
# MANAGERS = (
#     (
#         os.getenv('DJANGO_SETTINGS_MODULE_ADMIN_NAME',''), 
#         os.getenv('DJANGO_SETTINGS_MODULE_ADMIN_EMAIL','')
#     ),
# )
###################### 

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': os.getenv('DJANGO_SETTINGS_MODULE_DATABASE_NAME', ''),  # Or path to database file if using sqlite3.
        # The following settings are not used with sqlite3:
        'USER': os.getenv('DJANGO_SETTINGS_MODULE_DATABASE_USER', ''),
        'PASSWORD': os.getenv('DJANGO_SETTINGS_MODULE_DATABASE_PASSWORD', ''),
        # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
        'HOST': os.getenv('DJANGO_SETTINGS_MODULE_DATABASE_HOST', ''),
        # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
        'PORT': os.getenv('DJANGO_SETTINGS_MODULE_DATABASE_PORT', ''),  # Set to empty string for default.
    }
}
EMAIL_HOST = os.getenv('DJANGO_SETTINGS_MODULE_EMAIL_HOST', '')
EMAIL_HOST_USER = os.getenv('DJANGO_SETTINGS_MODULE_EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('DJANGO_SETTINGS_MODULE_EMAIL_HOST_PASSWORD', '')
EMAIL_PORT = os.getenv('DJANGO_SETTINGS_MODULE_EMAIL_PORT', '')
EMAIL_USE_TLS = True if os.getenv('DJANGO_SETTINGS_MODULE_EMAIL_USE_TLS', '') == 'True' else False
# if DEBUG:
#     EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
###################### I18N

TIME_ZONE = 'Europe/Brussels'
USE_TZ = True
# Before 22/02/2014 - DJANGO-CMS LANGUAGE_CODE = 'fr-BE'
LANGUAGE_CODE = 'fr'
USE_L10N = True
USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = '.'
NUMBER_GROUPING = 3
DECIMAL_SEPARATOR = ','
# 'fr-be'

##################### Django & Django CMS
LANGUAGES = [
    ('fr', 'Français'),
    ('nl', 'Neederlands'),
    ('en', 'English'),
]

CMS_LANGUAGES = {
    'default': {
        'fallbacks': ['fr', 'en', 'nl'],
        'redirect_on_fallback': True,
        'public': False,
        'hide_untranslated': False,
    }
}

LOCALE_PATHS = (
    os.path.join(PROJECT_DIR, "locale"),
)

MIDDLEWARE_CLASSES = (
    'django.middleware.cache.UpdateCacheMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.doc.XViewMiddleware',
    'django.middleware.common.CommonMiddleware',
    # 'cms.middleware.language.LanguageCookieMiddleware', Disable to avoid cookies advertising requirement
    'cms.middleware.user.CurrentUserMiddleware',
    'cms.middleware.page.CurrentPageMiddleware',
    'cms.middleware.toolbar.ToolbarMiddleware',
    'django.middleware.cache.FetchFromCacheMiddleware',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
    'django.core.context_processors.i18n',
    'django.core.context_processors.request',
    'django.core.context_processors.media',
    'django.core.context_processors.static',
    'cms.context_processors.cms_settings',
    # 'cms.context_processors.media',
    'sekizai.context_processors.sekizai',
)

INSTALLED_APPS = (
    'django.contrib.sites',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django.contrib.formtools',
    'djangocms_text_ckeditor',  # note this needs to be above the 'cms' entry
    'cms',
    'mptt',
    'menus',
    'south',
    'sekizai',
    'djangocms_admin_style',  # note this needs to be above
    # the 'django.contrib.admin' entry
    'django.contrib.admin',
    'adminsortable',
    # 'hvad',
    'filer',
    'easy_thumbnails',

    'cmsplugin_filer_file',
    'cmsplugin_filer_folder',
    'cmsplugin_filer_image',
    'cmsplugin_filer_video',
    'cmsplugin_filer_link',
    'reversion',
    'password_reset',

)

CMS_PERMISSION = False  # When set to True, don't forget 'cms.middleware.user.CurrentUserMiddleware'
CMS_PUBLIC_FOR = 'all'
CMS_SHOW_START_DATE = False
CMS_SHOW_END_DATE = False
CMS_SEO_FIELDS = False
CMS_URL_OVERWRITE = True
CMS_MENU_TITLE_OVERWRITE = True
CMS_REDIRECTS = True
LOGIN_URL = "/go_repanier/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_URL = "/leave_repanier/"

CKEDITOR_SETTINGS = {
    'language': '{{ language }}',
	'toolbar_CMS': [
		['Undo', 'Redo'],
		['cmsplugins', '-', 'ShowBlocks'],
		 # ['Format', 'Styles'],
		['Format', 'Templates'],
		['TextColor', 'BGColor', '-', 'PasteText'], #, 'PasteFromWord'],
		['Maximize', ''],
		'/',
		['Bold', 'Italic', 'Underline', '-', 'Subscript', 'Superscript', '-', 'RemoveFormat'],
		['JustifyLeft', 'JustifyCenter', 'JustifyRight'],
		['HorizontalRule'],
		['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent', '-', 'Table'],
		['Source']
	],
	'toolbar_HTMLField': [
		['Undo', 'Redo'],
		['ShowBlocks', 'Format'],
		['TextColor', 'BGColor', '-', 'PasteText'], #, 'PasteFromWord'],
		['Maximize', ''],
		'/',
		['Bold', 'Italic', 'Underline', '-', 'Subscript', 'Superscript', '-', 'RemoveFormat'],
		['JustifyLeft', 'JustifyCenter', 'JustifyRight'],
		['HorizontalRule'],
		['Link', 'Unlink'],
		['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent', '-', 'Table'],
		['Source']
	],
    'skin': 'moono',
    # 'stylesSet' : 'my_styles:%sjs/ckeditor-styles.js' % STATIC_URL,
    # 'stylesSet' : [],
    'extraPlugins': 'cmsplugins,templates',
    'format_tags': 'p;h1;h2;h3;h4;h5;blockquote;mutted;success;info;danger;heart;infosign;warningsign;pushpin;div',
    'format_blockquote': {'element': 'blockquote', 'name': 'Blockquote'},
    'format_heart': {'element': 'span', 'attributes': {'class': 'glyphicon glyphicon-heart-empty'}},
    'format_infosign': {'element': 'span', 'attributes': {'class': 'glyphicon glyphicon-info-sign'}},
    'format_warningsign': {'element': 'span', 'attributes': {'class': 'glyphicon glyphicon-warning-sign'}},
    'format_pushpin': {'element': 'span', 'attributes': {'class': 'glyphicon glyphicon-pushpin'}},
    'format_mutted': {'element': 'p', 'attributes': {'class': 'text-muted'}, 'name': 'Mutted'},
    'format_success': {'element': 'p', 'attributes': {'class': 'bg-success'}, 'name': 'Success'},
    'format_info': {'element': 'p', 'attributes': {'class': 'bg-info'}, 'name': 'Info'},
    'format_danger': {'element': 'p', 'attributes': {'class': 'bg-danger'}, 'name': 'Danger'},
    # format_p = { element: 'p', attributes: { 'class': 'normalPara' } };
    # format_test = { element : 'span', attributes : { 'class' : 'test' }, styles: { color: 'blue'} };
    # 'contentsCss' : '//netdna.bootstrapcdn.com/bootstrap/3.1.1/css/bootstrap.min.css',
    'contentsCss': '%sbootstrap/css/bootstrap.css' % STATIC_URL,
    # 'extraAllowedContent' : '*(*)',
    # 'removeFormatTags' : 'b,big,code,del,dfn,em,font,i,ins,kbd,q,s,samp,small,strike,strong,sub,sup,tt,u,var'
}

TEXT_ADDITIONAL_TAGS = ('span',)
TEXT_ADDITIONAL_ATTRIBUTES  = ('class',)
# TEXT_HTML_SANITIZE = False
# TEXT_SAVE_IMAGE_FUNCTION = 'cmsplugin_filer_image.integrations.ckeditor.create_image_plugin'
# TEXT_SAVE_IMAGE_FUNCTION = 'djangocms_text_ckeditor.picture_save.create_picture_plugin'
TEXT_SAVE_IMAGE_FUNCTION = None

FILER_ENABLE_LOGGING = False
FILER_IMAGE_USE_ICON = True
FILER_ALLOW_REGULAR_USERS_TO_ADD_ROOT_FOLDERS = True
FILER_ENABLE_PERMISSIONS = False
FILER_IS_PUBLIC_DEFAULT = True
FILER_SUBJECT_LOCATION_IMAGE_DEBUG = True
FILER_DEBUG = DEBUG

THUMBNAIL_PROCESSORS = (
    'easy_thumbnails.processors.colorspace',
    'easy_thumbnails.processors.autocrop',
    #'easy_thumbnails.processors.scale_and_crop',
    'filer.thumbnail_processors.scale_and_crop_with_subject_location',
    'easy_thumbnails.processors.filters',
)
THUMBNAIL_DEBUG = DEBUG

# https://docs.djangoproject.com/en/1.5/howto/static-files/
STATIC_ROOT = os.path.join(PROJECT_DIR, "collect-static")
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
USE_X_FORWARDED_HOST = True
SEND_BROKEN_LINK_EMAILS = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_ENGINE = "django.contrib.sessions.backends.file"
SESSION_COOKIE_HTTPONLY = True
SESSION_FILE_PATH = '/var/tmp/django_session'
SOUTH_TESTS_MIGRATE = DEBUG

##################### Repanier
AUTH_USER_MODEL = 'auth.User'
AUTHENTICATION_BACKENDS = ('repanier.auth_backend.RepanierCustomBackend',)
# ADMIN_LOGIN = 'pise'
# ADMIN_PASSWORD = 'raspberry'
INSTALLED_APPS += (
'repanier',
)


################# Django_crispy_forms
# INSTALLED_APPS += (
#     'crispy_forms',
# )

# CRISPY_TEMPLATE_PACK = "bootstrap3"
# JSON_MODULE = 'ujson'

################# Django_compressor
INSTALLED_APPS += (
    'compressor',
)
##### From : django/conf/global_settings.py
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    #    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

STATICFILES_FINDERS += (
    'compressor.finders.CompressorFinder',
)

COMPRESS_ENABLED = True
COMPRESS_OUTPUT_DIR = "compressor"
COMPRESS_STORAGE = 'compressor.storage.GzipCompressorFileStorage'
COMPRESS_PARSER = "compressor.parser.HtmlParser"
COMPRESS_OFFLINE = False

# COMPRESS_YUI_BINARY = "yui-compressor"
# COMPRESS_CLOSURE_COMPILER_BINARY = "/usr/local/bin/node /usr/local/bin/uglifyjs"
# COMPRESS_CLOSURE_COMPILER_ARGUMENTS = '--compress'

# COMPRESS_CSS_FILTERS = [
#    'compressor.filters.yui.YUICSSFilter',
#    'compressor.filters.css_default.CssAbsoluteFilter',
#    'compressor.filters.template.TemplateFilter'
#    ]

# COMPRESS_JS_FILTERS = [
#    'compressor.filters.yui.YUIJSFilter',
#     'compressor.filters.closure.ClosureCompilerFilter',
#    'compressor.filters.jsmin.JSMinFilter',
#    'compressor.filters.template.TemplateFilter'
#    ]

# COMPRESS_PRECOMPILERS = (
#    ('text/coffeescript', 'coffee --compile --stdio'),
#    ('text/less', 'lessc {infile} {outfile}'),
#    ('text/x-sass', 'sass {infile} {outfile}'),
#    ('text/x-scss', 'sass --scss {infile} {outfile}'),
#    ('text/stylus', 'stylus < {infile} > {outfile}'),
# )

###################### Django : Cache setup (https://docs.djangoproject.com/en/dev/topics/cache/)

CACHE_MIDDLEWARE_ALIAS = 'default'
CACHE_MIDDLEWARE_SECONDS = 3600

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/var/tmp/django_cache',
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
            'CULL_FREQUENCY': 3
        }
    }
}

CMS_CACHE_DURATIONS = {
    'content': 300,  # default 60
    'menus': 3600,  # default 3600
    'permissions': 3600  # default: 3600
}
CMS_PAGE_CACHE = True
CMS_PLACEHOLDER_CACHE = True
CMS_PLUGIN_CACHE = True

SOUTH_MIGRATION_MODULES = {
    'easy_thumbnails': 'easy_thumbnails.south_migrations',
}
###################### EASYMAP
#EASY_MAPS_CENTER = ( 50.630545,3.776955 )

#INSTALLED_APPS += (
#    'easy_maps',
#)


# if DEBUG:
#     import logging
#     l = logging.getLogger('django.db.backends')
#     l.setLevel(logging.DEBUG)
#     l.addHandler(logging.StreamHandler())


# LOGGING = {
#     'version': 1,
#     'disable_existing_loggers': False,
#     'filters': {
#         'require_debug_false': {
#             '()': 'django.utils.log.RequireDebugFalse'
#         }
#     },
#     'handlers': {
#         'mail_admins': {
#             'level': 'ERROR',
#             'filters': ['require_debug_false'],
#             'class': 'django.utils.log.AdminEmailHandler'
#         },'console': {
#             'level': 'DEBUG',
#             'class': 'logging.StreamHandler',
#         },
#     },
#     'loggers': {
#         'django.request': {
#             'handlers': ['mail_admins'],
#             'level': 'ERROR',
#             'propagate': True,
#         },'django.db.backends': {
#             'level': 'DEBUG',
#             'handlers': ['console'],
#         },
#     }
# }