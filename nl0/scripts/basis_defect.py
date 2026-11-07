"""A located downstream objection to a frozen basis, and its explicit, versioned restart."""
from datetime import datetime, timezone
from pathlib import Path
import json

from controller_common import bind, verify_bindings
from execution_health import StageFailure, record_qualification
import ir

STATUS = 'BASIS_REVISION_REQUIRED'
PHASES = {'basis-global-metadata', 'nl0-local-authoring', 'nl0-authoring', 'audit-a-global', 'translation-source-preparation', 'translation-cut-review',
          'interface-authoring', 'interface-semantic-review', 'interface-dispute-review',
          'interface-proof-diagnosis', 'audit-b-assembly', 'audit-b-semantic-review'}
TOOL = 'report_basis_defect'
FIELDS = ('basis_id','field','frozen_value','source_id','source_quote','use_id','use_pointer','use_quote',
          'explanation','correction')
HELP = ('Report a located conflict in the frozen basis only. Supply an existing basis_id, field '
        '(statement or lean.type), its exact frozen_value, a verbatim source_quote from an original '
        'problem/material or basis-evidence file, and the affected use with a verbatim use_quote. '
        'Use basis-proof.md or a declared nl0.json, contract.json or plan.json. For JSON, use_pointer '
        'must resolve to the text of the affected use; for text use an empty pointer. Explain the '
        'conflict and proposed correction. This pauses the case for an explicit operator repair.')


def enable(stage):
    if stage.artifact_phase not in PHASES or stage.arm!='yui':
        return
    from fault_control import run_root
    root=run_root(stage.logs)
    if not (root/'basis-selection.json').is_file():
        return
    job=ir.load(root/'job.json')
    if job.get('formalization')!='unconditional':
        return
    # Keep packet-only reviewers and local provers inside their existing disclosure boundary.
    # Global roles may inspect the selected mathematical inputs but never the basis role history.
    import basis
    active=basis.problem_inputs(job)
    docs=ir.load(active/'inputs.json')['inputs']
    for row in docs:
        name=row['id']
        if name in {'proof-context.json','target-selection.json'} or name in stage.task_inputs:
            continue
        path=active/row['path']
        if path.resolve().parent!=active or ir.digest(path)!=row['sha256']:
            raise ValueError('Changed declared basis diagnostic input')
        stage.task_inputs[name]=path.read_text()
    from model_pilot import carrier
    schema={k:{'type':'string'} for k in FIELDS}
    schema['field']['enum']=['statement','lean.type']
    stage.tools.append(carrier.tool(TOOL,HELP,schema,list(FIELDS)))


def locate(root, stage, args):
    import basis
    from nl0 import closure
    root=Path(root).resolve();stage=Path(stage).resolve()
    if not stage.is_relative_to(root) or set(args)!=set(FIELDS):
        raise ValueError('Select the exact basis, source and affected use')
    if any(not isinstance(args[k],str) or (k!='use_pointer' and not args[k].strip()) for k in FIELDS):
        raise ValueError('Missing a located basis defect field')
    job=ir.load(root/'job.json')
    try:active=basis.problem_inputs(job)
    except ValueError as error:
        raise RuntimeError('The previously frozen basis input changed') from error
    context=ir.load(active/basis.CONTEXT)
    rows={r['id']:r for r in ir.load(context['basis']['path'])['dependencies']}
    row=rows.get(args['basis_id'])
    if row is None or row['lean'] is None or args['field'] not in {'statement','lean.type'}:
        raise ValueError('Select a frozen formal basis item and protected field')
    frozen=row['statement'] if args['field']=='statement' else row['lean']['type']
    if args['frozen_value']!=frozen:
        raise ValueError('The quoted basis field differs from its selected version')
    source_names={Path(r['path']).name for r in context['original_inputs']} - {'target-selection.json'}
    source_names.update(f'basis-evidence-{i:03d}.txt' for i in range(len(context['evidence'])))
    if args['source_id'] not in source_names or args['use_id'] not in {'basis-proof.md','nl0.json','contract.json','plan.json'}:
        raise ValueError('Select an original source and an affected mathematical use')
    m=ir.load(stage/'execution-manifest.json')
    if m['phase'] not in PHASES or m['arm']!='yui':
        raise ValueError('This stage cannot report a frozen basis defect')
    docs={r['id']:r for r in m['frozen_task_files']}
    def document(key):
        name=args[key];doc=docs.get(name)
        if doc is None:raise ValueError('Document was not disclosed in this stage: '+name)
        path=(stage/doc['path']).resolve()
        if path.parent!=stage/'task-inputs' or ir.digest(path)!=doc['sha256'] or m['task_documents'][name]!=doc['sha256']:
            raise ValueError('Changed reporting-stage input')
        return path
    source=document('source_id');use=document('use_id')
    if source.read_bytes()!=(active/args['source_id']).read_bytes() or args['source_quote'] not in source.read_text():
        raise ValueError('Source quote must occur in the bound original/evidence')
    if args['use_id']=='basis-proof.md':
        if args['use_pointer'] or use.read_bytes()!=(active/'basis-proof.md').read_bytes():
            raise ValueError('Use the exact current basis proof for this text location')
        value=use.read_text()
    else:
        if not args['use_pointer'].startswith('/'):raise ValueError('Give the JSON pointer of the affected use')
        value=closure.resolve(ir.load(use),args['use_pointer'])
    if not isinstance(value,str) or args['use_quote'] not in value:
        raise ValueError('The quoted affected use must occur at the selected location')
    return {'status':STATUS,'finding':args,'job':bind(root/'job.json'),'basis':context['basis'],
            'selection':bind(root/'basis-selection.json'),'source':bind(source),'use':bind(use)}


