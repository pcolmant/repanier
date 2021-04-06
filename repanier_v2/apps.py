import logging
import sys
import time
from decimal import setcontext, DefaultContext, ROUND_HALF_UP

from django.apps import AppConfig
from django.conf import settings
from django.db import connection
# from django.utils.translation import ugettext_lazy as _

# DJANGO_IS_MIGRATION_RUNNING = "makemigrations" in sys.argv or "migrate" in sys.argv
# REPANIER_SETTINGS_AFTER_AMOUNT = None
# REPANIER_SETTINGS_BANK_ACCOUNT = None
# REPANIER_SETTINGS_CONFIG = None
# REPANIER_SETTINGS_CURRENCY_DISPLAY = None
# REPANIER_SETTINGS_CURRENCY_XLSX = None
# REPANIER_SETTINGS_DISPLAY_ANONYMOUS_ORDER_FORM = None
# REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO = None
# REPANIER_SETTINGS_HOME_SITE = None
# REPANIER_SETTINGS_MAX_WEEK_WO_PARTICIPATION = None
# REPANIER_SETTINGS_MEMBERSHIP_FEE = None
# REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION = None
# REPANIER_SETTINGS_NOTIFICATION = None
# REPANIER_SETTINGS_PAGE_BREAK_ON_CUSTOMER_CHECK = None
# REPANIER_SETTINGS_SALES_NAME = _("Sales")
# REPANIER_SETTINGS_ORDER_NAME = _("Sale")
# REPANIER_SETTINGS_ORDER_ON_NAME = _("Sale of ")
# REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_CUSTOMER = None
# REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_CUSTOMER = None
# REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_PRODUCER = None
# REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_BOARD = None
# REPANIER_SETTINGS_VAT_ID = None

logger = logging.getLogger(__name__)


class RepanierConfig(AppConfig):
    name = "repanier_v2"
    verbose_name = "Repanier"

    def ready(self):
        import repanier_v2.signals  # noqa

        # https://docs.python.org/3/library/decimal.html#working-with-threads
        DefaultContext.rounding = ROUND_HALF_UP
        setcontext(DefaultContext)

        # If PostgreSQL service is not started the const may not be set
        # Django doesn't complain
        # This happens when the server starts at power up
        # first launching uwsgi before PostgreSQL
        db_started = False
        while not db_started:
            try:
                db_started = connection.cursor() is not None
            except Exception:
                logger.info("Waiting for database connection")
                time.sleep(1)

        # Imports are inside the function because its point is to avoid importing
        # the models when django.contrib."MODELS" isn't installed.

        from repanier_v2.models.configuration import Configuration
        from repanier_v2.models.notification import Notification
        from repanier_v2.const import DECIMAL_ONE

        try:
            # Create if needed and load RepanierSettings var when performing config.save()
            notification = Notification.objects.filter(id=DECIMAL_ONE).first()
            if notification is None:
                notification = Notification.objects.create()
            notification.save()

            config = Configuration.init_repanier()

            if not settings.DEBUG:
                from repanier_v2.email.email import RepanierEmail

                RepanierEmail.send_startup_email(sys.argv[0])

        except Exception as error_str:
            logger.error("##################################")
            logger.error(error_str)
            logger.error("##################################")
