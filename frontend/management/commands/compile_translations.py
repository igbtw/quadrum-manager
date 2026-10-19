"""Compile gettext ``.po`` catalogs to ``.mo`` without external tools.

The project has no GNU gettext binaries available, so this command implements
the small subset of PO syntax used by Django catalogs and emits standard GNU
MO files (little endian, revision 0). Python's :mod:`gettext` and Django both
read the result.

Validation is intentionally strict: placeholder sets and HTML tags must match
between msgid and msgstr, plural entries must define every form, and fuzzy
entries must be translated before they are compiled. A broken catalog fails
the command instead of silently shipping English text.
"""
from __future__ import annotations

import re
import struct
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

PLACEHOLDER_RE = re.compile(r"%(?:\((?P<named>[^)]+)\))?[sd]")
TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
STRING_ESCAPES = {
    'n': '\n',
    't': '\t',
    'r': '\r',
    '"': '"',
    '\\': '\\',
}


def _parse_string(line, line_number, path=None):
    """Parse ``"..."`` with gettext escapes; reject trailing garbage."""
    prefix = f'{path}:{line_number}' if path else f'line {line_number}'
    line = line.strip()
    if not line.startswith('"'):
        raise CommandError(f'{prefix}: expected a quoted string')
    out = []
    index = 1
    while index < len(line):
        char = line[index]
        if char == '\\':
            if index + 1 >= len(line):
                raise CommandError(f'{prefix}: dangling escape')
            index += 1
            escaped = line[index]
            out.append(STRING_ESCAPES.get(escaped, escaped))
            index += 1
        elif char == '"':
            remainder = line[index + 1:].strip()
            if remainder:
                raise CommandError(
                    f'{prefix}: unexpected text after string: {remainder!r}'
                )
            return ''.join(out)
        else:
            out.append(char)
            index += 1
    raise CommandError(f'{prefix}: unterminated string')


class CatalogEntry:
    __slots__ = ('context', 'msgid', 'plural', 'translations', 'fuzzy', 'line')

    def __init__(self):
        self.context = None
        self.msgid = None
        self.plural = None
        self.translations = {}
        self.fuzzy = False
        self.line = 0

    def add(self, field, value):
        if field == 'msgctxt':
            self.context = (self.context or '') + value
        elif field == 'msgid':
            self.msgid = (self.msgid or '') + value
        elif field == 'msgid_plural':
            self.plural = (self.plural or '') + value
        elif field.startswith('msgstr'):
            index = 0
            bracket = field.find('[')
            if bracket != -1:
                index = int(field[bracket + 1:-1])
            self.translations[index] = self.translations.get(index, '') + value
        else:  # pragma: no cover - guarded by the parser
            raise CommandError(f'line {self.line}: unknown field {field!r}')

    def is_complete(self):
        return self.msgid is not None and bool(self.translations)

    def placeholder_set(self, text):
        return PLACEHOLDER_RE.findall(text)

    def tag_multiset(self, text):
        return sorted(TAG_RE.findall(text))


def parse_po(text, path):
    entries = []
    current = None
    active_field = None
    line_number = 0
    for raw_line in text.splitlines():
        line_number += 1
        stripped = raw_line.strip()
        if not stripped:
            active_field = None
            continue
        if stripped.startswith('#'):
            if stripped.startswith('#,') and 'fuzzy' in stripped:
                if current is None:
                    current = CatalogEntry()
                    current.line = line_number
                current.fuzzy = True
            active_field = None
            continue
        if stripped.startswith('msgctxt '):
            if current is None or current.is_complete():
                current = CatalogEntry()
                current.line = line_number
                entries.append(current)
            active_field = 'msgctxt'
            current.add('msgctxt', _parse_string(stripped[len('msgctxt'):], line_number, path))
        elif stripped.startswith('msgid_plural '):
            if current is None:
                raise CommandError(f'{path}:{line_number}: msgid_plural without msgid')
            active_field = 'msgid_plural'
            current.add('msgid_plural', _parse_string(stripped[len('msgid_plural'):], line_number, path))
        elif stripped.startswith('msgid '):
            if current is None or current.is_complete():
                current = CatalogEntry()
                current.line = line_number
                entries.append(current)
            active_field = 'msgid'
            current.add('msgid', _parse_string(stripped[len('msgid'):], line_number, path))
        elif stripped.startswith('msgstr'):
            if current is None:
                raise CommandError(f'{path}:{line_number}: msgstr without msgid')
            field = stripped.split(' ', 1)[0]
            remainder = stripped[len(field):]
            active_field = field
            current.add(field, _parse_string(remainder, line_number, path))
        elif stripped.startswith('"'):
            if current is None or active_field is None:
                raise CommandError(f'{path}:{line_number}: continuation without a field')
            current.add(active_field, _parse_string(stripped, line_number, path))
        else:
            raise CommandError(f'{path}:{line_number}: unsupported syntax: {stripped!r}')

    return [entry for entry in entries if entry.is_complete() or entry.msgid == '']


