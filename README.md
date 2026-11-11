Repanier
========

`Repanier` is an open-source web application designed for short-circuit food supply chains and local producer groups (GASAP, AMAP, food co-ops). 

Built with **Django 5.2**, **Django CMS 5.1**, **Bootstrap 5.3**, and **Python 3.13**.

- **Documentation & Info**: https://projet.repanier.be/
- **License**: GPL v3

### Active Customer Groups
- https://gasath.repanier.be/
- https://commande.coopeco-supermarche.be/
- https://exceptionnel.repanier.be/
- https://lepanierlensois.repanier.be/
- https://courtcircuit.repanier.be/
- https://pigal.repanier.be/
- https://epicentre.repanier.be/

### Active Producers
- https://commande.lebuisson.be/
- https://lejardinderomuald.repanier.be/

---

# How to Set Up `Repanier` on Debian 13

This guide provides step-by-step instructions for deploying `Repanier` on a Debian 13 server using `Nginx`, `uWSGI`, and `PostgreSQL`.

---

## 1. System Prerequisites (Run Once as Root)

These steps secure your server and install required base packages.

1. **Log in via SSH as `root`**.
2. **Update system packages and install `sudo`**:
   ```bash
   apt-get update && apt-get upgrade -y
   apt-get install -y sudo
   ```
3. **Remove Apache** (if installed, as `Nginx` will handle web requests):
   ```bash
   service apache2 stop 2>/dev/null
   apt-get purge -y apache2 apache2-utils
   apt-get autoremove -y
   ```
4. **Configure Locales** (required for PostgreSQL database creation):
   ```bash
   dpkg-reconfigure locales
   # Select fr_BE.UTF-8 (or your local equivalent, e.g., fr_FR.UTF-8, fr_CH.UTF-8)
   ```
5. **Create a non-root system user** (`repanier`):
   ```bash
   useradd -m -s /bin/bash repanier
   passwd repanier
   usermod -aG sudo repanier
   groupadd sshusers
   usermod -aG sshusers repanier
   ```
6. **Secure SSH Configuration**:
   ```bash
   nano /etc/ssh/sshd_config
   ```
   *Set or verify the following settings:*
   ```text
   PermitRootLogin no
   AllowGroups sshusers
   ```
   Restart SSH:
   ```bash
   systemctl restart ssh
   ```
7. **Test Sudo Access**:
   Open a new terminal window, log in as `repanier`, and test root permissions:
   ```bash
   sudo -l
   ```
8. **Install Server Dependencies**:
   ```bash
   sudo apt-get update
   sudo apt-get install -y build-essential wget gettext unzip git \
                           python3-pip python3-venv postgresql \
                           nginx uwsgi uwsgi-plugin-python3 certbot python3-certbot-nginx
   sudo rm -f /etc/nginx/sites-enabled/default
   ```
9. **Reboot**:
   ```bash
   sudo reboot
   ```

---

## 2. Directory Setup & Python Environment

Log back in as the `repanier` user.

### Cache & Session Storage
Create isolated directories for Django file-based caching and session storage:
```bash
sudo mkdir -p /var/tmp/django-cache /var/tmp/django-session
sudo chgrp www-data /var/tmp/django-cache /var/tmp/django-session
sudo chmod g+w /var/tmp/django-cache /var/tmp/django-session
```

### Python Virtual Environment
Create and activate a virtual environment (e.g., `prd1`):
```bash
cd ~
python3 -m venv prd1
source ~/prd1/bin/activate
pip install --upgrade pip
```

---

## 3. PostgreSQL Database Setup

1. **Connect to PostgreSQL**:
   ```bash
   sudo -u postgres psql
   ```
2. **Create User & Database**:
   ```sql
   CREATE USER _0_prd_example WITH PASSWORD 'db_password';
   ALTER ROLE _0_prd_example WITH CREATEDB;
   CREATE DATABASE _0_prd_example WITH TEMPLATE = template0 OWNER = _0_prd_example ENCODING = 'UTF8' LC_COLLATE = 'fr_BE.UTF-8' LC_CTYPE = 'fr_BE.UTF-8';
   \q
   ```

