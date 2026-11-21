"""Compile the .po translation catalogs into .mo without GNU gettext.

``django-admin compilemessages`` requires ``msgfmt`` on the PATH, which is
rarely available on plain Windows hosts. This command parses the .po files
directly and writes the .mo binaries in pure Python. The produced files are
standard GNU gettext catalogs (verified against real compilemessages output
and readable with Python's own gettext module).

Obsolete entries (#~) are skipped, exactly like msgfmt does.
"""
import struct
from pathlib import Path

from django.apps import apps as django_apps
from django.conf import settings
from django.core.management.base import BaseCommand

MO_MAGIC = 0x950412DE


def _unquote(po_string):
    """'a \\\"quoted\\\" string' -> the python string it denotes."""
    assert po_string.startswith('"') and po_string.endswith('"'), po_string
    body = po_string[1:-1]
    out = []
    i = 0
    while i < len(body):
        char = body[i]
        if char == "\\":
            escaped = body[i + 1]
            out.append(
                {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}.get(
                    escaped, escaped
                )
            )
            i += 2
        else:
            out.append(char)
            i += 1
    return "".join(out)


def parse_po(po_path):
    """Parse a .po file into a list of (msgid, msgstr) pairs.

    Plural entries are stored the GNU way, as ``(msgid + msgid_plural,
    msgstr[0] + msgstr[1] ...)`` joined by NUL bytes. Obsolete (#~) blocks
    and fuzzy entries are skipped, exactly like msgfmt does - with the
    exception of the header (the empty msgid), which is always kept even
    when it carries the "#, fuzzy" flag produced by xgettext. Untranslated
    entries, whose msgstr is empty, are skipped too: a compiled catalog
    must never map a msgid to an empty string that shadows the msgid.
    """
    entries = []
    cur_id = None
    cur_plural = None
    cur_strs = []
    # "id" | "plural" | "str" | None (outside of any message field)
    mode = None
    obsolete = False
    fuzzy = False
    have_entry = False

    def flush():
        nonlocal cur_id, cur_plural, cur_strs, mode
        nonlocal obsolete, fuzzy, have_entry
        # In a .po file a blank line always closes the current entry:
        # flush unconditionally there, and drop what msgfmt drops
        # (obsolete blocks, fuzzy entries - except a fuzzy header -
        # and untranslated entries, whose msgstr is empty: msgfmt
        # leaves them out of the .mo, and an empty translation MUST NOT
        # shadow the msgid of another application - the English admin
        # catalog of Django carries empty msgstrs by design).
        if not (have_entry and cur_id is not None):
            pass
        elif obsolete or (fuzzy and cur_id != ""):
            pass
        elif cur_plural is not None:
            if any(cur_strs):
                entries.append(
                    (cur_id + "\x00" + cur_plural, "\x00".join(cur_strs))
                )
        elif cur_strs and cur_strs[0]:
            entries.append((cur_id, cur_strs[0]))
        cur_id, cur_plural, cur_strs = None, None, []
        mode, obsolete, fuzzy, have_entry = None, False, False, False

    pending_fuzzy = False
    with open(po_path, encoding="utf-8") as po_file:
        for raw_line in po_file:
            line = raw_line.strip()
            if not line:
                flush()
                continue
            if line.startswith("#"):
                if line.startswith("#~"):
                    # An obsolete block acts as an entry for the
                    # bookkeeping (flushed then discarded), so that a
                    # real msgid glued to the block is not mistaken
                    # as part of it.
                    obsolete = True
                    have_entry = True
                elif line.startswith("#,") and "fuzzy" in {
                    flag.strip() for flag in line[2:].split(",")
                }:
                    pending_fuzzy = True
                # Other comment lines (translator notes, references,
                # flags) are ignored.
                continue
            if line.startswith("msgid "):
                if have_entry:
                    flush()
                fuzzy = pending_fuzzy
                pending_fuzzy = False
                cur_id = _unquote(line[6:].strip())
                mode = "id"
                have_entry = True
            elif line.startswith("msgid_plural "):
                cur_plural = _unquote(line[12:].strip())
                mode = "plural"
            elif line.startswith("msgstr"):
                token = line[6:].strip()
                if token.startswith("["):
                    close = token.index("]")
                    index = int(token[1:close])
                    rest = token[close + 1 :].strip()
                else:
                    index = 0
                    rest = token
                while len(cur_strs) <= index:
                    cur_strs.append("")
                cur_strs[index] = _unquote(rest)
                mode = "str"
            elif line.startswith('"'):
                piece = _unquote(line)
                if mode == "id":
                    cur_id += piece
                elif mode == "plural":
                    cur_plural = (cur_plural or "") + piece
                elif mode == "str":
                    cur_strs[-1] += piece
    flush()
    return entries


