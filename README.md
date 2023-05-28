Repanier
========

`Repanier` is a web tool for short circuit food supply using Django CMS 3.7 / Bootstrap 3 / Python 3.5.

- https://repanier.be/fr/documentation/survol/
- https://repanier.be/fr/
- access to https://demo.repanier.be/fr/ on demand

Active customers groups :

- https://apero.repanier.be/fr/
- https://commande.coopeco-supermarche.be/fr/
- https://exceptionnel.repanier.be/fr/
- https://lepanierlensois.repanier.be/fr/
- https://peupliedotrange.repanier.be/
- https://pigal.repanier.be/
- https://ptidej.repanier.be/fr/
- https://silly-bag.be/fr/

Active producer :

- https://commande.lebuisson.be/fr/

Licence : GPL v3

# How to setup `Repanier` on Debian 10

This procedure shows you step by step how to install `Repanier` on a server.
By applying it, you have all the elements to update a `Repanier` website with a new version of `Repanier`.
And even to install several `Repanier` websites on a server.

## Linux prerequisites to run only once

These prerequisites enhance the security of your server and configure it with the minimum libraries required for the installation of `Repanier`. 
If you use a different distribution than Debian 9, take a look at [cookiecutter-django](https://github.com/pydanny/cookiecutter-django/tree/master/%7B%7Bcookiecutter.project_slug%7D%7D/utility).
If you want to install `Repanier` on a container, a good starting point is [Today I Learned – A Brief Intro to Docker for Djangonauts](https://www.revsys.com/tidbits/brief-intro-docker-djangonauts/)

1. Log in as `root` using a ssh session.
2. Update Linux and install `sudo`.
    ```commandline
    apt-get update
    apt-get upgrade -y
    apt-get install -y sudo
    ```
3. Remove `apache` if enabled because we will use `nginx` and not `apache` to listen to port 80 and 443.
    ```commandline
    service apache2 stop
    apt-get purge apache2 apache2-utils
    sudo apt-get autoremove
    ```
4. Be sure to have the right locales set. **This will be used to create the PostgreSQL data base**.
    ```commandline
    dpkg-reconfigure locales    <<--- select>>>> fr_BE.UTF-8  and/or other following your need. E.g fr_CH.UTF-8
    ```
5. Create a new user whose name is `repanier` (or whatever else). It will be used to install the `Repanier` (avoid `root` for security purpose). Let it be sudoers and a sshuser.
    ```commandline
    useradd -m -s /bin/bash repanier
    passwd repanier             <<--- must be a complex password
    usermod -G sudo -a repanier
    groupadd sshusers
    usermod -G sshusers -a repanier
    nano /etc/ssh/sshd_config
    ```
        #Port 22                <<--- should be uncommented and changed
        Protocol 2
        PermitRootLogin no      <<--- uncomment and set to no
        AllowGroups sshusers    <<--- new line to add
6. Do not close *this current* SSH session.
    ```commandline
    service ssh restart
    ```
7. On a new SSH session, log you in with user `repanier`. Reminder : Use the correct ssh port. Then test.
    ```commandline
    sudo -l
    ```
8. If you encounter ***no issue*** to execute the *`sudo -l`*, then close all active ssh sessions.
9. On a new SSH session, log you in with user `repanier`. Then install needed linux packages.
    ```commandline
    sudo apt-get install build-essential wget gettext unzip git virtualenv postgresql nginx uwsgi uwsgi-plugin-python3
    sudo rm /etc/nginx/sites-enabled/default
    ```
10. Reboot to apply changes on all active processes.
    ```commandline
    sudo reboot
    ```

## From now on, I guess you're still logged in as user `repanier`

1. On a new SSH session, log you in with user `repanier`.

## Create Django cache and session directories
Each `Repanier` website will be (later) configured to use it's own cache and file session subdirectory under both main directories we create now.
For the impatient, this configuration will be made in [common_settings.py](https://raw.githubusercontent.com/pcolmant/repanier/master/mysite/common_settings.py) : `DJANGO_SETTINGS_CACHE` and `DJANGO_SETTINGS_SESSION`
1. Create Django cache directory and give acces to it at the group `www-data`. This group is used by the web server `nginx`.
    ```commandline
    mkdir /var/tmp/django-cache
    sudo chgrp www-data /var/tmp/django-cache
    chmod g+w /var/tmp/django-cache
    ```
2. Create Django file session directory and give acces to it at the group `www-data`.
    ```commandline
    mkdir /var/tmp/django-session
    sudo chgrp www-data /var/tmp/django-session
    chmod g+w /var/tmp/django-session
    ```
## Set up a Python virtualenv
A virtualenv let you isolate all the [pypi librairies](https://pypi.python.org/pypi) for a specific project.
One virtualenv can contains many `Repanier` websites, using such all the same version of the pypi librairies.
You will need to setup a new virtualenv at least at each security update of a package present in [requirement.txt](https://github.com/pcolmant/repanier/blob/master/requirements/requirement.txt)
And then create (or migrate) `Repanier` websites.

2. Create a python virtual environment called `prd1` here. Choose whatever you want, but carefully change it to what you choose everywhere in this tutorial.
    ```commandline
    cd ~
    python -m venv prd1
    # virtualenv --python=python3 prd1
     ```
3. Goto the virtualenv and activate it
    ```commandline
    cd ~/prd1
    source bin/activate
    ```
4. Install the pypi librairies versions required by `Repanier`
    ```commandline
    wget https://raw.githubusercontent.com/pcolmant/repanier/master/requirements/requirement.txt
    pip install -r requirement.txt
    ```

## Create a Django empty project with a PostgreSQL data base
We assume here :
* that the virtualenv is named `prd1`
* that the `Repanier` website will be named `_0_prd_example`

A recommended naming convention for a Django `Repanier` website is _counter_environment_name :
* `counter` : 0..9,a..z
* `environment` : `prd`, `dev`, ... The environment should match the virtualenv naming. For e.g. `prd` for virtualenv `prd1`.
* `name` : only made of lower cases.

1. Create a postgresql database
    * `db_user` is `_0_prd_example`. Choose whatever you want, but carefully change it to what you choose everywhere in this tutorial.
    * `db_password` is not the `repanier` user password. It's a new password you set to connect the user to the Db.
    * `db_name` is `_0_prd_example`. So, the same name as the `Repanier` website. This is not mandatory, but will ease the management.
    ```commandline
    sudo -u postgres psql
    ```
    ```postgresql
    CREATE USER _0_prd_example PASSWORD 'db_password';
    ALTER ROLE _0_prd_example WITH CREATEDB;
    CREATE DATABASE _0_prd_example WITH TEMPLATE = template0 OWNER = _0_prd_example ENCODING = 'UTF8' LC_COLLATE = 'fr_BE.UTF-8' LC_CTYPE = 'fr_BE.UTF-8';
    \q  <---- to leave postgresql
    ```
    I have not investigated why but `user`, `role` and `owner` must be set to the same value. 
2. Goto the virtualenv and activate it
    ```commandline
    cd ~/prd1
    source bin/activate
    ```
3. Create an empty django website
    ```commandline
    django-admin.py startproject _0_prd_example
    ```
4. Create the media directory and give it correct read/write acces rights for the webserver. For the impatient, this setting come from [common_settings.py](https://raw.githubusercontent.com/pcolmant/repanier/master/mysite/common_settings.py) : `MEDIA_ROOT`
    ```commandline
    cd ~/prd1/_0_prd_example/_0_prd_example/
    mkdir media/public -p
    sudo chgrp -R www-data media
    sudo chmod -R g+w media
    ```
    
## Configure nginx to answer to `example.com` dns name

Create self-signed certificates for SSL (only necessary for local networks)
```commandline
sudo mkdir /etc/nginx/ssl-certs/
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/nginx/ssl-certs/example.key -out /etc/nginx/ssl-certs/example.crt
    Country Name (2 letter code) [AU]:BE
    State or Province Name (full name) [Some-State]:Belgium
    Locality Name (eg, city) []:Ath
    Organization Name (eg, company) [Internet Widgits Pty Ltd]:Repanier
    Organizational Unit Name (eg, section) []:
    Common Name (e.g. server FQDN or YOUR name) []:example.com
    Email Address []:
```
Edit the nginx configuration file
```commandline
sudo nano /etc/nginx/nginx.conf
```
    ...
    user www-data;
    ...
    http {
        ...
        send_timeout                300s;
        proxy_connect_timeout       60s;
        proxy_send_timeout          60s;
        proxy_read_timeout          610s;
        ...
    }
```commandline
sudo nano /etc/nginx/sites-available/_0_prd_example
```
    server {
        listen 443;
        listen [::]:443;

        server_name example.com;

        # begin of ssl config for self-signed certificates
        ssl_certificate /etc/nginx/ssl-certs/example.crt;
        ssl_trusted_certificate /etc/nginx/ssl-certs/example.crt;
        ssl_certificate_key /etc/nginx/ssl-certs/example.key;
        # end of ssl config for self-signed certificates

        access_log /var/log/nginx/_0_prd_example_access.log;
        error_log /var/log/nginx/_0_prd_example_error.log;

        client_max_body_size 3M;

        location /media/ {
            alias /home/repanier/prd1/_0_prd_example/_0_prd_example/media/public/;
        }

        location /static/ {
            alias /home/repanier/prd1/_0_prd_example/_0_prd_example/collect-static/;
        }

        location /favicon.ico {
            alias /home/repanier/prd1/_0_prd_example/_0_prd_example/media/favicon.ico;
        }

        location /robots.txt {
            alias /home/repanier/prd1/_0_prd_example/_0_prd_example/media/robots.txt;
        }

        location / {
            include                 uwsgi_params;
            uwsgi_param             HTTP_X_FORWARDED_HOST $server_name;
            # With NAT on virtualbox, if you NAT local port 8080 to 80 on virtual server 
            #     replace HTTP_X_FORWARDED_HOST $server_name;
            #     with HTTP_X_FORWARDED_HOST $server_name:8080;
            uwsgi_pass              unix:///tmp/_0_prd_example.sock;
            uwsgi_read_timeout      600s;
            uwsgi_send_timeout      60s;
            uwsgi_connect_timeout   60s;
        }
    }
```commandline
sudo ln -s /etc/nginx/sites-available/_0_prd_example /etc/nginx/sites-enabled/_0_prd_example
```

## Configure uwsgi

```commandline
sudo nano /etc/uwsgi/apps-available/_0_prd_example.ini
```
    [uwsgi]
    vhost = true
    plugins = python3
    socket = /tmp/_0_prd_example.sock
    master = true
    enable-threads = true
    processes = 1
    thread = 2
    buffer-size = 8192
    wsgi-file = /home/repanier/prd1/_0_prd_example/_0_prd_example/wsgi.py
    virtualenv = /home/repanier/prd1/
    chdir = /home/repanier/prd1/_0_prd_example/
    harakiri = 360
```commandline
sudo ln -s /etc/uwsgi/apps-available/_0_prd_example.ini /etc/uwsgi/apps-enabled/_0_prd_example.ini
```

## Configure `Repanier`

Create the system configuration file for `Repanier`.
In the example, the very first person who will be responsible for the group is `Eva Frank`.
The name of the group is `GASAP Example`.

```commandline
nano ~/prd1/_0_prd_example/_0_prd_example/_0_prd_example.ini
```
    [DJANGO_SETTINGS]
    DJANGO_SETTINGS_ADMIN_EMAIL=admin_email@mail.org
    DJANGO_SETTINGS_ADMIN_NAME=admin_name
    DJANGO_SETTINGS_DATABASE_NAME=_0_prd_example
    DJANGO_SETTINGS_DATABASE_USER=_0_prd_example
    DJANGO_SETTINGS_DATABASE_PASSWORD=db_password
    DJANGO_SETTINGS_EMAIL_HOST=email_host
    DJANGO_SETTINGS_EMAIL_HOST_PASSWORD=email_host_password
    DJANGO_SETTINGS_EMAIL_HOST_USER=email_host_user
    DJANGO_SETTINGS_EMAIL_PORT=587
    DJANGO_SETTINGS_EMAIL_USE_TLS=True
    DJANGO_SETTINGS_LANGUAGE=fr
    [REPANIER_SETTINGS]
    REPANIER_SETTINGS_GROUP_NAME=GASAP Example
    REPANIER_SETTINGS_COORDINATOR_EMAIL=eva.frank@no-spam.ws
    REPANIER_SETTINGS_COORDINATOR_NAME=Eva Frank
    REPANIER_SETTINGS_COORDINATOR_PHONE=0456/12.34.56
    REPANIER_SETTINGS_COUNTRY=be
    [ALLOWED_HOSTS]
    1:example.com
A common mistake here is to use a non valid `example.com` DNS name on a production environnement, i.e. without DJANGO_SETTINGS_DEBUG=True
If you are on a local PC/MAC/.. do not forget to add 
example.com  127.0.0.1
to your "hosts" file. 
On Windows, it's usually : C:\WINDOWS\system32\drivers\etc\hosts
Always on windows, remember to open a shell as an Administrator to edit C:\WINDOWS\system32\drivers\etc\hosts with notepad

Some other parameters may be set in the `[REPANIER_SETTINGS]` section of here above `_0_prd_example.ini` 
- REPANIER_SETTINGS_BOOTSTRAP_CSS  (*bootstrap.css*, bootstrap_my_own.css, bootstrap_another.css) : Allows you to change the look of the site.
- REPANIER_SETTINGS_COUNTRY  (be, fr, ch, es) : Allows you to change the applicable VAT. The currency (EUR, CHF, ...) is configured directly in the management interface of `Repanier`.
- REPANIER_SETTINGS_BCC_ALL_EMAIL_TO : If present, email address to put in bcc of all the mails
- REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER (True, *False*) : If True, unconfirmed orders are cancelled by `Repanier`.
- REPANIER_SETTINGS_DELIVERY_POINT (True, *False*) : If True, Repanier lets you manage more than one delivery point per offer.
- REPANIER_SETTINGS_MANAGE_ACCOUNTING (*True*, False) : If True, Repanier is used to manage the accounts (customers, proucers, bank).
- REPANIER_SETTINGS_ROUND_INVOICES (True, *False*) : Round the total amount of the order as appropriate to [0 or 5 cents](https://economie.fgov.be/fr/themes/ventes/politique-des-prix/paiements/votre-paiement-arrondi-0-ou-5).
- REPANIER_SETTINGS_SHOW_PRODUCER_ON_ORDER_FORM (*True*, False) : If True, Repanier show the producer of the product on the order form.
- REPANIER_SETTINGS_SMS_GATEWAY_MAIL (*EMPTY_STRING*, ) : Email address of a sms gateway service.

## Install or update `Repanier`
1. Git clone the `Repanier` project into the home folder of the user `repanier`
    ```commandline
    cd ~
    rm -rf repanier_git
    git clone https://github.com/pcolmant/repanier repanier_git
    ```
2. Populate the `Repanier` django project
    ```commandline
    cp ~/repanier_git/mysite/media/robots.txt ~/prd1/_0_prd_example/_0_prd_example/media/
    cp ~/repanier_git/mysite/media/favicon.ico ~/prd1/_0_prd_example/_0_prd_example/media/
    cp ~/repanier_git/mysite/common_settings.py ~/prd1/_0_prd_example/_0_prd_example/
    cp ~/repanier_git/mysite/urls.py ~/prd1/_0_prd_example/_0_prd_example/
    cp ~/repanier_git/mysite/wsgi.py ~/prd1/_0_prd_example/_0_prd_example/
    cp -R ~/repanier_git/mysite/locale/ ~/prd1/_0_prd_example/_0_prd_example/
    cp -R ~/repanier_git/cron/ ~/prd1/_0_prd_example/
    sudo chown www-data:www-data ~/prd1/_0_prd_example/cron/*.sh
    sudo chmod +x ~/prd1/_0_prd_example/cron/*.sh
    cp ~/repanier_git/manage.py ~/prd1/_0_prd_example/
    cp -R ~/repanier_git/repanier/ ~/prd1/_0_prd_example/
    ```
3. Goto the virtualenv and activate it
    ```commandline
    cd ~/prd1
    source bin/activate
    ```
4. Clear the cache to avoid access rights conflicts
    ```commandline
    sudo rm -rf /var/tmp/django-cache/*
    ```
5. Update `Repanier` static files and data base
    ```commandline
    cd ~/prd1/_0_prd_example
    python manage.py collectstatic
    python manage.py empty_null_fields
    python manage.py makemigrations repanier
    python manage.py migrate
    ```
6. Create a superuser **if it's not done yet**
    ```commandline
    python manage.py createsuperuser
    ```
7. Clear again the cache to avoid access rights conflicts
    ```commandline
    sudo rm -rf /var/tmp/django-cache/*
    ```
8. Restart (`restart`) nginx and uwsgi -- or Reload (`reload`) if no DNS/certificate change 
    ```commandline
    sudo nginx -t && sudo service nginx restart
    sudo service uwsgi restart
    ```
9. Browse to http://example.com/
10. Reset the pasword for the very first user whose mail is `eva.frank@no-spam.ws`
11. Then log in as this user, create others customers, producers, products, ....

How to activate https with Let's Encrypt
----------------------------------------
Validate the defaults when prompted

    ```
    sudo git clone https://github.com/letsencrypt/letsencrypt /opt/letsencrypt
    cd /opt/letsencrypt
    sudo ./letsencrypt-auto
    ```

How to change superuser password
--------------------------------
`Repanier` users must be created and updated through the `Repanier` interface.
This command allows you to create or change password of *Django* administrators and not of users of your `Repanier` site.

1. Goto the virtualenv and activate it
    ```commandline
    cd ~/prd1
    source bin/activate
    ```
2. If you know the superuser user name
    ```commandline
    manage.py changepassword user_name
    ```
3. Else create a new one
    ```commandline
    python manage.py createsuperuser
    ```
4. Clear the cache to avoid access rights conflicts
    ```commandline
    sudo rm -rf /var/tmp/django-cache/*
    ```
10. Reload uwsgi
    ```commandline
    service uwsgi reload
    ```
How to debug
------------
/!\ Never do it on a production environment and never forget to set it back to non debug mode...

1. Update the `Repanier` config file
    ```commandline
    nano ~/prd1/_0_prd_example/_0_prd_example/_0_prd_example.ini
    ```
        DJANGO_SETTINGS_DEBUG=True
2. Reload uwsgi
    ```commandline
    service uwsgi reload
    ```
How to check log files
----------------------

```commandline
 sudo tail -f /var/log/uwsgi/app/_0_prd_example.log
 sudo tail -f /var/log/nginx/_0_prd_example_error.log
 sudo tail -f /var/log/nginx/_0_prd_example_access.log
```

How to backup / restore the data base
-------------------------------------

```commandline
pg_dump -Fc -U repanier _0_prd_example > db.sql
pg_restore  -U repanier --format=c --no-owner --dbname=_0_prd_example db.sql
```

Repanier cron jobs
------------------

`Repanier` povides scripts to backup the db, close the orders and delete pending purchases.
Those scripts have to be placed in cron jobs of the user `www-data`.

Due to the `GDPR`, the backup db script also anonymize old and inactive customers.

```commandline
/home/repanier/prd1/_0_prd_example/cron/backup_db.sh
/home/repanier/prd1/_0_prd_example/cron/close_orders.sh
/home/repanier/prd1/_0_prd_example/cron/delete_pending_purchases.sh
```


