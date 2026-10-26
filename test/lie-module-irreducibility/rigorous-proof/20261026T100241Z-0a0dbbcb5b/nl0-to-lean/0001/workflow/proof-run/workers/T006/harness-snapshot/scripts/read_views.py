"""Bounded, lossless read-only views of explicitly declared text and JSON."""
from __future__ import annotations

import json
import re

MAX_TOOL_BYTES = 32 * 1024


def encoded_size(value):
    return len(json.dumps(value, ensure_ascii=False).encode('utf-8'))


def checked(value):
    if encoded_size(value) > MAX_TOOL_BYTES:
        raise ValueError('Read metadata exceeds the serialized 32 KiB response limit')
    return value


def fit_prefix(text, build):
    """Choose Unicode character boundaries using the final JSON byte length."""
    lo, hi = 0, min(len(text), MAX_TOOL_BYTES)
    if encoded_size(build('')) > MAX_TOOL_BYTES:
        raise ValueError('Read metadata exceeds the serialized 32 KiB response limit')
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if encoded_size(build(text[:mid])) <= MAX_TOOL_BYTES:
            lo = mid
        else:
            hi = mid - 1
    if text and not lo:
        raise ValueError('Read metadata leaves no room for the next character')
    return build(text[:lo])


def read_page(text, start, end, *, column=0, metadata=None):
    """Inclusive 1-based lines; a long line resumes at a 0-based column."""
    lines = text.splitlines(); total = len(lines)
    if type(start) is not int or type(end) is not int or not 1 <= start <= end:
        raise ValueError('Use positive inclusive start/end line numbers')
    if start > max(total, 1):
        raise ValueError('Read start is outside the document; total_lines=' + str(total))
    if type(column) is not int or column < 0 or column > (len(lines[start-1]) if lines else 0):
        raise ValueError('Use a valid nonnegative character column in the starting line')
    stop = min(end, start + 249, total)
    prefix = []
    def result(n, col, content):
        complete = not lines or col == len(lines[n-1])
        nxt = (n + 1 if complete else n) if lines else None
        if nxt is not None and nxt > total: nxt = None
        return {**(metadata or {}), 'total_lines':total, 'start':start, 'end':n,
            'start_column':column, 'end_column':col, 'requested_end':end,
            'has_more':nxt is not None, 'next_start':nxt,
            'next_column':col if nxt is not None and not complete else 0,
            'next_end':min(nxt + 249, total) if nxt is not None else None,
            'text':content}
    if not lines: return checked(result(0, 0, ''))
    for n in range(start, stop + 1):
        first = column if n == start else 0
        line = lines[n-1]
        def build(part):
            return result(n, first + len(part), '\n'.join([*prefix, f'{n}: {part}']))
        full = build(line[first:]) if len(line)-first <= MAX_TOOL_BYTES else None
        if full is not None and encoded_size(full) <= MAX_TOOL_BYTES:
            prefix.append(f'{n}: {line[first:]}')
            continue
        if prefix:
            return checked(result(n-1, len(lines[n-2]), '\n'.join(prefix)))
        return checked(fit_prefix(line[first:], build))
    return checked(result(stop, len(lines[stop-1]), '\n'.join(prefix)))


def resolve(document, pointer):
    if not isinstance(pointer, str) or pointer and not pointer.startswith('/'):
        raise ValueError('Use an empty root pointer or an absolute JSON pointer')
    value = document
    for raw in pointer[1:].split('/') if pointer else []:
        if re.search(r'~(?![01])', raw): raise ValueError('Invalid JSON pointer escape')
        key = raw.replace('~1', '/').replace('~0', '~')
        if isinstance(value, list):
            if not re.fullmatch(r'0|[1-9][0-9]*', key): raise ValueError('Use a valid array index')
            value = value[int(key)]
        else: value = value[key]
    return value


def read_json(document, pointer='', *, offset=0, limit=250, metadata=None):
    """Large containers expose keys; strings expose exact continuation offsets."""
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 250:
        raise ValueError('Use a nonnegative offset and a limit from 1 to 250')
    value = resolve(document, pointer)
    base = {**(metadata or {}), 'pointer':pointer}
    if isinstance(value, str):
        if offset > len(value): raise ValueError('String offset is outside the selected value')
        def build(part):
            end = offset + len(part)
            return {**base, 'view':'string', 'offset':offset, 'end_offset':end,
                'total_chars':len(value), 'has_more':end < len(value),
                'next_offset':end if end < len(value) else None, 'value':part}
        return checked(fit_prefix(value[offset:], build))
    whole = {**base, 'view':'value', 'value':value, 'has_more':False, 'next_offset':None}
    if offset == 0 and encoded_size(whole) <= MAX_TOOL_BYTES: return whole
    if not isinstance(value, (dict, list)):
        raise ValueError('Offsets apply only to strings or container key pages')
    keys = list(value) if isinstance(value, dict) else list(range(len(value)))
    if offset > len(keys): raise ValueError('Key offset is outside the selected container')
    count = min(limit, len(keys) - offset)
    while True:
        end = offset + count
        page = {**base, 'view':'keys', 'container':'object' if isinstance(value,dict) else 'array',
            'keys':keys[offset:end], 'offset':offset, 'total_keys':len(keys),
            'has_more':end < len(keys), 'next_offset':end if end < len(keys) else None,
            'instruction':'Read a child by appending its escaped key/index to this JSON pointer. No values are omitted from the frozen document.'}
        if encoded_size(page) <= MAX_TOOL_BYTES: return page
        if count <= 1: raise ValueError('One JSON key exceeds the read size limit')
        count //= 2
