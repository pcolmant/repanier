"""The translation catalogs committed with the repository are compiled.

mysite/locale/fr/LC_MESSAGES/django.mo is loaded at runtime through
LOCALE_PATHS: it carries the django CMS template names, placeholder
names and help menu entries configured in mysite/common_settings.py.
A .po edited without recompiling the .mo silently falls back to
English in the CMS: these tests catch it in CI.
"""
import gettext
import struct
from pathlib import Path

from django.conf import settings
from django.test import TestCase


class MysiteCatalogTest(TestCase):
    """The project-level catalog must translate the CMS strings."""

    def setUp(self):
        locale_dir = Path(settings.LOCALE_PATHS[0]) / "fr" / "LC_MESSAGES"
        self.mo = locale_dir / "django.mo"
        self.po = locale_dir / "django.po"

    def test_the_catalog_translates_the_cms_strings(self):
        with open(self.mo, "rb") as f:
            catalog = gettext.GNUTranslations(f)
        expected = {
            "Home page": "Page d'accueil",
            "Internal page": "Page interne",
            "Internal page with menu on left": "Page interne avec menu à gauche",
            "Hero": "Bannière",
            "Column 1": "Colonne 1",
            "Column 2": "Colonne 2",
            "Column 3": "Colonne 3",
            "Content": "Contenu",
            "Footer": "Pied de page",
            "Repanier guide": "Mode d'emploi de Repanier",
            "django CMS guide": "Mode d'emploi de Django CMS",
        }
        for msgid, msgstr in expected.items():
            self.assertEqual(
                catalog.gettext(msgid),
                msgstr,
                "%s is untranslated in %s: the .po was edited without "
                "recompiling the .mo" % (msgid, self.mo),
            )

    def test_every_translation_of_the_po_lives_in_the_compiled_mo(self):
        # An entry count of 1 means an empty catalog: only the header.
        po_entries = 0
        with open(self.po, encoding="utf-8") as f:
            for line in f:
                # "#~" lines are obsolete entries, ignored by msgfmt
                if line.startswith("msgid ") and not line.startswith('msgid ""'):
                    po_entries += 1
        with open(self.mo, "rb") as f:
            data = f.read()
        magic, _revision, mo_entries = struct.unpack("<3I", data[:12])
        self.assertEqual(magic, 0x950412DE)
        self.assertEqual(
            mo_entries,
            po_entries + 1,  # + the header entry
            "The compiled catalog of %s is out of sync with its .po: "
            "recompile the .mo" % self.mo,
        )