def verified(stage, root):
    stage=Path(stage).resolve();root=Path(root).resolve()
    accepted=ir.load(stage/'accepted.json');result=ir.load(stage/'result.json')
    manifest=ir.load(stage/'execution-manifest.json')
    if (result.get('status')!='BLOCKED' or result.get('task_outcome')!=STATUS or
            result.get('exposure')!=ir.load(stage/'exposure-audit.json') or
            result.get('role_session')!=manifest.get('role_session') or
            not record_qualification(result,allow_blocked=True)['submitted_record_qualified']):
        raise ValueError('The downstream report lacks a qualified reporting stage')
    if accepted!=locate(root,stage,accepted['finding']):
        raise ValueError('Stale downstream basis defect')
    events=[json.loads(line) for line in (stage/'tools.jsonl').read_text().splitlines()]
    if not any(e['tool']==TOOL and e['arguments']==accepted['finding'] and
               e['result'].get('stage_complete') is True for e in events):
        raise ValueError('No completed downstream defect submission')
    return accepted


def stop(stage):
    from fault_control import run_root
    stage=Path(stage);report=verified(stage,run_root(stage))
    raise StageFailure(STATUS,'A protected basis field has a located downstream objection. Inspect the finding, '
        'cancel this paused run, then explicitly select resume RUN --repair-basis to revise it.',
        phase='basis-revision',evidence=stage/'accepted.json',details={'basis_defect':bind(stage/'accepted.json'),
        'basis_id':report['finding']['basis_id'],'affected':['NL0','Audit A','interface','proofs','Audit B','b2lean']})


def previous_program(stage,root):
    """Select the reporting workflow's own proof round, if it has completed local bodies."""
    import workflow
    scope=next((p for p in stage.parents if p.name=='workflow' and p.is_relative_to(root/'nl0-to-lean')),None)
    if scope is None:return None,[]
    workflow.bound(scope)
    current=next((p for p in stage.parents if p.parent==scope and p.name=='proof-run'
                  or p.parent==scope/'proof-repairs' and p.name.isdecimal()),None)
    current=current or workflow.proof_run(scope)
    if not (current/'report.json').is_file():return None,[]
    report=ir.load(current/'report.json')
    if report['status'] not in {'GRAPH_REPAIR_REQUIRED','GRAPH_UNFINISHED','FRAGMENT_ASSEMBLED'} or not report.get('proofs'):
        return None,[]
    files=[scope/'manifest.json',scope/'freeze-seal.json',current/'report.json',
           *(p for p in (current/'inputs').rglob('*') if p.is_file())]
    if (current/'proofs.json').is_file():files.append(current/'proofs.json')
    return str(current),[bind(p) for p in files]


def is_revision_program(out,previous):
    if previous is None:return False
    from fault_control import run_root
    root=run_root(out)
    if not (root/'.yui-run.json').is_file():return False
    job=ir.load(root/'job.json');resume=job.get('resume') or {}
    previous=Path(previous).resolve()
    if resume.get('mode')!='basis-revision' or resume.get('prior_proof_run')!=str(previous):
        return False
    refs=[r for r in job['authority_bindings'] if Path(r['path']).is_relative_to(previous)]
    if bind(previous/'report.json') not in refs:raise ValueError('Unbound prior basis proof program')
    verify_bindings(refs)
    return True


