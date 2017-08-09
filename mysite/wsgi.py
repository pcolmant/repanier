"""
WSGI config for project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/howto/deployment/wsgi/
"""

import os

os_environ = "DJANGO_SETTINGS_MODULE"
project = os.path.split(os.path.abspath(os.path.dirname(__file__)))[-1]
django_settings = "%s.common_settings" % project
os.environ.setdefault(os_environ, django_settings)
if os.environ.get(os_environ) != django_settings:
    os.environ.pop(os_environ)
    os.environ.setdefault(os_environ, django_settings)

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
