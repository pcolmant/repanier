#!/usr/bin/env python
import os
import sys


if __name__ == "__main__":

    os_environ = "DJANGO_SETTINGS_MODULE"
    project = os.path.split(os.path.abspath(os.path.dirname(__file__)))[-1]
    # Settings are set according to directory name
    # Assume developement environment by default
    if project == 'repanier':
        project = 'mysite'
    django_settings = "%s.common_settings" % project
    os.environ.setdefault(os_environ, django_settings)
    if os.environ.get(os_environ) != django_settings:
        os.environ.pop(os_environ)
        os.environ.setdefault(os_environ, django_settings)

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
