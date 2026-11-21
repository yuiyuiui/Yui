"""Validate source-backed outlines and locate blocks that need proof-based refinement."""
from collections import defaultdict

import artifact_protocol as protocol


FILENAME = 'proof-outline.json'
FIELD = 'proof_outline'
VERSION = 'yui-nl0-proof-outline-1'
# Flag larger source assignments for a granularity review.
REVIEW_CHARACTERS = 16000


def retention_schema(*, checked=False):
    required = ['kind', 'reason', 'at'] if checked else ['kind', 'reason']
    return protocol.obj({
        'kind': {'enum': ['shared_witness', 'shared_scope', 'single_argument']},
        'reason': protocol.TEXT,
        'at': protocol.array(protocol.TEXT, minItems=1, uniqueItems=True),
    }, required=required)


def schema():
    line = {'type': 'integer', 'minimum': 1}
    span = protocol.obj({'from_task': protocol.TEXT, 'start_line': line, 'end_line': line})
    step = protocol.obj({
        'conclusion': protocol.TEXT,
        'uses': protocol.array(protocol.TEXT, uniqueItems=True),
        'source_spans': protocol.array(span, uniqueItems=True),
    })
    inference = protocol.obj({
        'steps': protocol.array(step, minItems=1),
        'keep_together': retention_schema(),
    }, required=['steps'])
    return protocol.obj({}, extra=inference)


def source_sizes(spans, documents, offsets, inference):
    """Count the union of the selected source lines within this inference."""
    by_document = defaultdict(list)
    for span in spans:
        name, start, end = (span[key] for key in ('from_task', 'start_line', 'end_line'))
        if name not in documents:
            raise ValueError(f'OUTLINE_SOURCE: {inference} refers to undeclared input {name!r}')
        if name not in offsets:
            offsets[name] = [0]
            for line in documents[name].splitlines(keepends=True):
                offsets[name].append(offsets[name][-1] + len(line))
        if not 1 <= start <= end < len(offsets[name]):
            raise ValueError(f'OUTLINE_SOURCE: {inference} has an invalid line range {name}:{start}-{end}')
        by_document[name].append((start, end))

    merged = []
    for name, ranges in by_document.items():
        lines = []
        for start, end in sorted(ranges):
            if lines and start <= lines[-1][1] + 1:
                lines[-1] = (lines[-1][0], max(end, lines[-1][1]))
            else:
                lines.append((start, end))
        starts = offsets[name]
        merged.extend({
            'from_task': name, 'start_line': start, 'end_line': end,
            'characters': starts[end] - starts[start - 1],
        } for start, end in lines)
    return sum(span['characters'] for span in merged), max(
        merged, key=lambda span: span['characters'], default=None)


def check(graph, outline, documents, *, provisional=False):
    """Return workload evidence for the declared derivations and bound sources."""
    protocol.validate(outline, schema())
    inferences = {row['id']: row for row in graph['inferences']}
    if outline.keys() != inferences.keys():
        raise ValueError('OUTLINE_COVERAGE: supply one proof_outline entry for each R; '
                         f'missing={sorted(inferences.keys() - outline.keys())}, '
                         f'unknown={sorted(outline.keys() - inferences.keys())}')
    consumers = defaultdict(list)
    for row in inferences.values():
        for premise in row['inputs']:
            consumers[premise].append(row['id'])

    labels = graph.get('foundation_ports', {}).get('labels', {})
    offsets, workload = {}, {}
    for rid, row in inferences.items():
        entry = outline[rid]
        direct, earlier, used = set(row['inputs']), set(), set()
        for index, step in enumerate(entry['steps'], 1):
            sid = f'S{index:03d}'
            uses = {labels.get(key, key) for key in step['uses']}
            unknown = uses - direct - earlier
            if unknown:
                raise ValueError(f'OUTLINE_INPUT: {rid}/{sid} uses unavailable inputs {sorted(unknown)}')
            used.update(uses)
            earlier.add(sid)
        unused = (direct | (earlier - {sid})) - used
        if unused:
            raise ValueError(f'OUTLINE_INPUT: {rid} has premises or steps without a consumer {sorted(unused)}')

        size, largest = source_sizes(
            (span for step in entry['steps'] for span in step['source_spans']), documents, offsets, rid)
        reasons = []
        if len(entry['steps']) > 1:
            reasons.append('multiple_main_steps')
        if size >= REVIEW_CHARACTERS:
            reasons.append('large_source_span')
        workload[rid] = {'output': row['output'], 'consumers': consumers[row['output']],
                         'main_steps': len(entry['steps']), 'source_characters': size,
                         'largest_source_span': largest, 'review_reasons': reasons}
    report = {'schema': VERSION, 'inferences': outline, 'workload': workload}
    if not provisional and pending(report):
        raise ValueError('OUTLINE_REVIEW: split independent conclusions or explain an indivisible argument at '
                         + ', '.join(pending(report)))
    return report


def pending(report):
    return {rid: entry['review_reasons'] for rid, entry in report['workload'].items()
            if entry['review_reasons'] and 'keep_together' not in report['inferences'][rid]}


def include_written_size(report, graph):
    for row in graph['inferences']:
        if sum(len(step['text']) for step in row['argument']) >= REVIEW_CHARACTERS:
            report['workload'][row['id']]['review_reasons'].append('large_argument')
