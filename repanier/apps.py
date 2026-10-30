import logging
import sys
import time
import warnings
from decimal import setcontext, DefaultContext, ROUND_HALF_UP

from django.apps import AppConfig
from django.conf import settings
from django.db import connection
from django.utils import translation
from django.utils.translation import gettext_lazy as _

# --- SOLUTION GLOBALE ---
# On ignore globalement cet avertissement précis dès le chargement du module
warnings.filterwarnings(
    "ignore",
    message="Accessing the database during app initialization is discouraged.",
    category=RuntimeWarning,
)

logger = logging.getLogger(__name__)

DJANGO_IS_MIGRATION_RUNNING = "makemigrations" in sys.argv or "migrate" in sys.argv
REPANIER_SETTINGS_AFTER_AMOUNT = None
REPANIER_SETTINGS_BANK_ACCOUNT = None
REPANIER_SETTINGS_CONFIG = None
REPANIER_SETTINGS_CURRENCY_DISPLAY = None
REPANIER_SETTINGS_CURRENCY_XLSX = None
REPANIER_SETTINGS_DISPLAY_ANONYMOUS_ORDER_FORM = None
REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO = None
REPANIER_SETTINGS_HOME_SITE = None
REPANIER_SETTINGS_MAX_WEEK_WO_PARTICIPATION = None
REPANIER_SETTINGS_MEMBERSHIP_FEE = None
REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION = None
REPANIER_SETTINGS_NOTIFICATION = None
REPANIER_SETTINGS_PERMANENCES_NAME = _("Permanences")
REPANIER_SETTINGS_PERMANENCE_ON_NAME = _("Permanence on ")
REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_CUSTOMER = None
REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_CUSTOMER = None
REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_BOARD = None
REPANIER_SETTINGS_VAT_ID = None


class RepanierConfig(AppConfig):
    name = "repanier"
    verbose_name = "Repanier"

    def ready(self):
        import repanier.signals  # noqa

        # https://docs.python.org/3/library/decimal.html#working-with-threads
        DefaultContext.rounding = ROUND_HALF_UP
        setcontext(DefaultContext)

        # Boucle de sécurité pour s'assurer que PostgreSQL est prêt
        db_started = False
        while not db_started:
            try:
                db_started = connection.cursor() is not None
            except Exception:
                logger.info("Waiting for database connection")
                print("---- repanier:apps.py - ready : Waiting for database connection")
                time.sleep(1)

        try:
            from repanier.models.configuration import Configuration
            from repanier.models.notification import Notification
            from repanier.const import DECIMAL_ONE

            translation.activate(settings.LANGUAGE_CODE)

            notification = Notification.objects.filter(id=DECIMAL_ONE).first()
            if notification is None:
                notification = Notification.objects.create()
            notification.save()

            Configuration.init_repanier()

            if not settings.DEBUG:
                from repanier.email.email import RepanierEmail
                RepanierEmail.send_startup_email(sys.argv[0])

        except Exception as error_str:
            logger.error("##################################")
            logger.error(error_str)
            logger.error("##################################")