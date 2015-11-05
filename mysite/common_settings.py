# -*- coding: utf-8 -*-
import ConfigParser
import codecs
import logging
from settings import *

import os

gettext = lambda s: s

# os.path.realpath resolves symlinks and os.path.abspath doesn't.
PROJECT_PATH = os.path.split(os.path.realpath(os.path.dirname(__file__)))[0]
PROJECT_DIR = os.path.realpath(os.path.dirname(__file__))
os.sys.path.insert(0, PROJECT_PATH)
MEDIA_ROOT = os.path.join(PROJECT_DIR, "media", "public")
MEDIA_URL = "/media/"
STATIC_ROOT = os.path.join(PROJECT_DIR, "collect-static")
STATIC_URL = "/static/"
# STATICFILES_DIRS = (
#     os.path.join(PROJECT_PATH, "repanier", "static"),
# )

config = ConfigParser.RawConfigParser(allow_no_value=True)
conf_file_name = '%s/%s.ini' % (
            PROJECT_DIR,
            os.path.split(PROJECT_DIR)[-1]
)
try:
    # Open the file with the correct encoding
    with codecs.open(conf_file_name, 'r', encoding='utf-8') as f:
        config.readfp(f)
    DJANGO_SETTINGS_ADMIN_EMAIL = config.get('DJANGO_SETTINGS', 'DJANGO_SETTINGS_ADMIN_EMAIL')
    DJANGO_SETTINGS_ADMIN_NAME = config.get('DJANGO_SETTINGS', 'DJANGO_SETTINGS_ADMIN_NAME')
    DJANGO_SETTINGS_DATABASE_HOST = config.get('DJANGO_SETTINGS', 'DJANGO_SETTINGS_DATABASE_HOST')
    DJANGO_SETTINGS_DATABASE_NAME = config.get('DJANGO_SETTINGS', 'DJANGO_SETTINGS_DATABASE_NAME')
    DJANGO_SETTINGS_DATABASE_PASSWORD = config.get('DJANGO_SETTINGS', 'DJANGO_SETTINGS_DATABASE_PASSWORD')
    DJANGO_SETTINGS_DATABASE_PORT = config.getint('DJANGO_SETTINGS', 'DJANGO_SETTINGS_DATABASE_PORT')
    DJANGO_SETTINGS_DATABASE_USER = config.get('DJANGO_SETTINGS', 'DJANGO_SETTINGS_DATABASE_USER')
    DJANGO_SETTINGS_DEBUG = config.getboolean('DJANGO_SETTINGS', 'DJANGO_SETTINGS_DEBUG')
    DJANGO_SETTINGS_DEMO = config.getboolean('DJANGO_SETTINGS', 'DJANGO_SETTINGS_DEMO')
    DJANGO_SETTINGS_EMAIL_HOST = config.get('DJANGO_SETTINGS', 'DJANGO_SETTINGS_EMAIL_HOST')
    DJANGO_SETTINGS_EMAIL_HOST_PASSWORD = config.get('DJANGO_SETTINGS', 'DJANGO_SETTINGS_EMAIL_HOST_PASSWORD')
    DJANGO_SETTINGS_EMAIL_HOST_USER = config.get('DJANGO_SETTINGS', 'DJANGO_SETTINGS_EMAIL_HOST_USER')
    DJANGO_SETTINGS_EMAIL_PORT = config.getint('DJANGO_SETTINGS', 'DJANGO_SETTINGS_EMAIL_PORT')
    DJANGO_SETTINGS_EMAIL_USE_SSL = config.getboolean('DJANGO_SETTINGS', 'DJANGO_SETTINGS_EMAIL_USE_TLS')
    DJANGO_SETTINGS_EMAIL_USE_TLS = config.getboolean('DJANGO_SETTINGS', 'DJANGO_SETTINGS_EMAIL_USE_TLS')
    DJANGO_SETTINGS_ENV = config.get('DJANGO_SETTINGS', 'DJANGO_SETTINGS_ENV')
    DJANGO_SETTINGS_LANGUAGE = config.get('DJANGO_SETTINGS', 'DJANGO_SETTINGS_LANGUAGE')
    DJANGO_SETTINGS_LOGGING = config.getboolean('DJANGO_SETTINGS', 'DJANGO_SETTINGS_LOGGING')
    DJANGO_SETTINGS_SITE_NAME = os.path.split(PROJECT_DIR)[-1]
    DJANGO_SETTINGS_CACHE = config.get('DJANGO_SETTINGS', 'DJANGO_SETTINGS_CACHE')
    DJANGO_SETTINGS_SESSION = config.get('DJANGO_SETTINGS', 'DJANGO_SETTINGS_SESSION')
    DJANGO_SETTINGS_ANDROID_SMS_GATEWAY_MAIL = config.get('DJANGO_SETTINGS', 'DJANGO_SETTINGS_ANDROID_SMS_GATEWAY_MAIL')
    DJANGO_SETTINGS_ALLOWED_HOSTS = []
    for name in config.options('ALLOWED_HOSTS'):
        DJANGO_SETTINGS_ALLOWED_HOSTS.append(config.get('ALLOWED_HOSTS', name))
    logging.info("Settings loaded from %s" % (conf_file_name,))
    print ("Settings loaded from %s" % (conf_file_name,))
    print(DJANGO_SETTINGS_ALLOWED_HOSTS)
