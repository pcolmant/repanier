# sudo chown www-data:www-data backup_db.sh
# sudo chmod +x backup_db.sh
# sudo crontab -u www-data -e
# Every day at 1:25
# 25 01 * * * /home/repanier/prd1/_0_prd_example/cron/backup_db.sh

# Do not forget to change chmod +x on this .sh file
DIR=$( cd "$( dirname "${0}" )" && pwd )
$DIR/../../bin/python $DIR/../manage.py backup_db

