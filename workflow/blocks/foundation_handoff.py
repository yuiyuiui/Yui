"""Names in a working NL0 graph and citations to declared, stage-local documents."""
from copy import deepcopy
from pathlib import PurePosixPath
import re

VERSION = 'yui-foundation-ports-1'
FIELD = 'foundation_ports'


def prefix(row):
    return 'M' if row['category'] == 1 and row['compatibility'] == 'native' else 'E'


def allocate(row, occupied):
    first = int(row['id'][1:])
    kind = prefix(row)
    # The Lean premise interface accepts three digits. Wrap around if the
    # preferred label is already taken near the end of the available range.
    for offset in range(1000):
        label = f'{kind}{(first + offset) % 1000:03}'
        if label not in occupied:
            return label
    raise ValueError(f'All three-digit {kind} premise labels are occupied')


def numbered_seed(registry, previous=None):
    """Allocate labels only for direct uses, preserving existing seed labels."""
    graph = deepcopy(registry['global_graph'])
    rows = {r['id']: r for r in registry['dependencies']}
    if previous is not None:
        original = {step['id']:step for step in graph['inferences']}
        graph = {'propositions':[{k:p[k] for k in ('id','statement')} for p in previous['propositions']],
                 'inferences':[{k:s[k] for k in ('id','inputs','output')} for s in deepcopy(previous['inferences'])]}
        owners = by_port(registry, previous)
        for step in graph['inferences']:
            step['basis'] = [owners[p]['id'] for p in step['inputs'] if p in owners]
            seed = original.get(step['id'])
            if FIELD not in previous and seed and seed['output']==step['output']:
                step['basis'].extend(b for b in seed['basis'] if not rows[b]['port'])
        if FIELD in previous:
            return graph, dict(previous[FIELD]['labels'])
    props = {p['id']: p for p in graph['propositions']}
    occupied = set(props) | {r['port'] for r in rows.values() if r['port']}
    direct = {key for step in graph['inferences'] for key in step['basis']}
    labels = {}
    for key in sorted(direct):
        row = rows[key]
        label = row['port']
        if not label:
            label = allocate(row,occupied)
        labels[key] = label
        occupied.add(label)
        if label not in props:
            graph['propositions'].append({'id':label, 'statement':row['statement']})
    for step in graph['inferences']:
        step['inputs'] = list(dict.fromkeys([*step['inputs'], *(labels[b] for b in step['basis'])]))
    return graph, labels


def by_port(registry, graph=None):
    """Resolve the selected graph against the frozen registry, using registered ports before label assignment."""
    rows = {r['id']: r for r in registry['dependencies']}
    if graph is None or FIELD not in graph:
        return {r['port']:r for r in rows.values() if r['port']}
    binding = graph[FIELD]
    if not isinstance(binding,dict) or set(binding) != {'version','labels'} or binding['version'] != VERSION:
        raise ValueError('Unknown NL0 foundation label record')
    labels = binding['labels']
    if not isinstance(labels,dict):
        raise ValueError('Foundation labels must map frozen B IDs to graph IDs')
    items = graph.get('propositions')
    if not isinstance(items,list) or any(not isinstance(p,dict) or not isinstance(p.get('id'),str) for p in items):
        raise ValueError('Expected NL0 propositions with graph IDs')
    props = {p['id']:p for p in items}
    if len(props)!=len(items):
        raise ValueError('Duplicate NL0 proposition ID')
    resolved = {}
    for key,label in labels.items():
        if key not in rows or not isinstance(label,str) or not re.fullmatch(prefix(rows[key])+r'[0-9]{3}',label):
            raise ValueError(f'Unknown foundation or wrong graph label kind: {key} -> {label}')
        if label in resolved or label not in props:
            raise ValueError(f'Duplicate or missing foundation graph node: {key} -> {label}')
        row = rows[key]
        prop = props[label]
        if prop.get('statement') != row['statement'] or prop.get('kind') != ('mathlib' if prefix(row)=='M' else 'external'):
            raise ValueError(f'Changed frozen foundation statement or kind at {label} ({key})')
        resolved[label] = row
    initial = {p['id']:p for p in registry['global_graph']['propositions']}
    original_ports = {r['port'] for r in rows.values() if r['port']}
    for label,prop in props.items():
        if label.startswith(('M','E')) and label not in resolved:
            if (not label.startswith('M') or label in original_ports or label not in initial
                    or prop.get('statement') != initial[label]['statement']):
                raise ValueError(f'Undeclared or changed frozen foundation at {label}')
    return resolved


def attach(registry, graph, labels):
    """Persist only the labels used in this revision. Graph edges encode their consumers."""
    present = {p['id'] for p in graph['propositions']}
    graph[FIELD] = {'version':VERSION, 'labels':{b:p for b,p in labels.items() if p in present}}
    by_port(registry,graph)


def rename(registry, graph, changes):
    """Rename a working global assignment atomically, before any local proofs are assigned."""
    if not isinstance(changes,dict):
        raise ValueError('rename_foundations must map frozen B IDs to graph labels')
    original = graph[FIELD]['labels']
    if changes.keys() - original.keys():
        raise ValueError('Only assigned frozen foundations can be renamed')
    new = {**original, **changes}
    if any(not isinstance(v,str) for v in new.values()) or len(set(new.values())) != len(new):
        raise ValueError('Duplicate or invalid requested graph label')
    mapping = {original[b]:label for b,label in changes.items()}
    existing = {r['id'] for r in graph['propositions']}
    if set(mapping.values()) & (existing - mapping.keys()):
        raise ValueError('Requested graph label is already occupied')
    candidate = deepcopy(graph)
    for row in candidate['propositions']:
        row['id'] = mapping.get(row['id'],row['id'])
    for step in candidate['inferences']:
        if 'argument' in step or 'applications' in step:
            raise ValueError('Renumber the working global graph before assigning local proofs')
        step['inputs'] = [mapping.get(i,i) for i in step['inputs']]
    attach(registry,candidate,new)
    graph.update(candidate)


def material_ref(value, declared, where):
    """Return a local evidence reference. The receiving validator verifies its actual bytes."""
    if isinstance(value,dict) and set(value)=={'input'}:
        name = value['input']
        if not isinstance(name,str) or name not in declared:
            raise ValueError(f'{where}: unknown declared document {name!r}; available: {", ".join(declared)}')
        return dict(declared[name])
    if isinstance(value,dict) and set(value)=={'path','sha256'}:
        path, digest = value['path'], value['sha256']
        if (isinstance(path,str) and path and not PurePosixPath(path).is_absolute()
                and '..' not in PurePosixPath(path).parts and isinstance(digest,str)
                and re.fullmatch(r'[0-9a-f]{64}',digest)):
            return dict(value)
    raise ValueError(f'{where}: select a declared document with {{"input":"ID"}} or supply its case-relative path and sha256')
