#!/bin/bash
if [ -z "$1" ]; then
    echo "usage: $0 directory_of_the_new_virtualenv"
    exit
fi
cd ~
sudo -k
sudo -l
mkdir $1
virtualenv $1
cd $1
source bin/activate
pip install psycopg2
# IF installing the latest stable version
# pip install django-cms
# ELSE installing the latest development version
# pip install https://github.com/divio/django-cms/archive/develop.zip
# OR UPGRADE
pip install -U https://github.com/divio/django-cms/archive/develop.zip
# ELSE installing a specific version
# pip install https://github.com/divio/django-cms/archive/3.0.0.beta3.zip
# ENDIF
pip install -U djangocms-text-ckeditor
# pip install -U djangocms-link
# pip install -U djangocms-snippet
# pip install -U djangocms-style
# pip install -U djangocms-column
# pip install -U djangocms-grid
# pip install -U djangocms-oembed
# pip install -U djangocms-table
# pip install -U djangocms-googlemap
# For easy_thumbnails which need Pillow (https://github.com/python-imaging/Pillow)
pip install -U Pillow
pip install -U cmsplugin-filer
pip install -U django-reversion
pip install -U django_compressor
pip install -U django-admin-sortable2
pip install -U openpyxl
# pip install -U django-hvad
pip install -U docx
# pip install django_debug_toolbar
# pip install django-dajaxice ! not working with Django 1.6
# pip install django-custom-user
# pip install django-registration
pip install -U django-crispy-forms
pip install -U django-celery
