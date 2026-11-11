"""Tests of the BigBlind static files storage.

The storage must produce hashed (cache busting) urls when the manifest
knows the file, and NEVER break rendering when it does not: the plain
un-hashed url is served instead of raising or returning None.
"""
from django.test import SimpleTestCase

from repanier.big_blind_static import BigBlindManifestStaticFilesStorage


class BigBlindStorageFallbackTest(SimpleTestCase):
    def setUp(self):
        self.storage = BigBlindManifestStaticFilesStorage()

    def test_missing_manifest_entry_falls_back_to_the_plain_url(self):
        # No collectstatic has been (necessarily) run, and this name does
        # not exist anyway: rendering must not raise, and must not return
        # None (the old class could).
        self.assertEqual(
            self.storage.url("does/not/exist.css"),
            "/static/does/not/exist.css",
        )

    def test_hashed_name_of_a_missing_file_stays_unchanged(self):
        # collectstatic must never fail because a template references a
        # file that is not collected.
        self.assertEqual(
            self.storage.hashed_name("does/not/exist.css"),
            "does/not/exist.css",
        )

    def test_cms_asset_without_version_directory_falls_back(self):
        # The django-cms retries with the version directory inserted;
        # when nothing is found either, the plain url is still served.
        self.assertTrue(
            self.storage.url("cms/does/not/exist.css").endswith("/cms/does/not/exist.css")
        )

    def test_source_map_rewriting_patterns_are_dropped(self):
        # The vendored minified libraries reference their source maps,
        # which are not shipped: collectstatic must not try to hash them
        # (a warning was emitted per reference at every run).
        # In Django 5.2 a pattern entry is either a bare regex string or
        # a (regex, template) tuple.
        for extension, file_patterns in BigBlindManifestStaticFilesStorage.patterns:
            for entry in file_patterns:
                regex = entry if isinstance(entry, str) else entry[0]
                self.assertNotIn("sourceMappingURL", regex)
        # The css and js rewriting patterns (url(), @import) stay intact.
        regexes = [
            entry if isinstance(entry, str) else entry[0]
            for extension, file_patterns in BigBlindManifestStaticFilesStorage.patterns
            for entry in file_patterns
        ]
        joined = " ".join(regexes)
        self.assertIn("url\(", joined)
        self.assertIn("@import", joined)
