"""Optional 2basis front end; mathematical review remains the shared Audit A.

Original target authority and active proof route are separate frozen inputs.
No source category, compilation result or author note confers Audit A acceptance.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
import stat

from controller_common import bind, manifest, write, verify_bindings, copy_problem_documents
from execution_health import StageFailure, require_review_execution
import ir
from staging_storage import copy_input
import basis_native
import basis_review
import basis_graph

LEGACY_VERSION = 'yui-basis-1'
VERSION = basis_graph.VERSION
CONTEXT = 'proof-context.json'
CONTEXT_VERSION = 'yui-basis-context-2'
MODES = {'conditional', 'unconditional'}


def mode(job):return job.get('formalization', 'conditional')


def validate_mode(selected, track, *, resume=None):
    if selected not in MODES:raise ValueError('Unknown formalization goal')
    proof_recovery=track=='translate' and resume and resume.get('mode')=='native-proof-cleanup'
    if selected=='unconditional' and track!='full' and not proof_recovery:
        raise ValueError('Unconditional formalization requires track=full, starting before NL0/Audit A')


def text(value, label):
    if not isinstance(value, str) or not value.strip():raise ValueError('Missing '+label)


def artifact_schema(version=None, *, planning=False):
    if version is None:
        import artifact_protocol as p
        return p.choice(artifact_schema(LEGACY_VERSION),artifact_schema(VERSION))
    modern = version==basis_graph.VERSION
    import artifact_protocol as p
    evidence=p.choice(p.obj({'input':p.TEXT}),p.obj({'path':p.TEXT,'sha256':p.TEXT}))
    branches=[]
    for category,kind in [(1,'mathlib'),(2,'lean-library'),(3,'derivation'),(4,'textbook')]:
        branches.append(p.obj({'id':{'type':'string','pattern':r'^B\d{3,}$'},'category':p.literal(category),
            'statement':p.TEXT,'justification':p.TEXT,'uses':p.array(p.TEXT,uniqueItems=True),
            'port':p.nullable({'type':'string','pattern':r'^[EM]\d{3}$'}),
            'compatibility':{'enum':['native','adapted','internal','unresolved']},
            'origin':p.obj({'kind':p.literal(kind),'reference':p.TEXT,'revision':p.TEXT,
                'evidence':p.array(evidence,minItems=1 if category==4 or (modern and category==2) else 0)}),
            'lean':({'type':'null'} if category==3 and not modern else p.obj({'type':p.TEXT,
                'proof':{'type':'null'} if category==4 else p.nullable(p.TEXT) if modern and planning else p.TEXT}))}))
    dependency=p.choice(*branches)
    return p.obj({'version':p.literal(version),**({'global_graph':basis_graph.schema()} if modern else {}),'full_target':p.TEXT,'proof':p.TEXT,'lean_header':p.TEXT,
        'dependencies':p.array(dependency),'replacements':p.array(p.obj({
            'original_dependency':p.TEXT,'replacement':p.array(p.TEXT,minItems=1),'explanation':p.TEXT}))})


def validate(value, target):
    import artifact_protocol as p
    if not isinstance(value,dict) or value.get('version') not in {LEGACY_VERSION,VERSION}:
        raise ValueError('Unknown basis protocol version')
    modern = value['version']==basis_graph.VERSION
    p.validate(value,artifact_schema(value['version']))
    if modern:basis_graph.active(value)
    if value['full_target']!=target:raise ValueError('Basis must preserve the complete original selected target verbatim')
    text(value['proof'], 'basis proof')
    header = value['lean_header'];text(header, 'basis Lean header')
    if (not header.startswith('import Mathlib\n') or re.search(
            r'\b(sorry|admit|axiom|opaque|unsafe|run_meta|run_elab|run_tac|native_decide|initialize|elab|macro|syntax|theorem|lemma|set_option)\b|(^|\n)\s*#', header)
            or re.search(r'\n\s*import\b', header)):
        raise ValueError('Basis header may contain pinned Mathlib import and object definitions only')
    if not isinstance(value['dependencies'], list):raise ValueError('Basis dependencies must be a list')
    rows = {};ports = set()
    for row in value['dependencies']:
        key = row['id']
        if not isinstance(key, str) or not re.fullmatch(r'B\d{3,}', key) or key in rows:
            raise ValueError('Invalid/duplicate basis ID')
        category = row['category']
        if type(category) is not int or category not in {1,2,3,4}:raise ValueError('Unknown basis category')
        text(row['statement'], 'basis statement');text(row['justification'], 'dependency justification')
        origin = row['origin']
        if origin['kind']!={1:'mathlib',2:'lean-library',3:'derivation',4:'textbook'}[category]:
            raise ValueError('Basis category/origin mismatch')
        for name in ('reference','revision'):text(origin[name], 'source '+name)
        if not isinstance(origin['evidence'], list):raise ValueError('Source evidence must be a list')
        if category==4 and not origin['evidence']:raise ValueError('Class 4 requires retained complete textbook evidence')
        if not isinstance(row['uses'], list) or any(not isinstance(k,str) for k in row['uses']) or len(set(row['uses']))!=len(row['uses']):
            raise ValueError('Invalid basis dependency links')
        port = row['port'];compatibility = row['compatibility']
        if port is not None:
            if not isinstance(port,str) or not re.fullmatch(r'[EM]\d{3}',port) or port in ports:
                raise ValueError('Invalid/duplicate basis port')
            ports.add(port)
        if category==3 and modern:
            if compatibility!='internal' or (port and not port.startswith('E')) or not row['uses']:
                raise ValueError('A prepared derivation needs reducible dependencies and an optional discharge port')
            ir.type_text(row['lean']['type']);ir.proof_text(row['lean']['proof'])
        elif category==3:
            if port is not None or compatibility!='internal' or row['lean'] is not None or not row['uses']:
                raise ValueError('Class 3 is an internal concrete derivation, never an E premise')
        else:
            lean = row['lean']
            ir.type_text(lean['type'])
            if category==4:
                if compatibility!='unresolved' or lean['proof'] is not None or not port or not port.startswith('E'):
                    raise ValueError('Class 4 remains an explicit E with no claimed proof')
            else:
                if compatibility not in {'native','adapted'}:raise ValueError('Separate proof origin from native/adapted compatibility')
                ir.proof_text(lean['proof'])
                if category==2 or compatibility=='adapted':
                    if (not modern or port) and (not port or not port.startswith('E')):raise ValueError('Prepared library/adapted proofs need provisional E ports')
                elif port is not None and not port.startswith('M'):
                    raise ValueError('Native Mathlib uses direct access or optional M ports')
        rows[key] = row
    order = [];active = set();seen = set()
    def visit(key):
        if key not in rows:raise ValueError('Unknown basis dependency '+key)
        if key in active:raise ValueError('Cyclic basis dependencies')
        if key in seen:return
        active.add(key)
        for dep in rows[key]['uses']:
            if dep in rows and (rows[key]['category']==3 and rows[dep]['category']==4 or
                    rows[key]['category'] in {1,2} and rows[dep]['category'] not in {1,2}):
                raise ValueError('A prepared/internal basis proof cannot depend on unresolved or unformalized premises')
            visit(dep)
        active.remove(key);seen.add(key);order.append(key)
    for key in rows:visit(key)
    replacements = value['replacements']
    if not isinstance(replacements,list):raise ValueError('Replacement map must be a list')
    old = set()
    for row in replacements:
        text(row['original_dependency'], 'original dependency');text(row['explanation'], 'replacement explanation')
        if row['original_dependency'] in old:raise ValueError('Duplicate original dependency mapping')
        old.add(row['original_dependency'])
        if not isinstance(row['replacement'],list) or not row['replacement'] or not set(row['replacement'])<=rows.keys():
            raise ValueError('Replacement must identify actual basis derivations/dependencies')
    return rows, order


def prepared(row):
    return row['category']!=4 and row['lean'] is not None


def declarations(value):
    rows, order = validate(value, value['full_target'])
    source = '\nnamespace YuiBasis\nset_option autoImplicit false\n'
    checks = [];roots = []
    for key in order:
        row = rows[key]
        if prepared(row):
            source += f"set_option Elab.async false in\ntheorem {key} : {row['lean']['type']} := by\n{ir.proof_text(row['lean']['proof'])}\n"
            checks.append((key, 'YuiBasis.'+key, row['lean']['type']));roots.append('YuiBasis.'+key)
        elif row['category']==4:
            declaration, check = basis_native.proposition_probe(row)
            source += declaration
            roots.append(check[1])
            checks.append(check)
    source += '\nend YuiBasis\n'
    return source, checks, roots


def verify_native_edges(value, directory):
    if value['version']!=basis_graph.VERSION:return
    inspected=ir.load(Path(directory)/'elaborated.json')
    declarations={r['name']:r for r in inspected['dependencies']['declarations']}
    names={'YuiBasis.'+r['id']:r['id'] for r in value['dependencies'] if prepared(r)}
    for row in value['dependencies']:
        if prepared(row):
            actual=basis_review.native_basis_dependencies('YuiBasis.'+row['id'],declarations,names)
            unexpected=set(actual)-set(row['uses'])
            if unexpected:raise ValueError('Undeclared native foundation dependency at '+row['id']+': '+', '.join(sorted(unexpected)))


def evidence_bindings(value, inputs, stage):
    result = []
    for row in value['dependencies']:
        for evidence in row['origin']['evidence']:
            if not isinstance(evidence,dict):raise ValueError('Invalid source evidence reference')
            if set(evidence)=={'input'}:
                name = evidence['input']
                if not isinstance(name,str) or Path(name).name!=name or name in {'inputs.json','prior-basis.json','repair-findings.json'}:
                    raise ValueError('Source input must be a declared document ID')
                declared = {r['id']:r for r in ir.load(Path(inputs)/'inputs.json')['inputs']}
                if name not in declared:raise ValueError(f"{row['id']}: undeclared basis source input: {name}")
                path=Path(inputs)/name
                binding=bind(path)
                if path.is_symlink() or declared[name]['path']!=name or binding['sha256']!=declared[name]['sha256']:
                    raise RuntimeError('Changed previously declared basis source: '+name)
            elif set(evidence)=={'path','sha256'}:
                name = evidence['path']
                if not isinstance(name, str) or not name:
                    raise ValueError(f"{row['id']}: expected a relative evidence filename")
                relative = Path(name);path = Path(stage)/relative
                if relative.is_absolute() or '..' in relative.parts or not path.resolve().is_relative_to(Path(stage).resolve()):
                    raise ValueError(f"{row['id']}: basis evidence escaped its author stage")
                try:
                    if not stat.S_ISREG(path.stat().st_mode):
                        raise ValueError(f"{row['id']}: evidence is not a regular file: {name}")
                    binding = bind(path)
                except (FileNotFoundError, NotADirectoryError, IsADirectoryError) as error:
                    raise ValueError(f"{row['id']}: evidence file not found: {name}") from error
                if binding['sha256'] != evidence['sha256']:
                    raise ValueError(f"{row['id']}: changed basis source evidence: {name}")
                result.append(binding)
                continue
            else:raise ValueError('Use {input:ID} or own-stage {path,sha256} evidence')
            result.append(binding)
    return list({r['path']:r for r in result}.values())


PROMPT = '''Reduce the supplied existing proof to a basis suitable for unconditional
Lean formalization. Read original problem, selected target and materials first.
Preserve the full target, original H, quantifiers, domains, parameter ranges,
normalizations, constant dependencies and any specified algorithm. You may change
the proof route, auxiliary exponents and representations. Choose the mathematics;
no forced reduction tree, difficulty score or fixed search/retry budget applies.
Read nl0/references/basis.md for the submission contract and basis-planning.md for the reduction strategy.
Class 1 is an actual Mathlib proof, 2 an actual public Lean-library proof, 3 a
concrete recursive NL derivation from 1/2, 4 a verified complete textbook theorem
still lacking a Lean proof/reduction after serious mathematical work. Missing
sources, contradictions, unfinished internal arguments and unsupported claims are
not class 4. Record replaced dependencies and concrete derivations in the proof.
First outline the global proof and its actual consumers. Investigate remaining independent hard
foundations together with investigate_basis_frontier. Try a pinned declaration, a textbook derivation,
or a weaker theorem sufficient at every consumer. Optimize the selected graph jointly for shared
dependencies and independent natural cuts. Save a yui-basis-2 draft. Supply existing proofs for
1/2/3 or leave lean.proof null in a planning draft and call prepare_basis_graph. Independent workers
produce the missing proofs under the frozen direct premises. Actual signatures, source fidelity and
eventual discharge are checked. Class 4 requires an explicit user decision. Supply the global NL0
skeleton exactly; downstream authors elaborate its local steps. The separate Audit A reviews the
original target, the active basis proof, applications and replacement map.
Submit the complete basis artifact through submit_draft. Continue from saved
drafts after feedback; base_candidate and explicit JSON-pointer patches retain
your work, and accept_candidate resubmits an actual saved complete candidate.
'''


class BasisContract:
    def __init__(self, out, target, *, version=None):
        self.version=version
        self.concurrency='auto'
        self.out = Path(out);self.target = target;self.attempt = 0;self.drafts = {};self.selected = None
        self.last_checked = None
        self.last_receipt = None
        from payload_protocols import editable
        self.schema=editable(artifact_schema(version,planning=True))
        self.owner_stage=None
        self.early_stop=None

    def save(self, value):
        if not isinstance(value,dict):raise ValueError('Save a basis JSON object')
        from artifact_validation import expand_submission
        command = deepcopy(value)
        if any(k in command for k in ('base_input','base_candidate','accept_candidate')):
            for patch in command.get('patches',[]):patch['path']='/spec'+patch['path']
            documents = {}
            prior = self.out/'inputs/prior-basis.json'
            if prior.exists():documents['prior-basis.json']=json.dumps({'spec':ir.load(prior),'graph':{}})
            own = {n:json.dumps({'spec':v,'graph':{}}) for n,v in self.drafts.items()}
            expanded, _ = expand_submission(command, documents, own);candidate = expanded['spec']
        else:candidate = deepcopy(value)
        self.attempt += 1;directory = self.out/'candidates'/f'{self.attempt:04d}'
        write(directory/'basis.json',candidate);self.drafts[self.attempt]=candidate
        self.selected = None
        return candidate,directory

    def __call__(self, value):
        if (isinstance(value,dict) and set(value)=={'accept_candidate'} and
                type(value['accept_candidate']) is int and value['accept_candidate']==self.last_checked):
            # Explicit selection of the identical checked bytes needs no second Lean process.
            try:
                verify_bindings([self.last_receipt])
                checked=ir.load(self.last_receipt['path'])
                verify_bindings([checked['basis'],checked['native'],*checked['evidence']])
                basis_native.verify(checked['native']['path'])
            except (ValueError,KeyError) as error:
                raise RuntimeError('Previously checked basis evidence changed') from error
            self.selected=Path(self.last_receipt['path']).parent
            value.clear();value.update(ir.load(checked['basis']['path']))
            return {'candidate':self.last_checked,'status':'BASIS_MACHINE_CHECKED','mathematical_acceptance':False}
        candidate,directory = self.save(value)
        try:
            if self.version and candidate.get('version')!=self.version:
                raise ValueError('This author must submit '+self.version)
            if (self.owner_stage is not None and candidate.get('version')==basis_graph.VERSION and
                    any(r.get('category')!=4 and isinstance(r.get('lean'),dict) and r['lean'].get('proof') is None
                        for r in candidate.get('dependencies',[]) if isinstance(r,dict))):
                import basis_planning
                prepared=basis_planning.prepare(self.owner_stage,{'candidate':self.attempt})
                candidate=self.drafts[prepared['candidate']]
                directory=self.out/'candidates'/f'{self.attempt:04d}'
            validate(candidate, self.target)
            evidence = evidence_bindings(candidate, self.out/'inputs', self.out/'stage')
            declarations_, checks, roots = declarations(candidate)
            native = basis_native.check(candidate['lean_header']+declarations_, checks, roots, directory/'native')
            if not native['passed']:
                compiler = ir.load(directory/'native/compiler.json')
                raise ValueError(', '.join(native['errors'])+'\n'+ir.compiler_feedback(compiler))
            verify_native_edges(candidate,directory/'native')
            self.selected = directory
            self.last_checked = self.attempt
            write(directory/'checked.json',{'basis':bind(directory/'basis.json'),
                'native':bind(directory/'native/check.json'),'evidence':evidence})
            self.last_receipt=bind(directory/'checked.json')
        except (ValueError,KeyError,TypeError) as error:
            raise ValueError(f'Basis candidate {self.attempt} retained; repair with base_candidate. {error}') from error
        value.clear();value.update(candidate)
        return {'candidate':self.attempt,'status':'BASIS_MACHINE_CHECKED', 'mathematical_acceptance':False}


def decision(root, artifact, budget, *, planning=False):
    from fault_control import Gate
    rows = {r['id']:r for r in artifact['dependencies']} if planning else validate(artifact,artifact['full_target'])[0]
    residual = sorted(k for k,r in rows.items() if r['category']==4)
    if not residual:return None
    gate = Gate(Path(root)/'decision', recorder=getattr(budget,'execution',None), stage='basis-decision')
    review=bind(Path(root)/'review/report.json')
    terms=[{'id':k,'port':rows[k]['port'],'statement':rows[k]['statement'],'lean_type':rows[k]['lean']['type'],
            'reference':rows[k]['origin']['reference']} for k in residual]
    receipt = gate.pause({'status':'BASIS_USER_DECISION_REQUIRED','residual_class4':residual,'reviewed_premises':terms},
        resumable=False, checkpoint={'basis':bind(Path(root)/'stage/accepted.json'),'residual_class4':residual,'semantic_review':review},
        decisions=('stop','continue','accept-conditional'))
    return receipt


def run(job, budget, progress):
    from basis_author import BasisStage
    from role_sessions import Sessions
    root = Path(job['root']);sessions = Sessions();previous = None;revision = 0
    history = {};findings = None
    resume=job.get('resume') or {}
    if resume.get('mode')=='basis-revision':
        previous=Path(resume['basis']['path'])
        late_finding=ir.load(resume['report']['path'])['finding']
        findings={late_finding['basis_id']:late_finding}
        progress(job['case'],'BASIS_REVISION_STARTED',prior_run=resume['prior_run'],defect=resume['report'])
    elif resume:
        prior=ir.load(Path(job['resume']['prior_run'])/'job.json')
        ir.need(mode(prior)==mode(job),'Recovery changed the formalization goal')
        previous_inputs=problem_inputs(prior)
        (root/'active-inputs').mkdir()
        copy_problem_documents(previous_inputs,root/'active-inputs')
        manifest(root/'active-inputs')
        active=root/'active-inputs'
        write(root/'basis-selection.json',{'context':bind(active/CONTEXT),'inputs':bind(active/'inputs.json')})
        progress(job['case'],'BASIS_CHECKED_RESTORED',prior_run=prior['root'],new_basis_author_called=False)
        return ir.load(active/CONTEXT)
    target = ir.load(root/'inputs/target-selection.json')['full_target']
    while True:
        revision += 1;out = root/'2basis'/f'{revision:04d}';inputs = out/'inputs';inputs.mkdir(parents=True)
        copy_problem_documents(root/'inputs', inputs)
        prompt = PROMPT
        if previous:
            copy_input(previous, inputs/'prior-basis.json')
            if findings:
                write(inputs/'repair-findings.json',findings)
                prompt += '\nRepair the located basis defects in repair-findings.json. Start from prior-basis.json, preserve the original target, and recheck the revised formal propositions and their uses.'
            else:
                prompt += '\nThe user selected continue reducing class 4. Preserve the prior basis and accumulated work; eliminate the remaining dependencies without changing the original goal.'
        manifest(inputs);validator = BasisContract(out,target,version=basis_graph.VERSION)
        validator.concurrency = job.get('max_concurrency','auto')
        progress(job['case'],'BASIS_AUTHORING',directory=str(out))
        stage = BasisStage(out/'stage',prompt,phase='basis-authoring',inputs=inputs/'inputs.json',
            validator=validator,budget=budget,library=True,timeout=__import__('runtime_config').configured_timeout('stage'))
        if previous:
            for row in ir.load(previous)['dependencies']:
                for ref in row['origin']['evidence']:
                    if 'path' not in ref:continue
                    source=(previous.parent/ref['path']).resolve()
                    if not source.is_relative_to(previous.parent.resolve()) or bind(source)['sha256']!=ref['sha256']:
                        raise RuntimeError('Changed retained foundation evidence')
                    destination=out/'stage'/ref['path']
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    copy_input(source,destination)
        try:
            with sessions.use('basis-author'):stage.execute()
        finally:
            if validator.early_stop:
                sessions.cancel_all()
                raise StageFailure('STOPPED_BY_USER','User stopped before basis proof dispatch',phase='basis-decision',
                    evidence=validator.early_stop['path'],details={'user_decision':validator.early_stop})
        require_review_execution(ir.load(out/'stage/result.json'),out/'stage/result.json',phase='basis-authoring')
        if validator.selected is None:raise StageFailure('BASIS_INCOMPLETE','No machine-checked basis selected',phase='basis-authoring')
        artifact = ir.load(out/'stage/accepted.json')
        ir.need(artifact==ir.load(validator.selected/'basis.json'),'Basis submission differs from checked candidate')
        if resume.get('mode')=='basis-revision':
            import basis_defect
            basis_defect.require_revision(artifact,resume,late_finding)
        progress(job['case'],'BASIS_CHECKED',directory=str(out))
        checked = ir.load(validator.selected/'checked.json')
        context = {'version':CONTEXT_VERSION,'formalization':'unconditional','full_target':target,
            'basis':bind(out/'stage/accepted.json'), 'native':checked['native'],
            'original_inputs':[bind(root/'inputs'/r['path']) for r in ir.load(root/'inputs/inputs.json')['inputs']],
            'evidence':checked['evidence'], 'approval':None,
            'residual_class4':sorted(r['id'] for r in artifact['dependencies'] if r['category']==4)}
        if resume.get('mode')=='basis-revision':context['revision_report']=resume['report']
        progress(job['case'],'BASIS_SEMANTIC_REVIEW',directory=str(out/'review'))
        context['semantic_review'],findings = basis_review.assess(out,context,artifact,sessions,budget,history)
        if findings:
            if job['policy']=='first-pass':
                raise StageFailure('BASIS_SEMANTIC_NONPASS','First basis correspondence review did not pass',
                    phase='basis-semantic-review',evidence=context['semantic_review']['path'],details={'findings':findings})
            previous=out/'stage/accepted.json'
            continue
        progress(job['case'],'BASIS_REVIEWED',directory=str(out/'review'))
        import basis_preapproval
        chosen = (basis_preapproval.existing(out,artifact) if artifact['version']==basis_graph.VERSION else None) or decision(out,artifact,budget)
        action = chosen['control']['action'] if chosen else None
        if action=='stop':
            from case_outcomes import verify_basis_decision
            receipt = bind(out/'decision/error-incidents'/(chosen['incident']+'.json'))
            verify_basis_decision(root,receipt,'stop')
            sessions.cancel_all()
            raise StageFailure('STOPPED_BY_USER','User stopped at the unresolved basis boundary',
                phase='basis-decision', evidence=receipt['path'], details={'user_decision':receipt})
        if action=='continue':previous=out/'stage/accepted.json';continue
        context['approval']=chosen
        verify_context(context)
        active = root/'active-inputs';active.mkdir()
        copy_problem_documents(root/'inputs',active)
        from jobs import stage_document
        for number, evidence in enumerate(context['evidence']):
            stage_document(Path(evidence['path']), active/f'basis-evidence-{number:03d}.txt')
        (active/'basis-proof.md').write_text(artifact['proof']);write(active/'basis-registry.json',artifact)
        if artifact['version']==basis_graph.VERSION:write(active/'global-nl0.json',artifact['global_graph'])
        write(active/CONTEXT, context);manifest(active)
        write(root/'basis-selection.json',{'context':bind(active/CONTEXT),'inputs':bind(active/'inputs.json')})
        sessions.close_all('BASIS_PREPARED',[validator.selected/'checked.json',out/'review/report.json'])
        return context


def verify_context(context):
    ir.need(context.get('version')==CONTEXT_VERSION and context.get('formalization')=='unconditional',
        'A new unconditional handoff requires the early basis semantic review; use the frozen runtime for historical receipts')
    verify_bindings([context['basis'],context['native'],*context['original_inputs'],*context['evidence']])
    native = basis_native.verify(context['native']['path'])
    artifact = ir.load(context['basis']['path']);rows,_ = validate(artifact,context['full_target'])
    declarations_, checks, roots = declarations(artifact)
    ir.need(ir.digest(Path(context['native']['path']).parent/'Proof.lean')==
        __import__('hashlib').sha256((artifact['lean_header']+declarations_).encode()).hexdigest(), 'Prepared basis proof changed')
    ir.need(native['checks']==[list(c) for c in checks] and native['roots']==roots,'Prepared basis inspection scope changed')
    verify_native_edges(artifact,Path(context['native']['path']).parent)
    basis_review.verify(context['semantic_review'],context,artifact)
    residual = sorted(k for k,r in rows.items() if r['category']==4)
    ir.need(context['residual_class4']==residual,'Residual basis scope changed')
    approval = context['approval']
    if residual:
        from case_outcomes import verify_basis_decision
        revision=Path(context['basis']['path']).parent.parent
        if (artifact['version']==basis_graph.VERSION and isinstance(approval,dict) and
                approval.get('checkpoint',{}).get('basis')!=context['basis']):
            import basis_preapproval
            basis_preapproval.verify(revision,artifact,approval)
            return artifact
        ir.need(isinstance(approval,dict) and approval.get('checkpoint')=={'basis':context['basis'],'residual_class4':residual,
                'semantic_review':context['semantic_review']},
            'Residual class 4 lacks exact user approval')
        revision=Path(context['basis']['path']).parent.parent
        incident=approval.get('incident')
        ir.need(isinstance(incident,str) and re.fullmatch(r'[0-9a-f]{32}',incident),'Invalid basis approval incident')
        receipt=bind(revision/'decision/error-incidents'/(incident+'.json'))
        ir.need(approval==verify_basis_decision(revision.parent.parent,receipt,'accept-conditional'),
                'Residual approval differs from the actual operator decision')
    else:ir.need(approval is None,'Unexpected residual approval')
    return artifact


def problem_inputs(job):
    root = Path(job['root'])
    if mode(job)!='unconditional':return root/'inputs'
    selection = ir.load(root/'basis-selection.json');verify_bindings(list(selection.values()))
    active = root/'active-inputs';context = ir.load(active/CONTEXT);verify_context(context)
    resume=job.get('resume') or {}
    if resume.get('mode')=='basis-revision':
        ir.need(context.get('revision_report')==resume['report'],'Active basis lost its located revision obligation')
    ir.need(context['full_target']==job['target_selection']['full_target'],'Active basis changed the requested target')
    ir.need([r['sha256'] for r in context['original_inputs']]==[r['sha256'] for r in job['documents']],
        'Active basis was prepared for different original documents')
    ir.need(selection['context']==bind(active/CONTEXT) and selection['inputs']==bind(active/'inputs.json'),'Active proof selection escaped its run')
    for row in ir.load(active/'inputs.json')['inputs']:
        ir.need(Path(row['path']).name==row['path'] and ir.digest(active/row['path'])==row['sha256'],'Active proof input changed')
    return active


def recovery_bindings(job):
    if mode(job)!='unconditional':return []
    active=problem_inputs(job);context=ir.load(active/CONTEXT)
    native=basis_native.verify(context['native']['path'])
    files=[Path(job['root'])/'basis-selection.json',active/'inputs.json',
        *[active/r['path'] for r in ir.load(active/'inputs.json')['inputs']]]
    return [*[bind(p) for p in files],context['basis'],context['native'],context['semantic_review'],
        *context['original_inputs'],*context['evidence'],*native['bindings']]


def source_context(graph, spec):
    """Find only the context explicitly bound in the selected NL0 input manifest."""
    graph,spec = Path(graph),Path(spec);document = ir.load(spec)
    matches = [r for r in document.get('inputs',[]) if Path(r['path']).name==CONTEXT]
    if not matches:return None
    ir.need(len(matches)==1,'Duplicate active proof context')
    row = matches[0];path = graph.parent/row['path']
    ir.need(path.resolve().is_relative_to(graph.parent.resolve()) and ir.digest(path)==row['sha256'],'Changed source proof context')
    context = ir.load(path);artifact = verify_context(context)
    ir.need(document['full_target']==context['full_target'],'Source changed original target after basis reduction')
    source_graph = ir.load(graph)
    basis_graph.verify_handoff(artifact,source_graph)
    props = source_graph['propositions']
    expected = {r['port']:r for r in artifact['dependencies'] if r['port'] and r['port'].startswith('E')}
    actual = {p['id']:p for p in props if p['kind']=='external'}
    ir.need(set(actual)==set(expected),'Basis source changed the frozen external ports')
    for key,row in actual.items():ir.need(row['statement']==expected[key]['statement'],'Basis external statement changed')
    return context


def check_interface(context, contract):
    if context is None:return
    artifact = verify_context(context)
    ir.need(contract['header'].startswith(artifact['lean_header']),'Interface changed prepared basis definitions')
    expected = {r['port']:r for r in artifact['dependencies'] if r['port'] and r['port'].startswith('E')}
    actual = {p['id']:p for p in contract['premises'] if p['kind']=='external'}
    ir.need(set(expected)==set(actual),'Interface changed prepared basis E ports')
    for key,row in actual.items():
        ir.need(row['type']==expected[key]['lean']['type'] and row['statement']==expected[key]['statement'],
            'Interface changed prepared basis type/context at '+key)
