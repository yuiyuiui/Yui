"""Bounded Lean diagnostics. Complete streams stay in the native evidence."""
import re

HEADER = re.compile(r'(?m)^(?:[^\n]*\.lean:\d+:\d+:\s*)?'
                    r'(?P<level>error(?:\([^\n)]*\))?|warning|information):')


def excerpt(text, limit):
    if not isinstance(text, str) or limit < 256:
        raise ValueError('Expected text and a diagnostic limit of at least 256')
    headers = list(HEADER.finditer(text))
    errors = []
    for index, match in enumerate(headers):
        if match.group('level').startswith('error'):
            end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
            errors.append(text[match.start():end].strip())
    metadata = {'original_characters': len(text), 'error_messages': len(errors),
                'truncated': len(text) > limit, 'full_result_retained': True}
    if len(text) <= limit:
        return text, metadata
    if errors:
        notice = '[Warning prefix omitted; error excerpts follow. Full diagnostics remain in the saved check.]\n'
        selected = errors[:16]
        budget = limit - len(notice) - len(selected)
        quota = budget // len(selected)
        parts = [message if len(message) <= quota else message[:quota - 36] + '\n[Diagnostic excerpt truncated.]' for message in selected]
        metadata['error_messages_shown'] = len(selected)
        return notice + '\n'.join(parts), metadata
    # Resource/process failures need not use Lean's file/line error headers.
    notice = '\n[Middle omitted; full output retained.]\n'
    left = (limit - len(notice)) // 2
    return text[:left] + notice + text[-(limit - len(notice) - left):], metadata


def compact_result(result):
    output = dict(result)
    summaries = {}
    for stream, limit in [('stdout', 14000), ('stderr', 2000)]:
        output[stream], summaries[stream] = excerpt(result.get(stream, ''), limit)
    if any(row['truncated'] for row in summaries.values()):
        output['diagnostic_summary'] = summaries
    return output
