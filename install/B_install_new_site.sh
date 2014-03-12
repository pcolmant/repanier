#!/bin/bash
if [ -z "$1" ]; then
    echo "usage: $0 directory_of_the_new_virtualenv name_of_the_site"
    exit
fi
cd ~
sudo -k
sudo -l
cd $1
source bin/activate
export DJANGO_SETTINGS_MODULE=
django-admin.py startproject $2
cd ~/$1/$2/$2
mkdir media
mkdir collect-static
mkdir templates
# ----------------- Use compressor
cd ~/$1/$2/$2/collect-static
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
# ----------------- Config site folders
cd ~/$1/$2/$2/media
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
cd ~
