"""One global NL0 interface and two producers. Local authors supply only R bodies."""
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
FROZEN = 'frozen-global.json'
DIRECT = 'nl0-global'
BASIS = 'basis-global-metadata'
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

def checked_receipt(source, owner):
    source = Path(source)
    nl0.validate(source/'nl0.json',source/'spec.json',global_only=True)
    receipt = source/'checked-global.json'
    write(receipt, {'version':'yui-global-1','owner':owner,'spec':bind(source/'spec.json'),
                    'graph':bind(source/'nl0.json')})
    return bind(receipt)

def read_receipt(binding):
    verify_bindings([binding])
    record = nl0.load(binding['path'])
    if record['version'] != 'yui-global-1' or record['owner'] not in (DIRECT,BASIS):
        raise ValueError('Unknown global graph authority')
    verify_bindings([record['spec'],record['graph']])
    _, graph, spec, *_ = nl0.validate(record['graph']['path'],record['spec']['path'],global_only=True)
    return {'spec':spec, 'graph':graph}

def read_frozen(binding):
    if Path(binding['path']).name != 'frozen.json':
        raise ValueError('A frozen global graph is required')
    return read_receipt(binding)


def check_frozen(frozen, spec, graph):
    before = {k:v for k,v in frozen['spec'].items() if k!='inputs'}
    after = {k:v for k,v in spec.items() if k!='inputs'}
    if before != after or shape(graph) != shape(frozen['graph']):
        raise ValueError('Frozen global specification or dependency changed; return the finding to its global owner')

class AuthorContract(NL0Contract):
    def __init__(self, directory, documents, case_id, phase):
        super().__init__(directory, documents, case_id, global_only=phase!=LOCAL)
        self.expected_inputs = [r for r in self.expected_inputs if Path(r['path']).name not in
            {FROZEN,'prior-global.json','global-findings.json','baseline.json','repair-obligations.json'}]
        self.phase = phase
        self.prior = json.loads(documents['prior-global.json'])['spec'] if 'prior-global.json' in documents and phase!=LOCAL else None
        self.frozen = json.loads(documents[FROZEN]) if phase==LOCAL else None
        self.seed = json.loads(documents['global-nl0.json']) if phase==BASIS else None
        step = protocol.obj({'id':protocol.STRING, 'inputs':protocol.array(protocol.STRING),
                             'output':protocol.STRING, 'definitions':protocol.array(protocol.STRING)})
        if phase==DIRECT:
            form = protocol.obj({'spec':OBJECT,'propositions':protocol.array(OBJECT),
                                 'inferences':protocol.array(step,minItems=1)})
        elif phase==BASIS:
            form = protocol.obj({'spec':OBJECT, 'proposition_details':OBJECT,'inference_definitions':OBJECT})
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
            if self.phase==DIRECT:
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
            if any(spec.get(key) != self.prior[key] for key in ORIGINAL_FIELDS):
                raise ValueError('SOURCE_CHANGE_REQUIRES_USER: preserve the original target, parameters and hypotheses')
        if self.frozen:
            check_frozen(self.frozen, expanded['spec'],expanded['graph'])
        return super()._validate(expanded)

def global_stage(job, budget, *, owner, previous=None, findings=None):
    import basis
    from clean_stage import ArtifactStage
    from full_workflow import stage_seconds
    from full_workflow import accepted
    from controller_common import copy_problem_documents
    directory=Path(job['root'])/'global-graphs'
    directory.mkdir(exist_ok=True)
    attempt=directory/f'{len(list(directory.glob("[0-9]*")))+1:04d}'
    inputs=attempt/'inputs'
    inputs.mkdir(parents=True)
    copy_problem_documents(basis.problem_inputs(job),inputs)
    if previous:
        write(inputs/'prior-global.json',read_frozen(previous))
        write(inputs/'global-findings.json',findings)
    manifest(inputs)
    prompt=('Choose natural small inference nodes suitable for independent Lean workers. Keep shared witnesses and local scopes intact. '
            'Freeze the complete target, original H, parameters, definitions, sources and dependency graph. '
            'Use the NL0 specification and proposition fields, including nontrivial M/E source evidence. '
            'Each inference here has only id, inputs, output and definitions. No local proof paragraphs yet. ')
    if owner==BASIS:
        prompt+=('Use the already selected global-nl0.json exactly. Submit only spec, proposition_details '
                 '(ID to kind, definitions, binders, objects and source/origin as required), and '
                 'inference_definitions (R ID to D IDs). Do not regenerate nodes, statements or edges.')
    else:
        prompt+='Submit spec, propositions and inferences. Direct conditional external sources remain available.'
    if previous:
        prompt+=' Repair the located global findings in the supplied prior version. Preserve the original target and H.'
    stage=ArtifactStage(attempt/'stage',prompt,phase=owner,kind='nl0',case_id=job['case'],
                        inputs=inputs/'inputs.json',budget=budget,timeout=stage_seconds(budget))
    from role_sessions import Sessions
    owner_sessions=Sessions()
    with owner_sessions.use(owner):
        stage.execute()
    accepted(attempt)
    canonical={'spec':nl0.load(stage.logs/'case/spec.json'),'graph':nl0.load(stage.logs/'case/nl0.json')}
    if canonical!=nl0.load(stage.logs/'accepted.json'):
        raise ValueError('Global submit differs from the accepted graph')
    receipt=checked_receipt(stage.logs/'case',owner)
    if previous:
        before, after=read_frozen(previous),read_receipt(receipt)
        if any(before['spec'][key]!=after['spec'][key] for key in ORIGINAL_FIELDS):
            from execution_health import StageFailure
            raise StageFailure('SOURCE_CHANGE_REQUIRES_USER','Global revision changed the original target or hypotheses',
                               phase=owner,evidence=receipt['path'])
    owner_sessions.close_all('GLOBAL_GRAPH_CHECKED',[Path(receipt['path'])])
    return receipt

