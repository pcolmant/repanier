-----------------------
How to setup PostgreSQL
-----------------------

	- raspberrypi, using raspbian 'wheezy'
	- virtualbox, using debian 'wheezy'

Install PostgreSQL
------------------

The database name ($NAME$), user ($USER$), password ($PASSWORD$) must be identical to those in the django settings file ´mysite/production_settings.py´

.. code:: bash

	sudo apt-get install postgresql
	sudo -u postgres psql
		CREATE USER $USER$ PASSWORD '$PASSWORD$';
		ALTER ROLE $USER$ WITH CREATEDB;
		CREATE DATABASE $NAME$ OWNER $USER$;
		CREATE USER test_$USER$ PASSWORD '$PASSWORD$';
		ALTER ROLE test_$USER$ WITH CREATEDB;
		\q
	sudo nano /etc/postgresql/9.1/main/postgresql.conf
		listen_addresses = '*'
	sudo nano /etc/postgresql/9.1/main/pg_hba.conf
		# IPv4 local connections:
		host    all 		all 		127.0.0.1/32		md5
		# for the raspberry pi
		host    all 		all 		192.168.1.0/24		md5
		# for the virtualbox
		host    all 		all 		10.0.2.0/24			md5
	sudo /etc/init.d/postgresql restart

Now you got access to the PosgreSQL DB from any PC connected to the same network as the Raspberry Pi via "pgadmin" if you have installed it on your PC.
