# -*- coding: utf-8 -*-
import codecs
import configparser
import logging
import os
import sys

from django.urls import reverse_lazy
from django.utils.text import format_lazy
from django.utils.translation import get_language_info
from django.utils.translation import ugettext_lazy as _

from .settings import *

EMPTY_STRING = ""
# gettext = lambda s: s


def gettext(s):
    return s


logger = logging.getLogger(__name__)


# def get_allowed_mail_extension(site_name):
#     try:
#         component = site_name.split(".")
#         if component[-1] == "local":
#             allowed_mail_extension = "@repanier.be"
#         else:
#             allowed_mail_extension = "@{}.{}".format(component[-2], component[-1])
#     except:
#         allowed_mail_extension = "@repanier.be"
#     return allowed_mail_extension


def get_group_name(site_name):
    try:
        return (site_name.split(".")[0]).capitalize()
    except:
        return "Repanier"


# os.path.realpath resolves symlinks and os.path.abspath doesn't.
PROJECT_DIR = os.path.realpath(os.path.dirname(__file__))
PROJECT_PATH, DJANGO_SETTINGS_SITE_NAME = os.path.split(PROJECT_DIR)
os.sys.path.insert(0, PROJECT_PATH)
logger.info("Python path is : %s", sys.path)

config = configparser.RawConfigParser(allow_no_value=True)
conf_file_name = "{}.ini".format(os.path.join(PROJECT_DIR, DJANGO_SETTINGS_SITE_NAME))

try:
    # Open the file with the correct encoding
    with codecs.open(conf_file_name, "r", encoding="utf-8") as f:
        # TODO : Use parser.read_file() instead of readfp()
        config.readfp(f)
except IOError:
    logger.exception("Unable to open %s settings", conf_file_name)
    raise SystemExit(-1)

ADMIN_EMAIL = config.get("DJANGO_SETTINGS", "DJANGO_SETTINGS_ADMIN_EMAIL")
ADMIN_NAME = config.get("DJANGO_SETTINGS", "DJANGO_SETTINGS_ADMIN_NAME")
DJANGO_SETTINGS_CACHE = config.get(
    "DJANGO_SETTINGS", "DJANGO_SETTINGS_CACHE", fallback="/var/tmp/django-cache"
)
DJANGO_SETTINGS_CMS_FILER = config.getboolean(
    "DJANGO_SETTINGS", "DJANGO_SETTINGS_CMS_FILER", fallback=False
)
DJANGO_SETTINGS_CMS_CASCADE = config.getboolean(
    "DJANGO_SETTINGS", "DJANGO_SETTINGS_CMS_CASCADE", fallback=False
)
DJANGO_SETTINGS_DATABASE_ENGINE = config.get(
    "DJANGO_SETTINGS",
    "DJANGO_SETTINGS_DATABASE_ENGINE",
    fallback="django.db.backends.postgresql",
)
DJANGO_SETTINGS_DATABASE_HOST = config.get(
    "DJANGO_SETTINGS", "DJANGO_SETTINGS_DATABASE_HOST", fallback="127.0.0.1"
)
DJANGO_SETTINGS_DATABASE_NAME = config.get(
    "DJANGO_SETTINGS", "DJANGO_SETTINGS_DATABASE_NAME"
)
DJANGO_SETTINGS_DATABASE_PASSWORD = config.get(
    "DJANGO_SETTINGS", "DJANGO_SETTINGS_DATABASE_PASSWORD"
)
DJANGO_SETTINGS_DATABASE_PORT = config.getint(
    "DJANGO_SETTINGS", "DJANGO_SETTINGS_DATABASE_PORT", fallback=5432
)
DJANGO_SETTINGS_DATABASE_USER = config.get(
    "DJANGO_SETTINGS", "DJANGO_SETTINGS_DATABASE_USER"
)
DEBUG = config.getboolean("DJANGO_SETTINGS", "DJANGO_SETTINGS_DEBUG", fallback=False)
# NO debug tool if not in debug mode
DJANGO_SETTINGS_DEBUG_TOOLBAR = DEBUG and config.getboolean(
    "DJANGO_SETTINGS", "DJANGO_SETTINGS_DEBUG_TOOLBAR", fallback=False
)
EMAIL_HOST = config.get("DJANGO_SETTINGS", "DJANGO_SETTINGS_EMAIL_HOST")
EMAIL_HOST_PASSWORD = config.get(
    "DJANGO_SETTINGS", "DJANGO_SETTINGS_EMAIL_HOST_PASSWORD"
)
SERVER_EMAIL = EMAIL_HOST_USER = config.get(
    "DJANGO_SETTINGS", "DJANGO_SETTINGS_EMAIL_HOST_USER"
)
EMAIL_PORT = config.getint(
    "DJANGO_SETTINGS", "DJANGO_SETTINGS_EMAIL_PORT", fallback=587
)
EMAIL_USE_TLS = config.getboolean(
    "DJANGO_SETTINGS", "DJANGO_SETTINGS_EMAIL_USE_TLS", fallback=True
)
DJANGO_SETTINGS_LANGUAGE = config.get(
    "DJANGO_SETTINGS", "DJANGO_SETTINGS_LANGUAGE", fallback="fr"
)
DJANGO_SETTINGS_LOGGING = (
    config.getboolean("DJANGO_SETTINGS", "DJANGO_SETTINGS_LOGGING", fallback=False)
)
DJANGO_SETTINGS_SESSION = config.get(
    "DJANGO_SETTINGS", "DJANGO_SETTINGS_SESSION", fallback="/var/tmp/django-session"
)

