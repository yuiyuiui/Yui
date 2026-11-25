"""Located objections to the current NL0 graph. No report grants mathematical acceptance."""
import json
from pathlib import Path
import hashlib

import artifact_protocol as protocol
from graph_outline import SOURCE_SPAN, source_sizes

STATUS = 'NL0_GRAPH_REVISION_REQUIRED'
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
                       'explanation':protocol.TEXT,
                       'source_spans':protocol.array(SOURCE_SPAN,uniqueItems=True)},
                       required=['inference','kind','subject','explanation'])


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


def assess(frozen, batch, documents=None):
    """Admit located blockers against the same effective scope the author sees."""
    protocol.validate(batch,batch_schema())
    proof_rows(frozen,batch.get('local_proofs',[]))
    scopes=context(frozen)
    props={p['id'] for p in frozen['graph']['propositions']}
    defs={d['id'] for d in frozen['spec']['definitions']}
    issues=[]
    originals={Path(row['path']).name:row['sha256'] for row in frozen['spec']['inputs']}
    offsets={}
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
        spans=f.get('source_spans',[])
        for name in {span['from_task'] for span in spans}-offsets.keys():
            text=(documents or {}).get(name)
            if text is None or hashlib.sha256(text.encode()).hexdigest()!=originals.get(name):
                raise ValueError(f'{rid}: graph issue source is not a bound original task input: {name}')
        source_sizes(spans,documents or {},offsets,rid)
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


def revision_feedback(history, selected, current, *, rejections=None):
    """Prepare the next local assignment from the actual previous repair handoff."""
    from controller_common import verify_bindings
    from frozen_graph import BODY_FIELDS, check_assignment
    import nl0
    previous = history['global']
    if previous != nl0.load(selected['path'])['previous']:
        raise ValueError('Graph findings belong to a different predecessor')
    baseline = history.get('baseline', {})
    campaigns = history.get('campaigns', [])
    verify_bindings([previous,*history['evidence'],*baseline.values(),*campaigns])
    record = nl0.load(previous['path'])
    verify_bindings([record['spec'],record['graph']])
    before = {key:nl0.load(record[key]['path']) for key in ('spec','graph')}
    old, new = context(before), context(current)
    compatible = {key for key in old.keys() & new.keys() if same_scope(old[key],new[key])}
    if any(before['spec'][key] != current['spec'][key] for key in ('parameters','logic','pins','hypotheses')):
        compatible = set()
    report = history['obligations']
    drafts = {}
    unresolved = []
    if baseline:
        detailed = {key:nl0.load(baseline[file]['path']) for key,file in (('spec','spec'),('graph','nl0'))}
        check_assignment(before,detailed['spec'],detailed['graph'])
        compatible -= disputed_inferences(detailed['graph'], report['issues'])
        drafts = {row['id']:{key:row[key] for key in ('id', *BODY_FIELDS)}
                  for row in detailed['graph']['inferences']}
        if campaigns:
            if rejections is None:
                from audit_rejections import RejectedReviews
                rejections=RejectedReviews(Path(row['path']).parent for row in campaigns)
            matching=sorted(compatible & drafts.keys() & rejections.history.keys())
            if matching:
                source=Path(baseline['nl0']['path']).parent
                data=nl0.validate(source/'nl0.json',source/'spec.json')
                for rid in matching:
                    rejected=rejections.match(source,rid,data=data)
                    if rejected:
                        evidence=rejected['review']
                        unresolved.append({'inference':rid,'review':nl0.load(evidence['path']),'evidence':evidence})
    if 'blockers' in report:
        accepted = nl0.load(history['evidence'][0]['path'])
        drafts.update(proof_rows(before,accepted['local_proofs']))
    pending={row['inference'] for row in unresolved}
    return {'previous_graph':previous,'current_graph':selected,'issues':report['issues'],
            'blockers':report.get('blockers',[]), 'changed_inferences':sorted(new.keys()-compatible),
            'local_proofs':[row for rid,row in drafts.items() if rid in compatible-pending],
            'unresolved_reviews':unresolved}


