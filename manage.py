#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    # os.path.realpath resolves symlinks and os.path.abspath doesn't.
    project = os.path.split(os.path.realpath(os.path.dirname(__file__)))[1]
    django_settings = "{}.common_settings".format(project)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", django_settings)

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