REPANIER_SETTINGS_BOOTSTRAP_CSS = config.get(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_BOOTSTRAP_CSS", fallback="bootstrap.css"
)
REPANIER_SETTINGS_BOX = config.getboolean(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_BOX", fallback=False
)
REPANIER_SETTINGS_COORDINATOR_EMAIL = config.get(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_COORDINATOR_EMAIL", fallback=ADMIN_EMAIL
)
REPANIER_SETTINGS_COORDINATOR_NAME = config.get(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_COORDINATOR_NAME", fallback=ADMIN_NAME
)
REPANIER_SETTINGS_COORDINATOR_PHONE = config.get(
    "REPANIER_SETTINGS",
    "REPANIER_SETTINGS_COORDINATOR_PHONE",
    fallback="+32 499 96 64 32",
)
REPANIER_SETTINGS_COUNTRY = config.get(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_COUNTRY", fallback="be"
)
REPANIER_SETTINGS_BCC_ALL_EMAIL_TO = config.get(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_BCC_ALL_EMAIL_TO", fallback=EMPTY_STRING
)
REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER = config.getboolean(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER", fallback=False
)
REPANIER_SETTINGS_CUSTOM_CUSTOMER_PRICE = config.getboolean(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_CUSTOM_CUSTOMER_PRICE", fallback=False
)
REPANIER_SETTINGS_DELIVERY_POINT = config.getboolean(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_DELIVERY_POINT", fallback=False
)
REPANIER_SETTINGS_DEMO = config.getboolean(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_DEMO", fallback=False
)
REPANIER_SETTINGS_GROUP = config.getboolean(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_GROUP", fallback=False
)
REPANIER_SETTINGS_IS_MINIMALIST = config.getboolean(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_IS_MINIMALIST", fallback=True
)
REPANIER_SETTINGS_MANAGE_ACCOUNTING = config.getboolean(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_MANAGE_ACCOUNTING", fallback=True
)
REPANIER_SETTINGS_PRODUCT_LABEL = config.getboolean(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_PRODUCT_LABEL", fallback=False
)
REPANIER_SETTINGS_REPLY_ALL_EMAIL_TO = config.get(
    "REPANIER_SETTINGS",
    "REPANIER_SETTINGS_REPLY_ALL_EMAIL_TO",
    fallback=EMAIL_HOST_USER,
)

REPANIER_SETTINGS_ROUND_INVOICES = config.getboolean(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_ROUND_INVOICES", fallback=False
)

REPANIER_SETTINGS_SHOW_PRODUCER_ON_ORDER_FORM = config.getboolean(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_SHOW_PRODUCER_ON_ORDER_FORM", fallback=True
)
REPANIER_SETTINGS_SMS_GATEWAY_MAIL = config.get(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_SMS_GATEWAY_MAIL", fallback=EMPTY_STRING
)
REPANIER_SETTINGS_STOCK = config.getboolean(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_STOCK", fallback=False
)
REPANIER_SETTINGS_TEMPLATE = config.get(
    "REPANIER_SETTINGS", "REPANIER_SETTINGS_TEMPLATE", fallback="bs3"
)

ALLOWED_HOSTS = []
for name in config.options("ALLOWED_HOSTS"):
    allowed_host = config.get("ALLOWED_HOSTS", name)
    if allowed_host.startswith("demo"):
        REPANIER_SETTINGS_DEMO = True
    ALLOWED_HOSTS.append(allowed_host)
