from django.contrib.staticfiles.storage import ManifestStaticFilesStorage
from cms.utils.urlutils import static_with_version
import cms
__version__ = "/%s" % cms.__version__

class BigBlindManifestStaticFilesStorage(ManifestStaticFilesStorage):

    def url(self, context, force=True):
        """
        Override .url to use hashed url in development
        """
        try:
            return super(ManifestStaticFilesStorage, self).url(context, True)
        except ValueError:
            # Solve the reverted https://github.com/divio/django-cms/pull/5860/
            context = static_with_version(context)
            return super(ManifestStaticFilesStorage, self).url(context, True).replace(__version__, "")
