Repanier
========

Collective buying group management web site using Django CMS 3.4.5 / Bootstrap 3 / Python 3.5.

- https://repanier.be/fr/documentation/survol/
- https://repanier.be/fr/
- access to https://demo.repanier.be/fr/ on demand

Active customers groups :

- https://apero.repanier.be/fr/
- https://commande.coopeco-supermarche.be/fr/
- https://commandes.gac-hamois.be/fr/
- https://exceptionnel.repanier.be/fr/
- https://gacmonssud.repanier.be/fr/
- https://lepanierlensois.repanier.be/fr/
- https://niveze.repanier.be/fr/
- https://pigal.repanier.be/
- https://ptidej.repanier.be/fr/

Active producer :

- https://commande.lebuisson.be/fr/

Licence : GPL v3

Howto contribute to Repanier ?
------------------------------

  * En participant aux discussions entre utilisateurs et avec les développeur, lors des permanences, par téléphone ou par email, …
  * [En utilisant les tickets](https://github.com/pcolmant/repanier/issues)
  * [En envoyant un patch ou une demande de merge](https://guides.github.com/introduction/flow/)

Comment tester Repanier?
------------------------

Afin de pouvoir travailler en local sur Repanier, nous allons télécharger l'application et ses dépendances:

Clone du projet:

```commandline
git clone https://github.com/pcolmant/repanier.git
```

Initialisation et activation de l'environnement de développement, installation des dépendances:

```commandline
virtualenv -p python3 venv
. venv/bin/activate
pip install -r requirements/requirement.txt
```

Construction de la base de données et ajout des données factices:

```commandline
./manage.py migrate
./manage.py loaddata fixtures/initial_users.yaml
```

Démarrage de l'application:

```commandline
./manage.py runserver
```

Vous pouvez désormais accéder à l'application avec votre navigateur à l'adresse http://localhost:8000/ Pour s'authentifier comme administrateur vous pouvez utiliser: *admin* *secret*.

How to setup repanier on Debian 9
---------------------------------

~ As Root (or with sudo) ~

 * Be sure to have the right locales set
 
 ```commandline
dpkg-reconfigure locales
        -- select>>>> fr_BE.UTF-8  and/or other following your need
```

 * Packages to install

```commandline
apt-get install virtualenv nginx postgresql uwsgi uwsgi-plugin-python3 gettext unzip python3-dev build-essential python3-dev uwsgi-plugin-python3 git sudo
```

 * Create a postgresql database

```commandline
	sudo -u postgres psql
```
```postgresql
CREATE USER db_user PASSWORD 'db_password';
ALTER ROLE db_user WITH CREATEDB;
CREATE DATABASE db_name WITH TEMPLATE = template0 OWNER = db_user ENCODING = 'UTF8' LC_COLLATE = 'fr_BE.UTF-8' LC_CTYPE = 'fr_BE.UTF-8';
(\q to leave postgresql)
```

 * Create an user that will host the application (or use one you've already have, but avoid root for security purpose)

```commandline
useradd -m -s /bin/bash repanier
passwd repanier

# Add the user to the sudo group
usermod -G sudo -a repanier
```

 * Create cache and session directories used as temporary cache by the repanier django configuration.
	By the way, Django offers other cache and session management possibilities.

```commandline
# ----------------- Create django cache directory
mkdir /var/tmp/django-cache
chgrp repanier /var/tmp/django-cache
chmod g+w /var/tmp/django-cache
# ----------------- Create django file session directory
mkdir /var/tmp/django-session
chgrp repanier /var/tmp/django-session
chmod g+w /var/tmp/django-session
```

~ As user repanier ~
(connect as repanier or type 'sudo su - repanier')

 * Create a python virtual environment (called 'venv' here. Choose whatever you want, but be carefull to change to what you choose everywhere in this tuto)

```commandline
cd ~
virtualenv --python=python3 venv
cd venv
source bin/activate
```

 * Git clone the project into the home folder of the user repanier

```commandline
cd ~
git clone https://github.com/pcolmant/repanier.git
```

 * Install the requirements in the virtual env

```commandline
cd venv
pip install -r ~/repanier/requirement/requirement.txt
```

 * Create the django project (my_repanier in this tuto. Be carefull to change everywhere this varialbe if you choose another one)
	Also, do not use "repanier" as project name because it's reserved for the application.

```commandline
django-admin.py startproject my_repanier
```

 * Create the system configuration file for Repanier.

```commandline
nano ~/venv/my_repanier/my_repanier/my_repanier.ini
```
    [DJANGO_SETTINGS]
    DJANGO_SETTINGS_ADMIN_EMAIL=admin_email@mail.org
    DJANGO_SETTINGS_ADMIN_NAME=repanier
    DJANGO_SETTINGS_DATABASE_ENGINE=django.db.backends.postgresql_psycopg2
    DJANGO_SETTINGS_DATABASE_NAME=db_name
    DJANGO_SETTINGS_DATABASE_USER=db_user
    DJANGO_SETTINGS_DATABASE_PASSWORD=db_password
    DJANGO_SETTINGS_DATABASE_HOST=127.0.0.1
    DJANGO_SETTINGS_DATABASE_PORT=5432
    DJANGO_SETTINGS_DEBUG=True
    DJANGO_SETTINGS_DEMO=False
    DJANGO_SETTINGS_EMAIL_HOST=email_host
    DJANGO_SETTINGS_EMAIL_HOST_PASSWORD=email_host_password
    DJANGO_SETTINGS_EMAIL_HOST_USER=email_host_user
    DJANGO_SETTINGS_EMAIL_PORT=email_port
    DJANGO_SETTINGS_EMAIL_USE_TLS=True
    DJANGO_SETTINGS_LANGUAGE=fr-en
    DJANGO_SETTINGS_LOGGING=False
    DJANGO_SETTINGS_CACHE=/var/tmp/django-cache
    DJANGO_SETTINGS_SESSION=/var/tmp/django-session
    DJANGO_SETTINGS_COUNTRY=be
    DJANGO_SETTINGS_BOOTSTRAP_CSS=bootstrap.css
    DJANGO_SETTINGS_IS_MINIMALIST=False
    DJANGO_SETTINGS_GROUP=True
    DJANGO_SETTINGS_CONTRACT=True
    DJANGO_SETTINGS_STOCK=True
    DJANGO_SETTINGS_BOX=True
    DJANGO_SETTINGS_TEST_MODE=False
    [ALLOWED_HOSTS]
    1:repanier.myhost

 * Install & Configure Repanier

```commandline
cd ~/venv/gazewee/gazewee/
mkdir media/public -p
sudo chgrp -R www-data media
sudo chmod -R g+w media
cp ~/repanier_git/repanier/static/robots.txt ~/venv/gazewee/gazewee/media/
cp ~/repanier_git/repanier/static/favicon.ico ~/venv/gazewee/gazewee/media/
cp ~/repanier_git/mysite/common_settings.py ~/venv/gazewee/gazewee/
cp ~/repanier_git/mysite/urls.py ~/venv/gazewee/gazewee/
cp ~/repanier_git/mysite/wsgi.py ~/venv/gazewee/gazewee/
cp -R ~/repanier_git/repanier/locale/ ~/venv/gazewee/gazewee/
cp ~/repanier_git/manage.py ~/venv/gazewee/
cp -R ~/repanier_git/repanier/ ~/venv/gazewee/
```

 * Finalize the django configuration

```commandline
cd ~/venv/my_repanier
python manage.py collectstatic
python manage.py makemigrations repanier
python manage.py migrate
python manage.py createsuperuser
sudo rm -rf /var/tmp/django-cache/*
```

~ As Root (or with sudo) ~

 * Create nginx my_repanier vHost

```commandline
nano /etc/nginx/sites-available/my_repanier
```
    server {
        listen 80;
        listen [::]:80;

        server_name repanier.host;

        access_log /var/log/nginx/my_repanier_access.log;
        error_log /var/log/nginx/my_repanier_error.log;

        client_max_body_size 3M;

        location /media/ {
            alias /home/repanier/venv/my_repanier/my_repanier/media/public/;
        }

        location /static/ {
            alias /home/repanier/venv/my_repanier/my_repanier/collect-static/;
        }

        location /favicon.ico {
            alias /home/repanier/venv/my_repanier/my_repanier/collect-static/favicon.ico;
        }

        location /robots.txt {
            alias /home/repanier/venv/my_repanier/my_repanier/collect-static/robots.txt;
        }

        location / {
            include		uwsgi_params;
            uwsgi_param HTTP_X_FORWARDED_HOST $server_name;
            uwsgi_pass 	unix:///tmp/my_repanier.sock;
            uwsgi_read_timeout 600s;
            uwsgi_send_timeout 60s;
            uwsgi_connect_timeout 60s;
        }
    }
```commandline
ln -s /etc/nginx/sites-available/my_repanier /etc/nginx/sites-enabled/my_repanier
service nginx restart
```

 * Create uwsgi my_repanier config

```commandline
nano /etc/uwsgi/apps-available/my_repanier.ini
```
    [uwsgi]
    vhost = true
    plugins = python35
    socket = /tmp/my_repanier.sock
    master = true
    enable-threads = true
    processes = 1
    thread = 2
    buffer-size = 8192
    wsgi-file = /home/repanier/venv/my_repanier/my_repanier/wsgi.py
    virtualenv = /home/repanier/venv/
    chdir = /home/repanier/venv/my_repanier/
    harakiri = 360

```commandline
ln -s /etc/uwsgi/apps-available/my_repanier.ini /etc/uwsgi/apps-enabled/my_repanier.ini
service uwsgi restart
```


How to add more repanier instances
----------------------------------

~ As user repanier ~
(connect as repanier or type 'sudo su - repanier')

 * Create the database (using the same user as for the first repanier)

```commandline
	sudo -u postgres psql
```

```postgresql
		CREATE DATABASE my_repanier2 WITH TEMPLATE = template0 OWNER = db_user ENCODING = 'UTF8' LC_COLLATE = 'fr_BE.UTF-8' LC_CTYPE = 'fr_BE.UTF-8';
		\q  (to quit)
```

* Re-enter the python virtual environment if need be (ig you don't have the "(venv)" on the left of the shell command line)

```commandline
cd ~/venv
source bin/activate
```

 * Create the django project (my_repanier2)

```commandline
	cd ~/venv
	django-admin.py startproject my_repanier2
```

 * Create the system configuration file for Repanier.

```commandline
	nano ~/venv/my_repanier2/my_repanier2/my_repanier2.ini
```
	
    [DJANGO_SETTINGS]
    DJANGO_SETTINGS_ADMIN_EMAIL=admin_email@mail.org
    DJANGO_SETTINGS_ADMIN_NAME=repanier
    DJANGO_SETTINGS_DATABASE_ENGINE=django.db.backends.postgresql_psycopg2
    DJANGO_SETTINGS_DATABASE_NAME=my_repanier2
    DJANGO_SETTINGS_DATABASE_USER=db_user
    DJANGO_SETTINGS_DATABASE_PASSWORD=db_password
    DJANGO_SETTINGS_DATABASE_HOST=127.0.0.1
    DJANGO_SETTINGS_DATABASE_PORT=5432
    DJANGO_SETTINGS_DEBUG=False
    DJANGO_SETTINGS_DEMO=False
    DJANGO_SETTINGS_EMAIL_HOST=email_host
    DJANGO_SETTINGS_EMAIL_HOST_PASSWORD=email_host_password
    DJANGO_SETTINGS_EMAIL_HOST_USER=email_host_user
    DJANGO_SETTINGS_EMAIL_PORT=email_port
    DJANGO_SETTINGS_EMAIL_USE_TLS=True
    DJANGO_SETTINGS_LANGUAGE=fr-nl-en
    DJANGO_SETTINGS_LOGGING=False
    DJANGO_SETTINGS_CACHE=/var/tmp/django-cache
    DJANGO_SETTINGS_SESSION=/var/tmp/django-session
    DJANGO_SETTINGS_COUNTRY=be
    DJANGO_SETTINGS_BOOTSTRAP_CSS=bootstrap.css
    DJANGO_SETTINGS_IS_MINIMALIST=False
    DJANGO_SETTINGS_GROUP=True
    DJANGO_SETTINGS_CONTRACT=True
    DJANGO_SETTINGS_STOCK=True
    DJANGO_SETTINGS_BOX=True
    DJANGO_SETTINGS_TEST_MODE=False
    [ALLOWED_HOSTS]
    1:repanier2.myhost

 * Install & Configure Repanier

```commandline
cd ~/venv/my_repanier2/my_repanier2
mkdir media/public -p
sudo chgrp -R www-data media
sudo chmod -R g+w media
cp ~/repanier_git/repanier/static/robots.txt ~/venv/my_repanier2/my_repanier2/media/
cp ~/repanier_git/repanier/static/favicon.ico ~/venv/my_repanier2/my_repanier2/media/
cp ~/repanier_git/mysite/common_settings.py ~/venv/my_repanier2/my_repanier2/
cp ~/repanier_git/mysite/urls.py ~/venv/my_repanier2/my_repanier2/
cp ~/repanier_git/mysite/wsgi.py ~/venv/my_repanier2/my_repanier2/
cp -R ~/repanier_git/repanier/locale/ ~/venv/my_repanier2/my_repanier2/
cp ~/repanier_git/manage.py ~/venv/my_repanier2/
cp -R ~/repanier_git/repanier/ ~/venv/my_repanier2/
```

 * Finalize the django configuration

```commandline
cd ~/venv/my_repanier2
python manage.py collectstatic
python manage.py makemigrations repanier
python manage.py migrate
python manage.py createsuperuser
sudo rm -rf /var/tmp/django-cache/*
```

~ As Root (or with sudo) ~

 * Create nginx my_repanier2 vHost

```commandline
nano /etc/nginx/sites-available/my_repanier2
```
    server {
        listen 80;
        listen [::]:80;
    
        server_name repanier2.host;
    
        access_log /var/log/nginx/my_repanier2_access.log;
        error_log /var/log/nginx/my_repanier2_error.log;
    
        client_max_body_size 3M;
    
        location /media/ {
            alias /home/repanier/venv/my_repanier2/my_repanier2/media/public/;
        }
    
        location /static/ {
            alias /home/repanier/venv/my_repanier2/my_repanier2/collect-static/;
        }
    
        location /favicon.ico {
            alias /home/repanier/venv/my_repanier2/my_repanier2/collect-static/favicon.ico;
        }
    
        location /robots.txt {
            alias /home/repanier/venv/my_repanier2/my_repanier2/collect-static/robots.txt;
        }
        location / {
            include		uwsgi_params;
            uwsgi_param HTTP_X_FORWARDED_HOST $server_name;
            uwsgi_pass 	unix:///tmp/my_repanier2.sock;
            uwsgi_read_timeout 600s;
            uwsgi_send_timeout 60s;
            uwsgi_connect_timeout 60s;
        }
    }
```commandline
	ln -s /etc/nginx/sites-available/my_repanier2 /etc/nginx/sites-enabled/my_repanier2
	service nginx reload
```

 * Create uwsgi my_repanier2 config

```commandline
nano /etc/uwsgi/apps-available/my_repanier2.ini
```
    [uwsgi]
    vhost = true
    plugins = python35
    socket = /tmp/my_repanier2.sock
    master = true
    enable-threads = true
    processes = 1
    thread = 2
    buffer-size = 8192
    wsgi-file = /home/repanier/venv/my_repanier2/my_repanier2/wsgi.py
    virtualenv = /home/repanier/venv/
    chdir = /home/repanier/venv/my_repanier2/
    harakiri = 360
```commandline
ln -s /etc/uwsgi/apps-available/my_repanier2.ini /etc/uwsgi/apps-enabled/my_repanier2.ini
service uwsgi restart
```


How to use https (with letsencrypt)
-----------------------------------

~ As Root (or with sudo) ~

 * Install the certbot package

```commandline
	apt install certbot
```

 * Create Dhparams

```commandline
	mkdir /etc/nginx/ssl
	/usr/bin/openssl dhparam -out /etc/nginx/ssl/dhparam.pem 2048
```

 * Edit vhost my_repanier

```commandline
	nano /etc/nginx/sites-available/my_repanier
```
    server {
        listen 80;
        listen [::]:80;

        server_name repanier.host;

        access_log /var/log/nginx/my_repanier_access.log;
        error_log /var/log/nginx/my_repanier_error.log;

        client_max_body_size 3M;

        # Let's Encrypt certificates with Acmetool
        location ^~ /.well-known/acme-challenge/ {
            root   /var/www/html/;
            allow all;
            default_type "text/plain";
            try_files $uri /dev/null =404;
        }

        location /media/ {
            alias /home/repanier/venv/my_repanier/my_repanier/media/public/;
        }

        location /static/ {
            alias /home/repanier/venv/my_repanier/my_repanier/collect-static/;
        }

        location /favicon.ico {
            alias /home/repanier/venv/my_repanier/my_repanier/collect-static/favicon.ico;
        }

        location /robots.txt {
            alias /home/repanier/venv/my_repanier/my_repanier/collect-static/robots.txt;
        }
        location / {
            include	 uwsgi_params;
            uwsgi_param HTTP_X_FORWARDED_HOST $server_name;
            uwsgi_pass  unix:///tmp/my_repanier.sock;
            uwsgi_read_timeout 600s;
            uwsgi_send_timeout 60s;
            uwsgi_connect_timeout 60s;
        }
    }
```commandline
service nginx reload
```

 * Create the certificate

```commandline
	certbot certonly --webroot -m admin_email@mail.org -t --agree-tos  -w /var/www/html/ -d repanier.host
```

 * Edit vhost my_repanier
	(check here: https://mozilla.github.io/server-side-tls/ssl-config-generator/ to help youfind the ciphers that suit best your situation)

```commandline
nano /etc/nginx/sites-available/my_repanier
```
    server {
        listen 80;
        listen [::]:80;

        server_name repanier.host;

        # Let's Encrypt certificates with Acmetool
        location ^~ /.well-known/acme-challenge/ {
            root   /var/www/html/;
            allow all;
            default_type "text/plain";
            try_files $uri /dev/null =404;
        }

        location / {
            return     301 https://$host$request_uri;
        }
    }

    server {
        listen 443 ssl http2;
        listen [::]:443 ssl http2;

        server_name repanier.host;

        client_max_body_size 3M;

        ssl on;
        ssl_ciphers 'EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH';

        ssl_protocols              TLSv1 TLSv1.1 TLSv1.2;
        ssl_prefer_server_ciphers on;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 1h;
        ssl_dhparam /etc/nginx/ssl/dhparam.pem;

        ssl_stapling on;
        ssl_stapling_verify on;
        resolver 8.8.8.8 8.8.4.4 valid=300s;
        resolver_timeout 5s;

        ssl_certificate /etc/letsencrypt/live/repanier.host/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/repanier.host/privkey.pem;

        location /media/ {
            alias /home/repanier/venv/my_repanier/my_repanier/media/public/;
        }

        location /static/ {
            alias /home/repanier/venv/my_repanier/my_repanier/collect-static/;
        }

        location /favicon.ico {
            alias /home/repanier/venv/my_repanier/my_repanier/collect-static/favicon.ico;
        }

        location /robots.txt {
            alias /home/repanier/venv/my_repanier/my_repanier/collect-static/robots.txt;
        }

        location / {
            include     uwsgi_params;
            uwsgi_param HTTP_X_FORWARDED_HOST $server_name;
            uwsgi_pass  unix:///tmp/my_repanier.sock;
            uwsgi_read_timeout 600s;
            uwsgi_send_timeout 60s;
            uwsgi_connect_timeout 60s;
        }

        access_log /var/log/nginx/access.log;
        error_log /var/log/nginx/error.log;
    }

```commandline
service nginx reload
```

How to update repanir instances
-------------------------------

Je n'ai pas encore eu la possibilité de mettre à jour et donc de tester la procédure
Check pour voir si ça te semble correct.

```commandline
(cd ~/repanier_git && git pull)
cd ~/venv/my_repanier
rm -R ~/venv/my_repanier/repanier
cp -R ~/repanier_git/repanier/ ~/venv/my_repanier/

rm -R ~/venv/my_repanier/my_repanier/collect-static/
sudo rm -rf /var/tmp/django-cache/*
python manage.py collectstatic
python manage.py makemigrations repanier
python manage.py migrate
sudo rm -rf /var/tmp/django-cache/*

service uwsgi reload
```

How to change superuser passord
-------------------------------

Celui qui est créé va la commande 'python manage.py createsuperuser'. 
Y a pas moyen de changer son mdp via l'interface web

How to debug
------------
```commandline
nano ~/venv/my_repanier/my_repanier/my_repanier.ini
```

    DJANGO_SETTINGS_DEBUG=True
    DJANGO_SETTINGS_LOGGING=True

```commandline
rm -R ~/venv/my_repanier/my_repanier/collect-static/
sudo rm -rf /var/tmp/django-cache/*
python manage.py collectstatic
python manage.py makemigrations repanier
python manage.py migrate
sudo rm -rf /var/tmp/django-cache/*

service uwsgi reload
```
(check log files in /var/log/uwsgi/app/)

