"""Versioned NL0 working graphs. Local authors write R bodies against one selected revision."""
from copy import deepcopy
import json
import os
import tempfile
from pathlib import Path

import artifact_protocol as protocol
import nl0
from artifact_validation import NL0Contract
from controller_common import bind, manifest, verify_bindings, write
from staging_storage import copy_input

ORIGINAL_FIELDS = ('full_target', 'conclusion', 'parameters', 'hypotheses')
GLOBAL_FIELDS = ('id', 'inputs', 'output', 'definitions')
BODY_FIELDS = ('rules', 'locals', 'argument', 'applications')
ASSIGNED = 'assigned-global.json'
DIRECT = 'nl0-global'
BASIS = 'nl0-global-from-basis'
LEGACY_BASIS = 'basis-global-metadata'
LOCAL = 'nl0-local-authoring'
OBJECT = {'type':'object', 'additionalProperties':True}

def shape(graph):
    return {'propositions':graph['propositions'],
            'inferences':[{name:row[name] for name in GLOBAL_FIELDS} for row in graph['inferences']]}

def indexed(rows):
    result = {row['id']:row for row in rows}
    if len(rows) != len(result):
        raise ValueError('Repeated global or local node ID')
    return result

def evidence(source, graph, target):
    import source_preparation
    for path in source_preparation.evidence_paths(graph, source):
        dest = target / path.relative_to(source)
        if dest.exists():
            if nl0.sha(dest) != nl0.sha(path):
                raise ValueError('Frozen evidence collision at '+str(dest))
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            copy_input(path, dest)

def checked_receipt(source, owner, *, foundation=None, previous=None):
    source = Path(source)
    nl0.validate(source/'nl0.json',source/'spec.json',global_only=True)
    receipt = source/'checked-global.json'
    write(receipt, {'version':'yui-working-graph-2','owner':owner,'previous':previous,'spec':bind(source/'spec.json'),
                    'graph':bind(source/'nl0.json'),**({'foundation':foundation} if foundation else {})})
    return bind(receipt)

def read_receipt(binding):
    verify_bindings([binding])
    record = nl0.load(binding['path'])
    owners={'yui-global-1':(DIRECT,LEGACY_BASIS),'yui-working-graph-2':(DIRECT,BASIS)}
    if record['owner'] not in owners.get(record['version'],()):
        raise ValueError('Unknown global graph authority')
    verify_bindings([record['spec'],record['graph']]+([record['foundation']] if 'foundation' in record else []))
    _, graph, spec, *_ = nl0.validate(record['graph']['path'],record['spec']['path'],global_only=True)
    return {'spec':spec, 'graph':graph}

def read_working(binding):
    if Path(binding['path']).name not in ('working.json','frozen.json'):
        raise ValueError('A selected NL0 working revision is required')
    return read_receipt(binding)


def check_assignment(frozen, spec, graph):
    before = {k:v for k,v in frozen['spec'].items() if k!='inputs'}
    after = {k:v for k,v in spec.items() if k!='inputs'}
    if before != after or shape(graph) != shape(frozen['graph']):
        raise ValueError('Assigned global specification or dependency changed; report a graph issue to its NL0 owner')