except IOError:
    logging.exception("Unable to open %s settings" % (conf_file_name,))
    print ("Unable to open %s settings" % (conf_file_name,))
    raise SystemExit(-1)

###################### ANDROID SMS GATEWAY MAIL
ANDROID_SMS_GATEWAY_MAIL = DJANGO_SETTINGS_ANDROID_SMS_GATEWAY_MAIL
###################### DEBUG

DEBUG = DJANGO_SETTINGS_DEBUG
DEBUG_PROPAGATE_EXCEPTIONS = DEBUG
ADMINS = (
    (
        DJANGO_SETTINGS_ADMIN_NAME,
        DJANGO_SETTINGS_ADMIN_EMAIL
    ),
)
SERVER_EMAIL = DJANGO_SETTINGS_ADMIN_EMAIL
######################

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': DJANGO_SETTINGS_DATABASE_NAME,  # Or path to database file if using sqlite3.
        # The following settings are not used with sqlite3:
        'USER': DJANGO_SETTINGS_DATABASE_USER,
        'PASSWORD': DJANGO_SETTINGS_DATABASE_PASSWORD,
        # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
        'HOST': DJANGO_SETTINGS_DATABASE_HOST,
        # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
        'PORT': DJANGO_SETTINGS_DATABASE_PORT,  # Set to empty string for default.
    }
}
EMAIL_HOST = DJANGO_SETTINGS_EMAIL_HOST
EMAIL_HOST_USER = DJANGO_SETTINGS_EMAIL_HOST_USER
EMAIL_HOST_PASSWORD = DJANGO_SETTINGS_EMAIL_HOST_PASSWORD
EMAIL_PORT = DJANGO_SETTINGS_EMAIL_PORT
EMAIL_USE_TLS = DJANGO_SETTINGS_EMAIL_USE_TLS
if EMAIL_USE_TLS:
    EMAIL_USE_SSL = False
else:
    EMAIL_USE_SSL =DJANGO_SETTINGS_EMAIL_USE_SSL
# if DEBUG:
#     EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
###################### I18N

TIME_ZONE = 'Europe/Brussels'
USE_TZ = True
# Before 22/02/2014 - DJANGO-CMS LANGUAGE_CODE = 'fr-BE'
USE_L10N = True
USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = '.'
NUMBER_GROUPING = 3
DECIMAL_SEPARATOR = ','
# 'fr-be'

SITE_ID = 1
ALLOWED_HOSTS = DJANGO_SETTINGS_ALLOWED_HOSTS
ROOT_URLCONF = '%s.urls' % (DJANGO_SETTINGS_SITE_NAME,)
WSGI_APPLICATION = '%s.wsgi.application' % (DJANGO_SETTINGS_SITE_NAME,)
EMAIL_SUBJECT_PREFIX = '[' + DJANGO_SETTINGS_ALLOWED_HOSTS[0] + ']'
# DEFAULT_FROM_EMAIL Used by PASSWORD RESET
DEFAULT_FROM_EMAIL = DJANGO_SETTINGS_ALLOWED_HOSTS[0] + "@repanier.be"

