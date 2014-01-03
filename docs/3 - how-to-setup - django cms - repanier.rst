------------------------------------------
How to setup Django, Django-cms - Repanier
------------------------------------------

	- raspberrypi, using raspbian 'wheezy'
	- virtualbox, using debian 'wheezy'


Install Django, Django-cms
--------------------------

Copy /install/install_new_virtualenv.sh and install_new_site.sh to your home directory.

.. code:: bash

	chmod +x ~/install_new_virtualenv.sh
	chmod +x ~/install_new_site.sh
	~/install_new_virtualenv.sh v1

For each site replacing ´$REPANIER.BE$´ with the domain name of the corresponding site execute install_new_site.sh.

.. code:: bash

	chmod +x ~/install_new_site.sh
	~/install_new_site.sh v1 $REPANIER.BE$

Merge the folder /mysite of the git repo with the folder to ~/v1/mysite/mysite of your installation. Copy the folder /repanier of the git repo to ~/v1/mysite, giving ~/v1/mysite/repanier.... Copy your favicon.ico to ~/v1/mysite/mysite/media/

Copy the ´secret_key´ of ~/v1/mysite/mysite/setup.py and check DB paramters into the file ~/v1/mysite/mysite/production_settings.py. The database name ($NAME$), user ($USER$), password ($PASSWORD$) must be identical to those in the setup of PostgreSQL. 

Generate a copy of static files needed by Django

.. code:: bash

	cd ~/v1
	source bin/activate
	cd mysite
	python manage.py collectstatic --settings=mysite.repanier_settings
	# If some errors execute 
	# python manage.py collectstatic --traceback --settings=mysite.repanier_settings
	# to detect the root cause

Create the DB with south. During this step you will be asked to create the ´superuser´ of Django.

.. code:: bash

	python manage.py syncdb --all --settings=mysite.repanier_settings
	python manage.py schemamigration repanier --initial --settings=mysite.repanier_settings
	python manage.py migrate --fake --settings=mysite.repanier_settings

Check if CMS install is ok

.. code:: bash

	python manage.py cms check --settings=mysite.repanier_settings

Compile translation files

.. code:: bash

	cd ~/v1/mysite/repanier
	django-admin.py compilemessages 


If you want, initialize the DB with test content : copy the content of /install/createdb into ~/v1/mysite/

.. code:: bash

	cd ~/v1/mysite/
	export DJANGO_SETTINGS_MODULE='mysite.repanier_settings'
	python createdb.py

Finalize th configuration


.. code:: bash

	cd ~
	ln -s ~/v1 ~/production

Restart Nginx and Uwsgi

.. code:: bash

	# Restart Nginx
	sudo /etc/init.d/nginx restart
	# Stop Uwsgi
	sudo /etc/init.d/uwsgi stop
	# Clean the Django cache
	rm -rf /var/tmp/django_cache/*
	# Start Uwsgi
	sudo /etc/init.d/uwsgi start

The surf on your sites

When needed, upgrade the DB with south for a new version of specific INSTALLED_APPS (eg repanier)
-------------------------------------------------------------------------------------------------

.. code:: bash

	cd ~/production/mysite/
	python manage.py schemamigration repanier --auto --settings=mysite.repanier_settings
	python manage.py migrate repanier --settings=mysite.repanier_settings

If needed, check what South has done

.. code:: bash

	cd ~/production/mysite/
	python manage.py migrate --list --settings=mysite.repanier_settings