logger.info("Settings loaded from: %s", conf_file_name)
logger.info("Allowed hosts: %s", ALLOWED_HOSTS)
# REPANIER_SETTINGS_ALLOWED_MAIL_EXTENSION = get_allowed_mail_extension(DJANGO_SETTINGS_ALLOWED_HOSTS[0])
REPANIER_SETTINGS_GROUP_NAME = config.get(
    "REPANIER_SETTINGS",
    "REPANIER_SETTINGS_GROUP_NAME",
    fallback=get_group_name(ALLOWED_HOSTS[0]),
)
DEFAULT_FROM_EMAIL = "{} <{}>".format(REPANIER_SETTINGS_GROUP_NAME, EMAIL_HOST_USER)
REPANIER_DEMO_EMAIL = "repanier@no-spam.ws"

DJANGO_SETTINGS_DATES_SEPARATOR = ","
DJANGO_SETTINGS_DAY_MONTH = "%d-%m"
DJANGO_SETTINGS_DATE = "%d-%m-%Y"
DJANGO_SETTINGS_DATETIME = "%d-%m-%Y %H:%M"

if DJANGO_SETTINGS_SITE_NAME == "mysite":
    STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
    STATICFILES_DIRS = (os.path.join(PROJECT_PATH, "collect-static"),)
else:
    # Activate ManifestStaticFilesStorage also when in debug mode
    STATICFILES_STORAGE = "repanier.big_blind_static.BigBlindManifestStaticFilesStorage"

# Directory where working files, such as media and databases are kept
MEDIA_DIR = os.path.join(PROJECT_DIR, "media")
logger.debug("------- media dir : %s", MEDIA_DIR)

MEDIA_PUBLIC_DIR = os.path.join(MEDIA_DIR, "public")
logger.debug("------- media public dir : %s", MEDIA_PUBLIC_DIR)

STATIC_DIR = os.path.join(PROJECT_DIR, "collect-static")
logger.debug("------- static dir : %s", STATIC_DIR)

MEDIA_ROOT = MEDIA_PUBLIC_DIR
MEDIA_URL = "{}{}{}".format(os.sep, "media", os.sep)
STATIC_ROOT = STATIC_DIR
STATIC_URL = "{}{}{}".format(os.sep, "static", os.sep)


def get_repanier_css_name(template_name):
    return os.path.join("repanier", REPANIER_SETTINGS_TEMPLATE, template_name)


REPANIER_SETTINGS_BOOTSTRAP_CSS_PATH = get_repanier_css_name(
    os.path.join("bootstrap", "css", REPANIER_SETTINGS_BOOTSTRAP_CSS)
)

REPANIER_SETTINGS_CUSTOM_CSS_PATH = get_repanier_css_name(
    os.path.join("css", "custom.css")
)

REPANIER_SETTINGS_BRANDING_CSS_PATH = get_repanier_css_name(
    os.path.join("css", "branding.css")
)

logger.debug("------- bootstrap path dir : %s", REPANIER_SETTINGS_BOOTSTRAP_CSS_PATH)

###################### LUT_CONFIRM
if REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
    LOCK_UNICODE = "📧"  # "🔑"  # "✓"  # "✉" "📧"
else:
    LOCK_UNICODE = EMPTY_STRING

LUT_CONFIRM = ((True, LOCK_UNICODE), (False, EMPTY_STRING))

###################### DEBUG
DEBUG_PROPAGATE_EXCEPTIONS = DEBUG

ADMINS = ((ADMIN_NAME, ADMIN_EMAIL),)
######################

DATABASES = {
    "default": {
        "ENGINE": DJANGO_SETTINGS_DATABASE_ENGINE,
        "NAME": DJANGO_SETTINGS_DATABASE_NAME,  # Or path to database file if using sqlite3.
        "USER": DJANGO_SETTINGS_DATABASE_USER,
        "PASSWORD": DJANGO_SETTINGS_DATABASE_PASSWORD,
        "HOST": DJANGO_SETTINGS_DATABASE_HOST,
        "PORT": DJANGO_SETTINGS_DATABASE_PORT,  # Set to empty string for default.
    }
}
###################### I18N

TIME_ZONE = "Europe/Brussels"
USE_TZ = True
USE_L10N = True
USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = "."
NUMBER_GROUPING = 3
DECIMAL_SEPARATOR = ","

SITE_ID = 1
ROOT_URLCONF = "{}.urls".format(DJANGO_SETTINGS_SITE_NAME)
WSGI_APPLICATION = "{}.wsgi.application".format(DJANGO_SETTINGS_SITE_NAME)

USE_X_FORWARDED_HOST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_COOKIE_HTTPONLY = True
SESSION_FILE_PATH = DJANGO_SETTINGS_SESSION

