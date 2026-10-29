"""Bounded, lossless read-only views of explicitly declared text and JSON."""
from __future__ import annotations

import json
import re

MAX_TOOL_BYTES = 32 * 1024


def encoded_size(value):
    return len(json.dumps(value, ensure_ascii=False).encode('utf-8'))


def checked(value, *, max_bytes=MAX_TOOL_BYTES):
    if encoded_size(value) > max_bytes:
        raise ValueError('Read metadata exceeds the serialized 32 KiB response limit')
    return value


def fit_prefix(text, build, *, max_bytes=MAX_TOOL_BYTES):
    """Choose Unicode character boundaries using the final JSON byte length."""
    lo, hi = 0, min(len(text), max_bytes)
    if encoded_size(build('')) > max_bytes:
        raise ValueError('Read metadata exceeds the serialized 32 KiB response limit')
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if encoded_size(build(text[:mid])) <= max_bytes:
            lo = mid
        else:
            hi = mid - 1
    if text and not lo:
        raise ValueError('Read metadata leaves no room for the next character')
    return build(text[:lo])


def read_page(text, start, end, *, column=0, metadata=None, max_bytes=MAX_TOOL_BYTES):
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
    if not lines: return checked(result(0, 0, ''), max_bytes=max_bytes)
    for n in range(start, stop + 1):
        first = column if n == start else 0
        line = lines[n-1]
        def build(part):
            return result(n, first + len(part), '\n'.join([*prefix, f'{n}: {part}']))
        full = build(line[first:]) if len(line)-first <= max_bytes else None
        if full is not None and encoded_size(full) <= max_bytes:
            prefix.append(f'{n}: {line[first:]}')
            continue
        if prefix:
            return checked(result(n-1, len(lines[n-2]), '\n'.join(prefix)), max_bytes=max_bytes)
        return checked(fit_prefix(line[first:], build, max_bytes=max_bytes), max_bytes=max_bytes)
    return checked(result(stop, len(lines[stop-1]), '\n'.join(prefix)), max_bytes=max_bytes)


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


def read_json(document, pointer='', *, offset=0, limit=250, metadata=None, max_bytes=MAX_TOOL_BYTES):
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
        return checked(fit_prefix(value[offset:], build, max_bytes=max_bytes), max_bytes=max_bytes)
    whole = {**base, 'view':'value', 'value':value, 'has_more':False, 'next_offset':None}
    if offset == 0 and encoded_size(whole) <= max_bytes: return whole
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
        if encoded_size(page) <= max_bytes: return page
        if count <= 1: raise ValueError('One JSON key exceeds the read size limit')
        count //= 2


def read_batch(documents, requests, *, cache=None):
    """Read up to eight declared fragments with per-read and batch continuations."""
    if not isinstance(requests, list) or not 1 <= len(requests) <= 8:
        raise ValueError('Request from one to eight declared document fragments')
    cache = {} if cache is None else cache
    results = []
    for index, request in enumerate(requests):
        if (not isinstance(request, dict) or 'id' not in request
                or set(request)-{'id','pointer','offset','limit','start','end','column'}):
            raise ValueError('Use declared document IDs and supported fragment coordinates')
        name = request['id']
        if name not in documents:
            raise ValueError('Only declared task inputs may be read')
        frame = {'results':results,'has_more':True,'next_request':index+1,'total_requests':len(requests)}
        available = MAX_TOOL_BYTES-encoded_size(frame)-64
        if available < 1024 and results:
            break
        if 'pointer' in request:
            if set(request)&{'start','end','column'}:
                raise ValueError('Do not mix JSON pointer and text-line coordinates')
            if name not in cache:
                cache[name] = json.loads(documents[name])
            value = read_json(cache[name],request['pointer'],offset=request.get('offset',0),
                limit=request.get('limit',250),metadata={'id':name},max_bytes=available)
        else:
            if set(request)&{'offset','limit'} or not {'start','end'} <= set(request):
                raise ValueError('Text fragments need start/end, JSON fragments need pointer')
            value = read_page(documents[name],request['start'],request['end'],
                column=request.get('column',0),metadata={'id':name},max_bytes=available)
        results.append(value)
    count = len(results)
    return checked({'results':results,'has_more':count<len(requests),
                    'next_request':count if count<len(requests) else None,
                    'total_requests':len(requests)})