USE_X_FORWARDED_HOST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_ENGINE = "django.contrib.sessions.backends.file"
SESSION_COOKIE_HTTPONLY = True
SESSION_FILE_PATH = DJANGO_SETTINGS_SESSION
# SOUTH_TESTS_MIGRATE = DEBUG

##################### Django & Django CMS
LOCALE_PATHS = (
    os.path.join(PROJECT_DIR, "locale"),
)

INSTALLED_APPS = (
    'django.contrib.sites',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'filer',
    'repanier', # ! Important : for template precedence Repanier must be first INSTALLED_APPS after django.contrib
    'djangocms_text_ckeditor',  # note this needs to be above the 'cms' entry
    'cmsplugin_cascade',
    'cmsplugin_cascade.extra_fields',  # optional
    'cmsplugin_cascade.sharable',  # optional
    'cms',
    "treebeard",
    'mptt',
    'menus',
    'djangocms_admin_style',  # note this needs to be above the 'django.contrib.admin' entry
    'django.contrib.admin',
    'django_mptt_admin',
    'easy_thumbnails',
    'easy_thumbnails.optimize',
    'sekizai',
    'cmsplugin_filer_file',
    'cmsplugin_filer_folder',
    'cmsplugin_filer_link',
    'cmsplugin_filer_image',
    'cmsplugin_filer_video',
    'reversion',
    'aldryn_reversion',
    'parler',
    'import_export',


    # 'aldryn_bootstrap3',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.cache.UpdateCacheMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.middleware.common.BrokenLinkEmailsMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    # 'django.middleware.doc.XViewMiddleware',
    'cms.middleware.user.CurrentUserMiddleware',
    'cms.middleware.page.CurrentPageMiddleware',
    'cms.middleware.toolbar.ToolbarMiddleware',
    'cms.middleware.language.LanguageCookieMiddleware',
    'django.middleware.cache.FetchFromCacheMiddleware',
)

TEMPLATES = [
{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [
        os.path.join(PROJECT_DIR, "templates"),
    ],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.contrib.auth.context_processors.auth',
            'django.template.context_processors.debug',
            'django.template.context_processors.i18n',
            'django.template.context_processors.media',
            'django.template.context_processors.static',
            'django.template.context_processors.tz',
            'django.template.context_processors.csrf',
            'django.template.context_processors.request',
            'django.contrib.messages.context_processors.messages',
            'cms.context_processors.cms_settings',
            'sekizai.context_processors.sekizai',
        ],
    }
},
]

MIGRATION_MODULES = {
    # 'cms': 'cms.migrations_django',
    # 'menus': 'menus.migrations_django',
    # 'filer': 'filer.migrations_django',
    'djangocms_text_ckeditor': 'djangocms_text_ckeditor.migrations_django',
    'cmsplugin_filer_file': 'cmsplugin_filer_file.migrations_django',
    'cmsplugin_filer_folder': 'cmsplugin_filer_folder.migrations_django',
    'cmsplugin_filer_link': 'cmsplugin_filer_link.migrations_django',
    'cmsplugin_filer_image': 'cmsplugin_filer_image.migrations_django',
    'cmsplugin_filer_video': 'cmsplugin_filer_video.migrations_django',
}

CMS_PERMISSION = False  # When set to True, don't forget 'cms.middleware.user.CurrentUserMiddleware'
CMS_PUBLIC_FOR = 'all'
# CMS_PUBLIC_FOR = 'staff'
CMS_SHOW_START_DATE = False
CMS_SHOW_END_DATE = False
CMS_SEO_FIELDS = False
CMS_URL_OVERWRITE = True
CMS_MENU_TITLE_OVERWRITE = True
CMS_REDIRECTS = True

