"""Located objections to the current NL0 graph. No report grants mathematical acceptance."""
import json

import artifact_protocol as protocol

STATUS = 'NL0_GRAPH_REVISION_REQUIRED'
UNRESOLVED = 'NL0_GRAPH_REVISION_UNRESOLVED'
LIMIT = 'NL0_GRAPH_REVISION_LIMIT'
TOOL = 'report_graph_issue'
SCHEMA = protocol.obj({
    'inference': protocol.TEXT,
    'related_propositions': protocol.array(protocol.TEXT, uniqueItems=True),
    'field': {'type': 'string', 'enum': ['inputs', 'output', 'definitions', 'statement']},
    'explanation': protocol.TEXT,
}, required=['inference', 'related_propositions', 'explanation'])


class Request(Exception):
    def __init__(self, obligations, *, baseline=None, evidence=(), prior=()):
        super().__init__('Located NL0 graph revision required')
        self.obligations,self.baseline=obligations,baseline
        self.evidence,self.prior=list(evidence),list(prior)


def locate(frozen, finding):
    protocol.validate(finding, SCHEMA)
    graph = frozen['graph']
    inference_index = next((i for i, row in enumerate(graph['inferences'])
                            if row['id'] == finding['inference']), None)
    if inference_index is None:
        raise ValueError('Select an inference in the assigned global revision')
    related = finding['related_propositions']
    proposition_indices = {p['id']: i for i, p in enumerate(graph['propositions'])}
    if set(related) - proposition_indices.keys():
        raise ValueError('Related propositions must exist in this revision. Report a foundation defect separately.')
    field = finding.get('field', 'inputs')
    location = f'/graph/inferences/{inference_index}/{field}'
    if field == 'statement':
        inference = graph['inferences'][inference_index]
        adjacent = {*inference['inputs'], inference['output']}
        if len(related) != 1 or not related[0].startswith('N') or related[0] not in adjacent:
            raise ValueError('For a statement repair, select one intermediate input or output of this inference.')
        location = f'/graph/propositions/{proposition_indices[related[0]]}/statement'
    return {'id': 'ISSUE001', 'criterion': 'structure', 'location': location,
            'note': ' '.join(part for part in (finding['inference'], ', '.join(related), finding['explanation']) if part)}


def verify_local(stage,selected):
    from controller_common import bind, verify_bindings
    from execution_health import record_qualification
    from frozen_graph import ASSIGNED,read_working
    import nl0
    result=nl0.load(stage/'result.json')
    accepted=nl0.load(stage/'accepted.json')
    inputs=stage.parent/'inputs'/ASSIGNED
    verify_bindings([selected,accepted['assigned']])
    frozen=nl0.load(inputs)
    manifest=nl0.load(stage/'execution-manifest.json')
    if (result.get('exposure')!=nl0.load(stage/'exposure-audit.json')
            or result.get('role_session')!=manifest.get('role_session')
            or result.get('status')!='BLOCKED' or result.get('task_outcome')!=STATUS or result.get('execution_fault')
            or not record_qualification(result,allow_blocked=True)['submitted_record_qualified']
            or accepted.get('status')!=STATUS or accepted['assigned']!=bind(inputs)
            or frozen!=read_working(selected)):
        raise ValueError('Unqualified or stale local graph finding')
    finding=accepted['finding']
    events=[json.loads(line) for line in (stage/'tools.jsonl').read_text().splitlines()]
    if not any(e['tool']==TOOL and e['arguments']==finding and e['result'].get('stage_complete') is True for e in events):
        raise ValueError('No completed located graph issue submission')
    return {'issues':[locate(frozen,finding)]}
