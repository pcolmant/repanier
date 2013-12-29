# -*- coding: utf-8 -*-
from production_settings import *

### Site 1 specific parameters
SITE_ID = 1
ALLOWED_HOSTS = ['$REPANIER.BE$','$REPANIER.LOCAL$']
EMAIL_SUBJECT_PREFIX = '['+ ALLOWED_HOSTS[0] +']'
MEDIA_ROOT = os.path.join(PROJECT_DIR, "media", ALLOWED_HOSTS[0], "public")
TEMPLATE_DIRS = (
    os.path.join(PROJECT_DIR, "templates"),
)
CACHE_MIDDLEWARE_KEY_PREFIX = ALLOWED_HOSTS[0]
CMS_CACHE_PREFIX = ALLOWED_HOSTS[0]
# BEGIN OF : Use email instead of username as login name
# from django.contrib.auth.models import User
## ImportError: Could not import settings 'mysite.repanier_settings' (Is it on sys.path? Is there an import error in the settings file?): cannot import name auth
# User.USERNAME_FIELD = 'email'
# User.REQUIRED_FIELDS.remove('email')
# User._meta.get_field('email')._unique = True
# END OF : Use email instead of username as login name

CMS_TEMPLATES = (
    ('home.html', gettext("Homepage")),
    ('subpage.html', gettext("Secondary Page")),
)

CMS_LANGUAGES[SITE_ID] = [
    {
        'code': 'fr',
        'name': gettext('French'),
        # 'fallbacks': ['en', 'nl'],
        'public': True,
        # 'redirect_on_fallback':False,
        # 'hide_untranslated': False,
    },
    {
        'code': 'nl',
        'name': gettext('Dutch'),
        # 'fallbacks': ['en', 'fr'],
        'public': True,
    },
    {
        'code': 'en',
        'name': gettext('English'),
        'public': True,
    },
]

CMS_PLACEHOLDER_CONF = {
    'home-hero': {
        'name': gettext('Hero'),
        'plugins': ['TextPlugin',],
    },
    'home-col-1': {
        'name': gettext('Column 1'),
        'plugins': ['TextPlugin',],
    },
    'home-col-2': {
        'name': gettext('Column 2'),
        'plugins': ['TextPlugin',],
    },
    'home-col-3': {
        'name': gettext('Column 3'),
        'plugins': ['TextPlugin',],
        # 'limits': {
        #     'global': 2,
        #     'TextPlugin': 1,
        #     'PollPlugin': 1,
        # },
    },
    'subpage_content': {
        'name': gettext('Content'),
    },
}