CKEDITOR_SETTINGS = {
    'language': '{{ language }}',
    'toolbar_CMS': [
        ['Undo', 'Redo'],
        ['cmsplugins', '-', 'ShowBlocks'],
        ['Format',],
        ['TextColor', 'BGColor', '-', 'PasteText'],
        ['Maximize', ''],
        '/',
        ['Bold', 'Italic', 'Underline', '-', 'Subscript', 'Superscript', '-', 'RemoveFormat'],
        ['JustifyLeft', 'JustifyCenter', 'JustifyRight'],
        ['HorizontalRule'],
        ['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent', '-', 'Table'],
        ['Source']
    ],
    'toolbar_HTMLField': [
        ['Format', 'Bold', 'Italic', 'TextColor', '-', 'NumberedList', 'BulletedList', 'RemoveFormat'],
        ['Preview', 'Cut', 'Copy', 'PasteText', 'Link', '-', 'Undo', 'Redo'],
        ['Maximize', '']
    ],
    'forcePasteAsPlainText': 'true',
    'skin': 'moono',
    # 'stylesSet' : 'my_styles:%sjs/ckeditor-styles.js' % STATIC_URL,
    # 'stylesSet' : [],
    # 'extraPlugins': 'cmsplugins',
    'format_tags': 'p;h4;h5;blockquote;mutted;success;info;danger;heart;pushpin',
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
    # 'extraAllowedContent' : 'iframe[*]',
    # 'removeFormatTags': 'big,code,del,dfn,em,font,ins,kbd,q,s,samp,small,strike,strong,sub,sup,tt,u,var',
    # NOTE: Some versions of CKEditor will pre-sanitize your text before
    # passing it to the web server, rendering the above settings useless.
    # To ensure this does not happen, you may need to add
    # the following parameters to CKEDITOR_SETTINGS:
    'basicEntities': False,
    'entities': False,
    # Do not dispaly the HTML Path below the edit window
    'removePlugins': 'elementspath',
}

CKEDITOR_SETTINGS_MODEL2 = {
    'language': '{{ language }}',
    'toolbar_HTMLField': [
        ['Format', 'Bold', 'Italic', 'TextColor', '-', 'NumberedList', 'BulletedList', 'RemoveFormat'],
        ['Preview', 'Cut', 'Copy', 'PasteText', 'Link', '-', 'Undo', 'Redo'],
        ['Maximize', '']
    ],
    'forcePasteAsPlainText': 'true',
    'skin': 'moono',
    'format_tags': 'p;h4;h5',
    'contentsCss': '%sbootstrap/css/bootstrap.css' % STATIC_URL,
    'removeFormatTags': 'big,code,del,dfn,em,font,ins,kbd,q,s,samp,small,strike,strong,sub,sup,tt,u,var',
    'basicEntities': False,
    'entities': False,
    'removePlugins': 'elementspath',
}

# TEXT_SAVE_IMAGE_FUNCTION = 'cmsplugin_filer_image.integrations.ckeditor.create_image_plugin'
# TEXT_SAVE_IMAGE_FUNCTION = 'djangocms_text_ckeditor.picture_save.create_picture_plugin'
TEXT_SAVE_IMAGE_FUNCTION = None
# djangocms-text-ckeditor uses html5lib to sanitize HTML
# to avoid security issues and to check for correct HTML code.
# Sanitisation may strip tags usesful for some use cases such as iframe;
# you may customize the tags and attributes allowed by overriding
# the TEXT_ADDITIONAL_TAGS and TEXT_ADDITIONAL_ATTRIBUTES settings:
TEXT_ADDITIONAL_TAGS = ('span', 'iframe',)
TEXT_ADDITIONAL_ATTRIBUTES = ('class', 'scrolling', 'allowfullscreen', 'frameborder')
TEXT_HTML_SANITIZE = True

FILER_ENABLE_LOGGING = False
FILER_IMAGE_USE_ICON = True
FILER_ALLOW_REGULAR_USERS_TO_ADD_ROOT_FOLDERS = True
FILER_ENABLE_PERMISSIONS = False
FILER_IS_PUBLIC_DEFAULT = True
FILER_SUBJECT_LOCATION_IMAGE_DEBUG = True
FILER_DUMP_PAYLOAD = True
FILER_DEBUG = False

THUMBNAIL_PROCESSORS = (
    'easy_thumbnails.processors.colorspace',
    'easy_thumbnails.processors.autocrop',
    #'easy_thumbnails.processors.scale_and_crop',
    'filer.thumbnail_processors.scale_and_crop_with_subject_location',
    'easy_thumbnails.processors.filters',
    'easy_thumbnails.processors.background',
)
THUMBNAIL_HIGH_RESOLUTION = True
THUMBNAIL_PROGRESSIVE = 100
THUMBNAIL_PRESERVE_EXTENSIONS = True

