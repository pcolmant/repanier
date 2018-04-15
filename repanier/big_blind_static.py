import cms
from cms.utils.urlutils import static_with_version
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage

__version__ = "/{}".format(cms.__version__)


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
            try:
                return super(ManifestStaticFilesStorage, self).url(context, True).replace(__version__, "")
            except ValueError:
                if context == "djangocms_text_ckeditor/js/dist/bundle-45a646fecc.cms.ckeditor.min.js":
                    context = "djangocms_text_ckeditor/js/dist/bundle-bca0d2d3f4.cms.ckeditor.min.js"
                return super(ManifestStaticFilesStorage, self).url(context, True).replace(__version__, "")
