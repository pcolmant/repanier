#!/bin/bash
if [ -z "$1" ]; then
    echo "usage: $0 directory_of_the_new_virtualenv"
    exit
fi
A_install_new_virtualenv $1
B_install_new_site $1 repanier
B_install_new_site $1 ptidej
B_install_new_site $1 apero
B_install_new_site $1 lelensois 
B_install_new_site $1 lebio
B_install_new_site $1 claude
cd ~/$1
echo "#"
echo "# To be done manually :"
echo "# ---------------------"
echo "# Copy /mysite/* and subfolers to $1/mysite/mysite/*"
echo "# Copy /repanier/* and subfolders to $1/mysite/repanier/*"
echo cd ~/$1/mysite
echo python manage.py collectstatic --settings=mysite.repanier_settings
echo python manage.py syncdb --all --settings=mysite.repanier_settings
echo python manage.py schemamigration repanier --initial --settings=mysite.repanier_settings
echo python manage.py migrate --fake --settings=mysite.repanier_settings
echo "# Check if CMS is ok"
echo python manage.py cms check --settings=mysite.repanier_settings
echo "# Compile translation files"
echo "export DJANGO_SETTINGS_MODULE="
echo cd ~/$1/mysite/repanier
echo django-admin.py compilemessages 
echo cd ~/$1/mysite/mysite
echo django-admin.py compilemessages 
echo export DJANGO_SETTINGS_MODULE='mysite.repanier_settings'
echo "# Initialize the DB with test content"
echo "# Copy /mysite/createdb/createdb.py and *.csv into ~/$1/mysite/"
echo cd ~/$1/mysite/
echo python createdb.py
echo "#"
echo "# WHEN READY"
echo "# Restart the webserver"
echo sudo /etc/init.d/nginx restart
echo sudo /etc/init.d/uwsgi stop
echo rm -rf /var/tmp/django_cache/*
echo sudo /etc/init.d/uwsgi start
