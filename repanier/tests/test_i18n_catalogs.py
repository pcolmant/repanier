"""The translation catalogs committed with the repository are compiled.

mysite/locale/fr/LC_MESSAGES/django.mo is loaded at runtime through
LOCALE_PATHS: it carries the django CMS template names, placeholder
names and help menu entries configured in mysite/common_settings.py.
A .po edited without recompiling the .mo silently falls back to
English in the CMS: these tests catch it in CI.

The nl and de catalogs are fully translated: the same sync checks
apply to them.
"""
import gettext
import struct
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.utils import translation


def count_expected_mo_entries(po_path):
    """msgfmt keeps the header and drops the empty translations.

    Returns the number of entries a freshly compiled .mo must carry.
    An entry with msgid plural forms counts as soon as one form is
    translated.
    """
    entries = []  # (msgid, translated)
    current_id = []
    translated = [False]
    mode = None
    is_header = [True]
    with open(po_path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n").rstrip("\r")
            if line.startswith("msgid "):
                if mode is not None:
                    entries.append(("".join(current_id), translated[0]))
                current_id = [line[6:].strip('"')]
                translated = [False]
                mode = "id"
            elif line.startswith("msgstr") and mode:
                # msgstr "..." or msgstr[0] "..." (plural forms)
                payload = line.split('"', 1)[1].rstrip('"') if '"' in line else ""
                if payload:
                    translated[0] = True
                mode = "str"
            elif line.startswith('"') and mode:
                # continuation of a multi line msgid or msgstr
                if mode == "id":
                    current_id.append(line.strip('"'))
                elif line.strip('"'):
                    translated[0] = True
        if mode:
            entries.append(("".join(current_id), translated[0]))
    expected = 0
    seen = set()
    for index, (msgid, translated_flag) in enumerate(entries):
        if msgid in seen:
            # msgfmt keeps one translation per msgid
            continue
        seen.add(msgid)
        if index == 0 and not msgid:
            # the header is always kept
            expected += 1
        elif translated_flag:
            expected += 1
    return expected


def count_mo_entries(mo_path):
    with open(mo_path, "rb") as f:
        data = f.read()
    magic, _revision, mo_entries = struct.unpack("<3I", data[:12])
    if magic != 0x950412DE:
        raise AssertionError("not a GNU mo file: %s" % mo_path)
    return mo_entries


def assert_mo_in_sync(testcase, po_path):
    mo_path = po_path.with_suffix(".mo")
    if not mo_path.exists():
        raise AssertionError("missing compiled catalog: %s" % mo_path)
    testcase.assertEqual(
        count_mo_entries(mo_path),
        count_expected_mo_entries(po_path),
        "The compiled catalog of %s is out of sync with its .po: "
        "recompile the .mo" % mo_path,
    )


class MysiteCatalogTest(TestCase):
    """The project-level catalog must translate the CMS strings."""

    def setUp(self):
        locale_dir = Path(settings.LOCALE_PATHS[0]) / "fr" / "LC_MESSAGES"
        self.mo = locale_dir / "django.mo"
        self.po = locale_dir / "django.po"

    def test_the_cms_template_names_translate_at_display_time(self):
        # common_settings.py wraps gettext_lazy: the template names stay
        # lazy proxies and resolve with the language of the current user,
        # not at settings import.
        from django.utils.functional import Promise

        name = dict(settings.CMS_TEMPLATES)[settings.CMS_TEMPLATE_HOME]
        self.assertIsInstance(name, Promise)
        with translation.override("en"):
            self.assertEqual(str(name), "Home page")
        with translation.override("fr"):
            self.assertEqual(str(name), "Page d'accueil")
            self.assertEqual(
                str(dict(settings.CMS_TEMPLATES)[settings.CMS_TEMPLATE_PAGE]),
                "Page interne",
            )
            self.assertEqual(
                str(dict(settings.CMS_TEMPLATES)[settings.CMS_TEMPLATE_SUB_PAGE]),
                "Page interne avec menu à gauche",
            )

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
        assert_mo_in_sync(self, self.po)


class DutchAndGermanCatalogsTest(TestCase):
    """The nl and de catalogs carry the full set of the repanier strings.

    The Dutch and German catalogs were produced in one go, deliberately
    glossary driven (permanence = uitdeling / Verteilung, membership fee
    = lidgeld / Mitgliedsbeitrag, ...): these tests pin the glossary and
    catch .po / .mo drift like the French ones do.
    """

    CATALOGS = (
        ("repanier", "django"),
        ("repanier", "djangojs"),
        ("mysite", "django"),
        ("mysite", "djangojs"),
    )

    def app_dir(self, app):
        index = 0 if app == "mysite" else 1
        return Path(settings.LOCALE_PATHS[index])

    def load_mo(self, app, domain, lang):
        mo_path = self.app_dir(app) / lang / "LC_MESSAGES" / ("%s.mo" % domain)
        with open(mo_path, "rb") as f:
            return gettext.GNUTranslations(f)

    def test_every_catalog_is_compiled_and_in_sync(self):
        for app, domain in self.CATALOGS:
            for lang in ("nl", "de"):
                po_path = (
                    self.app_dir(app) / lang / "LC_MESSAGES" / ("%s.po" % domain)
                )
                assert_mo_in_sync(self, po_path)

    def test_the_glossary_of_the_repanier_catalog(self):
        expected = {
            "nl": {
                "Permanence": "Uitdeling",
                "Permanences": "Uitdelingen",
                "Membership fee": "Lidgeld",
                "Customer": "Klant",
                "My cart": "Mijn mandje",
                "Delivery point": "Leveringspunt",
                "Deposit": "Statiegeld",
                "Rule of 3": "Regel van drie",
            },
            "de": {
                "Permanence": "Verteilung",
                "Permanences": "Verteilungen",
                "Membership fee": "Mitgliedsbeitrag",
                "Customer": "Kunde",
                "My cart": "Mein Warenkorb",
                "Delivery point": "Lieferpunkt",
                "Deposit": "Pfand",
                "Rule of 3": "Dreisatz",
            },
        }
        for lang, entries in expected.items():
            catalog = self.load_mo("repanier", "django", lang)
            for msgid, msgstr in entries.items():
                self.assertEqual(
                    catalog.gettext(msgid),
                    msgstr,
                    "%s is wrong in the %s catalog" % (msgid, lang),
                )

    def test_the_mysite_catalog_translates_the_cms_template_names(self):
        for lang, footer, home in (
            ("nl", "Voettekst", "Startpagina"),
            ("de", "Fußzeile", "Startseite"),
        ):
            catalog = self.load_mo("mysite", "django", lang)
            self.assertEqual(catalog.gettext("Footer"), footer)
            self.assertEqual(catalog.gettext("Home page"), home)

    def test_the_mysite_javascript_catalog_translates_the_admin_widgets(self):
        # Sourced from the official catalogs of django and of the third
        # party packages: Same, Now, ...
        for lang, now in (("nl", "Nu"), ("de", "Jetzt")):
            catalog = self.load_mo("mysite", "djangojs", lang)
            self.assertEqual(catalog.gettext("Now"), now)
