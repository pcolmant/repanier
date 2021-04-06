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
            try:
                if context == "djangocms_text_ckeditor/js/dist/bundle-45a646fecc.cms.ckeditor.min.js":
                    context = "djangocms_text_ckeditor/js/dist/bundle-bca0d2d3f4.cms.ckeditor.min.js"
                try:
                    return super(ManifestStaticFilesStorage, self).url(context, True)
                except ValueError:
                    # Solve the reverted https://github.com/divio/django-cms/pull/5860/
                    new_context = static_with_version(context)
                    return super(ManifestStaticFilesStorage, self).url(new_context, True).replace(__version__, "")
            except:
                if context == "djangocms_text_ckeditor/js/dist/bundle-bca0d2d3f4.cms.ckeditor.min.js":
                    context = "djangocms_text_ckeditor/js/dist/bundle-45a646fecc.cms.ckeditor.min.js"
                try:
                    return super(ManifestStaticFilesStorage, self).url(context, True)
                except ValueError:
                    # Solve the reverted https://github.com/divio/django-cms/pull/5860/
                    new_context = static_with_version(context)
                    return super(ManifestStaticFilesStorage, self).url(new_context, True).replace(__version__, "")
        except:
            pass