def select(job, checked):
    """Publish only the reviewed graph and specification of this case."""
    root = Path(job['root']).resolve()
    source = Path(checked['path']).resolve()
    if (not source.is_relative_to(root/'global-graphs') or
            source.relative_to(root/'global-graphs').parts[1:] != ('stage','case','checked-global.json')):
        raise ValueError('Expected a checked global graph from this case')
    frozen_path = source.with_name('frozen.json')
    # Validate a private copy, then publish those exact bytes without overwriting a prior freeze.
    with tempfile.TemporaryDirectory(dir=source.parent) as temp:
        candidate = Path(temp)/'receipt.json'
        candidate.write_bytes(source.read_bytes())
        receipt = bind(candidate)
        if receipt['sha256'] != checked['sha256']:
            raise ValueError('The checked global receipt changed before freeze')
        record = nl0.load(candidate)
        if record['spec'] != bind(source.with_name('spec.json')) or record['graph'] != bind(source.with_name('nl0.json')):
            raise ValueError('The checked global specification or graph differs from this stage')
        read_receipt(receipt)
        try:
            os.link(candidate, frozen_path)
        except FileExistsError:
            pass
    frozen = bind(frozen_path)
    if frozen['sha256'] != checked['sha256']:
        raise ValueError('The frozen global receipt differs from the checked revision')
    write(root/'global-selection.json', frozen)
    return frozen

def issue_owner(issue, global_owner):
    """Distinguish frozen proof edges/statements from graph metadata and local arguments."""
    fields=issue.get('location','').strip('/').split('/')
    if fields[0]=='spec':return 'global'
    if fields[:2]==['graph','propositions']:
        protected=len(fields)<=3 or fields[3] in {'id','statement'}
    elif fields[:2]==['graph','inferences']:
        protected=(len(fields)<=2 or (len(fields)==3 and issue.get('criterion')=='structure')
                   or (len(fields)>3 and fields[3] in {'id','inputs','output'}))
        if not protected and (len(fields)<=3 or fields[3]!='definitions'):return 'local'
    else:return 'local'
    return 'basis' if protected and global_owner==BASIS else 'global'


def local_stage(job, directory, budget, *, baseline=None, obligations=None):
    import basis
    import nl0_author
    import full_workflow
    from clean_stage import ArtifactStage
    root=Path(job['root'])
    previous=nl0.load(root/'global-selection.json')
    owner=nl0.load(previous['path'])['owner']
    issues=(obligations or {}).get('issues',[])
    owners={issue_owner(issue,owner) for issue in issues}
    if 'basis' in owners:
        from workflow_execution import active
        session=active.get()
        if session is None:raise ValueError('A basis graph revision requires its owning case')
        basis.run(job,budget,session.progress,graph_findings=obligations)
    if owners & {'basis','global'}:
        previous=global_stage(job,budget,owner=owner,previous=previous,findings=obligations)
        previous=select(job,previous)
    frozen=read_frozen(previous)
    nl0_author.prepare(basis.problem_inputs(job),directory,baseline=baseline,obligations=obligations)
    inputs=directory/'inputs'
    write(inputs/FROZEN,frozen)
    manifest(inputs)
    prompt=('Read frozen-global.json and the original proof. The controller supplies all global declarations, '
            'statements and inference interfaces. Submit local_proofs with the rules, scoped locals, argument and '
            'actual applications of every R. Use the NL0 authoring and closure rules. Use check_draft, '
            'read_author_packet and record_author_checks before submitting accept_candidate. '
            'Only the detailed proofs are yours to edit. Read located repair findings when supplied.')
    stage=ArtifactStage(directory/'stage',prompt,phase=LOCAL,kind='nl0',case_id=job['case'],
                        inputs=inputs/'inputs.json',budget=budget,timeout=full_workflow.stage_seconds(budget))
    record=nl0.load(previous['path'])
    evidence(Path(record['graph']['path']).parent,frozen['graph'],stage.validator.directory)
    stage.execute()
    budget.execution.check()
    full_workflow.nl0_artifact_for_audit(directory)
    source=stage.validator.directory
    check_frozen(frozen,nl0.load(source/'spec.json'),nl0.load(source/'nl0.json'))
    return source