def write_mo(items, mo_path):
    """Write the (msgid, msgstr) pairs as a GNU gettext .mo catalog."""
    # The header entry (empty msgid) comes first, the rest is sorted so
    # that the binary lookup of the catalog stays consistent.
    header = dict(items).get("")
    ordered = sorted((k, v) for k, v in items if k != "")
    catalog = [("", header)] if header is not None else []
    catalog += ordered

    count = len(catalog)
    original_table_offset = 7 * 4
    translation_table_offset = original_table_offset + 8 * count
    data_offset = translation_table_offset + 8 * count
    # The offsets of the translations must skip the WHOLE block of the
    # originals, not only the ones written so far.
    originals_length = sum(len(k.encode("utf-8")) + 1 for k, _ in catalog)

    ids_blob = b""
    strings_blob = b""
    original_rows = b""
    translation_rows = b""
    for msgid, msgstr in catalog:
        msgid_bytes = msgid.encode("utf-8")
        msgstr_bytes = msgstr.encode("utf-8")
        original_rows += struct.pack(
            "<II", len(msgid_bytes), data_offset + len(ids_blob)
        )
        ids_blob += msgid_bytes + b"\x00"
        translation_rows += struct.pack(
            "<II",
            len(msgstr_bytes),
            data_offset + originals_length + len(strings_blob),
        )
        strings_blob += msgstr_bytes + b"\x00"

    with open(mo_path, "wb") as mo_file:
        mo_file.write(
            struct.pack(
                "<IiiIIII",
                MO_MAGIC,
                0,
                count,
                original_table_offset,
                translation_table_offset,
                data_offset,
                0,
            )
        )
        mo_file.write(original_rows)
        mo_file.write(translation_rows)
        mo_file.write(ids_blob)
        mo_file.write(strings_blob)


def compile_catalog(po_path):
    """Compile one .po file into the .mo sitting next to it.

    Returns the number of compiled messages, the header entry excluded.
    """
    entries = parse_po(po_path)
    # On duplicated msgids msgfmt keeps the first one; a well formed
    # catalog has no duplicates at all.
    dedup = dict(reversed(entries))
    mo_path = po_path.with_suffix(".mo")
    write_mo(list(dedup.items()), mo_path)
    return len(dedup) - (1 if "" in dedup else 0)


class Command(BaseCommand):
    help = (
        "Compile the .po translation catalogs into .mo without GNU gettext "
        "(pure Python replacement for compilemessages). By default it walks "
        "the locale directories of LOCALE_PATHS and of the local "
        "applications; pass one or more locale directory paths to compile "
        "them instead."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "locale_paths",
            nargs="*",
            type=str,
            help=(
                "Locale directories to compile (each holding "
                "<language>/LC_MESSAGES/*.po). Defaults to LOCALE_PATHS and "
                "the locale directories of the local applications."
            ),
        )

    def default_locale_paths(self):
        paths = list(settings.LOCALE_PATHS)
        for app_config in django_apps.get_app_configs():
            app_path = Path(app_config.path).resolve()
            # Only the applications living in the project tree: never
            # recompile the catalogs shipped inside site-packages. A
            # virtual environment located inside the project counts as
            # third party code, not as a local application.
            if "site-packages" in app_path.parts or "dist-packages" in app_path.parts:
                continue
            locale_path = app_path / "locale"
            if locale_path.is_dir():
                paths.append(locale_path)
        # Deduplicate while keeping the order
        return list(map(str, dict.fromkeys(paths)))

    def handle(self, *args, **options):
        if options["locale_paths"]:
            locale_paths = options["locale_paths"]
        else:
            locale_paths = self.default_locale_paths()
        compiled = 0
        for locale_path in locale_paths:
            for po_path in sorted(Path(locale_path).glob("*/LC_MESSAGES/*.po")):
                try:
                    catalog_size = compile_catalog(po_path)
                except Exception as error:
                    self.stderr.write(
                        "{}: {}".format(po_path, error)
                    )
                    raise
                self.stdout.write(
                    "File {!s} compiled, {} messages".format(po_path, catalog_size)
                )
                compiled += 1
        if compiled == 0:
            self.stdout.write("No .po catalog found.")
        else:
            self.stdout.write("{} catalog(s) compiled.".format(compiled))
