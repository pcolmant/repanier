---------------------------------------------------------
How to setup django + postgresql + nginx on debian wheezy
---------------------------------------------------------

Installed on : 
	- raspberrypi, using raspbian 'wheezy' (http://www.raspberrypi.org/downloads)
	- virtualbox, using debian 'wheezy' (http://cdimage.debian.org/cdimage/weekly-builds/i386/iso-cd/debian-testing-i386-netinst.iso)


Copy nginx.conf to /etc/nginx :
*sudo cp nginx.conf /etc/nginx/nginx.conf*

Copy repanier, apero, producteur, ptidej to /etc/nginx/sites-available/ :
*sudo cp * /etc/nginx/sites-available/*

sudo ln -s /etc/nginx/sites-available/a-repanier /etc/nginx/sites-enabled/a-repanier
sudo ln -s /etc/nginx/sites-available/1-ptidej /etc/nginx/sites-enabled/1-ptidej
sudo ln -s /etc/nginx/sites-available/2-apero /etc/nginx/sites-enabled/2-apero
sudo ln -s /etc/nginx/sites-available/3-lelensois /etc/nginx/sites-enabled/3-lelensois
sudo ln -s /etc/nginx/sites-available/4-lebio /etc/nginx/sites-enabled/4-lebio
sudo ln -s /etc/nginx/sites-available/b-lepi /etc/nginx/sites-enabled/b-lepi
sudo ln -s /etc/nginx/sites-available/5-exceptionnel /etc/nginx/sites-enabled/5-exceptionnel
sudo ln -s /etc/nginx/sites-available/6-bees /etc/nginx/sites-enabled/6-bees
sudo ln -s /etc/nginx/sites-available/c-gasath /etc/nginx/sites-enabled/c-gasath


Copy repanier.ini, apero.ini, producteur.ini, ptidej.ini to /etc/uwsgi/apps-available/ :
*sudo cp *.ini /etc/uwsgi/apps-available/*

sudo ln -s /etc/uwsgi/apps-available/a-repanier.ini /etc/uwsgi/apps-enabled/a-repanier.ini
sudo ln -s /etc/uwsgi/apps-available/1-ptidej.ini /etc/uwsgi/apps-enabled/1-ptidej.ini
sudo ln -s /etc/uwsgi/apps-available/2-apero.ini /etc/uwsgi/apps-enabled/2-apero.ini
sudo ln -s /etc/uwsgi/apps-available/3-lelensois.ini /etc/uwsgi/apps-enabled/3-lelensois.ini
sudo ln -s /etc/uwsgi/apps-available/4-lebio.ini /etc/uwsgi/apps-enabled/4-lebio.ini
sudo ln -s /etc/uwsgi/apps-available/b-lepi.ini /etc/uwsgi/apps-enabled/b-lepi.ini
sudo ln -s /etc/uwsgi/apps-available/5-exceptionnel.ini /etc/uwsgi/apps-enabled/5-exceptionnel.ini
sudo ln -s /etc/uwsgi/apps-available/6-bees.ini /etc/uwsgi/apps-enabled/6-bees.ini
sudo ln -s /etc/uwsgi/apps-available/c-gasath.ini /etc/uwsgi/apps-enabled/c-gasath.ini

Install Django
--------------
./install_new_virtualenv.sh v1

------------ generate pdf : don't forget to also modifiy common_setting.py
sudo apt-get install xorg
sudo apt-get install xvfb
sudo apt-get install wkhtmltopdf
pip install django-wkhtmltopdf
create wkhtmltopdf.sh containing :  
	#!/bin/sh
	xvfb-run -a -s "-screen 0 640x480x16" wkhtmltopdf $*

sudo mv wkhtmltopdf.sh /usr/bin/
cd /usr/bin/
sudo chmod a+x /usr/bin/wkhtmltopdf.sh
ln -s /usr/bin/wkhtmltopdf.sh wkhtmltopdf
cd ~/production/mysite



Make translation files
----------------------

sudo apt-get install gettext
create /conf/locale into repanier / polls / plugins / mysite
cd repanier / polls / plugins / mysite

export DJANGO_SETTINGS_MODULE=
django-admin.py makemessages -l fr
django-admin.py makemessages -d djangojs -l fr
django-admin.py compilemessages

sudo rm -rf /var/tmp/django_cache/ptidej.repanier.be/
python manage.py makemigrations repanier
python manage.py migrate repanier
python manage.py recalculate_order_amount
sudo chown www-data:www-data /var/tmp/django_cache/ptidej.repanier.be/
sudo /etc/init.d/uwsgi reload

pip install django-ajaximage



Dump database with natural keys
-------------------------------
cd /home/pi/production/mysite
django-admin.py dumpdata --all --indent 4 --natural --settings=mysite.repanier_settings --pythonpath='/home/pi/production/mysite'

apt-get install sysstat
--> iostat, sar, mpstat

Restore DB
----------

pg_restore  --username=pi --format=c --no-owner --dbname=ptidej ptidej-db.bak.ETM4XE 

---------------- Migrate DB
python manage.py schemamigration --auto repanier
python manage.py migrate repanier
python manage.py migrate --fake repanier 0008
python manage.py migrate repanier 0009_auto__add_lut_productionmodetranslation__add_unique_lut_productionmode


----------------- Clear cache
sudo /etc/init.d/uwsgi stop && rm -rf /var/tmp/django_cache/* && sudo /etc/init.d/uwsgi start
rm -rf /var/tmp/django_cache/* && sudo /etc/init.d/uwsgi reload

-------
Change nowrap to normal
http://ptidej.repanier.be:9000/static/admin/css/changelists.css ligne 59
#changelist table thead th {
white-space: nowrap;
}

!!!!!!!!!!! remove in /home/pi/v2/lib/python2.7/site-packages/django/contrib/admin/templates/admin/base.html vvvv and copy this file to *******ptidej/templates/admin/base.html***********
    {% block breadcrumbs %}
    <div class="breadcrumbs">
    <a href="{% url 'admin:index' %}">{% trans 'Home' %}</a>
    {% if title %} &rsaquo; {{ title }}{% endif %}
    </div>
    {% endblock %}


******* remove also  ***********

        <div id="branding">
        {% block branding %}{% endblock %}
        </div>
        {% if user.is_active and user.is_staff %}
        <div id="user-tools">
            {% trans 'Welcome,' %}
            <strong>{% firstof user.get_short_name user.get_username %}</strong>.
            {% block userlinks %}
                {% url 'django-admindocs-docroot' as docsroot %}
                {% if docsroot %}
                    <a href="{{ docsroot }}">{% trans 'Documentation' %}</a> /
                {% endif %}
                {% if user.has_usable_password %}
                <a href="{% url 'admin:password_change' %}">{% trans 'Change password' %}</a> /
                {% endif %}
                <a href="{% url 'admin:logout' %}">{% trans 'Log out' %}</a>
            {% endblock %}
        </div>
        {% endif %}

Git

git add *
git commit -m "New release"
git push origin master

# updates were rejected because the tip of your current branch is behind its remote counterpart
git push -f

# delete
git rm -r wsgi.py
git commit -m "Remove duplicated directory"
git push origin master

git init
git clone https://github.com/pcolmant/repanier.git
git config --global user.email pcolmant@gmail.com
git config --global user.name Patrick Colmant
git commit -m 'new release cnadidate'
git status
cd repanier/
git add .
git status
git commit -a
git commit -m 'release candidate'
git push origin master
git rm -r mysite/collect-static/foundation
git commit -m 'release candidate'
git push origin master

#-----------------------------------------------------------

--> conditional formating must be placed before data validations
otherwise when opening the document with EXCEL 
"We found a problem with some content in 'TST.XLSX'. Do you want us to try to recover as much as we can ? ..."

---> in openpyxl / openpyxl / writer / worksheet.py move according.

before :

103  write_worksheet_datavalidations(doc, worksheet)
104  write_worksheet_hyperlinks(doc, worksheet)
105  write_worksheet_conditional_formatting(doc, worksheet)

after :

103  write_worksheet_conditional_formatting(doc, worksheet)
104  write_worksheet_datavalidations(doc, worksheet)
105  write_worksheet_hyperlinks(doc, worksheet)




from openpyxl import Workbook
from openpyxl.style import Color, Fill
wb = Workbook()
ws = wb.get_active_sheet()

yellowFill = Fill()
yellowFill.start_color.index = 'FFEEEE11'
yellowFill.end_color.index = 'FFEEEE11'
yellowFill.fill_type = Fill.FILL_SOLID

ws.cell('A1').value = 0.5
ws.cell('B1').value = 0.5
ws.cell('B2').value = 1
ws.conditional_formatting.addCellIs('A1','notEqual', ['1'], True, wb, None, None, yellowFill)
dv = DataValidation(ValidationType.LIST, formula1='B1:B2', allow_blank=True)
ws.add_data_validation(dv)
dv.ranges.append('A1:A1')
wb.save('TST.XLSX')

-----------------------------
python manage.py schemamigration --auto cmsplugin_filer_link
python manage.py migrate
sudo service uwsgi reload

python manage.py migrate cms 0066_auto__add_aliaspluginmodel
python manage.py migrate cms 0067_auto__add_field_aliaspluginmodel_alias_placeholder__chg_field_aliasplu
python manage.py migrate cmsplugin_filer_image 0011_auto__add_field_filerimage_style
python manage.py migrate cmsplugin_filer_file 0003_auto__add_field_filerfile_style
python manage.py migrate cmsplugin_filer_folder 0002_auto__add_field_filerfolder_style
python manage.py migrate cmsplugin_filer_folder 0003_move_view_option_to_style
python manage.py migrate cmsplugin_filer_folder 0004_auto__del_field_filerfolder_view_option
python manage.py migrate cmsplugin_filer_link 0002_auto__chg_field_filerlinkplugin_file
sudo service uwsgi reload


cd v2
source bin/1_activate_ptidej
sudo /etc/init.d/postgresql restart
sudo -u postgres psql
pg_restore  --username=pi --format=c --no-owner --dbname=ptidej ptidej-db.bak.rTVnFS

# Step 1
# With new site
# DELETE migrations content and if exists, delete migration folder
# set old models_step4.py into repanier
# python manage.py schemamigration --initial repanier
# python manage.py migrate --fake --delete-ghost-migrations repanier 0001

# use models_step5
python manage.py schemamigration --auto repanier
# 2 / datetime.date.today()
# comment lines 15, 102, 194, 197
python manage.py migrate repanier
python manage.py step5_clean_purchase
# use models_step6
python manage.py schemamigration --auto repanier
# comment 95, 98, 101, 166, 169
python manage.py migrate repanier
python manage.py step6_clean_purchase

--------------------------------------------------
MIGRATION
--------------------------------------------------

Attention vérifier ckeditor
-------------------------
pip install -U psycopg2
# pip install https://github.com/divio/django-cms/archive/develop.zip
pip install -U django-cms
pip install -U djangocms-text-ckeditor
pip install https://github.com/stefanfoulis/django-filer/archive/develop.zip
# pip install -U django-filer
pip install https://github.com/stefanfoulis/cmsplugin-filer/archive/develop.zip
# pip install -U cmsplugin-filer
pip install -U django-reversion
pip install -U django_compressor
pip install -U django_mptt_admin
pip install -U django-parler
pip install -U django-treebeard
pip install openpyxl==1.8.6

sudo -u postgres psql
\c ptidej
ALTER TABLE cmsplugin_filerimage RENAME TO cmsplugin_filer_image_filerimage;
\q

Copy mysite/ ptidej common settings
Update ptidej settings:
REPANIER_SEND_ORDER_TO_BOARD = True
REPANIER_INVOICE = True
all
        'plugins': ['TextPlugin', 'FilerLinkPlugin', 'FilerImagePlugin', 'FilerFilePlugin', 'FilerVideoPlugin', ],

footer
        'plugins': ['TextPlugin', 'FilerLinkPlugin', ],

ci-dessous, l'un après l'autre
--------------------
python manage.py collectstatic
sudo rm -rf /var/tmp/django_cache/www.gasath.be/
python manage.py makemigrations
python manage.py migrate --fake cms 0003
python manage.py migrate --fake filer
python manage.py migrate --fake cmsplugin_filer_image
python manage.py migrate --fake easy_thumbnails
sudo rm -rf /var/tmp/django_cache/www.gasath.be/
python manage.py migrate
sudo rm -rf /var/tmp/django_cache/www.gasath.be/
-----------------
sudo chown www-data:www-data www.gasath.be/
-------------
repad users
----------------
python manage.py createsuperuser

-------------------------
python manage.py makemigrations repanier
python manage.py migrate --fake repanier 0001
COPY NEW
sudo rm -rf /var/tmp/django_cache/www.gasath.be/
python manage.py makemigrations repanier
python manage.py migrate repanier
python manage.py createsuperuser
sudo chown www-data:www-data /var/tmp/django_cache/www.gasath.be/
sudo /etc/init.d/uwsgi reload

export DJANGO_SETTINGS_MODULE=
django-admin.py makemessages -l fr
django-admin.py makemessages -d djangojs -l fr
django-admin.py compilemessages


Groupe parent / enfant
--------------------------
Notion d'arrondi à la commande fournisseur
Membre avec statut "Groupe enfant" dans le site parent. Le flag peut commander ou non est d'application aussi pour les groupes enfants.
Lorsqu'il se connecte le groupe enfant a la possibilité de voir la liste des fournisseurs et un lien associé
Ajouter le lien "fournisseur parent" dans la fiche fournisseur.
Ce lien peut fonctionner avec en enfant "repanier" ou non
La recopie a lieu soit à la demande du groupe enfant, soit automatiquement à l'ouverture des cdes, ssi une commande est ouverte pour ce frn chez le groupe parent.
Pour cela le fournisseur a un flag : recopie automatique à l'ouverture O/N.
Le groupe enfant recopie ce lien dans sa fiche producteur
La référence produit est celle du parent
Le tarif d'achat du fils est celui de vente du père.
Les produits en offre sont ceux du père.
A l'envoi des commandes du groupe enfant vers ses fournisseurs, le système arrondi, si ce n'est déjà fait.
Le groupe parent peut refuser la commande si le groupe enfant ne peut pas commander. Tout comme pour les membres normaux.
Le groupe parent refuse la commande s'il na pas de permanence ouverte pour ce producteur.
Le groupe parent vérifie que les produits commandés sont bien en offre, dans les qtés commandées.
Un mécanisme existe pour commander au d&part d'un site non "repanier".

----------------------------

IMPORTANT !!!!!!!!!!!!!!!! vvvvvvvvvvvvvvvvv
# chmod +x ./ptidej_close_orders.sh
# sudo chmod +s ./ptidej_close_orders.sh
# sudo chown www-data:www-data  the cron job
# sudo -u www-data ./ptidej_close_orders.sh
# sudo crontab -u www-data -e
#sudo nano /etc/postgresql/9.1/main/pg_hba.conf
#local   all             repad                                   trust
#local   all             all                                     peer