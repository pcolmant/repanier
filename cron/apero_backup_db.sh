# crontab -e
# Every hour/5'
# 5 */1 * * * /home/pi/v1/apero/cron/close_orders.sh >/dev/null 2>&1 
# Each thuesday at 20:10
# 10 20 * * 2 /home/repad/v1/apero/cron/apero_backup_db.sh >/dev/null 2>&1

# Do not forget to change chmod +x on this .sh file

export DJANGO_SETTINGS_MODULE=apero.apero_settings
export DJANGO_SETTINGS_MODULE_DEBUG=False
export DJANGO_SETTINGS_MODULE_DATABASE_NAME=uapero
export DJANGO_SETTINGS_MODULE_DATABASE_USER=repad
export DJANGO_SETTINGS_MODULE_DATABASE_PASSWORD=FJ:!EA3I*bX#
export DJANGO_SETTINGS_MODULE_DATABASE_HOST=127.0.0.1
export DJANGO_SETTINGS_MODULE_DATABASE_PORT=5432
export DJANGO_SETTINGS_MODULE_EMAIL_HOST=mail.gandi.net
export DJANGO_SETTINGS_MODULE_EMAIL_HOST_USER=pcolmant@repanier.be
export DJANGO_SETTINGS_MODULE_EMAIL_HOST_PASSWORD=k30Nao#Ku8t:
export DJANGO_SETTINGS_MODULE_EMAIL_PORT=587
export DJANGO_SETTINGS_MODULE_EMAIL_USE_TLS=True
export DJANGO_SETTINGS_MODULE_ADMIN_NAME=ptidej
export DJANGO_SETTINGS_MODULE_ADMIN_EMAIL=pcolmant@gmail.com
/home/repad/v1/bin/python /home/repad/v1/apero/manage.py backup_db
