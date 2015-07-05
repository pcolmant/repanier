# crontab -e
# Every hour/5'
# 5 */1 * * * /home/pi/v1/ptidej/cron/close_orders.sh >/dev/null 2>&1 
# At 6h5, 12h5, .., 22h5
# 5 6,12,14,16,18,19,20,21,22 * * * /home/pi/v1/ptidej/cron/close_orders.sh >/dev$

# Do not forget to change chmod +x on this .sh file

export DJANGO_SETTINGS_MODULE=bees.bees_settings
export DJANGO_SETTINGS_MODULE_DEBUG=True
export DJANGO_SETTINGS_MODULE_DATABASE_NAME=ubees
export DJANGO_SETTINGS_MODULE_DATABASE_USER=repad
export DJANGO_SETTINGS_MODULE_DATABASE_PASSWORD=FJ:!EA3I*bX#
export DJANGO_SETTINGS_MODULE_DATABASE_HOST=127.0.0.1
export DJANGO_SETTINGS_MODULE_DATABASE_PORT=5432
export DJANGO_SETTINGS_MODULE_EMAIL_HOST=mail.gandi.net
export DJANGO_SETTINGS_MODULE_EMAIL_HOST_USER=pcolmant@repanier.be
export DJANGO_SETTINGS_MODULE_EMAIL_HOST_PASSWORD=k30Nao#Ku8t:
export DJANGO_SETTINGS_MODULE_EMAIL_PORT=587
export DJANGO_SETTINGS_MODULE_EMAIL_USE_TLS=True
export DJANGO_SETTINGS_MODULE_ADMIN_NAME=bees
export DJANGO_SETTINGS_MODULE_ADMIN_EMAIL=repanier-adm@repanier.be
/home/pi/v1/bin/python /home/repad/v1/bees/manage.py close_orders