def validate_entry(entry, path):
    if entry.fuzzy:
        raise CommandError(
            f'{path}:{entry.line}: fuzzy entry {entry.msgid!r} must be reviewed before compiling'
        )
    forms = [entry.translations[index] for index in sorted(entry.translations)]
    if entry.plural is None:
        if len(forms) != 1:
            raise CommandError(f'{path}:{entry.line}: singular entry has multiple msgstr values')
        source_forms = [entry.msgid]
    else:
        if len(forms) != 2:
            raise CommandError(
                f'{path}:{entry.line}: plural entry must define exactly 2 forms for pt-BR'
            )
        source_forms = [entry.msgid, entry.plural]
    for source, translated in zip(source_forms, forms):
        if not translated:
            raise CommandError(
                f'{path}:{entry.line}: missing translation for {source!r}'
            )
        if sorted(entry.placeholder_set(source)) != sorted(entry.placeholder_set(translated)):
            raise CommandError(
                f'{path}:{entry.line}: placeholder mismatch for {source!r} -> {translated!r}'
            )
        if entry.tag_multiset(source) != entry.tag_multiset(translated):
            raise CommandError(
                f'{path}:{entry.line}: HTML tag mismatch for {source!r} -> {translated!r}'
            )


def build_mo(entries):
    messages = {}
    for entry in entries:
        if entry.msgid == '' and entry.context is None:
            messages[''] = entry.translations.get(0, '')
            continue
        key = entry.msgid
        if entry.context:
            key = entry.context + '\x04' + key
        if entry.plural is None:
            messages[key] = entry.translations[0]
        else:
            messages[key + '\x00' + entry.plural] = '\x00'.join(
                entry.translations[index] for index in sorted(entry.translations)
            )
    keys = sorted(messages)
    offsets = []
    ids = b''
    strings = b''
    for key in keys:
        key_bytes = key.encode('utf-8')
        value_bytes = messages[key].encode('utf-8')
        offsets.append((len(ids), len(key_bytes), len(strings), len(value_bytes)))
        ids += key_bytes + b'\x00'
        strings += value_bytes + b'\x00'
    header_size = 7 * 4
    table_size = len(keys) * 8
    key_table_offset = header_size
    value_table_offset = key_table_offset + table_size
    data_offset = value_table_offset + table_size
    key_table = b''.join(
        struct.pack('<II', length, data_offset + offset)
        for offset, length, _string_offset, _string_length in offsets
    )
    value_table = b''.join(
        struct.pack('<II', length, data_offset + len(ids) + string_offset)
        for _offset, _length, string_offset, length in offsets
    )
    header = struct.pack(
        '<7I',
        0x950412DE,
        0,
        len(keys),
        key_table_offset,
        value_table_offset,
        0,
        0,
    )
    return header + key_table + value_table + ids + strings


class Command(BaseCommand):
    help = 'Compile every locale/*/LC_MESSAGES/django.po catalog into django.mo.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            help='Validate catalogs without writing .mo files.',
        )

    def handle(self, *args, **options):
        locale_root = Path(settings.BASE_DIR) / 'locale'
        po_paths = sorted(locale_root.glob('*/LC_MESSAGES/django.po'))
        if not po_paths:
            raise CommandError(f'no catalogs found under {locale_root}')
        for po_path in po_paths:
            entries = parse_po(po_path.read_text(encoding='utf-8'), po_path)
            seen = set()
            for entry in entries:
                if entry.msgid == '' and entry.context is None:
                    continue
                key = (entry.context, entry.msgid)
                if key in seen:
                    raise CommandError(
                        f'{po_path}:{entry.line}: duplicate message {entry.msgid!r}'
                    )
                seen.add(key)
                validate_entry(entry, po_path)
            if options['check']:
                self.stdout.write(f'valid: {po_path}')
                continue
            mo_path = po_path.with_suffix('.mo')
            mo_path.write_bytes(build_mo(entries))
            self.stdout.write(f'compiled: {mo_path}')
