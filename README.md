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

    git clone https://github.com/pcolmant/repanier.git

Initialisation et activation de l'environnement de développement, installation des dépendances:

    virtualenv -p python3 venv
    . venv/bin/activate
    pip install -r requirements/requirement.txt

Construction de la base de données et ajout des données factices:

    ./manage.py migrate
    ./manage.py loaddata fixtures/initial_users.yaml

Démarrage de l'application:

    ./manage.py runserver

Vous pouvez désormais accéder à l'application avec votre navigateur à l'adresse http://localhost:8000/ Pour s'authentifier comme administrateur vous pouvez utiliser: *admin* *secret*.

How to setup repanier on Debian 9
---------------------------------

Log into the terminal as "root" user

    useradd -m pi
    passwd pi
    apt-get update
    apt-get install sudo
    nano /etc/sudoers
        # User privilege specification
        root	ALL=(ALL:ALL) ALL
        pi	    ALL=(ALL:ALL) ALL
    groupadd sshusers
    usermod -a -G sshusers pi
    nano /etc/ssh/sshd_config
        PermitRootLogin no
        AllowGroups sshusers   <<--- Attention do not forget to add this line
    service sshd restart


Try to connect with a ssh client as user "pi" before closing the current session.


    sudo dpkg-reconfigure locales
            -- select>>>> fr_BE.UTF-8  and/or other following your need
    sudo apt-get install virtualenv nginx postgresql uwsgi uwsgi-plugin-python3 gettext unzip python3-dev build-essential
    sudo apt-get install python3-dev
    sudo apt-get install uwsgi-plugin-python3
    
    sudo -u postgres psql
        CREATE USER db_user PASSWORD 'db_password';
        ALTER ROLE db_user WITH CREATEDB;
        CREATE DATABASE db_name WITH TEMPLATE = template0 OWNER = db_user ENCODING = 'UTF8' LC_COLLATE = 'fr_BE.UTF-8' LC_CTYPE = 'fr_BE.UTF-8';

Create a python virtual environment whose name is 'venv'

    cd ~
    virtualenv --python=python3 venv
    cd venv
    source bin/activate

Copy from gihub/pcolmant/repanier/requirements/requirement.txt to ~/pi/venv
Then :

    pip install -r requirement.txt

Create the django project my_web_site


    django-admin.py startproject my_web_site
    # ----------------- Create django cache directory
    mkdir /var/tmp/django-cache
    sudo chgrp www-data /var/tmp/django-cache
    sudo chmod g+w /var/tmp/django-cache
    sudo rm -rf /var/tmp/django-cache/*
    # ----------------- Create django file session directory
    sudo chgrp www-data /var/tmp/django-session
    sudo chmod g+w /var/tmp/django-session
    sudo rm -rf /var/tmp/django-session/*


Set the system configuration of Repanier.


    nano ~/venv/my_web_site/my_web_site/my_web_site.ini
        [DJANGO_SETTINGS]
        DJANGO_SETTINGS_ADMIN_EMAIL=admin_email@gmail.com
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
        DJANGO_SETTINGS_ENV=dev
        DJANGO_SETTINGS_LANGUAGE=fr-en
        DJANGO_SETTINGS_LOGGING=False
        DJANGO_SETTINGS_CACHE=/var/tmp/django-cache
        DJANGO_SETTINGS_SESSION=/var/tmp/django-session
        DJANGO_SETTINGS_COUNTRY=be
        DJANGO_SETTINGS_STATIC=static
        DJANGO_SETTINGS_BOOTSTRAP_CSS=bootstrap.css
        DJANGO_SETTINGS_IS_MINIMALIST=False
        DJANGO_SETTINGS_GROUP=True
        DJANGO_SETTINGS_CONTRACT=True
        DJANGO_SETTINGS_STOCK=True
        DJANGO_SETTINGS_BOX=True
        [ALLOWED_HOSTS]
        1:repanier.local


Install Repanier

    cd ~/venv/my_web_site/my_web_site/
    mkdir media
    cd media
    mkdir public
    cd ..
    sudo chgrp -R www-data media
    sudo chmod -R g+w media
    # now : copy from gihub/pcolmant/repanier/mysite/media/... to ~/venv/my_web_site/my_web_site/media/
    #            favicon.ico
    #            robot.txt
    # now : copy from gihub/pcolmant/repanier/mysite/... to ~/venv/my_web_site/my_web_site/
    #            locale (all the directory and subdirectories content)
    #            my_web_site.ini
    #            common_settings.py
    #            urls.py
    #            wsgi.py
    # now : copy from gihub/pcolmant/repanier to ~/venv/my_web_site/
    #            manage.py
    #            repanier (all the directory and subdirectories content)


Finalize the django configuration


    python manage.py collectstatic
    python manage.py makemigrations repanier
    python manage.py migrate
    python manage.py createsuperuser
    sudo rm -rf /var/tmp/django-cache/*

Create nginx my_web_site config

    sudo nano /etc/nginx/sites-available/my_web_site
        server {
            listen 80;
            server_name repanier.local;

            access_log /var/log/nginx/my_web_site_access.log;
            error_log /var/log/nginx/my_web_site_error.log;
            client_max_body_size 3M;
            location /media/ {
                alias /home/pi/venv/my_web_site/my_web_site/media/public/;
            }

            location /static/ {
                alias /home/pi/venv/my_web_site/my_web_site/collect-static/;
            }

            location /favicon.ico {
                alias /home/pi/venv/my_web_site/my_web_site/collect-static/favicon.ico;
            }

            location /robots.txt {
                alias /home/pi/venv/my_web_site/my_web_site/collect-static/robots.txt;
            }
            location / {
                include		uwsgi_params;
                uwsgi_param HTTP_X_FORWARDED_HOST $server_name:9000;
                uwsgi_pass 	unix:///tmp/my_web_site.sock;
                uwsgi_read_timeout 600s;
                uwsgi_send_timeout 60s;
                uwsgi_connect_timeout 60s;
            }
        }

    sudo ln -s /etc/nginx/sites-available/my_web_site /etc/nginx/sites-enabled/my_web_site
    sudo rm /etc/nginx/sites-enabled/default

Create uwsgi my_web_site config

    sudo nano /etc/uwsgi/apps-available/my_web_site.ini
        [uwsgi]
        vhost = true
        plugins = python35
        socket = /tmp/my_web_site.sock
        master = true
        enable-threads = true
        processes = 1
        thread = 2
        buffer-size = 8192
        wsgi-file = /home/pi/venv/my_web_site/my_web_site/wsgi.py
        virtualenv = /home/pi/venv/
        chdir = /home/pi/venv/my_web_site/
        harakiri = 360
    sudo ln -s /etc/uwsgi/apps-available/my_web_site.ini /etc/uwsgi/apps-enabled/my_web_site.ini

Start Repanier

    sudo /etc/init.d/uwsgi restart
    sudo /etc/init.d/nginx restart
