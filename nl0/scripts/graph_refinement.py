"""Extract smaller NL0 inferences inside a checked local proof boundary."""
from copy import deepcopy

import artifact_protocol as protocol
import graph_outline


def schema():
    from frozen_graph import LOCAL_PROOF
    from payload_protocols import POSITIVE

    inference = protocol.obj({
        **LOCAL_PROOF['properties'], 'inputs': protocol.array(protocol.TEXT, uniqueItems=True),
        'output': protocol.TEXT, 'definitions': protocol.array(protocol.TEXT, uniqueItems=True),
    })
    proposition = protocol.obj({
        'id': {'type': 'string', 'pattern': r'^N\d{3,}$'}, 'kind': protocol.literal('internal'),
        'statement': protocol.TEXT, 'origin': protocol.TEXT, 'definitions': protocol.array(protocol.TEXT),
        'binders': protocol.array({}), 'objects': protocol.array(protocol.TEXT),
        'usage': protocol.obj({'references': protocol.array(protocol.obj({
            'document': protocol.TEXT, 'locator': protocol.TEXT,
        }))}),
    }, required=['id', 'kind', 'statement', 'origin', 'definitions', 'binders', 'objects'])
    split = protocol.obj({
        'inference': protocol.TEXT, 'propositions': protocol.array(proposition, minItems=1),
        'inferences': protocol.array(inference, minItems=2), graph_outline.FIELD: graph_outline.schema(),
    })
    return protocol.obj({
        'refine_candidate': POSITIVE, 'splits': protocol.array(split, minItems=1),
        'keep_together': protocol.obj({}, extra=graph_outline.retention_schema(checked=True)),
    }, required=['refine_candidate'])


def apply(base, outline, artifact):
    """Apply only authored splits. The ordinary NL0 validator checks each resulting proof."""
    from frozen_graph import indexed
    from nl0 import closure

    value = deepcopy(base)
    graph = value['graph']
    outline = deepcopy(outline)
    proposals = artifact.get('splits', [])
    retained = artifact.get('keep_together', {})
    targets = {part['inference'] for part in proposals}
    original = indexed(graph['inferences'])
    if (not (targets or retained) or len(targets) != len(proposals)
            or targets - original.keys() or retained.keys() - original.keys() or targets & retained.keys()):
        raise ValueError('NL0_REFINEMENT: choose distinct current inferences to split or justify retaining')
    props = indexed(graph['propositions'])
    definitions = indexed(value['spec']['definitions'])
    occupied = set(original)
    replacements = {}
    for part in proposals:
        rid = part['inference']
        prior = original[rid]
        added = indexed(deepcopy(part['propositions']))
        steps = indexed(deepcopy(part['inferences']))
        if added.keys() & props.keys() or (steps.keys() - {rid}) & occupied:
            raise ValueError(f'NL0_REFINEMENT: {rid} must use fresh IDs for the extracted N/R nodes')
        if rid not in steps or steps[rid]['output'] != prior['output']:
            raise ValueError(f'NL0_REFINEMENT: {rid} must still prove the original output {prior["output"]}')
        if {row['output'] for row in steps.values()} != {prior['output'], *added}:
            raise ValueError(f'NL0_REFINEMENT: {rid} may produce only its original output and the new N nodes')
        inputs = set(prior['inputs'])
        used = {key for row in steps.values() for key in row['inputs']}
        if used - added.keys() != inputs:
            raise ValueError(f'NL0_REFINEMENT: {rid} must preserve its outside premises {sorted(inputs)}; '
                             f'got {sorted(used - added.keys())}')
        _, _, old_definitions = closure.inference_scope(prior, props, definitions)
        allowed = {row['id'] for row in old_definitions}
        props.update(added)
        for row in steps.values():
            _, _, scope = closure.inference_scope(row, props, definitions)
            if any(definition['id'] not in allowed for definition in scope):
                raise ValueError(f'NL0_REFINEMENT: {row["id"]} uses a definition outside {rid}')
        declared = part[graph_outline.FIELD]
        if declared.keys() != steps.keys():
            raise ValueError(f'NL0_REFINEMENT: supply the updated source outline for each inference replacing {rid}')
        # Workload exceptions are made only against a checked version of these new bodies.
        if any('keep_together' in entry for entry in declared.values()):
            raise ValueError('NL0_REFINEMENT: check the new bodies first, then justify any indivisible block')
        outline.update(deepcopy(declared))
        occupied.update(steps)
        replacements[rid] = list(steps.values())
    for rid, reason in retained.items():
        if set(reason['at']) - {step['id'] for step in original[rid]['argument']}:
            raise ValueError(f'NL0_REFINEMENT: {rid} keep_together must name actual written S steps')
        outline[rid]['keep_together'] = deepcopy(reason)
    graph['propositions'] = list(props.values())
    graph['inferences'] = [row for rid, prior in original.items() for row in replacements.get(rid, [prior])]
    if replacements:
        from nl0 import usage
        for prop in graph['propositions']:
            prop.get('usage', {}).pop('inferences', None)
        usage.bind(graph, {item['path'] for item in value['spec']['inputs']})
    return value, outline
