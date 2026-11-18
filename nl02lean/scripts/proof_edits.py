"""Exact edits of an author's own retained Lean drafts."""

import re

import artifact_protocol as protocol


POLICY = 'retained-proof-edit-1'
LINE = re.compile(r'(?m)^(?:[^\n]*/)?Check\.lean:(\d+):(\d+): error(?:\([^\n)]*\))?:')
SUBMISSION = protocol.obj({
    'proof': protocol.TEXT,
    'edit': protocol.obj({
        'base': {'type': 'integer', 'minimum': 1},
        'old': protocol.TEXT,
        'new': protocol.STRING,
    }, required=['base']),
}, required=[])


def expand(args, drafts):
    """Accept a full body, one unambiguous literal edit, or a saved body."""
    protocol.validate(args, SUBMISSION)
    if ('proof' in args) == ('edit' in args):
        raise ValueError('Supply exactly one of proof or edit')
    if 'proof' in args:
        return args['proof']
    edit = args['edit']
    base = drafts.get(edit['base'])
    if base is None:
        raise ValueError('Select a retained proof draft from this author')
    body = base['proof']
    if 'old' not in edit and 'new' not in edit:
        return body
    if 'old' not in edit or 'new' not in edit:
        raise ValueError('A replacement needs both old and new')
    old = edit['old']
    first = body.find(old)
    if first < 0 or body.find(old, first + 1) >= 0:
        raise ValueError('The old text must occur exactly once in the selected draft')
    return body[:first] + edit['new'] + body[first + len(old):]


def locations(result, span):
    """Map real Lean error starts inside the tactic body to draft lines."""
    start, end, draft_start = span
    rows = []
    for stream in ('stdout', 'stderr'):
        for match in LINE.finditer(result.get(stream, '')):
            line, column = map(int, match.groups())
            if start <= line <= end:
                rows.append({'draft_line': draft_start + line - start,
                             'lean_line': line, 'lean_column': column})
                if len(rows) == 8:
                    return rows
    return rows