THUMBNAIL_OPTIMIZE_COMMAND = {
    'png': '/usr/bin/optipng {filename}',
    'gif': '/usr/bin/optipng {filename}',
    'jpeg': '/usr/bin/jpegoptim {filename}',
}
THUMBNAIL_DEBUG = FILER_DEBUG

##################### Repanier
AUTH_USER_MODEL = 'auth.User'
AUTHENTICATION_BACKENDS = ('repanier.auth_backend.RepanierCustomBackend',)
# ADMIN_LOGIN = 'pi'
# ADMIN_PASSWORD = 'raspberry'
# ! Important : for template precedence Repanier must be first INSTALLED_APPS
# INSTALLED_APPS = (
#     'repanier',
# ) + INSTALLED_APPS
LOGIN_URL = "/repanier/go_repanier/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_URL = "/repanier/leave_repanier/"

################# Django_crispy_forms
INSTALLED_APPS += (
    'crispy_forms',
    # 'crispy_forms_foundation',
)

CRISPY_TEMPLATE_PACK = "bootstrap3"
# # CRISPY_TEMPLATE_PACK = "foundation"
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

###################### Django : Cache setup (https://docs.djangoproject.com/en/dev/topics/cache/)

CACHE_MIDDLEWARE_ALIAS = 'default'
CACHE_MIDDLEWARE_SECONDS = 3600

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.path.join(DJANGO_SETTINGS_CACHE, ALLOWED_HOSTS[0]),
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

##################### DECIMAL
from decimal import getcontext, ROUND_HALF_UP

getcontext().rounding = ROUND_HALF_UP

##################### DJANGOCMS-CASCADE
CMSPLUGIN_CASCADE_PLUGINS = (
    'cmsplugin_cascade.bootstrap3',
    'cmsplugin_cascade.link',)
CMSPLUGIN_CASCADE_ALIEN_PLUGINS = ('TextPlugin', )

##################### DJANGO IMPORT EXPORT
IMPORT_EXPORT_USE_TRANSACTIONS = True
DATE_INPUT_FORMATS = ('%d-%m-%Y',)
DATETIME_INPUT_FORMATS = ("%d-%m-%Y %H:%M:%S",)

if DJANGO_SETTINGS_LOGGING:
    import logging
    l = logging.getLogger('django.db.backends')
    l.setLevel(logging.DEBUG)
    l.addHandler(logging.StreamHandler())


    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'filters': {
            'require_debug_false': {
                '()': 'django.utils.log.RequireDebugFalse'
            }
        },
        'handlers': {
            'mail_admins': {
                'level': 'ERROR',
                'filters': ['require_debug_false'],
                'class': 'django.utils.log.AdminEmailHandler'
            },'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
            },
        },
        'loggers': {
            'django.request': {
                'handlers': ['mail_admins'],
                'level': 'ERROR',
                'propagate': True,
            },'django.db.backends': {
                'level': 'DEBUG',
                'handlers': ['console'],
            },
        }
    }


CMS_TEMPLATES = (
    ('cms_home.html', gettext("Homepage")),
    ('cms_page.html', gettext("Primary Page")),
    ('cms_subpage.html', gettext("Secondary Page")),
)

if DJANGO_SETTINGS_LANGUAGE == 'fr':

    LANGUAGE_CODE = 'fr'
    LANGUAGES = [
        ('fr', u'Français'),
    ]
    CMS_LANGUAGES = {
        SITE_ID: [
            {
            'code': 'fr',
            'name': gettext('French'),
            'public': True,
            'hide_untranslated': False,
            },
        ]
    }
    PARLER_DEFAULT_LANGUAGE_CODE = LANGUAGE_CODE
    PARLER_LANGUAGES = {
        SITE_ID: (
            {'code': 'fr',},
        ),
    }

