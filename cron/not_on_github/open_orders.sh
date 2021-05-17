# sudo chown www-data:www-data close_orders.sh
# sudo chmod +x close_orders.sh
# sudo crontab -u www-data -e
# Every hour/5'
# 5 */1 * * * /home/pi/v1/ptidej/cron/close_orders.sh
# Each thuesday at 20:05
# 5 20 * * 2 /home/repad/v1/ptidej/cron/backup_db.sh

# Do not forget to change chmod +x on this .sh file
DIR=$( cd "$( dirname "${0}" )" && pwd )
$DIR/../../bin/python $DIR/../manage.py open_orders