class AuthorContract(NL0Contract):
    def __init__(self, directory, documents, case_id, phase):
        super().__init__(directory, documents, case_id, global_only=phase!=LOCAL)
        self.expected_inputs = [r for r in self.expected_inputs if Path(r['path']).name not in
            {ASSIGNED,'protected-roots.json','prior-global.json','global-findings.json','baseline.json','repair-obligations.json'}]
        self.phase = phase
        self.prior = json.loads(documents['prior-global.json']) if 'prior-global.json' in documents and phase!=LOCAL else None
        self.earlier=json.loads(documents.get('protected-roots.json','[]'))
        self.frozen = json.loads(documents[ASSIGNED]) if phase==LOCAL else None
        self.seed = json.loads(documents['global-nl0.json']) if phase==BASIS else None
        step = protocol.obj({'id':protocol.STRING, 'inputs':protocol.array(protocol.STRING),
                             'output':protocol.STRING, 'definitions':protocol.array(protocol.STRING)})
        if phase in (DIRECT,BASIS):
            form = protocol.obj({'spec':OBJECT,'propositions':protocol.array(OBJECT),
                                 'inferences':protocol.array(step,minItems=1)})
            if phase==BASIS:
                form = protocol.choice(form,protocol.obj({'spec':OBJECT, 'proposition_details':OBJECT,'inference_definitions':OBJECT}))
        else:
            fields = {'rules':protocol.array(protocol.STRING),'locals':protocol.array(OBJECT),
                      'argument':protocol.array(OBJECT,minItems=1),'applications':protocol.array(OBJECT)}
            form = protocol.obj({'local_proofs':protocol.array(protocol.obj({'id':protocol.STRING,**fields}),minItems=1)})
        from payload_protocols import editable
        self.schema = editable(form) if phase==LOCAL else protocol.choice(form,protocol.obj({'accept_candidate':{'type':'integer','minimum':1}}))

    def __call__(self, value):
        protocol.validate(value,self.schema)
        if set(value) & {'accept_candidate','base_candidate','base_input'}:
            return super().__call__(value)
        if self.phase==LOCAL:
            rows = indexed(value['local_proofs'])
            expanded = deepcopy(self.frozen)
            steps = expanded['graph']['inferences']
            if set(rows) != set(indexed(steps)):
                raise ValueError('Supply one local proof for each frozen R ID')
            for step in steps:
                step.update({name:rows[step['id']][name] for name in BODY_FIELDS})
        else:
            spec = deepcopy(value['spec'])
            spec.setdefault('format_version',2)
            if 'propositions' in value:
                props, steps = value['propositions'], value['inferences']
            else:
                details = value['proposition_details']
                definitions = value['inference_definitions']
                if set(details)!=set(indexed(self.seed['propositions'])) or set(definitions)!=set(indexed(self.seed['inferences'])):
                    raise ValueError('Supply metadata for exactly the existing basis graph IDs')
                props, steps = [], []
                for row in self.seed['propositions']:
                    extra=details[row['id']]
                    if not isinstance(extra,dict) or {'id','statement'} & extra.keys():
                        raise ValueError('Basis proposition identities and statements are supplied by the controller')
                    props.append({**row,**extra})
                for row in self.seed['inferences']:
                    steps.append({k:row[k] for k in ('id','inputs','output')} |
                                 {'definitions':definitions[row['id']]})
            expanded={'spec':spec,'graph':{'format_version':2,'propositions':props,'inferences':steps}}
        result=super().__call__(expanded)
        value.clear()
        value.update(expanded)
        return result

    def _validate(self, expanded):
        if self.prior:
            spec = expanded['spec']
            if any(spec.get(key) != self.prior['spec'][key] for key in ORIGINAL_FIELDS):
                raise ValueError('SOURCE_CHANGE_REQUIRES_USER: preserve the original target, parameters and hypotheses')
        if self.frozen:
            check_assignment(self.frozen, expanded['spec'],expanded['graph'])
        return super()._validate(expanded)

    def validate_canonical(self,spec,graph):
        if self.prior:
            current={'spec':spec,'graph':graph}
            for prior in [self.prior,*self.earlier]:
                preserve_originals(prior,current,basis=self.phase==BASIS)

def preserve_originals(prior, current, *, basis):
    before,after=prior['spec'],current['spec']
    if any(before[k]!=after[k] for k in ORIGINAL_FIELDS):
        raise ValueError('SOURCE_CHANGE_REQUIRES_USER: original problem changed')
    old,new=indexed(prior['graph']['propositions']),indexed(current['graph']['propositions'])
    protected={k for k in old if k=='P' or k.startswith('H') or (basis and k.startswith(('M','E')))}
    used_definitions=set()
    for key in protected:
        row=old[key]
        if key in new:
            if row!=new[key]:
                raise ValueError('Original or foundation declaration changed at '+key)
            used_definitions.update(row['definitions'])
        elif key=='P' or key.startswith('H'):
            raise ValueError('Original proposition omitted: '+key)
    old_defs,new_defs=indexed(before['definitions']),indexed(after['definitions'])
    pending=list(used_definitions)
    while pending:
        rid=pending.pop()
        definition=old_defs[rid]
        if definition!=new_defs.get(rid):
            raise ValueError('Definition used by a protected declaration changed: '+rid)
        dependencies=set(definition.get('depends_on',[]))-used_definitions
        used_definitions.update(dependencies)
        pending.extend(dependencies)


def prior_versions(binding,root):
    seen=set()
    while binding:
        path=Path(binding['path'])
        if path in seen or not path.is_relative_to(root/'global-graphs'):
            raise ValueError('Invalid NL0 working revision history')
        seen.add(path)
        checked=read_working(binding)
        record=nl0.load(path)
        yield checked,record
        binding=record.get('previous')