elif DJANGO_SETTINGS_LANGUAGE == 'fr-nl-en':

    LANGUAGE_CODE = 'fr'
    LANGUAGES = [
        ('fr', u'Français'),
        ('nl', u'Neederlands'),
        ('en', u'English'),
    ]
    CMS_LANGUAGES = {
        SITE_ID: [
            {
                'code': 'fr',
                'name': gettext('French'),
                'fallbacks': ['en', 'nl'],
                'public': True,
                'redirect_on_fallback':False,
                'hide_untranslated': False,
            },
            {
                'code': 'nl',
                'name': gettext('Dutch'),
                'fallbacks': ['en', 'fr'],
                'public': True,
            },
            {
                'code': 'en',
                'name': gettext('English'),
                'fallbacks': ['fr'],
                'public': True,
            },
        ]
    }
    PARLER_DEFAULT_LANGUAGE_CODE = LANGUAGE_CODE
    PARLER_LANGUAGES = {
        SITE_ID: (
            {'code': 'fr',},
            {'code': 'nl',},
            {'code': 'en',},
        ),
        'default': {
                'fallbacks': ['fr'],
                'hide_untranslated': False,
        },
    }

DJANGOCMS_CASCADE_COLUMN_GLOSSARY = {
    'breakpoints': ['xs', 'sm', 'md', 'lg'],
    'container_max_widths': {'xs': 750, 'sm': 750, 'md': 970, 'lg': 1170},
    'fluid': False,
    'media_queries': {
        'xs': ['(max-width: 768px)'],
        'sm': ['(min-width: 768px)', '(max-width: 992px)'],
        'md': ['(min-width: 992px)', '(max-width: 1200px)'],
        'lg': ['(min-width: 1200px)'],
    },
}