---

## 4. Application Configuration

### Project Structure
```bash
source ~/prd1/bin/activate
django-admin startproject _0_prd_example ~/prd1/_0_prd_example
mkdir -p ~/prd1/_0_prd_example/_0_prd_example/media/public
sudo chgrp -R www-data ~/prd1/_0_prd_example/_0_prd_example/media
sudo chmod -R g+w ~/prd1/_0_prd_example/_0_prd_example/media
```

### Repanier Configuration File (`_0_prd_example.ini`)
Create the environment settings file:
```bash
nano ~/prd1/_0_prd_example/_0_prd_example/_0_prd_example.ini
```

Add the following configuration block:
```ini
[DJANGO_SETTINGS]
DJANGO_SETTINGS_ADMIN_EMAIL=admin@example.com
DJANGO_SETTINGS_ADMIN_NAME=Admin Name
DJANGO_SETTINGS_DATABASE_NAME=_0_prd_example
DJANGO_SETTINGS_DATABASE_USER=_0_prd_example
DJANGO_SETTINGS_DATABASE_PASSWORD=db_password
DJANGO_SETTINGS_EMAIL_HOST=smtp.example.com
DJANGO_SETTINGS_EMAIL_HOST_USER=smtp_user
DJANGO_SETTINGS_EMAIL_HOST_PASSWORD=smtp_password
DJANGO_SETTINGS_EMAIL_PORT=587
DJANGO_SETTINGS_EMAIL_USE_TLS=True
DJANGO_SETTINGS_LANGUAGE=fr

[REPANIER_SETTINGS]
REPANIER_SETTINGS_GROUP_NAME=GASAP Example
REPANIER_SETTINGS_COORDINATOR_EMAIL=coordinator@example.com
REPANIER_SETTINGS_COORDINATOR_NAME=Coordinator Name
REPANIER_SETTINGS_COORDINATOR_PHONE=0456/12.34.56
REPANIER_SETTINGS_COUNTRY=be
REPANIER_SETTINGS_MANAGE_ACCOUNTING=True
REPANIER_SETTINGS_ROUND_INVOICES=False
REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER=False

[ALLOWED_HOSTS]
1:example.com
```

#### Available Options in `[REPANIER_SETTINGS]`:
- `REPANIER_SETTINGS_COUNTRY` (`be`, `fr`, `ch`, `es`): Controls VAT calculations. Currency settings are configured directly within the web UI.
- `REPANIER_SETTINGS_MANAGE_ACCOUNTING` (`True`, `False`): Enables integrated accounting (customer balance, producer balances, payments).
- `REPANIER_SETTINGS_ROUND_INVOICES` (`True`, `False`): Enables cash payment rounding (0 or 5 cents) where mandated by law.
- `REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER` (`True`, `False`): Automatically cancels unconfirmed customer orders if set to `True`.
- `REPANIER_SETTINGS_BCC_ALL_EMAIL_TO`: Send copy of all outbound transactional emails to this address.

---

## 5. Web Server Configuration

### Nginx Configuration (`/etc/nginx/sites-available/_0_prd_example`)
```nginx
server {
    listen 80;
    server_name example.com;

    access_log /var/log/nginx/_0_prd_example_access.log;
    error_log /var/log/nginx/_0_prd_example_error.log;

    client_max_body_size 10M;

    location /media/ {
        alias /home/repanier/prd1/_0_prd_example/_0_prd_example/media/public/;
    }

    location /static/ {
        alias /home/repanier/prd1/_0_prd_example/_0_prd_example/collect-static/;

        # Anti hotlinking: third party sites may not embed our assets.
        #   none    = no referer at all (direct access, bookmark, privacy
        #             extensions, first navigation): ALLOWED, never block
        #             our own users.
        #   blocked = sanitized or proxied referers: ALLOWED.
        #   server_names = the domains of this server block.
        valid_referers none blocked server_names;
        if ($invalid_referer) {
            return 403;
        }

        # Modern browsers refuse to load a resource across origins:
        # even a referer spoofing cannot bypass this one.
        # Warning: an add_header in a location replaces the inherited
        # ones: repeat here any header set at the server level.
        add_header Cross-Origin-Resource-Policy same-origin always;

        expires 30d;
        access_log off;
    }

    location /favicon.ico {
        alias /home/repanier/prd1/_0_prd_example/_0_prd_example/media/favicon.ico;
    }

    location /robots.txt {
        alias /home/repanier/prd1/_0_prd_example/_0_prd_example/media/robots.txt;
    }

    location / {
        include         uwsgi_params;
        uwsgi_param     HTTP_X_FORWARDED_HOST $server_name;
        uwsgi_pass      unix:///tmp/_0_prd_example.sock;
        uwsgi_read_timeout 600s;
    }
}
```

