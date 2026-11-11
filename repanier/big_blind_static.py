import logging
import posixpath

from django.contrib.staticfiles.storage import ManifestStaticFilesStorage

logger = logging.getLogger(__name__)


class BigBlindManifestStaticFilesStorage(ManifestStaticFilesStorage):
    """Hashed static urls (checksum cache busting) that never break rendering.

    Django's ManifestStaticFilesStorage raises ValueError when a name is
    missing from the manifest. This storage falls back instead:

    - a django-cms asset may live in a version suffixed directory
      (divio/django-cms#5860): retry with the version inserted, then strip
      the version segment from the resulting url;
    - anything else (fresh checkout, file referenced by a template but not
      collected, missing manifest during testing) falls back to the plain
      un-hashed static url.

    Compared to the previous version of this class, url() never returns
    None: rendering pages never breaks because of a static file.

    Since Django 5.1 the storage is activated through the STORAGES setting
    (see mysite/common_settings.py), not STATICFILES_STORAGE.
    """

    def url(self, name, force=True):
        try:
            return super().url(name, force)
        except ValueError:
            # The name may be a django-cms asset referenced without its
            # version directory (divio/django-cms#5860).
            try:
                import cms  # Setting dependent: import lazily
                from cms.utils.urlutils import static_with_version

                return (
                    super()
                    .url(static_with_version(name), force)
                    .replace("/%s/" % cms.__version__, "/")
                )
            except Exception:
                logger.warning('Static file "%s" not found in the manifest.', name)
                return posixpath.join(self.base_url, name)

    def hashed_name(self, name, content=None, filename=None):
        try:
            return super().hashed_name(name, content, filename)
        except ValueError:
            # Referenced by a template but not collected: keep the
            # un-hashed name, collectstatic must not fail.
            logger.warning('Static file "%s" could not be hashed.', name)
            return name