CMS_PLACEHOLDER_CONF = {
    'home-hero': {
        'name': gettext('Hero'),
        'plugins': [
            'TextPlugin',
        ],
        'text_only_plugins': [
            'FilerLinkPlugin', 'FilerImagePlugin', 'FilerFilePlugin', 'FilerVideoPlugin',
        ],
        'default_plugins': [
            {
                'plugin_type': 'TextPlugin',
                'values': {
                    'body':
                        """
                        <h3>Lorem ipsum</h3>
                        <p>Lorem ipsum.</p>
                        <p class="text-muted"><span class="glyphicon glyphicon-pushpin"></span>&nbsp;Lorem ipsum.</p>
                        <h3>Lorem ipsum</h3>
                        <p class="text-muted">Lorem ipsum.</p>
                        """
                },
            },
        ]
    },
    'home-col-1': {
        'name': gettext('Column 1'),
        'plugins': [
            'TextPlugin',
        ],
        'text_only_plugins': [
            'FilerLinkPlugin', 'FilerImagePlugin', 'FilerFilePlugin', 'FilerVideoPlugin',
        ],
        'default_plugins': [
            {
                'plugin_type': 'TextPlugin',
                'values': {
                    'body':
                        """
                        <div class="panel panel-info">
                        <div class="panel-heading"><h4>Lorem ipsum</h4></div>
                        <div class="panel-body">
                        <ul class="list-group">
                        <li class="list-group-item">Lorem ipsum.</li>
                        <li class="list-group-item">Lorem ipsum.</li>
                        </ul>
                        </div>
                        </div>
                        """
                },
            },
        ]
    },
    'home-col-2': {
        'name': gettext('Column 2'),
        'plugins': [
            'TextPlugin',
        ],
        'text_only_plugins': [
            'FilerLinkPlugin', 'FilerImagePlugin', 'FilerFilePlugin', 'FilerVideoPlugin',
        ],

        'default_plugins': [
            {
                'plugin_type': 'TextPlugin',
                'values': {
                    'body':
                        """
                        <div class="panel panel-danger">
                        <div class="panel-heading"><h4>Lorem ipsum</h4></div>
                        <div class="panel-body">
                        <ul class="list-group">
                        <li class="list-group-item">Lorem ipsum.</li>
                        <li class="list-group-item">Lorem ipsum.</li>
                        </ul>
                        </div>
                        </div>
                        """
                },
            },
        ]
    },
    'home-col-3': {
        'name': gettext('Column 3'),
        'plugins': [
            'TextPlugin',
        ],
        'text_only_plugins': [
            'FilerLinkPlugin', 'FilerImagePlugin', 'FilerFilePlugin', 'FilerVideoPlugin',
        ],
        'default_plugins': [
            {
                'plugin_type': 'TextPlugin',
                'values': {
                    'body':
                        """
                        <div class="panel panel-warning">
                        <div class="panel-heading"><h4>Lorem ipsum</h4></div>
                        <div class="panel-body">
                        <ul class="list-group">
                        <li class="list-group-item">Lorem ipsum.</li>
                        <li class="list-group-item">Lorem ipsum.</li>
                        </ul>
                        </div>
                        </div>
                        """
                },
            },
        ]
    },
    'subpage_content': {
        'name': gettext('Content'),
        'plugins': [
            'TextPlugin',
            'BootstrapRowPlugin',
            # Aldryn start
            # 'Bootstrap3BlockquoteCMSPlugin',
            # 'Bootstrap3IconCMSPlugin',
            # 'Bootstrap3LabelCMSPlugin',
            # 'Bootstrap3WellCMSPlugin',
            # 'Bootstrap3AlertCMSPlugin',
            # 'Bootstrap3ButtonCMSPlugin',
            # 'Bootstrap3ImageCMSPlugin',
            # 'Bootstrap3SpacerCMSPlugin',
            # 'Bootstrap3FileCMSPlugin',
            # 'Bootstrap3PanelCMSPlugin',
            # 'Bootstrap3RowCMSPlugin',
            # 'Bootstrap3AccordionCMSPlugin',
            # 'Bootstrap3ListGroupCMSPlugin',
            # 'Bootstrap3CarouselCMSPlugin',
            # Aldryn end

        ],
        'text_only_plugins': [
            'FilerLinkPlugin', 'FilerImagePlugin', 'FilerFilePlugin', 'FilerVideoPlugin',
        ],
        'parent_classes': {
            'BootstrapRowPlugin': [],
        },
        'require_parent': False,
        'glossary': DJANGOCMS_CASCADE_COLUMN_GLOSSARY,
        'default_plugins': [
            {
                'plugin_type': 'TextPlugin',
                'values': {
                    'body':
                        """
                        <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed luctus tortor quis imperdiet egestas. Proin mollis sem ipsum, nec facilisis nibh cursus eu. Sed convallis cursus venenatis. Maecenas rutrum, elit ut ornare lobortis, mi dolor placerat elit, at laoreet sapien urna vitae arcu. Phasellus consectetur tincidunt ullamcorper. Sed et enim at lacus cursus rhoncus. Vestibulum porttitor velit non ante ullamcorper, ut gravida ipsum vestibulum. Aenean sed condimentum nisi. Quisque sagittis mauris non leo tincidunt vulputate. Ut euismod ante purus, sed pulvinar nisl volutpat quis. Maecenas consequat mi vitae libero egestas varius. Nam in tempor augue, sit amet pulvinar purus.</p>
                        <p>Vestibulum sed elit mollis, dapibus ligula in, ultricies purus. Proin fermentum blandit ultrices. Suspendisse vitae nisi mollis, viverra ipsum vitae, adipiscing lorem. Curabitur vestibulum orci felis, nec pretium arcu elementum a. Curabitur blandit fermentum tellus at consequat. Sed eget tempor elit. Donec in elit purus.</p>
                        <p>Morbi vulputate dolor sed nibh ullamcorper, eget molestie justo adipiscing. Fusce faucibus vel quam eu ultrices. Sed aliquet fringilla tristique. Vestibulum sit amet nunc tincidunt turpis tristique ullamcorper. Nam tempor mi felis, ac vulputate quam varius eget. Nunc blandit nulla vel metus lacinia, sit amet posuere lectus viverra. Praesent vel tortor facilisis, imperdiet orci sed, auctor erat.</p>
                        """
                },
            },
        ]
    },
    'footer': {
        'name': gettext('Footer'),
        'plugins': ['TextPlugin', ],
        'text_only_plugins': ['FilerLinkPlugin',],
        'limits': {
            'TextPlugin': 1,
        },
        'default_plugins': [
            {
                'plugin_type': 'TextPlugin',
                'values': {
                    'body':
                        'Lorem ipsum dolor sit amet'

                },
            },
        ]
    },
}
