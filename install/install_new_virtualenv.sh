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
sudo apt-get install gettext unzip
sudo apt-get install libpq-dev python-dev python-setuptools
pip install psycopg2
# IF installing the latest stable version
# pip install django-cms
# ELSE installing the latest development version
# pip install https://github.com/divio/django-cms/archive/develop.zip
# ELSE installing a specific version
pip install https://github.com/divio/django-cms/archive/3.0.0.beta3.zip
# ENDIF
pip install djangocms-text-ckeditor
# For easy_thumbnails which need Pillow (https://github.com/python-imaging/Pillow)
sudo apt-get install libtiff4-dev libjpeg8-dev zlib1g-dev libfreetype6-dev liblcms1-dev libwebp-dev tcl8.5-dev tk8.5-dev
pip install Pillow
pip install cmsplugin-filer
pip install django-reversion
pip install django_compressor
pip install django-admin-sortable2
pip install openpyxl
sudo apt-get install libxml2-dev libxslt1-dev
pip install docx
# pip install django_debug_toolbar
# pip install django-dajaxice ! not working with Django 1.6
# pip install django-custom-user
# pip install django-registration
pip install django-crispy-forms
pip install crispy-forms-foundation
export DJANGO_SETTINGS_MODULE=
django-admin.py startproject mysite
cd ~/$1/mysite/mysite
mkdir media
mkdir collect-static
mkdir templates
# ----------------- Use compressor
cd ~/$1/mysite/mysite/collect-static
mkdir compressor
cd compressor
mkdir css
sudo chgrp www-data css
chmod g+w css
mkdir js
sudo chgrp www-data js
chmod g+w js
# ----------------- Use django cache
cd /var/tmp
mkdir django_cache
sudo chgrp www-data django_cache
chmod g+w django_cache
rm -rf /var/tmp/django_cache/*
# ----------------- Use django file session
cd /var/tmp
mkdir django_session
sudo chgrp www-data django_session
chmod g+w django_session
rm -rf /var/tmp/django_session/*
cd ~
