----------------------------
How to setup debian (wheezy)
----------------------------

	- raspberrypi, using raspbian 'wheezy' (http://www.raspberrypi.org/downloads)
	- virtualbox, using debian 'wheezy' (http://cdimage.debian.org/cdimage/weekly-builds/i386/iso-cd/debian-testing-i386-netinst.iso)

Add 'sudo' on the Debian OS (not on the Raspian)
------------------------------------------------

This step has not to be done on the Raspberry Pi Raspbian because it's already automaticaly done during the first Raspbian installation.

Login as : root

.. code:: bash

	sudo apt-get update
	sudo apt-get install sudo
	nano /etc/sudoers
		# User privilege specification
		root	ALL=(ALL:ALL) ALL
		pi	ALL=(ALL:ALL) ALL
	exit

From now, don't log you anymore as ´root´. Log you as ´pi´

Update the Debian OS
--------------------

Login as : pi

.. code:: bash

	sudo apt-get update && sudo apt-get -y upgrade

Install Virtualenv, Nginx, Uwsgi
--------------------------------

.. code:: bash

	sudo apt-get install python-virtualenv

Install Nginx
-------------

.. code:: bash

	sudo apt-get install nginx

Copy install/nginx/nginx.conf to /etc/nginx using sudo.

.. code:: bash

	sudo cp nginx.conf /etc/nginx/nginx.conf

For each sites, create a copy of install/nginx/sites-available/example. Replace ´$REPANIER.BE$´ with the domain name of the corresponding site and ´$FAVICON_FILE_NAME$.ico´ with the name of the corresponding favicon file and ´/$PATH_TO$/´ with the path of your home directory. You can get it using ´cd ~´ then ´pwd´. Usualy this path is ´home/pi´ for the Raspberry Pi. Copy the resulting files to /etc/nginx/sites-available using sudo. 

.. code:: bash

	sudo cp * /etc/nginx/sites-available/

For each of those files create a symbolic link between /etc/nginx/sites-enabled and /etc/nginx/sites-available.

.. code:: bash

	sudo ln -s /etc/nginx/sites-available/´$FILE_NAME$´ /etc/nginx/sites-enabled/´$FILE_NAME$´

Install Uwsgi
-------------

.. code:: bash

	sudo apt-get install uwsgi uwsgi-plugin-python

For each sites, create a copy of install/uwsgi/sites-available/example.ini. Replace ´$REPANIER.BE$´ with the domain name of the corresponding site and ´/$PATH_TO$/´ with the path of your home directory. You can get it using ´cd ~´ then ´pwd´. Usualy this path is ´home/pi´ for the Raspberry Pi. Copy the resulting files to /etc/uwsgi/apps-available using sudo.

.. code:: bash

	sudo cp *.ini /etc/uwsgi/apps-available/

For each of those files create a symbolic link between /etc/uwsgi/apps-enabled and /etc/uwsgi/apps-available.

.. code:: bash

	sudo ln -s /etc/wsgi/apps-available/´$FILE_NAME$´ /etc/wsgi/apps-enabled/´$FILE_NAME$´

Optional : force static IP adress
---------------------------------

This step is usefull to force the Raspberry Pi to use a static IP adress so that you can easily access to it with a ssh client. Don't forget to activate ´ssh client´ during the first Raspbian installation. If this has not be done, run ´raspi-config´again to fix it.

My BBOX IP is 192.168.1.1. The static IP is 192.168.1.100.

.. code:: bash

	sudo nano /etc/network/interfaces
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
