"""Located objections to the current NL0 graph. No report grants mathematical acceptance."""
import json

import artifact_protocol as protocol

STATUS = 'NL0_GRAPH_REVISION_REQUIRED'
UNRESOLVED = 'NL0_GRAPH_REVISION_UNRESOLVED'
LIMIT = 'NL0_GRAPH_REVISION_LIMIT'
TOOL = 'report_graph_issue'
VERSION = 'yui-nl0-blockers-1'
FEEDBACK = 'global-findings.json'
RULE = ('Use the actual conditional packet: it supplies direct premises and the definition closure '
        'of the inference and its ports. A return needs a missing or incorrect piece of that contract '
        'that prevents the proof or a concrete downstream use. Use local proof steps for a valid '
        'alternative organization of the same implication.')
SCHEMA = protocol.obj({
    'inference': protocol.TEXT,
    'related_propositions': protocol.array(protocol.TEXT, uniqueItems=True),
    'field': {'type': 'string', 'enum': ['inputs', 'output', 'definitions', 'statement']},
    'explanation': protocol.TEXT,
}, required=['inference', 'related_propositions', 'explanation'])

FIELDS = {'missing_input':'inputs', 'wrong_input':'inputs',
          'missing_definition':'definitions', 'wrong_definition':'definitions',
          'wrong_statement':'statement'}
BLOCKER = protocol.obj({'inference':protocol.TEXT,
                       'kind':{'enum':list(FIELDS)},
                       'subject':protocol.nullable(protocol.TEXT),
                       'explanation':protocol.TEXT})


def batch_schema():
    from frozen_graph import LOCAL_PROOFS
    return protocol.obj({'findings':protocol.array(BLOCKER,minItems=1,uniqueItems=True),
                         'local_proofs':LOCAL_PROOFS}, required=['findings'])


def context(frozen):
    from nl0 import closure
    spec, graph = frozen['spec'], frozen['graph']
    props = {p['id']:p for p in graph['propositions']}
    defs = {d['id']:d for d in spec['definitions']}
    return {r['id']:closure.inference_scope(r,props,defs) for r in graph['inferences']}


def same_scope(before, after):
    """Compare the declarations actually exposed to the receiving proof."""
    from nl0 import closure
    def actual(scope):
        inputs, output, definitions = scope
        return [closure.inference_port(row) for row in inputs],closure.inference_port(output),definitions
    return actual(before)==actual(after)


def proof_rows(frozen, rows):
    from frozen_graph import LOCAL_PROOFS, indexed
    if not rows:
        return {}
    protocol.validate(rows,LOCAL_PROOFS)
    drafts=indexed(rows)
    if drafts.keys()-indexed(frozen['graph']['inferences']).keys():
        raise ValueError('Use local proof bodies for current assigned inferences only')
    return drafts


def retained_proofs(frozen, batch, feedback):
    retained = proof_rows(frozen, feedback.get('local_proofs', []))
    retained.update(proof_rows(frozen, batch.get('local_proofs', [])))
    return list(retained.values())


def assess(frozen, batch):
    """Admit located blockers against the same effective scope the author sees."""
    protocol.validate(batch,batch_schema())
    proof_rows(frozen,batch.get('local_proofs',[]))
    scopes=context(frozen)
    props={p['id'] for p in frozen['graph']['propositions']}
    defs={d['id'] for d in frozen['spec']['definitions']}
    issues=[]
    for f in batch['findings']:
        rid, kind, subject = f['inference'], f['kind'], f['subject']
        if rid not in scopes:
            raise ValueError('Select an inference in the assigned global revision: '+rid)
        inputs, _, definitions=scopes[rid]
        known, delivered=(defs,definitions) if FIELDS[kind]=='definitions' else (props,inputs)
        available={row['id'] for row in delivered}
        related=[subject] if subject in props else []
        if kind.startswith('missing_') and subject is not None:
            if subject not in known:
                raise ValueError(f'{rid}: {subject} is unregistered. Describe the exact missing content with subject=null.')
            if subject in available:
                raise ValueError(f'{rid}: {subject} is already supplied in the conditional packet. Continue the proof or locate an actual incompatibility.')
        if kind in {'wrong_input','wrong_definition'} and subject not in available:
            raise ValueError(f'{rid}: choose an existing item from the actual conditional packet')
        if kind=='wrong_statement' and subject not in props:
            raise ValueError(f'{rid}: choose the actual incorrect intermediate proposition')
        issue=locate(frozen,{'inference':rid,'related_propositions':related,'field':FIELDS[kind],
                             'explanation':f'{kind} {subject or "unregistered content"}. '+f['explanation']})
        issue['id']=f'ISSUE{len(issues)+1:03d}'
        issues.append(issue)
    return {'issues':issues,'blockers':batch['findings']}


def check_revision(previous, after, blockers):
    """Keep unchanged affected interfaces with their author for another edit."""
    before = context(previous)
    unchanged={f['inference'] for f in blockers if f['inference'] in after
               and same_scope(before[f['inference']],after[f['inference']])}
    if unchanged:
        raise ValueError('GRAPH_REPAIR_SCOPE: the reported conditional packets are unchanged at '
                         +', '.join(sorted(unchanged))+'. Repair the affected premises, statement or definitions.')


def revision_feedback(history, selected, current):
    """Prepare the next local assignment from the actual previous repair handoff."""
    from controller_common import verify_bindings
    import nl0
    previous = history['global']
    if previous != nl0.load(selected['path'])['previous']:
        raise ValueError('Graph findings belong to a different predecessor')
    verify_bindings([previous,*history['evidence']])
    record = nl0.load(previous['path'])
    verify_bindings([record['spec'],record['graph']])
    before = {key:nl0.load(record[key]['path']) for key in ('spec','graph')}
    old, new = context(before), context(current)
    compatible = {key for key in old.keys() & new.keys() if same_scope(old[key],new[key])}
    if any(before['spec'][key] != current['spec'][key] for key in ('parameters','logic','pins','hypotheses')):
        compatible = set()
    report = history['obligations']
    drafts = []
    if 'blockers' in report:
        accepted = nl0.load(history['evidence'][0]['path'])
        drafts = [row for row in accepted['local_proofs'] if row['id'] in compatible]
    return {'previous_graph':previous,'current_graph':selected,'issues':report['issues'],
            'blockers':report.get('blockers',[]), 'changed_inferences':sorted(new.keys()-compatible),
            'local_proofs':drafts}


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
    events=[json.loads(line) for line in (stage/'tools.jsonl').read_text().splitlines()]
    batch=accepted.get('version')==VERSION
    submission=accepted['batch'] if batch else accepted['finding']
    if not any(e['tool']==TOOL and e['arguments']==submission and e['result'].get('stage_complete') is True for e in events):
        raise ValueError('No completed located graph issue submission')
    if not batch:
        return {'issues':[locate(frozen,submission)]}
    feedback={}
    path=inputs.with_name(FEEDBACK)
    if path.is_file():
        if manifest['task_documents'].get(FEEDBACK)!=bind(path)['sha256']:
            raise ValueError('Graph repair feedback changed during authoring')
        feedback=nl0.load(path)
    if accepted['local_proofs']!=retained_proofs(frozen,submission,feedback):
        raise ValueError('Local drafts differ from reported graph repair evidence')
    return assess(frozen,submission)
