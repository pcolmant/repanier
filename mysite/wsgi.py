import os

from django.core.wsgi import get_wsgi_application

# os.path.realpath resolves symlinks and os.path.abspath doesn't.
project = os.path.split(os.path.realpath(os.path.dirname(__file__)))[1]
django_settings = "{}.common_settings".format(project)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", django_settings)

application = get_wsgi_application()
