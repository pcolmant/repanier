"""Tests of the compile_po management command.

``compilemessages`` requires GNU gettext (msgfmt) on the PATH, which is
not available on every Windows host. ``compile_po`` is a pure Python
replacement: it must read the .po files like msgfmt does - multi-line
strings, escape sequences, plural forms - skip what msgfmt skips
(obsolete blocks, fuzzy entries) and write standard .mo catalogs that
Python's own gettext module loads back correctly.
"""
import gettext
import struct
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase

from repanier.management.commands.compile_po import parse_po, write_mo

HEADER = (
    'msgid ""\n'
    'msgstr ""\n'
    '"Project-Id-Version: PACKAGE VERSION\\n"\n'
    '"Content-Type: text/plain; charset=UTF-8\\n"\n'
    '"Plural-Forms: nplurals=2; plural=(n > 1);\\n"\n'
)


def write_po(path, body):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(HEADER + body, encoding="utf-8")


class ParsePoTest(SimpleTestCase):
    """The parser must read a .po the way msgfmt reads it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.po = Path(self.tmp.name) / "django.po"

    def test_multiline_and_escaped_strings(self):
        write_po(
            self.po,
            'msgid "A \\"quoted\\" word"\n'
            'msgstr "Un mot \\"cité\\""\n'
            "\n"
            'msgid "on two lines"\n'
            'msgstr ""\n'
            '"sur deux\\n"\n'
            '"lignes"\n',
        )
        entries = dict(parse_po(self.po))
        self.assertEqual(entries['A "quoted" word'], 'Un mot "cité"')
        self.assertEqual(entries["on two lines"], "sur deux\nlignes")

    def test_plural_entries_are_stored_the_gnu_way(self):
        write_po(
            self.po,
            'msgid "one apple"\n'
            'msgid_plural "several apples"\n'
            'msgstr[0] "une pomme"\n'
            'msgstr[1] "plusieurs pommes"\n',
        )
        entries = dict(parse_po(self.po))
        self.assertEqual(
            entries["one apple\x00several apples"],
            "une pomme\x00plusieurs pommes",
        )

    def test_obsolete_blocks_are_skipped(self):
        write_po(
            self.po,
            "#~ msgid \"old\"\n"
            "#~ msgstr \"vieux\"\n"
            "\n"
            'msgid "new"\n'
            'msgstr "nouveau"\n',
        )
        entries = dict(parse_po(self.po))
        self.assertNotIn("old", entries)
        self.assertEqual(entries["new"], "nouveau")

    def test_an_obsolete_block_glued_to_a_real_entry_keeps_it(self):
        # No blank line between the obsolete block and the next entry:
        # the real msgid must not be swallowed by the #~ block.
        write_po(
            self.po,
            "#~ msgid \"old\"\n"
            "#~ msgstr \"vieux\"\n"
            'msgid "new"\n'
            'msgstr "nouveau"\n',
        )
        entries = dict(parse_po(self.po))
        self.assertNotIn("old", entries)
        self.assertEqual(entries["new"], "nouveau")

    def test_fuzzy_entries_are_skipped_but_not_the_header(self):
        write_po(
            self.po,
            "#, fuzzy\n"
            'msgid "still unsure"\n'
            'msgstr "pas certain"\n'
            "\n"
            'msgid "sure"\n'
            'msgstr "certain"\n',
        )
        # Replace the plain header with a fuzzy one: it must survive.
        write_po(
            self.po,
            "#, fuzzy\n"
            + HEADER
            + "#, fuzzy\n"
            + 'msgid "still unsure"\n'
            + 'msgstr "pas certain"\n',
        )
        entries = dict(parse_po(self.po))
        self.assertNotIn("still unsure", entries)
        self.assertIn("", entries)
        self.assertIn("Plural-Forms", entries[""])

    def test_utf8_accents_survive_the_round_trip(self):
        write_po(
            self.po,
            'msgid "This permanence will be cancelled."\n'
            'msgstr "Cette permanence sera annulée."\n',
        )
        self.assertEqual(
            dict(parse_po(self.po))["This permanence will be cancelled."],
            "Cette permanence sera annulée.",
        )

    def test_untranslated_entries_are_skipped(self):
        # msgfmt leaves them out of the .mo. An empty translation must
        # never shadow the msgid: the English admin catalog of Django
        # carries empty msgstrs by design, and mapping them into the
        # .mo once emptied the "History" label of a translated screen.
        write_po(
            self.po,
            'msgid "History"\n'
            'msgstr ""\n'
            "\n"
            'msgid "translated"\n'
            'msgstr "traduit"\n',
        )
        entries = dict(parse_po(self.po))
        self.assertNotIn("History", entries)
        self.assertEqual(entries["translated"], "traduit")


class WriteMoTest(SimpleTestCase):
    """The .mo output must be a standard GNU gettext catalog."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mo = Path(self.tmp.name) / "django.mo"

    def load(self):
        with open(self.mo, "rb") as mo_file:
            return gettext.GNUTranslations(mo_file)

    def test_the_catalog_translates_and_chooses_the_plural(self):
        items = [
            ("", "Content-Type: text/plain; charset=UTF-8\nPlural-Forms: nplurals=2; plural=(n > 1);\n"),
            ("one apple\x00several apples", "une pomme\x00plusieurs pommes"),
            ("This permanence will be cancelled.", "Cette permanence sera annulée."),
        ]
        write_mo(items, self.mo)
        catalog = self.load()
        self.assertEqual(
            catalog.gettext("This permanence will be cancelled."),
            "Cette permanence sera annulée.",
        )
        self.assertEqual(catalog.ngettext("one apple", "several apples", 1), "une pomme")
        self.assertEqual(
            catalog.ngettext("one apple", "several apples", 2), "plusieurs pommes"
        )

    def test_the_binary_layout_is_the_gnu_one(self):
        write_mo([("", "Content-Type: text/plain; charset=UTF-8\nPlural-Forms: nplurals=2; plural=(n > 1);\n")], self.mo)
        with open(self.mo, "rb") as mo_file:
            magic, revision, count = struct.unpack("<3I", mo_file.read(12))
        self.assertEqual(magic, 0x950412DE)
        self.assertEqual(revision, 0)
        self.assertEqual(count, 1)  # the header only