##################### Django & Django CMS
LOCALE_PATHS = (os.path.join(PROJECT_DIR, "locale"),)

INSTALLED_APPS = (
    "repanier",  # ! Important : for template precedence Repanier must be first INSTALLED_APPS after django.contrib
    "djangocms_admin_style",  # note this needs to be above the 'django.contrib.admin' entry
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.sitemaps",
    "django.contrib.staticfiles",
    "django.contrib.messages",
    "djangocms_text_ckeditor",  # note this needs to be above the 'cms' entry
    # 'django_select2',
    "djangocms_link",
    "djangocms_file",
    "djangocms_picture",
    "djangocms_video",
    # "django_extensions", # Need only to be present on dev environment
    "cms",
    # 'cms_bootstrap3',
    "menus",
    "treebeard",
    "easy_thumbnails",
    "easy_thumbnails.optimize",
    "filer",
    "sekizai",
    "mptt",
    "django_mptt_admin",
    "reversion",
    # 'aldryn_reversion',
    "parler",
    "import_export",
    "rest_framework",
    "easy_select2",
    "recurrence",
    "crispy_forms",
)

# set djangocms and filer plugins as cmsplugin for ckeditor
# and such remove access to cmsplugin_filer and cmsplugin_cascade plugins from ckeditor cmsplugin
text_only_plugins = [
    "LinkPlugin",  # djangocms_link
    "PicturePlugin",  # djangocms_picture
    "FilePlugin",  # filer
    "FolderPlugin",  # filer
    "VideoPlayerPlugin",  # djangocms_video
]

if DJANGO_SETTINGS_CMS_FILER:
    try:
        import cmsplugin_filer_utils

        # TODO : remove cmsplugin which is replaced by djangocms_file / link / picture / video
        INSTALLED_APPS += (
            "cmsplugin_filer_file",
            "cmsplugin_filer_folder",
            "cmsplugin_filer_link",
            "cmsplugin_filer_image",
            "cmsplugin_filer_video",
        )
    except ImportError:
        pass  # module doesn't exist

cascade_is_installed = False
if DJANGO_SETTINGS_CMS_CASCADE:
    try:
        # TODO : remove cmsplugin cascade
        import cmsplugin_cascade

        INSTALLED_APPS += (
            "cmsplugin_cascade",
            "cmsplugin_cascade.clipboard",
            "cmsplugin_cascade.extra_fields",
            "cmsplugin_cascade.icon",
            "cmsplugin_cascade.sharable",
            "cmsplugin_cascade.segmentation",
        )

        cascade_is_installed = True
    except ImportError:
        pass  # module doesn't exist

# http://docs.django-cms.org/en/develop/how_to/caching.html

MIDDLEWARE = (
    "django.middleware.cache.UpdateCacheMiddleware",
    "cms.middleware.utils.ApphookReloadMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "cms.middleware.page.CurrentPageMiddleware",
    "cms.middleware.user.CurrentUserMiddleware",
    "cms.middleware.toolbar.ToolbarMiddleware",
    "cms.middleware.language.LanguageCookieMiddleware",
    "django.middleware.cache.FetchFromCacheMiddleware",
)

if DJANGO_SETTINGS_DEBUG_TOOLBAR:
    INSTALLED_APPS += ("debug_toolbar",)
    INTERNAL_IPS = ["10.0.2.2"]
    MIDDLEWARE = ("debug_toolbar.middleware.DebugToolbarMiddleware",) + MIDDLEWARE

CONTEXT_PROCESSORS = [
    "django.contrib.auth.context_processors.auth",
    "django.template.context_processors.debug",
    "django.template.context_processors.i18n",
    "django.template.context_processors.media",
    "django.template.context_processors.static",
    "django.template.context_processors.tz",
    "django.template.context_processors.csrf",
    "django.template.context_processors.request",
    "django.contrib.messages.context_processors.messages",
    "sekizai.context_processors.sekizai",
    "cms.context_processors.cms_settings",
    "repanier.context_processors.repanier_settings",
]

if DEBUG:
    TEMPLATES = [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [
                os.path.join(
                    PROJECT_PATH, "repanier", "templates", REPANIER_SETTINGS_TEMPLATE
                )
            ],
            # "APP_DIRS": True,
            "OPTIONS": {
                "context_processors": CONTEXT_PROCESSORS,
                "loaders": [
                        "django.template.loaders.filesystem.Loader",
                        "django.template.loaders.app_directories.Loader",
                ],
                "debug": True,
            },
        }
    ]
