import logging
import threading

from django.db import close_old_connections

logger = logging.getLogger(__name__)


def start_background_task(name, target, *args, **kwargs):
    def run():
        close_old_connections()
        try:
            target(*args, **kwargs)
        except Exception:
            logger.exception("Background task %s failed", name)
        finally:
            close_old_connections()

    thread = threading.Thread(target=run, name=name)
    thread.start()
    return thread
