"""
WSGI config for project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# os.path.realpath resolves symlinks and os.path.abspath doesn't.
project = os.path.split(os.path.abspath(os.path.dirname(__file__)))[1]
django_settings = "{}.common_settings".format(project)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", django_settings)

application = get_wsgi_application()
