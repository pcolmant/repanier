from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class BigBlindManifestStaticFilesStorage(ManifestStaticFilesStorage):

    def url(self, name, force=True):
        """
        Override .url to use hashed url in development
        """
        return super(ManifestStaticFilesStorage, self).url(name, True)