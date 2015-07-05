# -*- coding: utf-8 -*-
from common_settings import *
from django.utils.translation import ugettext_lazy as _
gettext = lambda s: s

### Site 4 specific parameters
SITE_ID = 1
ALLOWED_HOSTS = ['apero.repanier.be','apero.repanier.local']
EMAIL_SUBJECT_PREFIX = '['+ ALLOWED_HOSTS[0] +']'
# DEFAULT_FROM_EMAIL Used by PASSWORD RESET
DEFAULT_FROM_EMAIL=ALLOWED_HOSTS[0] + "@repanier.be"
MEDIA_ROOT = os.path.join(PROJECT_DIR, "media", "public")
TEMPLATE_DIRS = (
    os.path.join(PROJECT_DIR, "templates"),
)

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/var/tmp/django_cache/' + ALLOWED_HOSTS[0],
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
            'CULL_FREQUENCY': 3
        }
    }
}

# CACHE_MIDDLEWARE_KEY_PREFIX = ALLOWED_HOSTS[0]
# CMS_CACHE_PREFIX = ALLOWED_HOSTS[0]

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

PARLER_DEFAULT_LANGUAGE_CODE = LANGUAGE_CODE

PARLER_LANGUAGES = {
    SITE_ID: (
        {'code': 'fr',},
    ),
    'default': {
        'fallback': 'fr',             # defaults to PARLER_DEFAULT_LANGUAGE_CODE
        'hide_untranslated': False,   # the default; let .active_translations() return fallbacks too.
    }
}

