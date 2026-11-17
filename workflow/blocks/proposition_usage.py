"""Usage on a global proposition: graph consumers and locations in specific input documents."""
from collections import defaultdict


def references(usage, documents, where):
    if not isinstance(usage, dict) or usage.keys() - {'inferences', 'references'}:
        raise ValueError(f'USAGE: {where}: expected inferences and/or references')
    entries = usage.get('references', [])
    if not isinstance(entries, list):
        raise ValueError(f'USAGE: {where}.references must be a list')
    seen = set()
    for entry in entries:
        if (not isinstance(entry, dict) or set(entry) != {'document', 'locator'}
                or not all(isinstance(v, str) and v.strip() for v in entry.values())):
            raise ValueError(f'USAGE: {where}: each reference needs a document and a nonempty locator')
        document, locator = entry['document'], entry['locator']
        if document not in documents:
            raise ValueError(f'USAGE: {where}: unknown input document {document!r}; available: {sorted(documents)}')
        if (document, locator) in seen:
            raise ValueError(f'USAGE: {where}: duplicate location in {document}: {locator}')
        seen.add((document, locator))
    return entries


def bind(graph, documents, *, check=False):
    """Materialize reverse input edges on submission, or check the persisted index without mutation."""
    if not isinstance(graph.get('propositions'), list) or not isinstance(graph.get('inferences'), list):
        raise ValueError('USAGE: expected proposition and inference lists')
    consumers = defaultdict(list)
    for step in graph['inferences']:
        if not isinstance(step, dict) or not isinstance(step.get('id'), str) or not isinstance(step.get('inputs'), list):
            raise ValueError('USAGE: a graph inference needs an ID and an input list')
        for pid in step['inputs']:
            if not isinstance(pid, str):
                raise ValueError(f'USAGE: {step["id"]}: expected a proposition ID in inputs')
            consumers[pid].append(step['id'])
    for prop in graph['propositions']:
        if not isinstance(prop, dict) or not isinstance(prop.get('id'), str):
            raise ValueError('USAGE: a graph proposition needs an ID')
        pid = prop['id']
        usage = prop.get('usage', {})
        refs = references(usage, documents, pid)
        expected = {'inferences': consumers[pid], 'references': refs}
        if check and set(usage) != set(expected):
            raise ValueError(f'USAGE: {pid}: the stored usage needs both inferences and references')
        if 'inferences' in usage and usage['inferences'] != consumers[pid]:
            raise ValueError(f'USAGE: {pid}: expected direct consumers {consumers[pid]}; '
                             'omit the derived inferences field when editing graph edges')
        if not check:
            prop['usage'] = expected
