#!/usr/bin/env bash
set -euo pipefail

# sudo chown www-data:www-data close_orders.sh
# sudo chmod +x close_orders.sh
# sudo crontab -u www-data -e
# Every 10 minutes. Stagger the start minute for each site.
# 1,11,21,31,41,51 * * * * /home/repaad/_3_prd_lelensois/cron/close_orders.sh

DIR=$(cd "$(dirname "${0}")" && pwd)
SITE_DIR=$(cd "$DIR/.." && pwd)
SITE_NAME=$(basename "$SITE_DIR")
LOCK_FILE="/tmp/repanier_close_orders_${SITE_NAME}.lock"

exec 200>"$LOCK_FILE"
flock -n 200 || exit 0

"$DIR/../../_1_venv/bin/python" "$SITE_DIR/manage.py" close_orders