CMS_PLACEHOLDER_CONF = {
    'home-hero': {
        'name': gettext('Hero'),
        'plugins': ['TextPlugin',],
        # 'plugins': ['TextPlugin', 'LinkPlugin', 'StylePlugin', 'GoogleMapPlugin', 'MultiColumnPlugin', 'SnippetPlugin', 'VideoPlugin', 'CMSOembedVideoPlugin', 'TablePlugin'],
        'default_plugins':[
            {
                'plugin_type':'TextPlugin',
                'values':{
                    'body':
        '<h3>Gasath Ap&eacute;ro</h3>' + \
        '<p>Bienvenue sur le site de commande du groupe Gasath Ap&eacute;ro.</p>' + \
        '<p class="text-muted"><span class="glyphicon glyphicon-pushpin"></span>&nbsp;Veuillez utiliser ce site pour passer vos commandes.</p>' + \
        '<h3>Premi&egrave;re connexion</h3>' + \
        '<p class="text-muted">Cliquez sur &quot;Connexion&quot; en haut &agrave; droite de l&#39;&eacute;cran. Ensuite sur &quot;Mot de passe perdu ?&quot;. Respectez bien les majuscules/minuscules/espaces.</p>'

                },
            },
        ]
    },
    'home-col-1': {
        'name': gettext('Column 1'),
        'plugins': ['TextPlugin',],
        'default_plugins':[
            {
                'plugin_type':'TextPlugin',
                'values':{
                    'body':
        '<div class="panel panel-warning">' + \
        '<div class="panel-heading"><h4>Tableau des permanences</h4></div>' + \
        '<ul class="list-group">' + \
        '<li class="list-group-item">Le tableau des permanences est &agrave; pr&eacute;sent disponible &agrave; partir du menu &quot;Permanence&quot; en haut de l\'&eacute;cran, entr&eacute;e &quot;Tableau des permanences&quot;.</li>' + \
        '<li class="list-group-item">Pour vous inscrire &agrave; une permanence, s&eacute;lectionnez votre nom.</li>' + \
        '<li class="list-group-item">Pour vous d&eacute;sinscrire, d&eacute;s&eacute;lectionnez votre nom.</li>' + \
        '<li class="list-group-item">Seules sont reprises les permanences planifi&eacute;es par le/la responsable commandes.</li>' + \
        '</ul>' + \
        '</div>'

                },
            },
        ]
    },
    'home-col-2': {
        'name': gettext('Column 2'),
        'plugins': ['TextPlugin',],
        'default_plugins':[
            {
                'plugin_type':'TextPlugin',
                'values':{
                    'body':
        '<div class="panel panel-warning">' + \
        '<div class="panel-heading"><h4>Commandes</h4></div>' + \
        '<ul class="list-group">' + \
        '<li class="list-group-item">A partir du menu &quot;Permanence&quot; en haut de l\'&eacute;cran, vous s&eacute;lectionnez une permanence.</li>' + \
        '<li class="list-group-item">Si elle est ouverte, vous pouvez modifiez votre commande jusqu\'&agrave; la cl&ocirc;ture des commandes.</li>' + \
        '<li class="list-group-item">Un r&eacute;capitulatif vous perviendra par mail au moment de la cl&ocirc;ture.</li>' + \
        '<li class="list-group-item">D&egrave;s qu\'elle est ferm&eacute;e, vous ne pouvez plus modifier votre commande.</li>' + \
        '</ul>' + \
        '</div>'

                },
            },
        ]
    },
    'home-col-3': {
        'name': gettext('Column 3'),
        'plugins': ['TextPlugin',],
        # 'limits': {
        #     'global': 2,
        #     'TextPlugin': 1,
        #     'PollPlugin': 1,
        # },
        'default_plugins':[
            {
                'plugin_type':'TextPlugin',
                'values':{
                    'body':
        '<div class="panel panel-warning">' + \
        '<div class="panel-heading"><h4>Comptabilit&eacute;</h4></div>' + \
        '<ul class="list-group">' + \
        '<li class="list-group-item">Connect&eacute;, le solde de votre compte est affich&eacute; dans le menu &quot;Mon solde&quot; en haut de l\'&eacute;cran.</li>' + \
        '<li class="list-group-item">En cliquant sur votre solde vous acc&eacute;dez &agrave; l\'historique de vos achats et versements depuis le 1/1/2014.</li>' + \
        '</ul>' + \
        '</div>'

                },
            },
        ]
    },
    'subpage_content': {
        'name': gettext('Content'),
        'plugins': ['TextPlugin',],
        'default_plugins':[
            {
                'plugin_type':'TextPlugin',
                'values':{
                    'body':
        '<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed luctus tortor quis imperdiet egestas. Proin mollis sem ipsum, nec facilisis nibh cursus eu. Sed convallis cursus venenatis. Maecenas rutrum, elit ut ornare lobortis, mi dolor placerat elit, at laoreet sapien urna vitae arcu. Phasellus consectetur tincidunt ullamcorper. Sed et enim at lacus cursus rhoncus. Vestibulum porttitor velit non ante ullamcorper, ut gravida ipsum vestibulum. Aenean sed condimentum nisi. Quisque sagittis mauris non leo tincidunt vulputate. Ut euismod ante purus, sed pulvinar nisl volutpat quis. Maecenas consequat mi vitae libero egestas varius. Nam in tempor augue, sit amet pulvinar purus.</p>' + \
        '<p>Vestibulum sed elit mollis, dapibus ligula in, ultricies purus. Proin fermentum blandit ultrices. Suspendisse vitae nisi mollis, viverra ipsum vitae, adipiscing lorem. Curabitur vestibulum orci felis, nec pretium arcu elementum a. Curabitur blandit fermentum tellus at consequat. Sed eget tempor elit. Donec in elit purus.</p>' + \
        '<p>Morbi vulputate dolor sed nibh ullamcorper, eget molestie justo adipiscing. Fusce faucibus vel quam eu ultrices. Sed aliquet fringilla tristique. Vestibulum sit amet nunc tincidunt turpis tristique ullamcorper. Nam tempor mi felis, ac vulputate quam varius eget. Nunc blandit nulla vel metus lacinia, sit amet posuere lectus viverra. Praesent vel tortor facilisis, imperdiet orci sed, auctor erat.</p>'
                },
            },
        ]
    },
    'footer': {
        'name': gettext('Footer'),
        'plugins': ['TextPlugin',],
        'default_plugins':[
            {
                'plugin_type':'TextPlugin',
                'values':{
                    'body':
        'Contact : coordi@repanier.be. <span  class="hidden-xs"> | Participer : <a href="https://github.com/pcolmant/repanier">github</a></span>'

                },
            },
        ]
    },
}

REPANIER_PERMANENCE_NAME = _("Permanence")
# REPANIER_PERMANENCE_NAME = _("Closure")
REPANIER_PERMANENCES_NAME = _("Permanences")
# REPANIER_PERMANENCES_NAME = _("Closures")
REPANIER_PERMANENCE_ON_NAME = _("Permanence on ")
# REPANIER_PERMANENCE_ON_NAME = _("Closure on ")
REPANIER_SEND_ORDER_TO_BOARD = True

REPANIER_DISPLAY_PRODUCERS_ON_ORDER_FORM = True
REPANIER_BANK_ACCOUNT = "BE88 5230 8040 9641"