def global_stage(job, budget, *, owner, previous=None, findings=None, foundation=None):
    import basis
    from clean_stage import ArtifactStage
    from full_workflow import stage_seconds
    from full_workflow import accepted
    from controller_common import copy_problem_documents
    directory=Path(job['root'])/'global-graphs'
    directory.mkdir(exist_ok=True)
    number=max((int(p.name) for p in directory.iterdir() if p.name.isdecimal()),default=0)
    while True:
        number+=1
        attempt=directory/f'{number:04d}'
        try:
            attempt.mkdir()
            break
        except FileExistsError:
            continue
    inputs=attempt/'inputs'
    inputs.mkdir(parents=True)
    copy_problem_documents(basis.problem_inputs(job),inputs)
    if previous:
        versions=prior_versions(previous,Path(job['root']).resolve())
        latest,_=next(versions)
        write(inputs/'prior-global.json',latest)
        roots=[]
        for old,_ in versions:
            spec={k:old['spec'][k] for k in (*ORIGINAL_FIELDS,'definitions')}
            props=[p for p in old['graph']['propositions'] if p['id']=='P' or p['id'].startswith(('H','E','M'))]
            saved={'spec':spec,'graph':{'propositions':props}}
            if saved not in roots:roots.append(saved)
        if roots:write(inputs/'protected-roots.json',roots)
        write(inputs/'global-findings.json',findings)
    manifest(inputs)
    prompt=('Choose natural small inference nodes suitable for independent Lean workers. Keep shared witnesses and local scopes intact. '
            'Preserve the complete target, original H, parameters and foundation material. You own the intermediate statements and edges. '
            'Use the NL0 specification and proposition fields, including nontrivial M/E source evidence. '
            'Each inference here has only id, inputs, output and definitions. No local proof paragraphs yet. ')
    if owner==BASIS:
        prompt+=('Start from the structured route in global-nl0.json. For an unchanged seed submit spec, '
                 'proposition_details and inference_definitions. To revise N/R statements or dependencies, submit '
                 'spec, propositions and inferences. Use only the authorized foundations, with their exact meanings. ')
    else:
        prompt+='Submit spec, propositions and inferences. Direct conditional external sources remain available.'
    if previous:
        prompt+=' Repair the located global findings in the supplied prior version. Preserve the original target and H.'
    stage=ArtifactStage(attempt/'stage',prompt,phase=owner,kind='nl0',case_id=job['case'],
                        inputs=inputs/'inputs.json',budget=budget,timeout=stage_seconds(budget))
    if previous:
        prior_record=nl0.load(previous['path'])
        prior_graph=read_working(previous)['graph']
        evidence(Path(prior_record['graph']['path']).parent,prior_graph,stage.validator.directory)
    from role_sessions import Sessions
    owner_sessions=Sessions()
    with owner_sessions.use(owner):
        stage.execute()
    accepted(attempt)
    canonical={'spec':nl0.load(stage.logs/'case/spec.json'),'graph':nl0.load(stage.logs/'case/nl0.json')}
    if canonical!=nl0.load(stage.logs/'accepted.json'):
        raise ValueError('Global submit differs from the accepted graph')
    receipt=checked_receipt(stage.logs/'case',owner,foundation=foundation,previous=previous)
    if previous:
        before, after=read_working(previous),read_receipt(receipt)
        if any(before['spec'][key]!=after['spec'][key] for key in ORIGINAL_FIELDS):
            from execution_health import StageFailure
            raise StageFailure('SOURCE_CHANGE_REQUIRES_USER','Global revision changed the original target or hypotheses',
                               phase=owner,evidence=receipt['path'])
    owner_sessions.close_all('GLOBAL_GRAPH_CHECKED',[Path(receipt['path'])])
    return receipt

