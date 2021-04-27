# sudo chown www-data:www-data delete_pending_purchases.sh
# sudo chmod +x delete_pending_purchases.sh
# sudo crontab -u www-data -e
# Every hour/5'
# 5 */1 * * * /home/repanier/prd1/_0_prd_example/cron/delete_pending_purchases.sh

# Do not forget to change chmod +x on this .sh file
DIR=$( cd "$( dirname "${0}" )" && pwd )
$DIR/../../../../venvs/_a_/bin/python $DIR/../manage.py delete_pending_purchases
