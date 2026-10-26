"""Parse data-only Lean declaration names without an ASCII-only assumption.

This is an input boundary, not proof that a declaration exists. The pinned
Lean environment resolves the resulting name components during inspection.
"""
from __future__ import annotations

import unicodedata


def parts(name):
    if not isinstance(name, str) or not name or len(name) > 4096:
        raise ValueError('expected a nonempty Lean declaration name')
    result = []
    pos = 0
    while pos < len(name):
        if name[pos] == '«':
            end = name.find('»', pos + 1)
            if end < 0:
                raise ValueError('unclosed quoted Lean name component')
            item = name[pos + 1:end]
            if not item or any(c in '«»' or unicodedata.category(c).startswith('C') for c in item):
                raise ValueError('invalid quoted Lean name component')
            pos = end + 1
        else:
            end = name.find('.', pos)
            end = len(name) if end < 0 else end
            item = name[pos:end]
            if not item or not (item[0] == '_' or unicodedata.category(item[0]).startswith('L')):
                raise ValueError('invalid Lean name component')
            if any(not (c in "_'!?" or unicodedata.category(c)[0] in 'LMN') for c in item):
                raise ValueError('invalid character in Lean name component')
            pos = end
        result.append(item)
        if pos == len(name):
            break
        if name[pos] != '.' or pos + 1 == len(name):
            raise ValueError('invalid Lean namespace separator')
        pos += 1
    return result


def valid(name):
    try:
        parts(name)
        return True
    except ValueError:
        return False


def canonical(name):
    """Compare harmless quoted spellings by their actual name components."""
    encoded = []
    for item in parts(name):
        try:
            bare = parts(item) == [item]
        except ValueError:
            bare = False
        encoded.append(item if bare else '«' + item + '»')
    return '.'.join(encoded)
