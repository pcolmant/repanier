# -*- coding: utf-8 -*-
from common_settings import *

### Site 3 specific parameters
SITE_ID = 1
ALLOWED_HOSTS = ['ptidej.$REPANIER.BE$',]
EMAIL_SUBJECT_PREFIX = '['+ ALLOWED_HOSTS[0] +']'
# DEFAULT_FROM_EMAIL Used by PASSWORD RESET
DEFAULT_FROM_EMAIL=ALLOWED_HOSTS[0] + "@repanier.be"
MEDIA_ROOT = os.path.join(PROJECT_DIR, "media", "public")
TEMPLATE_DIRS = (
    os.path.join(PROJECT_DIR, "templates"),
)
CACHE_MIDDLEWARE_KEY_PREFIX = ALLOWED_HOSTS[0]
CMS_CACHE_PREFIX = ALLOWED_HOSTS[0]

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
        'plugins': ['TextPlugin',],
    },
}