class CompilePoCommandTest(SimpleTestCase):
    """End to end: call_command compiles a locale directory."""

    def test_the_command_compiles_a_locale_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            po_dir = Path(tmp) / "fr" / "LC_MESSAGES"
            write_po(
                po_dir / "django.po",
                'msgid "This permanence will be cancelled."\n'
                'msgstr "Cette permanence sera annulée."\n',
            )
            mo_path = po_dir / "django.mo"
            self.assertFalse(mo_path.exists())
            stdout = StringIO()
            call_command("compile_po", tmp, stdout=stdout)
            self.assertTrue(mo_path.exists())
            self.assertIn("1 messages", stdout.getvalue())
            with open(mo_path, "rb") as mo_file:
                catalog = gettext.GNUTranslations(mo_file)
            self.assertEqual(
                catalog.gettext("This permanence will be cancelled."),
                "Cette permanence sera annulée.",
            )

    def test_the_default_targets_the_project_catalogs_only(self):
        # The default (no argument) must never walk site-packages, even
        # when the virtual environment lives inside the project tree.
        from django.apps import apps as django_apps
        from django.conf import settings

        with mock.patch(
            "repanier.management.commands.compile_po.django_apps"
        ) as fake_apps:
            fake_apps.get_app_configs.return_value = [
                app
                for app in django_apps.get_app_configs()
                if "site-packages" in Path(app.path).parts
            ] + [
                # A fake local app next to the settings
                mock.Mock(path=str(Path(settings.PROJECT_DIR) / "repanier"))
            ]
            with mock.patch(
                "repanier.management.commands.compile_po.settings"
            ) as fake_settings:
                fake_settings.LOCALE_PATHS = [
                    str(Path(settings.PROJECT_DIR) / "locale")
                ]
                from repanier.management.commands import compile_po

                paths = compile_po.Command().default_locale_paths()
        for path in paths:
            self.assertNotIn("site-packages", Path(path).parts)
        self.assertTrue(
            any(path == str(Path(settings.PROJECT_DIR) / "locale") for path in paths)
        )