def qualify(previous):
    import basis
    import jobs
    from owner_observation import process_table, matches, group_present
    root=Path(previous).resolve()
    old=jobs.validate(ir.load(root/'job.json'),verify_runtime=False)
    status=ir.load(root/'case-result.json')
    prior=status['result']
    if (old['track']!='full' or basis.mode(old)!='unconditional' or status['job']!=bind(root/'job.json') or
            prior['status']!='CANCELLED' or prior.get('retained_error',{}).get('status')!=STATUS):
        raise ValueError('Explicit basis repair requires a cancelled, located basis-revision checkpoint')
    state=ir.load(root/'execution-status.json')
    owners=[state['controller'],*state['processes'].values()]
    table=process_table()
    if any(matches(r,table) for r in owners) or any(group_present(r['pgid'],owners,table) for r in owners
            if r.get('pgid')==r.get('pid')):
        raise ValueError('Verify exit of the previous case and its owned processes before basis repair')
    ref=prior['retained_error']['basis_defect'];stage=Path(ref['path']).resolve().parent
    if not stage.is_relative_to(root) or ref!=bind(stage/'accepted.json'):
        raise ValueError('Foreign or changed downstream report')
    report=verified(stage,root)
    deadline=state['time_budget'].get('deadline_at_utc')
    if (old['time_budget_seconds'] is None)!=(deadline is None):
        raise ValueError('The original case deadline is unavailable')
    proof_round,program_bindings=previous_program(stage,root)
    result={'mode':'basis-revision','version':1,'prior_proof_run':proof_round,'prior_run':str(root),'basis':report['basis'],
            'report':ref,'deadline':deadline}
    files=[root/'job.json',root/'case-result.json',root/'execution-status.json',
           *[stage/n for n in ('accepted.json','result.json','execution-manifest.json','tools.jsonl','exposure-audit.json')]]
    return old,result,[bind(p) for p in files]+[report['source'],report['use']]+program_bindings


def require_revision(artifact,descriptor,finding):
    old=ir.load(descriptor['basis']['path'])
    key=finding['basis_id']
    previous=next(r for r in old['dependencies'] if r['id']==key)
    current=next((r for r in artifact['dependencies'] if r['id']==key),None)
    if current and current['lean'] is not None and current['statement']==previous['statement'] and (
            current['lean']['type']==previous['lean']['type'] and artifact['proof']==old['proof'] and
            artifact['lean_header']==old['lean_header'] and current['origin']==previous['origin']):
        raise StageFailure('REPAIR_UNCHANGED','The reported basis statement, type, source and use are unchanged',
            phase='basis-revision',evidence=descriptor['report']['path'])


def remaining(descriptor):
    deadline=descriptor['deadline']
    if deadline is None:return None
    seconds=(datetime.fromisoformat(deadline.replace('Z','+00:00'))-datetime.now(timezone.utc)).total_seconds()
    if seconds<=0:raise ValueError('Original whole-case deadline is exhausted')
    return seconds


def validate_descriptor(job):
    resume=job['resume']
    if Path(resume['prior_run']).resolve()==Path(job['root']).resolve():
        raise ValueError('Use a separate prior run')
    old,expected,files=qualify(resume['prior_run'])
    if resume!=expected or any(job.get(k)!=old.get(k) for k in
            ('case','track','formalization','policy','profiles','max_concurrency','target_selection','documents')):
        raise ValueError('The basis repair changed the problem or execution configuration')
    if any(ref not in job['authority_bindings'] for ref in files):
        raise ValueError('Missing prior basis revision evidence')
    limit=job['time_budget_seconds']
    if (limit is None)!=(old['time_budget_seconds'] is None) or limit is not None and limit>old['time_budget_seconds']:
        raise ValueError('The basis repair cannot reset the case budget')


def prepare(previous):
    import jobs
    old,descriptor,bindings=qualify(previous)
    materials=[Path(r['original']['path']) for r in old['documents'][1:] if r['id']!='target-selection.json']
    return jobs.prepare(old['problem'],track=old['track'],profiles=old['profiles'],max_concurrency=old['max_concurrency'],
        policy=old['policy'],materials=materials,target=old['target_selection'],formalization='unconditional',
        time_budget_seconds=remaining(descriptor),resume=descriptor,resume_bindings=bindings)
