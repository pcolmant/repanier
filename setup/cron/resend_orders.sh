# sudo chown www-data:www-data resend_orders.sh
# sudo chmod +x resend_orders.sh
# sudo -u www-data ./resend_orders.sh

# Do not forget to change chmod +x on this .sh file
DIR=$( cd "$( dirname "${0}" )" && pwd )
$DIR/../../_1_venv/bin/python $DIR/../manage.py resend_orders "$@"
