---------------------------------------------------------
How to setup django + postgresql + nginx on debian wheezy
---------------------------------------------------------

Tested on : 
	- raspberrypi, using raspbian 'wheezy' (http://www.raspberrypi.org/downloads)
	- virtualbox, using debian 'wheezy' (http://cdimage.debian.org/cdimage/weekly-builds/i386/iso-cd/debian-testing-i386-netinst.iso)

Add 'sudo' on the Debian OS (not on the Raspian)
------------------------------------------------

Login as : root

*sudo apt-get update*

*sudo apt-get install sudo*

*nano /etc/sudoers*
::

	# User privilege specification
	root	ALL=(ALL:ALL) ALL
	pi	ALL=(ALL:ALL) ALL

*exit*

Update the Debian OS
--------------------

Login as : pi

*sudo apt-get update && sudo apt-get -y upgrade*

Optional : Fix the IP adress
----------------------------
*sudo nano /etc/network/interfaces*
::

	auto lo
	
	iface lo inet loopback
	# iface eth0 inet dhcp
	iface eth0 inet static
	address 192.168.1.100
	gateway 192.168.1.1
	netmask 255.255.255.0
	network 192.168.1.0
	broadcast 192.168.1.255
	
	allow-hotplug wlan0
	iface wlan0 inet manual
	wpa-roam /etc/wpa_supplicant/wpa_supplicant.conf
	iface default inet dhcp

Install PostgreSQL
------------------
*sudo apt-get install postgresql*
*sudo -u postgres psql*
::

	CREATE USER pi PASSWORD 'raspberry';
	ALTER ROLE pi WITH CREATEDB;
	CREATE DATABASE pi OWNER pi;
	CREATE USER test_pi PASSWORD 'raspberry';
	ALTER ROLE test_pi WITH CREATEDB;
	\q

*sudo nano /etc/postgresql/9.1/main/postgresql.conf*
::

	listen_addresses = '*'

*sudo nano /etc/postgresql/9.1/main/pg_hba.conf*
::

	# IPv4 local connections:
	host    all             all             127.0.0.1/32               md5
	# for the raspberry pi
	host    all             all             192.168.1.0/24          md5
	# for the virtualbox
	host    all             all             10.0.2.0/24          md5

*sudo /etc/init.d/postgresql restart*

Now you got access to the PosgreSQL DB from any PC connected to the same network as the raspberry via "pgadmin" if you have installed it on your PC.

Install virtualenv
------------------
*sudo apt-get install python-virtualenv*

*virtualenv projects*

*cd ~/projects*

*source bin/activate*

Install Django
--------------
*sudo apt-get install libpq-dev python-dev*

*pip install psycopg2*

*pip install django-cms*

*pip install South*

*sudo apt-get install libjpeg8-dev*

*pip install pillow*

*pip install easy-thumbnails*

*pip install djangocms-text-ckeditor*

*django-admin.py startproject mysite*

*cd ~/projects/mysite*

*mkdir media*

*mkdir static*

*mkdir templates*

*cd ~/projects/mysite/media*

*mkdir cms*

*mkdir cms_page_media*

If you wish, place a "favicon.ico* file into ~/projects/mysite/static

*cd ~/projects/mysite/templates*

Copy base.html, and templates_1.html into it

base.html
::

	{% load cms_tags sekizai_tags menu_tags %}
	<html>
	  <head>
		  {% render_block "css" %}
	  </head>
	  <body>
		  {% cms_toolbar %}
		  {% language_chooser "menu/language_chooser.html" %}
		  {% placeholder base_content %}
		  {% block base_content %}{% endblock %}
		  {% render_block "js" %}
	  </body>
	</html>

templates_1.html
::

	{% extends "base.html" %}
	{% load cms_tags %}

	{% block base_content %}
	  {% placeholder template_1_content %}
	{% endblock %}

*mkdir cms*

*cd ~/projects/mysite/templates/cms*

*mkdir plugins*

Copy picture.hml into it.

picture.html
::

	{% load thumbnail %}

	{% if link %}<a href="{{ link }}">{% endif %}
	{% if placeholder == "template_1_content" %}
		<img src="{% thumbnail picture.image 400x300 %}"{% if picture.alt %} alt="{{ picture.alt }}"{% endif %} />
	{% else %}
		{% if placeholder == "teaser" %}
			<img src="{% thumbnail picture.image 150x150 %}"{% if picture.alt %} alt="{{ picture.alt }}"{% endif %} />
		{% endif %}
	{% endif %}
	{% if link %}</a>{% endif %}

*cd ~/projects/mysite/*

Copy common_settings.py, producteur_settings.py, ptidej_settings.py, apero_settings.py, urls.py into it

producteur_settings.py
::

	# -*- coding: utf-8 -*-
	from common_settings import *

	### Site 1 specific parameters
	SITE_ID = 1
	ALLOWED_HOSTS = ['producteur.intergas.be',]
	SECRET_KEY = '%+9cp2(c0&oe-6b##6uu1$y(s%8&7!eo=_-^ya6xxqvtof!jez'

ptidej_settings.py
::

	# -*- coding: utf-8 -*-
	from common_settings import *

	### Site 2 specific parameters
	SITE_ID = 2
	ALLOWED_HOSTS = ['ptidej.intergas.be',]
	SECRET_KEY = '%+9cp2(c0&oe-6b##6uu1$y(s%8&7!eo=_-^ya6xxqvtof!jez'

	
apero_settings.py
::

	# -*- coding: utf-8 -*-
	from common_settings import *

	### Site 3 specific parameters
	SITE_ID = 3
	ALLOWED_HOSTS = ['apero.intergas.be',]
	SECRET_KEY = '%+9cp2(c0&oe-7b##6uu1$y(s%8&7!eo=_-^ya6xxqvtof!jez'
	
common_settings.py
::

	# -*- coding: utf-8 -*-
	from settings import *

	import os
	gettext = lambda s: s
	PROJECT_PATH = os.path.abspath(os.path.dirname(__file__))

	###################### Django
	DATABASES = {
		'default': {
			'ENGINE': 'django.db.backends.postgresql_psycopg2', # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
			'NAME': 'pi',                      # Or path to database file if using sqlite3.
			# The following settings are not used with sqlite3:
			'USER': 'pi',
			'PASSWORD': 'raspberry',
			'HOST': '127.0.0.1',                      # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
			'PORT': '5432',                      # Set to empty string for default.
		}
	}

	TIME_ZONE = 'Europe/Brussels'
	LANGUAGE_CODE = 'fr-BE'
	STATIC_ROOT = os.path.join(PROJECT_PATH, "static")
	STATIC_URL = "/static/"
	MEDIA_ROOT = os.path.join(PROJECT_PATH, "media")
	MEDIA_URL = "/media/"
	SOUTH_TESTS_MIGRATE = False

	TEMPLATE_CONTEXT_PROCESSORS = (
		'django.contrib.auth.context_processors.auth',
		'django.core.context_processors.i18n',
		'django.core.context_processors.request',
		'django.core.context_processors.media',
		'django.core.context_processors.static',
	)
	INSTALLED_APPS += (
		# 'debug_toolbar',
		'django.contrib.admin',
		'south',
	)

	##################### Repanier
	AUTHENTICATION_BACKENDS = ('repanier.auth_backend.RepanierCustomBackend',)
	# ADMIN_LOGIN = 'pise'
	# ADMIN_PASSWORD = 'raspberry'
	INSTALLED_APPS += (
		'repanier',
	)

	##################### Django CMS
	LANGUAGES = [
		('fr', 'French'),
		('nl', 'Dutch'),
		('en', 'English'),
	]

	TEMPLATE_DIRS = (
		# The docs say it should be absolute path: PROJECT_PATH is precisely one.
		# Life is wonderful!
		os.path.join(PROJECT_PATH, "templates"),
	)
	CMS_TEMPLATES = (
		('template_1.html', 'Template One'),
		('template_2.html', 'Template Two'),
	)

	THUMBNAIL_DEBUG = False

	MIDDLEWARE_CLASSES += (
		'cms.middleware.multilingual.MultilingualURLMiddleware',
		'cms.middleware.user.CurrentUserMiddleware',
		'cms.middleware.page.CurrentPageMiddleware',
		'cms.middleware.toolbar.ToolbarMiddleware',
	)

	TEMPLATE_CONTEXT_PROCESSORS += (
		'cms.context_processors.media',
		'sekizai.context_processors.sekizai',
	)

	INSTALLED_APPS += (
		'djangocms_text_ckeditor',
		'easy_thumbnails',
		'cms',
		'mptt',
		'menus',
		'sekizai',
		'cms.plugins.file',
		'cms.plugins.flash',
		'cms.plugins.googlemap',
		'cms.plugins.link',
		'cms.plugins.picture',
		'cms.plugins.snippet',
		'cms.plugins.teaser',
	#	'cms.plugins.text',
		'cms.plugins.video',
		'cms.plugins.twitter',
		'django.contrib.sitemaps',
	)
	CMS_MENU_TITLE_OVERWRITE = False
	CMS_SOFTROOT = True
	CMS_PERMISSION = True
	CMS_PUBLIC_FOR = 'all'
	CMS_MODERATOR = True
	CMS_SHOW_START_DATE = False
	CMS_SHOW_END_DATE = False
	CMS_SEO_FIELDS = True

	CKEDITOR_SETTINGS = {
			'language': '{{ language }}',
			'toolbar': 'CMS',
			'skin': 'moono'
	}


Configuring hosts
-----------------

*sudo nano /etc/hosts*
::

	127.0.0.1	raspberrypi
	127.0.0.1	producteur.intergas.be
	127.0.0.1	ptidej.intergas.be
	127.0.0.1	apero.intergas.be

To be able to view the site from your PC add also to c:\windows\System32\drivers\etc\hosts replacing 127.0.0.1 with the IP of the raspberrypi or of the virtual machine
::

	127.0.0.1 raspberrypi
	127.0.0.1 ptidej.intergas.be
	127.0.0.1 apero.intergas.be
	127.0.0.1 producteur.intergas.be

*sudo apt-get install nginx uwsgi uwsgi-plugin-python*

If using virtualbox shared folder
---------------------------------

*cd ~/projects/mysite*

*sudo mount -t vboxsf mysite ./mysite*

*cd ~/projects/mysite*

*sudo mount -t vboxsf repanier ./repanier*

*cd ~/etc/nginx*

*sudo mount -t vboxsf sites-available ./sites-available*

*cd ~/etc/uwsgi*

*sudo mount -t vboxsf  apps-available ./apps-available*

End if
------

Install Nginx, Uwsgi
--------------------

*sudo nano /etc/nginx/sites-available/producteur*
::

	server {
		listen 80;
		server_name producteur.intergas.be;

		access_log /var/log/nginx/producteur_access.log;
		error_log /var/log/nginx/producteur_error.log;
		client_max_body_size 3M;
		location / {
			uwsgi_pass 	unix:///tmp/producteur.sock;
			include		uwsgi_params;
		}

		location /media/ {
			alias /home/pi/projects/mysite/mysite/media/;
		}

		location /static/ {
			alias /home/pi/projects/mysite/mysite/static/;
		}
		
		location /favicon.ico {
			alias /home/pi/projects/mysite/mysite/static/favicon.ico;
		}
	}

Same for ptidej and apero replacing "producteur" with "ptidej" or "apero"

*sudo ln -s /etc/nginx/sites-available/producteur /etc/nginx/sites-enabled/producteur*

*sudo ln -s /etc/nginx/sites-available/ptidej /etc/nginx/sites-enabled/ptidej*

*sudo ln -s /etc/nginx/sites-available/apero /etc/nginx/sites-enabled/apero*

*sudo nano /etc/uwsgi/apps-available/producteur.ini*
::

	[uwsgi]
		vhost = true
		plugins = python
		socket = /tmp/producteur.sock
		master = true
		enable-threads = true
		processes = 2
		buffer-size = 8192
		env = DJANGO_SETTINGS_MODULE=mysite.producteur_settings
		wsgi-file = /home/pi/projects/mysite/mysite/wsgi.py
		virtualenv = /home/pi/projects/
		chdir = /home/pi/projects/mysite/



Same for ptidej and apero replacing "producteur" with "ptidej" or "apero"

*sudo ln -s /etc/uwsgi/apps-available/producteur.ini /etc/uwsgi/apps-enabled/producteur.ini*

*sudo ln -s /etc/uwsgi/apps-available/ptidej.ini /etc/uwsgi/apps-enabled/ptidej.ini*

*sudo ln -s /etc/uwsgi/apps-available/apero.ini /etc/uwsgi/apps-enabled/apero.ini*

Create the DB with south
------------------------

*cd ~/projects/mysite/*

*python manage.py syncdb --all --settings=mysite.ptidej_settings*
::
	Superuser : pi, raspberry

*python manage.py migrate --fake --settings=mysite.ptidej_settings*

Copy static files to be available through the webserver
-------------------------------------------------------

*python manage.py collectstatic --settings=mysite.ptidej_settings*

Restarting services
-------------------

*sudo /etc/init.d/nginx restart*

*sudo /etc/init.d/uwsgi restart*

When needed, upgrade the DB with south for a specific INSTALLED_APPS (eg repanier)
----------------------------------------------------------------------------------

*cd ~/projects/mysite/*

*python manage.py schemamigration repanier --auto --settings=mysite.ptidej_settings*

*python manage.py migrate repanier --settings=mysite.ptidej_settings*

If needed, check what South has done
------------------------------------

*cd ~/projects/mysite/*

*python manage.py migrate --list --settings=mysite.ptidej_settings*