def disputed_inferences(graph, issues):
    """An audit's own located objection invalidates that draft even if its port survives."""
    result = set()
    producers = {row['output']:row['id'] for row in graph['inferences']}
    for issue in issues:
        path = issue['location'].strip('/').split('/')
        if len(path) < 3 or path[0] != 'graph' or not path[2].isdigit():
            continue
        index = int(path[2])
        if path[1]=='inferences' and index < len(graph['inferences']):
            result.add(graph['inferences'][index]['id'])
        if path[1]=='propositions' and index < len(graph['propositions']):
            owner = producers.get(graph['propositions'][index]['id'])
            if owner:
                result.add(owner)
    return result


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
    from frozen_graph import ASSIGNED,ASSIGNED_PROOFS,read_working
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
    if 'saved_proofs' in accepted:
        saved=stage/'case'/ASSIGNED_PROOFS
        if accepted['saved_proofs']!=bind(saved):
            raise ValueError('Saved local proofs changed before graph repair')
        feedback={'local_proofs':nl0.load(saved)}
    if accepted['local_proofs']!=retained_proofs(frozen,submission,feedback):
        raise ValueError('Local drafts differ from reported graph repair evidence')
    names={span['from_task'] for row in submission['findings'] for span in row.get('source_spans',[])}
    originals={Path(row['path']).name for row in frozen['spec']['inputs']}
    documents={name: (inputs.parent/name).read_text() for name in names.intersection(originals)}
    return assess(frozen,submission,documents)


def consecutive_reports(root, receipt):
    """Read consecutive named local objections from the exact repair lineage."""
    from controller_common import bind, verify_bindings
    import nl0

    groups={};wanted=None;seen=set();newer=None
    job=bind(root/'job.json')
    owners=[job]
    current=nl0.load(job['path'])
    if current.get('graph_continuation'):
        from graph_continuation import descriptor
        owners.extend(descriptor(current)['historical_jobs'])
    while receipt is not None:
        path=Path(receipt['path'])
        if path.parent!=root/'handoffs' or path in seen:
            raise ValueError('Invalid NL0 repair history lineage')
        seen.add(path)
        verify_bindings([receipt])
        report=nl0.load(path)
        graph=report['global']
        if report['job'] not in owners or not Path(graph['path']).is_relative_to(root/'global-graphs'):
            raise ValueError('NL0 repair history belongs to a different run')
        verify_bindings([graph])
        if newer is not None and newer!=graph:
            verify_bindings([newer])
            if nl0.load(newer['path'])['previous']!=graph:
                raise ValueError('NL0 repair history is not a predecessor of the current graph')
        blockers=report['obligations'].get('blockers',[])
        pairs={(row['inference'],row['subject']) for row in blockers if row['subject'] is not None}
        wanted=pairs if wanted is None else wanted & pairs
        if not wanted:break
        [evidence]=report['evidence']
        verify_bindings([evidence])
        stage=Path(evidence['path']).parent
        if not stage.is_relative_to(root/'nl0') or stage/'accepted.json'!=Path(evidence['path']):
            raise ValueError('NL0 repair history lacks its own qualified local report')
        checked=verify_local(stage,graph)
        if checked['blockers']!=blockers or checked['issues']!=report['obligations']['issues']:
            raise ValueError('NL0 repair history differs from the accepted local report')
        for consumer,interface in sorted(wanted):
            findings=[row for row in blockers if (row['inference'],row['subject'])==(consumer,interface)]
            groups.setdefault((consumer,interface),[]).append(
                {'graph':graph,'receipt':receipt,'evidence':evidence,'findings':findings})
        newer=nl0.load(graph['path'])['previous']
        receipt=report.get('previous_repair')
    return [{'consumer':consumer,'interface':interface,'reports':list(reversed(reports))}
            for (consumer,interface),reports in groups.items() if len(reports)>1]