else:
    TEMPLATES = [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [
                os.path.join(
                    PROJECT_PATH, "repanier", "templates", REPANIER_SETTINGS_TEMPLATE
                )
            ],
            # 'APP_DIRS': True,
            "OPTIONS": {
                "context_processors": CONTEXT_PROCESSORS,
                "loaders": [
                    (
                        "django.template.loaders.cached.Loader",
                        [
                            "django.template.loaders.filesystem.Loader",
                            "django.template.loaders.app_directories.Loader",
                        ],
                    )
                ],
                "debug": False,
            },
        }
    ]

if REPANIER_SETTINGS_TEMPLATE == "bs3":
    CRISPY_TEMPLATE_PACK = "bootstrap3"
else:
    CRISPY_TEMPLATE_PACK = "bootstrap4"

CMS_PERMISSION = (
    False
)  # When set to True, don't forget 'cms.middleware.user.CurrentUserMiddleware'
CMS_PUBLIC_FOR = "all"
CMS_SHOW_START_DATE = False
CMS_SHOW_END_DATE = False
CMS_SEO_FIELDS = False
CMS_URL_OVERWRITE = True
CMS_MENU_TITLE_OVERWRITE = True
CMS_REDIRECTS = True
DJANGOCMS_PICTURE_RESPONSIVE_IMAGES = True

CKEDITOR_SETTINGS = {
    "language": "{{ language }}",
    "toolbar_CMS": [
        ["Undo", "Redo"],
        ["cmsplugins", "-", "ShowBlocks"],
        ["Format"],
        ["TextColor", "BGColor", "Smiley", "-", "PasteText"],
        ["Maximize", ""],
        "/",
        [
            "Bold",
            "Italic",
            "Underline",
            "-",
            "Subscript",
            "Superscript",
            "-",
            "RemoveFormat",
        ],
        ["JustifyLeft", "JustifyCenter", "JustifyRight"],
        ["HorizontalRule"],
        ["NumberedList", "BulletedList", "-", "Outdent", "Indent", "-", "Table"],
        ["Source"],
    ],
    "toolbar_HTMLField": [
        [
            "Format",
            "Bold",
            "Italic",
            "TextColor",
            "Smiley",
            "-",
            "NumberedList",
            "BulletedList",
            "RemoveFormat",
        ],
        ["Preview", "Cut", "Copy", "PasteText", "Link", "-", "Undo", "Redo"],
        ["Source"],
    ],
    "forcePasteAsPlainText": "true",
    "format_tags": "p;h2;h3;h4;h5",
    # format_test = { element : 'span', attributes : { 'class' : 'test' }, styles: { color: 'blue'}, 'name': 'Test Name' };
    "contentsCss": "{}{}".format(STATIC_URL, REPANIER_SETTINGS_BOOTSTRAP_CSS_PATH),
    # NOTE: Some versions of CKEditor will pre-sanitize your text before
    # passing it to the web server, rendering the above settings useless.
    # To ensure this does not happen, you may need to add
    # the following parameters to CKEDITOR_SETTINGS:
    "basicEntities": False,
    "entities": False,
    "enterMode": 2,
    # Do not dispaly the HTML Path below the edit window
    "removePlugins": "elementspath",
    # 'stylesSet' : 'my_styles:{}js/ckeditor-styles.js'.format(STATIC_URL),
    # 'stylesSet': format_lazy('default:{}', reverse_lazy('admin:cascade_texticon_wysiwig_config')),
}

if cascade_is_installed:
    CKEDITOR_SETTINGS["stylesSet"] = format_lazy(
        "default:{}", reverse_lazy("admin:cascade_texticon_wysiwig_config")
    )

CKEDITOR_SETTINGS_MODEL2 = {
    "language": "{{ language }}",
    "toolbar_HTMLField": [
        [
            "Bold",
            "Italic",
            "TextColor",
            "Smiley",
            "-",
            "NumberedList",
            "BulletedList",
            "RemoveFormat",
        ],
        [
            "Preview",
            "Cut",
            "Copy",
            "PasteText",
            "Simplebox",
            "Link",
            "-",
            "Undo",
            "Redo",
        ],
        ["Source"],
    ],
    # 'extraPlugins': 'simplebox',
    "forcePasteAsPlainText": "true",
    # 'skin': 'moono',
    "contentsCss": "{}{}".format(STATIC_URL, REPANIER_SETTINGS_BOOTSTRAP_CSS_PATH),
    "removeFormatTags": "iframe,big,code,del,dfn,em,font,ins,kbd,q,s,samp,small,strike,strong,sub,sup,tt,u,var",
    "basicEntities": False,
    "entities": False,
    "enterMode": 2,
    "removePlugins": "elementspath",
}

