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
sudo apt-get install gettext
sudo apt-get install libpq-dev python-dev python-setuptools
pip install psycopg2
# IF installing the latest stable version
# pip install django-cms
# ELSE installing the latest development version
# sudo apt-get install unzip
# wget https://github.com/divio/django-cms/archive/develop.zip
# unzip develop.zip
# pip install -e django-cms-develop/
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
cd media
mkdir repanier.be
cd repanier.be
mkdir public
cd public
mkdir cms
mkdir cms_page_media
sudo chgrp www-data cms_page_media
chmod g+w cms_page_media
mkdir tmp
sudo chgrp www-data tmp
chmod g+w tmp
mkdir filer_public
sudo chgrp www-data filer_public
chmod g+w filer_public
mkdir filer_public_thumbnails
sudo chgrp www-data filer_public_thumbnails
chmod g+w filer_public_thumbnails
mkdir uploaded_pictures
sudo chgrp www-data uploaded_pictures
chmod g+w uploaded_pictures
cd ..
mkdir smedia
cd smedia
mkdir filer_private
sudo chgrp www-data filer_private
chmod g+w filer_private
mkdir filer_private_thumbnails
sudo chgrp www-data filer_private_thumbnails
chmod g+w filer_private_thumbnails
cd ..
cd ..
mkdir apero.repanier.be
cd apero.repanier.be
mkdir public
cd public
mkdir cms
mkdir cms_page_media
sudo chgrp www-data cms_page_media
chmod g+w cms_page_media
mkdir tmp
sudo chgrp www-data tmp
chmod g+w tmp
mkdir filer_public
sudo chgrp www-data filer_public
chmod g+w filer_public
mkdir filer_public_thumbnails
sudo chgrp www-data filer_public_thumbnails
chmod g+w filer_public_thumbnails
mkdir uploaded_pictures
sudo chgrp www-data uploaded_pictures
chmod g+w uploaded_pictures
cd ..
mkdir smedia
cd smedia
mkdir filer_private
sudo chgrp www-data filer_private
chmod g+w filer_private
mkdir filer_private_thumbnails
sudo chgrp www-data filer_private_thumbnails
chmod g+w filer_private_thumbnails
cd ..
cd ..
mkdir producteur.repanier.be
cd producteur.repanier.be
mkdir public
cd public
mkdir cms
mkdir cms_page_media
sudo chgrp www-data cms_page_media
chmod g+w cms_page_media
mkdir tmp
sudo chgrp www-data tmp
chmod g+w tmp
mkdir filer_public
sudo chgrp www-data filer_public
chmod g+w filer_public
mkdir filer_public_thumbnails
sudo chgrp www-data filer_public_thumbnails
chmod g+w filer_public_thumbnails
mkdir uploaded_pictures
sudo chgrp www-data uploaded_pictures
chmod g+w uploaded_pictures
cd ..
mkdir smedia
cd smedia
mkdir filer_private
sudo chgrp www-data filer_private
chmod g+w filer_private
mkdir filer_private_thumbnails
sudo chgrp www-data filer_private_thumbnails
chmod g+w filer_private_thumbnails
cd ..
cd ..
mkdir ptidej.repanier.be
cd ptidej.repanier.be
mkdir public
cd public
mkdir cms
mkdir cms_page_media
sudo chgrp www-data cms_page_media
chmod g+w cms_page_media
mkdir tmp
sudo chgrp www-data tmp
chmod g+w tmp
mkdir filer_public
sudo chgrp www-data filer_public
chmod g+w filer_public
mkdir filer_public_thumbnails
sudo chgrp www-data filer_public_thumbnails
chmod g+w filer_public_thumbnails
mkdir uploaded_pictures
sudo chgrp www-data uploaded_pictures
chmod g+w uploaded_pictures
cd ..
mkdir smedia
cd smedia
mkdir filer_private
sudo chgrp www-data filer_private
chmod g+w filer_private
mkdir filer_private_thumbnails
sudo chgrp www-data filer_private_thumbnails
chmod g+w filer_private_thumbnails
cd ..
cd ..
mkdir lepanierlensois.repanier.be
cd lepanierlensois.repanier.be
mkdir public
cd public
mkdir cms
mkdir cms_page_media
sudo chgrp www-data cms_page_media
chmod g+w cms_page_media
mkdir tmp
sudo chgrp www-data tmp
chmod g+w tmp
mkdir filer_public
sudo chgrp www-data filer_public
chmod g+w filer_public
mkdir filer_public_thumbnails
sudo chgrp www-data filer_public_thumbnails
chmod g+w filer_public_thumbnails
mkdir uploaded_pictures
sudo chgrp www-data uploaded_pictures
chmod g+w uploaded_pictures
cd ..
mkdir smedia
cd smedia
mkdir filer_private
sudo chgrp www-data filer_private
chmod g+w filer_private
mkdir filer_private_thumbnails
sudo chgrp www-data filer_private_thumbnails
chmod g+w filer_private_thumbnails
cd ..
cd ..
mkdir l_epi_dici.be
cd l_epi_dici.be
mkdir public
cd public
mkdir cms
mkdir cms_page_media
sudo chgrp www-data cms_page_media
chmod g+w cms_page_media
mkdir tmp
sudo chgrp www-data tmp
chmod g+w tmp
mkdir filer_public
sudo chgrp www-data filer_public
chmod g+w filer_public
mkdir filer_public_thumbnails
sudo chgrp www-data filer_public_thumbnails
chmod g+w filer_public_thumbnails
mkdir uploaded_pictures
sudo chgrp www-data uploaded_pictures
chmod g+w uploaded_pictures
cd ..
mkdir smedia
cd smedia
mkdir filer_private
sudo chgrp www-data filer_private
chmod g+w filer_private
mkdir filer_private_thumbnails
sudo chgrp www-data filer_private_thumbnails
chmod g+w filer_private_thumbnails
cd ..
cd ..
cd ..
mkdir collect-static
mkdir templates
cd ~/$1/mysite
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
cd ~/$1
echo "#"
echo "# To be done manually :"
echo "# ---------------------"
echo "# Copy /mysite/*_settings.py, urls.py and subfolers (templates, js, ...) to $1/mysite/mysite/*"
echo "# Copy /mysite/media/favico to $1/mysite/mysite/media/*"
echo "# Copy /mysite/template/* and subfolder to $1/mysite/mysite/template/*"
echo "# Copy /repanier/* and subfolders to $1/mysite/repanier/*"
echo "# Copy static files to be available through the webserver"
echo cd ~/$1/mysite
echo python manage.py collectstatic --settings=mysite.repanier_settings
echo "# Copy without replacing /mysite/collect-static/* and subfolder to $1/mysite/mysite/collect-static/*"
echo "# If some errors execute python manage.py collectstatic --traceback --settings=mysite.repanier_settings"
echo "# Create the DB with south"
echo "# Check DB paramters, secret_key, ... into ~/$1/mysite/mysite/production_settings.py"
echo cd ~/$1/mysite
echo python manage.py syncdb --all --settings=mysite.repanier_settings
echo python manage.py schemamigration repanier --initial --settings=mysite.repanier_settings
echo python manage.py migrate --fake --settings=mysite.repanier_settings
echo "# Check if CMS is ok"
echo cd ~/$1/mysite
echo python manage.py cms check --settings=mysite.repanier_settings
echo "# Compile translation files"
echo cd ~/$1/mysite/repanier
echo django-admin.py compilemessages 
echo cd ~/$1/mysite/mysite
echo django-admin.py compilemessages 
echo "# Initialize the DB with test content"
echo "# Copy /mysite/createdb/createdb.py and *.csv into ~/$1/mysite/"
echo cd ~/$1/mysite/
echo export DJANGO_SETTINGS_MODULE='mysite.repanier_settings'
echo python createdb.py
echo "#"
echo "# WHEN READY"
echo ln -s ~/$1 ~/production
echo "# Restart the webserver"
echo sudo /etc/init.d/nginx restart
echo sudo /etc/init.d/uwsgi stop
echo rm -rf /var/tmp/django_cache/*
echo sudo /etc/init.d/uwsgi start
