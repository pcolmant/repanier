-----------------------
How to setup PostgreSQL
-----------------------

Install PostgreSQL
------------------

The database name ($NAME$), user ($USER$), password ($PASSWORD$) must be identical to those in the django settings file ´mysite/production_settings.py´

.. code:: bash

    sudo dpkg-reconfigure locales >>>> fr_BE.UTF-8
	sudo apt-get install postgresql
	sudo -u postgres psql
		CREATE USER $USER$ PASSWORD '$PASSWORD$';
		ALTER ROLE $USER$ WITH CREATEDB;
		NOT >>>>>>>>>>>>>>> CREATE DATABASE $NAME$ OWNER $USER$ ENCODING 'UTF8';
		CREATE DATABASE $NAME$ WITH TEMPLATE = template0 OWNER = $USER$ ENCODING = 'UTF8' LC_COLLATE = 'fr_BE.UTF-8' LC_CTYPE = 'fr_BE.UTF-8';
		>>>>>>>>>>>> pg_dump -Fc -U repad ptidej > db.sql
		>>>>>>>>>>>> pg_restore  --username=repad --format=c --no-owner --dbname=patrick db.sql

                                    List of databases
     Name      |  Owner   | Encoding  |   Collate   |    Ctype    |   Access privileges
---------------+----------+-----------+-------------+-------------+-----------------------
 apero         | repad    | SQL_ASCII | C           | C           |
 bees          | repad    | SQL_ASCII | C           | C           |
 coopeco2      | repad    | SQL_ASCII | C           | C           |
 exceptionnel  | repad    | SQL_ASCII | C           | C           |
 gasath        | repad    | SQL_ASCII | C           | C           |
 lebio         | repad    | SQL_ASCII | C           | C           |
 lelensois     | repad    | SQL_ASCII | C           | C           |
 lepi          | repad    | SQL_ASCII | C           | C           |
 postgres      | postgres | SQL_ASCII | C           | C           |
 ptidej        | repad    | SQL_ASCII | C           | C           |
 repanier      | repad    | SQL_ASCII | C           | C           |
 template0     | postgres | SQL_ASCII | C           | C           | =c/postgres          +
               |          |           |             |             | postgres=CTc/postgres
 template1     | postgres | SQL_ASCII | C           | C           | =c/postgres          +
               |          |           |             |             | postgres=CTc/postgres
 uapero        | repad    | UTF8      | fr_BE.UTF-8 | fr_BE.UTF-8 |
 ubees         | repad    | UTF8      | fr_BE.UTF-8 | fr_BE.UTF-8 |
 ucoopeco2     | repad    | UTF8      | fr_BE.UTF-8 | fr_BE.UTF-8 |
 uexceptionnel | repad    | UTF8      | fr_BE.UTF-8 | fr_BE.UTF-8 |
 ugasath       | repad    | UTF8      | fr_BE.UTF-8 | fr_BE.UTF-8 |
 ulebio        | repad    | UTF8      | fr_BE.UTF-8 | fr_BE.UTF-8 |
 ulelensois    | repad    | UTF8      | fr_BE.UTF-8 | fr_BE.UTF-8 |
 ulepi         | repad    | UTF8      | fr_BE.UTF-8 | fr_BE.UTF-8 |
 uptidej       | repad    | UTF8      | fr_BE.UTF-8 | fr_BE.UTF-8 |
 urepanier     | repad    | UTF8      | fr_BE.UTF-8 | fr_BE.UTF-8 |
(23 rows)


		CREATE USER test_$USER$ PASSWORD '$PASSWORD$';
		ALTER ROLE test_$USER$ WITH CREATEDB;
		\q
	sudo nano /etc/postgresql/9.1/main/postgresql.conf
		listen_addresses = '*'
	sudo nano /etc/postgresql/9.1/main/pg_hba.conf
		# Database administrative login by Unix domain socket                 
		local   all             postgresql 					md5

		# IPv4 local connections:
		host    all 		all 		127.0.0.1/32		md5
		# for the raspberry pi
		host    all 		all 		192.168.1.0/24		md5
		# for the virtualbox
		host    all 		all 		10.0.2.0/24			md5
	sudo /etc/init.d/postgresql restart

	How-to backup : http://www.thegeekstuff.com/2009/01/how-to-backup-and-restore-postgres-database-using-pg_dump-and-psql/
		pg_dump -U $USER$ $NAME$ -f dump.sql

Now you got access to the PosgreSQL DB from any PC connected to the same network as the Raspberry Pi via "pgadmin" if you have installed it on your PC.