def select(job, checked, *, previous=None):
    import fcntl
    with (Path(job['root'])/'global-graphs/.selection.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        return _select(job,checked,previous)


def _select(job, checked, previous):
    """Assign a checked working revision to local authors, retaining older versions."""
    root = Path(job['root']).resolve()
    source = Path(checked['path']).resolve()
    if (not source.is_relative_to(root/'global-graphs') or
            source.relative_to(root/'global-graphs').parts[1:] != ('stage','case','checked-global.json')):
        raise ValueError('Expected a checked global graph from this case')
    revision=source.with_name('working.json')
    selection=root/'global-selection.json'
    current=nl0.load(selection) if selection.exists() else None
    if current and current['path']==str(revision) and current['sha256']==checked['sha256']:
        read_working(current)
        return current
    if current!=previous:
        raise ValueError('Stale NL0 global selection')
    with tempfile.TemporaryDirectory(dir=source.parent) as temp:
        candidate=Path(temp)/'receipt.json'
        candidate.write_bytes(source.read_bytes())
        if bind(candidate)['sha256']!=checked['sha256']:
            raise ValueError('The checked global receipt changed before assignment')
        record=nl0.load(candidate)
        if (record['spec']!=bind(source.with_name('spec.json')) or record['graph']!=bind(source.with_name('nl0.json'))
                or record.get('previous')!=previous):
            raise ValueError('The checked global specification, parent or graph differs from this stage')
        proposed=read_receipt(bind(candidate))
        for old,record_old in prior_versions(current,root):
            if record_old.get('foundation')!=record.get('foundation') or record_old['owner']!=record['owner']:
                raise ValueError('Cannot replace the selected foundation or entry during graph revision')
            preserve_originals(old,proposed,basis=record['owner']==BASIS)
            if ({k:v for k,v in old['spec'].items() if k!='inputs'}==
                    {k:v for k,v in proposed['spec'].items() if k!='inputs'}
                    and shape(old['graph'])==shape(proposed['graph'])):
                from execution_health import StageFailure
                from graph_repair import UNRESOLVED
                raise StageFailure(UNRESOLVED,'The graph owner returned an unchanged or previously rejected revision',
                                   phase='nl0-global',evidence=source)
        try:
            os.link(candidate,revision)
        except FileExistsError:
            pass
    selected=bind(revision)
    if selected['sha256']!=checked['sha256']:
        raise ValueError('The assigned global receipt differs from the checked revision')
    write(selection,selected)
    return selected


def issue_owner(issue, global_owner=None):
    """Audit findings on shared declarations and ports belong to the global NL0 author."""
    fields=issue.get('location','').strip('/').split('/')
    if fields[0]=='spec' or fields[:2]==['graph','propositions']:return 'global'
    if fields[:2]==['graph','inferences']:
        if len(fields)<=2 or (len(fields)==3 and issue.get('criterion')=='structure'):
            return 'global'
        if len(fields)>3 and fields[3] in GLOBAL_FIELDS:return 'global'
    return 'local'


def local_stage(job, directory, budget, *, baseline=None, obligations=None):
    import basis
    import nl0_author
    import full_workflow
    import graph_repair
    from clean_stage import ArtifactStage
    root=Path(job['root'])
    previous=nl0.load(root/'global-selection.json')
    frozen=read_working(previous)
    nl0_author.prepare(basis.problem_inputs(job),directory,baseline=baseline,obligations=obligations)
    inputs=directory/'inputs'
    write(inputs/ASSIGNED,frozen)
    manifest(inputs)
    prompt=('Read assigned-global.json and the original proof. The controller supplies all global declarations, '
            'statements and inference interfaces. Submit local_proofs with the rules, scoped locals, argument and '
            'actual applications of every R. Use the NL0 authoring and closure rules. Use check_draft, '
            'read_author_packet and record_author_checks before submitting accept_candidate. '
            'Use report_graph_issue for a missing edge, a wrong R interface, or an incorrect intermediate statement. '
            'Give the R ID, field, related proposition IDs and a specific explanation. Report genuine mathematical gaps via report_obstacle. '
            'Only the detailed proofs are yours to edit. Read located repair findings when supplied.')
    stage=ArtifactStage(directory/'stage',prompt,phase=LOCAL,kind='nl0',case_id=job['case'],
                        inputs=inputs/'inputs.json',budget=budget,timeout=full_workflow.stage_seconds(budget))
    record=nl0.load(previous['path'])
    evidence(Path(record['graph']['path']).parent,frozen['graph'],stage.validator.directory)
    stage.execute()
    budget.execution.check()
    if nl0.load(stage.logs/'result.json').get('task_outcome')==graph_repair.STATUS:
        report=graph_repair.verify_local(stage.logs,previous)
        prior=None
        if stage.validator.last_valid_candidate is not None:
            from author_check import digest
            prior=stage.validator.directory
            candidate={'spec':nl0.load(prior/'spec.json'),'graph':nl0.load(prior/'nl0.json')}
            check_assignment(frozen,candidate['spec'],candidate['graph'])
            report.update(version='yui-repair-obligations-1',baseline_input='baseline.json',
                          baseline_content_sha256=digest(candidate))
        raise graph_repair.Request(report,baseline=prior,evidence=[stage.logs/'accepted.json'])
    full_workflow.nl0_artifact_for_audit(directory)
    source=stage.validator.directory
    check_assignment(frozen,nl0.load(source/'spec.json'),nl0.load(source/'nl0.json'))
    return source