# Drag & Drop Images
# TEXT_SAVE_IMAGE_FUNCTION = 'djangocms_text_ckeditor.picture_save.create_picture_plugin'

# djangocms-text-ckeditor uses html5lib to sanitize HTML
# to avoid security issues and to check for correct HTML code.
# Sanitisation may strip tags usesful for some use cases such as iframe;
# you may customize the tags and attributes allowed by overriding
# the TEXT_ADDITIONAL_TAGS and TEXT_ADDITIONAL_ATTRIBUTES settings:
TEXT_ADDITIONAL_TAGS = ("span", "iframe")
TEXT_ADDITIONAL_ATTRIBUTES = ("class", "scrolling", "allowfullscreen", "frameborder")
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
    "easy_thumbnails.processors.colorspace",
    "easy_thumbnails.processors.autocrop",
    "filer.thumbnail_processors.scale_and_crop_with_subject_location",
    "easy_thumbnails.processors.filters",
    "easy_thumbnails.processors.background",
)
THUMBNAIL_HIGH_RESOLUTION = True
THUMBNAIL_PROGRESSIVE = 100
THUMBNAIL_PRESERVE_EXTENSIONS = True

THUMBNAIL_OPTIMIZE_COMMAND = {
    "png": "/usr/bin/optipng {filename}",
    "gif": "/usr/bin/optipng {filename}",
    "jpeg": "/usr/bin/jpegoptim {filename}",
}
THUMBNAIL_DEBUG = FILER_DEBUG

##################### Repanier
# AUTH_USER_MODEL = 'auth.User'
AUTHENTICATION_BACKENDS = ("repanier.auth_backend.RepanierAuthBackend",)
# ADMIN_LOGIN = 'pi'
# ADMIN_PASSWORD = 'raspberry'
LOGIN_URL = "/repanier/go_repanier/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_URL = "/repanier/leave_repanier/"

##### From : django/conf/global_settings.py
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)

##################### DJANGO REST_FRAMEWORK
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 10,
}

##################### DJANGO IMPORT EXPORT
IMPORT_EXPORT_USE_TRANSACTIONS = True

DATE_INPUT_FORMATS = (DJANGO_SETTINGS_DATE, "%d/%m/%Y", "%Y-%m-%d")
DATETIME_INPUT_FORMATS = (DJANGO_SETTINGS_DATETIME,)

##################### LOGGING
if DJANGO_SETTINGS_LOGGING:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"console": {"format": "%(levelname)s %(name)s %(message)s"}},
        "handlers": {
            "console": {
                "level": "DEBUG", # DEBUG INFO WARNING ERROR CRITICAL
                "class": "logging.StreamHandler",
                "formatter": "console",
            }
        },
        "loggers": {
            "django.db.backends": {"level": "DEBUG", "handlers": ["console"]},
            "repanier": {"level": "DEBUG", "handlers": ["console"]},
        },
    }

####################### LANGUAGE

LANGUAGE_CODE = "fr"
LANGUAGES = [("fr", get_language_info("fr")["name_local"])]
CMS_LANGUAGES = {
    SITE_ID: [
        {
            "code": "fr",
            "name": get_language_info("fr")["name"],
            "public": True,
            "hide_untranslated": False,
        }
    ]
}
PARLER_DEFAULT_LANGUAGE_CODE = LANGUAGE_CODE
PARLER_LANGUAGES = {
    SITE_ID: ({"code": LANGUAGE_CODE},),
    "default": {"fallbacks": [LANGUAGE_CODE], "hide_untranslated": False},
}

if DJANGO_SETTINGS_LANGUAGE == "es":

    LANGUAGE_CODE = "es"
    LANGUAGES = [("es", get_language_info("es")["name_local"])]
    CMS_LANGUAGES = {
        SITE_ID: [
            {
                "code": "es",
                "name": get_language_info("es")["name"],
                "public": True,
                "hide_untranslated": False,
            }
        ]
    }
    PARLER_DEFAULT_LANGUAGE_CODE = LANGUAGE_CODE
    PARLER_LANGUAGES = {
        SITE_ID: ({"code": LANGUAGE_CODE},),
        "default": {"fallbacks": [LANGUAGE_CODE], "hide_untranslated": False},
    }

