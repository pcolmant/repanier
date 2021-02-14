import logging
import sys
import time
from decimal import setcontext, DefaultContext, ROUND_HALF_UP

from django.apps import AppConfig
from django.conf import settings
from django.db import connection
from django.utils import translation


logger = logging.getLogger(__name__)


class RepanierConfig(AppConfig):
    name = "repanier"
    verbose_name = "Repanier"

    def ready(self):
        import repanier.signals  # noqa

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

        from repanier.models.configuration import Configuration
        from repanier.models.notification import Notification
        from repanier.const import DECIMAL_ONE

        # try:
        # Create if needed and load RepanierSettings var when performing config.save()
        translation.activate(settings.LANGUAGE_CODE)

        notification = Notification.objects.filter(id=DECIMAL_ONE).first()
        if notification is None:
            notification = Notification.objects.create()
        notification.save()

        config = Configuration.init_repanier()

        if not settings.DEBUG:
            from repanier.email.email import RepanierEmail

            RepanierEmail.send_startup_email(sys.argv[0])

        # except Exception as error_str:
        #     logger.error("##################################")
        #     logger.error(error_str)
        #     logger.error("##################################")
