# sudo chown www-data:www-data close_orders.sh
# sudo chmod +x close_orders.sh
# sudo crontab -u www-data -e
# Each thuesday at 20:05
# 5 20 * * 2 /home/repanier/prd1/_0_prd_example/cron/close_orders.sh

# Do not forget to change chmod +x on this .sh file
DIR=$( cd "$( dirname "${0}" )" && pwd )
$DIR/../../../../venvs/_a_/bin/python $DIR/../manage.py close_orders