elif DJANGO_SETTINGS_LANGUAGE == "fr-nl-en":

    LANGUAGE_CODE = "fr"
    LANGUAGES = [
        ("fr", get_language_info("fr")["name_local"]),
        ("nl", get_language_info("nl")["name_local"]),
        ("en", get_language_info("en")["name_local"]),
    ]
    CMS_LANGUAGES = {
        SITE_ID: [
            {
                "code": "fr",
                "name": get_language_info("fr")["name"],
                "public": True,
                "redirect_on_fallback": False,
                "hide_untranslated": False,
            },
            {
                "code": "nl",
                "name": get_language_info("nl")["name"],
                "fallbacks": ["en", "fr"],
                "public": True,
            },
            {
                "code": "en",
                "name": get_language_info("en")["name"],
                "fallbacks": [LANGUAGE_CODE],
                "public": True,
            },
        ]
    }
    PARLER_DEFAULT_LANGUAGE_CODE = LANGUAGE_CODE
    PARLER_LANGUAGES = {
        SITE_ID: ({"code": "fr"}, {"code": "nl"}, {"code": "en"}),
        "default": {"fallbacks": [LANGUAGE_CODE], "hide_untranslated": False},
    }
elif DJANGO_SETTINGS_LANGUAGE == "fr-en":

    LANGUAGE_CODE = "fr"
    LANGUAGES = [
        ("fr", get_language_info("fr")["name_local"]),
        ("en", get_language_info("en")["name_local"]),
    ]
    CMS_LANGUAGES = {
        SITE_ID: [
            {
                "code": "fr",
                "name": get_language_info("fr")["name"],
                "public": True,
                "redirect_on_fallback": False,
                "hide_untranslated": False,
            },
            {
                "code": "en",
                "name": get_language_info("en")["name"],
                "fallbacks": [LANGUAGE_CODE],
                "public": True,
            },
        ]
    }
    PARLER_DEFAULT_LANGUAGE_CODE = LANGUAGE_CODE
    PARLER_LANGUAGES = {
        SITE_ID: ({"code": "fr"}, {"code": "en"}),
        "default": {"fallbacks": [LANGUAGE_CODE], "hide_untranslated": False},
    }
elif DJANGO_SETTINGS_LANGUAGE == "fr-nl":

    LANGUAGE_CODE = "fr"
    LANGUAGES = [
        ("fr", get_language_info("fr")["name_local"]),
        ("nl", get_language_info("nl")["name_local"]),
    ]
    CMS_LANGUAGES = {
        SITE_ID: [
            {
                "code": "fr",
                "name": get_language_info("fr")["name"],
                "public": True,
                "redirect_on_fallback": False,
                "hide_untranslated": False,
            },
            {
                "code": "nl",
                "name": get_language_info("nl")["name"],
                "fallbacks": [LANGUAGE_CODE],
                "public": True,
            },
        ]
    }
    PARLER_DEFAULT_LANGUAGE_CODE = LANGUAGE_CODE
    PARLER_LANGUAGES = {
        SITE_ID: ({"code": "fr"}, {"code": "nl"}),
        "default": {"fallbacks": [LANGUAGE_CODE], "hide_untranslated": False},
    }

DJANGO_SETTINGS_MULTIPLE_LANGUAGE = len(LANGUAGES) > 1

###################### Django : Cache setup (https://docs.djangoproject.com/en/dev/topics/cache/)

CACHE_MIDDLEWARE_ALIAS = "default"
CACHE_MIDDLEWARE_SECONDS = 3600

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": os.path.join(DJANGO_SETTINGS_CACHE, ALLOWED_HOSTS[0]),
        "TIMEOUT": 3000,
        "OPTIONS": {"MAX_ENTRIES": 10000, "CULL_FREQUENCY": 3},
    }
}

######################## CMS

CMS_CACHE_DURATIONS = {
    "content": 60,  # default 60
    "menus": 60,  # default 3600
    "permissions": 3600,  # default: 3600
}

CMS_TEMPLATE_HOME = "cms_home.html"
CMS_TEMPLATE_PAGE = "cms_page.html"
CMS_TEMPLATE_SUB_PAGE = "cms_subpage.html"
CMS_TEMPLATES = (
    (CMS_TEMPLATE_SUB_PAGE, gettext("Internal page with menu on left")),
    (CMS_TEMPLATE_PAGE, gettext("Internal page")),
    (CMS_TEMPLATE_HOME, gettext("Home page")),
    # ('cms_bootstrap_page.html', gettext("Bootstrap page")),
    # ('cms_bootstrap_subpage.html', gettext("Bootstrap page with menu on left"))
)
CMS_TEMPLATE_INHERITANCE = False