Enable site configuration:
```bash
sudo ln -s /etc/nginx/sites-available/_0_prd_example /etc/nginx/sites-enabled/_0_prd_example
```

**Hotlink protection on `/static/`** (already included in the configuration
above): the referer filter answers `403` when the assets are requested
from a page hosted on a third party site, and the
`Cross-Origin-Resource-Policy: same-origin` response header makes modern
browsers refuse to load a cross origin resource even when the referer is
missing or spoofed.

Its purpose is to keep Repanier sites from being used as a free CDN on
someone else's bandwidth budget. Requests without a referer stay allowed
(`valid_referers ... none blocked`) so bookmarks, privacy extensions and
first navigations of our own visitors are never blocked. A server side
download (curl, wget) stays technically possible: this protection is about
bandwidth, not about copying (the Repanier source code is GPLv3 anyway).

Check and reload after any nginx change:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

### uWSGI Configuration (`/etc/uwsgi/apps-available/_0_prd_example.ini`)
```ini
[uwsgi]
vhost = true
plugins = python3
socket = /tmp/_0_prd_example.sock
master = true
enable-threads = true
processes = 2
threads = 2
buffer-size = 8192
wsgi-file = /home/repanier/prd1/_0_prd_example/_0_prd_example/wsgi.py
virtualenv = /home/repanier/prd1/
chdir = /home/repanier/prd1/_0_prd_example/
harakiri = 360
```

Enable uWSGI application:
```bash
sudo ln -s /etc/uwsgi/apps-available/_0_prd_example.ini /etc/uwsgi/apps-enabled/_0_prd_example.ini
```

---

## 6. Deploying & Updating Repanier

1. **Fetch Latest Source Code**:
   ```bash
   cd ~
   rm -rf repanier_git
   git clone https://github.com/pcolmant/repanier repanier_git
   ```

2. **Install Dependencies**:
   ```bash
   source ~/prd1/bin/activate
   pip install -r ~/repanier_git/requirements/requirement.txt
   ```

3. **Deploy Codebase**:
   ```bash
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

4. **Run Migrations & Static Collection**:
   ```bash
   cd ~/prd1/_0_prd_example
   python manage.py collectstatic --noinput
   python manage.py makemigrations repanier
   python manage.py migrate
   ```

5. **Create Admin Superuser**:
   ```bash
   python manage.py createsuperuser
   ```

6. **Clear Cache & Restart Services**:
   ```bash
   sudo rm -rf /var/tmp/django-cache/*
   sudo systemctl restart nginx
   sudo systemctl restart uwsgi
   ```

---

## 7. SSL Setup with Let's Encrypt

To issue and automatically configure a free SSL certificate:
```bash
sudo certbot --nginx -d example.com
```

---

## 8. Automated Cron Jobs

`Repanier` includes scripts to automate database backups, order closures, and cleanups. Add these tasks to the `www-data` crontab:

```bash
sudo crontab -u www-data -e
```

Example Schedule:
```cron
# Daily backup and GDPR-compliant customer data anonymization
0 2 * * * /home/repanier/prd1/_0_prd_example/cron/backup_db.sh >/dev/null 2>&1

# Close active orders automatically at deadline
*/15 * * * * /home/repanier/prd1/_0_prd_example/cron/close_orders.sh >/dev/null 2>&1

# Delete unconfirmed pending orders
0 4 * * * /home/repanier/prd1/_0_prd_example/cron/delete_pending_purchases.sh >/dev/null 2>&1
```