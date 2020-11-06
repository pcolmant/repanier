"""
ASGI config for project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# os.path.realpath resolves symlinks and os.path.abspath doesn't.
project = os.path.split(os.path.abspath(os.path.dirname(__file__)))[1]
django_settings = "{}.common_settings".format(project)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", django_settings)

application = get_asgi_application()
