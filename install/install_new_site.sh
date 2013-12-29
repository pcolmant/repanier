#!/bin/bash
if [ -z "$1" ]; then
    echo "usage: $0 directory_of_the_new_virtualenv domain name of the site"
    exit
fi
cd ~
sudo -k
sudo -l
cd ~/$1/mysite/mysite/media
mkdir $2
cd $2
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