CMS_PAGE_CACHE = True
CMS_PLACEHOLDER_CACHE = True
CMS_PLUGIN_CACHE = True
CMS_TOOLBAR_ANONYMOUS_ON = False
CMS_PAGE_WIZARD_DEFAULT_TEMPLATE = CMS_TEMPLATE_SUB_PAGE
CMS_PAGE_WIZARD_CONTENT_PLACEHOLDER = "subpage_content"

CMS_TEMPLATE_HOME_HERO = """
<h3>Lorem ipsum</h3>
<p>Lorem ipsum.</p>
<p class="text-muted">Lorem ipsum.</p>
<h3>Lorem ipsum</h3>
<p class="text-muted">Lorem ipsum.</p>
"""

CMS_TEMPLATE_HOME_COL_1 = """
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

CMS_TEMPLATE_HOME_COL_2 = """
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

CMS_TEMPLATE_HOME_COL_3 = """
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

CMS_TEMPLATE_FOOTER = """
Lorem ipsum dolor sit amet
"""

CMS_PLACEHOLDER_CONF = {
    "home-hero": {
        "name": gettext("Hero"),
        "plugins": ["TextPlugin"],
        "text_only_plugins": text_only_plugins,
        "default_plugins": [
            {"plugin_type": "TextPlugin", "values": {"body": CMS_TEMPLATE_HOME_HERO}}
        ],
    },
    'home-col-1': {
        'name': gettext('Column 1'),
        'plugins': [
            'TextPlugin',
        ],
        'text_only_plugins': text_only_plugins,
        'default_plugins': [
            {
                'plugin_type': 'TextPlugin',
                'values': {
                    'body':
                        CMS_TEMPLATE_HOME_COL_1
                },
            },
        ]
    },
    'home-col-2': {
        'name': gettext('Column 2'),
        'plugins': [
            'TextPlugin',
        ],
        'text_only_plugins': text_only_plugins,
        'default_plugins': [
            {
                'plugin_type': 'TextPlugin',
                'values': {
                    'body':
                        CMS_TEMPLATE_HOME_COL_2
                },
            },
        ]
    },
    'home-col-3': {
        'name': gettext('Column 3'),
        'plugins': [
            'TextPlugin',
        ],
        'text_only_plugins': text_only_plugins,
        'default_plugins': [
            {
                'plugin_type': 'TextPlugin',
                'values': {
                    'body':
                        CMS_TEMPLATE_HOME_COL_3
                },
            },
        ]
    },
    "subpage_content": {
        "name": gettext("Content"),
        "plugins": ["TextPlugin"],
        "text_only_plugins": text_only_plugins,
        "default_plugins": [
            {
                "plugin_type": "TextPlugin",
                "values": {
                    "body": """
                        <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed luctus tortor quis imperdiet egestas. Proin mollis sem ipsum, nec facilisis nibh cursus eu. Sed convallis cursus venenatis. Maecenas rutrum, elit ut ornare lobortis, mi dolor placerat elit, at laoreet sapien urna vitae arcu. Phasellus consectetur tincidunt ullamcorper. Sed et enim at lacus cursus rhoncus. Vestibulum porttitor velit non ante ullamcorper, ut gravida ipsum vestibulum. Aenean sed condimentum nisi. Quisque sagittis mauris non leo tincidunt vulputate. Ut euismod ante purus, sed pulvinar nisl volutpat quis. Maecenas consequat mi vitae libero egestas varius. Nam in tempor augue, sit amet pulvinar purus.</p>
                        <p>Vestibulum sed elit mollis, dapibus ligula in, ultricies purus. Proin fermentum blandit ultrices. Suspendisse vitae nisi mollis, viverra ipsum vitae, adipiscing lorem. Curabitur vestibulum orci felis, nec pretium arcu elementum a. Curabitur blandit fermentum tellus at consequat. Sed eget tempor elit. Donec in elit purus.</p>
                        <p>Morbi vulputate dolor sed nibh ullamcorper, eget molestie justo adipiscing. Fusce faucibus vel quam eu ultrices. Sed aliquet fringilla tristique. Vestibulum sit amet nunc tincidunt turpis tristique ullamcorper. Nam tempor mi felis, ac vulputate quam varius eget. Nunc blandit nulla vel metus lacinia, sit amet posuere lectus viverra. Praesent vel tortor facilisis, imperdiet orci sed, auctor erat.</p>
                        """
                },
            }
        ],
    },
    "footer": {
        "name": gettext("Footer"),
        "plugins": ["TextPlugin"],
        "text_only_plugins": text_only_plugins,
        "limits": {"TextPlugin": 1},
        "default_plugins": [
            {"plugin_type": "TextPlugin", "values": {"body": CMS_TEMPLATE_FOOTER}}
        ],
    },
}
