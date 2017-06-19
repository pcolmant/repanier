#!/bin/sh
# initialize environment for repanier development
#
# please apt-get install python3-dev

virtualenv -p python3 venv
venv/bin/pip install -r requirements/requirement.txt

# activate environment before executing django commands:
#
#   $ . venv/bin/activate
#   $ ./manage.py migrate
#   $ ./manage.py runserver
#   ...
