"""Publish and recheck the four public artifacts, independently of removable run state."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import shutil
import tempfile
import time

from controller_common import bind, write
import nl0
from staging_storage import copy_input

STATEMENTS = 'theorem_formalization_statement.json'
TOP = {'formalization','nl0',STATEMENTS,'run.json'}
LEAN = {'CONDITIONAL_LEAN','UNCONDITIONAL_LEAN','CLOSED_LEAN_SOURCE_QUALIFIED'}


def files(directory):
    result={}
    for p in sorted(directory.rglob('*')):
        if p.is_symlink() or not (p.is_file() or p.is_dir()):
            raise ValueError('Nonportable delivery member: '+str(p))
        if p.is_file() and p!=directory/'run.json':
            result[p.relative_to(directory).as_posix()]=nl0.sha(p)
    return result


def export_nl0(authority, directory):
    import source_preparation
    data,paths=source_preparation.read_source(**authority)
    if not (data[0]['current_standard_receipt_valid'] or data[0].get('current_conditional_receipt_valid')):
        raise ValueError('Selected NL0 lacks actual Audit A acceptance')
    if 'audit_a' not in authority:
        raise ValueError('Public NL0 requires a bound ordinary Audit A report')
    source=Path(authority['graph']).parent
    selected=set(paths)
    review_results=set()
    # Each inherited assessment has its own index into the previous review.
    audit=nl0.load(authority['audit_a'])
    def inherited(value):
        if isinstance(value,dict):
            if 'inheritance' in value:
                import audit_reuse
                index,previous=audit_reuse.read_binding(source,value['inheritance'])
                selected.update(previous.values())
                review_results.add(previous['result'])
                if 'index_repair' in index:
                    selected.add(nl0.local_path(source,index['index_repair']['original']['path']))
            for child in value.values(): inherited(child)
        elif isinstance(value,list):
            for child in value: inherited(child)
    inherited(audit)
    for path in sorted(selected):
        target=directory/path.relative_to(source)
        target.parent.mkdir(exist_ok=True,parents=True)
        copy_input(path,target)
    # Store the actual release and resume receipts alongside the review they qualify.
    # Reverification must work even after the owning workspace and its logs are gone.
    archive=directory/'review-evidence/execution'
    import audit_reuse
    from controller_common import CORE
    (archive/'rules').mkdir(parents=True,exist_ok=True)
    for name in audit_reuse.SEMANTIC_RULES:
        copy_input(CORE/name,archive/'rules'/Path(name).name)
    for result_path in review_results:
        result=nl0.load(result_path)
        dest=archive/nl0.sha(result_path)
        dest.mkdir(exist_ok=True)
        if result.get('temporary_workspace_removed') is False:
            logs=Path(result['workspace_retention']['logs'])
            copy_input(logs/'resources/release.json',dest/'release.json')
            # One persistent native role may submit several reviews. Its release
            # identifies the original owner result, while this review binds its own.
            if nl0.sha(logs/'result.json')!=nl0.sha(result_path):
                copy_input(logs/'result.json',dest/'workspace-owner-result.json')
        for pause in result.get('error_pauses',[]):
            path=Path(pause['path'])
            if nl0.sha(path)!=pause['sha256']:
                raise ValueError('A review recovery receipt changed before export')
            copy_input(path,dest/(pause['sha256']+'.json'))
    return data


def challenge_source(contract,retained,name):
    import audit_b
    namespace, theorem=name.rsplit('.',1)
    expected=audit_b.full_type(contract,contract['conclusion']['type'],retained)
    challenge=(contract['header'].rstrip()+'\n\nnamespace '+namespace+'\nset_option autoImplicit false\n'
               +'theorem '+theorem+' : '+expected+' := by sorry\nend '+namespace+'\n')
    return challenge,expected


def comparator_config(name):
    import audit_b
    return {'challenge_module':'Challenge','solution_module':'Solution','theorem_names':[name],
            'permitted_axioms':sorted(audit_b.AXIOMS),'enable_nanoda':False}


def lean_project(directory, contract, retained, name, solution):
    from runtime_config import load_lock
    lock=load_lock()
    challenge,expected=challenge_source(contract,retained,name)
    (directory/'Challenge.lean').write_text(challenge)
    copy_input(Path(solution),directory/'Solution.lean')
    write(directory/'config.json',comparator_config(name))
    (directory/'lean-toolchain').write_text(lock['lean']['toolchain']+'\n')
    lib=lock['mathlib']
    (directory/'lakefile.toml').write_text('name = "YuiDelivery"\n\n[[require]]\nname = "mathlib"\n'
        +'git = '+json.dumps(lib['url'])+'\nrev = '+json.dumps(lib['rev'])
        +'\n\n[[lean_lib]]\nname = "Challenge"\n\n[[lean_lib]]\nname = "Solution"\n')
    manifest=nl0.load(Path(lib['local_path'])/'lake-manifest.json')
    manifest['name']='YuiDelivery'
    for dep in manifest['packages']: dep['inherited']=True
    manifest['packages'].append({'url':lib['url'],'type':'git','subDir':None,'scope':'','rev':lib['rev'],'name':'mathlib',
        'manifestFile':'lake-manifest.json','inputRev':lib['rev'],'inherited':False,'configFile':'lakefile.lean'})
    write(directory/'lake-manifest.json',manifest)
    return expected


def export_lean(result,scope,source,directory):
    import audit_b
    import b2lean
    import final_acceptance
    import ir
    import workflow
    receipt=final_acceptance.validate_receipt(result['audit_b']['receipt_path'])
    native=Path(receipt['workflow'])
    frozen=workflow.bound(native)
    contract=ir.contract(frozen['contract'])
    if receipt['freeze_deviation']:
        from execution_health import StageFailure
        raise StageFailure('FINAL_INTERFACE_DEVIATION','Reviewed actual proof differs from the frozen Comparator challenge',
                           phase='delivery',evidence=result['audit_b']['receipt_path'])
    if result.get('closure'):
        closed=b2lean.validate_receipt(Path(result['proof']).parent)
        if closed['achieved_scope']!=scope: raise ValueError('Discharge and public result disagree')
        remaining=set(closed['closure']['remaining_premises'])
        retained=[p for p in contract['premises'] if p['id'] in remaining]
        export=closed['closure']['export']
        proof=closed['proof']
    else:
        retained=[p for p in contract['premises'] if p['kind']!='mathlib']
        export='AuditBExport.P'
        proof=native/'audit-b/Proof.lean'
    if frozen['authority']['graph']!=str(source):
        if nl0.sha(frozen['authority']['graph'])!=nl0.sha(source):
            raise ValueError('Delivery and frozen Audit B refer to different NL0 sources')
    # This projection is taken from the independent, content-bound pre-proof review.
    frozen_endpoint={k:contract[k] for k in ('parameters','header','conclusion')}
    frozen_endpoint.update(retained=retained,export=export,
                           source_contract_sha256=nl0.sha(frozen['contract']),
                           semantic_review_sha256=receipt['gate']['semantic_review']['sha256'])
    evidence=directory.parent/'nl0/lean-evidence'
    evidence.mkdir()
    for name,path in [('contract',frozen['contract']),('semantic-review',receipt['gate']['semantic_review']['path']),
                      ('mechanical',receipt['gate']['mechanical']['path'])]:
        copy_input(Path(path),evidence/(name+'.json'))
    if result.get('closure'):
        copy_input(Path(closed['closure']['native']['path']),evidence/'discharge.json')
    write(directory.parent/'nl0/lean-endpoints.json',frozen_endpoint)
    expected=lean_project(directory,contract,retained,export,proof)
    native_types={r['id']:r['actual_type'] for r in nl0.load(native/'audit-b/elaborated.json')['comparisons']}
    if result.get('closure'):
        native_types['P']=next(r['actual_type'] for r in nl0.load(Path(proof).parent/'elaborated.json')['comparisons'] if r['id']=='P')
    notes=nl0.load(native/'audit-b/mapping.json')['entries']
    statements={p['id']:p['statement'] for p in nl0.load(source)['propositions']}
    target=nl0.load(source.parent/'spec.json')['full_target']
    entries=[{'id':'P','original':target,'lean':expected,'elaborated_lean':native_types['P'],'correspondence':notes['P']['correspondence']['explanation']}]
    for index,premise in enumerate(retained):
        if premise['kind']=='external':
            sid=premise['id']
            entries.append({'id':sid,'original':statements[sid],'lean':audit_b.full_type(contract,premise['type'],retained[:index]),
                            'formal_premise':premise['type'],'correspondence':notes[sid]['correspondence']['explanation']})
    return entries,receipt['status']


def verify_lean_evidence(directory,endpoint,record,expected):
    import workflow
    evidence=directory/'nl0/lean-evidence'
    contract=nl0.load(evidence/'contract.json')
    review=nl0.load(evidence/'semantic-review.json')
    machine=nl0.load(evidence/'mechanical.json')
    contract_hash=nl0.sha(evidence/'contract.json')
    if (review['contract_sha256']!=contract_hash or endpoint['source_contract_sha256']!=contract_hash
            or machine['frozen_contract_sha256']!=contract_hash or not machine['passed'] or machine['compiler_exit_code']!=0
            or review['source_graph_sha256']!=nl0.sha(directory/'nl0/nl0.json')
            or nl0.sha(evidence/'semantic-review.json')!=endpoint['semantic_review_sha256']
            or set(review['checks'])!=workflow.INTERFACE_CHECKS or not all(v['verdict']=='PASS' for v in review['checks'].values())):
        raise ValueError('The packaged interface review and machine results do not verify this NL0 and contract')
    if any(endpoint[k]!=contract[k] for k in ('parameters','header','conclusion')):
        raise ValueError('Comparator endpoint differs from the reviewed contract')
    retained=[p for p in contract['premises'] if p['kind']=='hypothesis' or p['id'] in record['remaining_extra_premises']]
    if retained!=endpoint['retained']:
        raise ValueError('Export changed an original or retained premise')
    solution=nl0.sha(directory/'formalization/Solution.lean')
    if (evidence/'discharge.json').is_file():
        native=nl0.load(evidence/'discharge.json')
        proofs=[row['sha256'] for row in native['bindings'] if Path(row['path']).name=='Proof.lean']
        if not native['passed'] or proofs!=[solution] or native['checks']!=[['P',endpoint['export'],expected]]:
            raise ValueError('The solution differs from its actual checked discharge')
    elif machine['artifacts']['Proof.lean']!=solution:
        raise ValueError('The solution differs from its actual checked Audit B export')


def verify_route(directory, record, scope, qualified):
    """Read back the public exit from the evidence that survived cleanup."""
    from controller_common import CORE
    from workflow_execution import block_module
    from frozen_graph import BASIS, DIRECT, LEGACY_BASIS
    goal=record['requested_goal']
    entry='2basis' if goal=='unconditional' else 'nl0'
    if goal not in {'audit','conditional','unconditional'} or record['entry']!=entry:
        raise ValueError('Published entry differs from the requested goal')
    natural=directory/'nl0'
    if record['audit_a'] and nl0.load(natural/'global.json')['owner'] not in ((BASIS,LEGACY_BASIS) if entry=='2basis' else (DIRECT,)):
        raise ValueError('Published entry differs from the frozen graph producer')
    discharged=(natural/'lean-evidence/discharge.json').is_file()
    alternate=(natural/'alternative/Actual.lean').is_file() and (natural/'alternative/findings.json').is_file()
    has_solution=(directory/'formalization/Solution.lean').is_file()
    exit_name='b2lean' if discharged else 'nl02lean' if has_solution or alternate else 'nl0' if record['audit_a'] else entry
    if record['exit']!=exit_name or alternate!=(scope=='DIFFERENT_RESULT'):
        raise ValueError('Published exit differs from the retained stage evidence')
    if scope in {'NL0','NL0_SOURCE_QUALIFIED'} and (scope=='NL0_SOURCE_QUALIFIED')!=qualified:
        raise ValueError('Published audit scope differs from its source review')
    if scope in LEAN:
        if (discharged!=(goal=='unconditional') or
                record['audit_b']!=('AUDIT-B-CONDITIONAL' if qualified else 'AUDIT-B-PASSED')):
            raise ValueError('Published Lean route differs from its Audit B or discharge evidence')
        if discharged:
            complete=not record['remaining_extra_premises'] and not qualified
            if record['case_status']!=('WORKFLOW-PASSED' if complete else 'WORKFLOW-CONDITIONAL'):
                raise ValueError('Case status differs from its final discharge and source review')
    elif record['audit_b'] or discharged:
        raise ValueError('Unexpected Lean acceptance on the published route')
    if (scope=='STOPPED' and goal!='unconditional') or (alternate and goal=='audit'):
        raise ValueError('The declared entry cannot reach this operator decision')
    if scope=='INTERRUPTED':
        from case_outcomes import PASSED, CONDITIONAL
        if record['case_status'] in PASSED|CONDITIONAL|{'STOPPED_BY_USER','DIFFERENT_RESULT_DELIVERED'}:
            raise ValueError('An interrupted delivery claims a completed case')
    else:
        rules=block_module(CORE/'workflow','routing')
        closed=discharged and not record['remaining_extra_premises']
        _,expected=rules.classify(goal,record['case_status'],closed=closed,qualified=qualified)
        if scope!=expected:
            raise ValueError('Published scope differs from the accepted case outcome')


def verify(directory, *, anchor=None):
    directory=Path(directory)
    if directory.is_symlink() or {p.name for p in directory.iterdir()}!=TOP:
        raise ValueError('Incomplete public delivery tree')
    if not all((directory/n).is_dir() for n in ('formalization','nl0')):
        raise ValueError('Missing public delivery directories')
    inventory=files(directory)
    record=nl0.load(directory/'run.json')
    if record.get('version')!='yui-delivery-1' or record['files']!=inventory:
        raise ValueError('Delivered content differs from its inventory')
    if anchor is not None and anchor!={'run_id':record['run_id'],'run_sha256':nl0.sha(directory/'run.json'),'files':inventory}:
        raise ValueError('Delivered content differs from the published protocol receipt')
    entries=nl0.load(directory/STATEMENTS)['entries']
    scope=record['actual_result']
    if scope not in LEAN | {'NL0','NL0_SOURCE_QUALIFIED','STOPPED','DIFFERENT_RESULT','INTERRUPTED'}:
        raise ValueError('Unknown published result')
    if scope in LEAN:
        if not record.get('audit_b') or record.get('requested_goal')=='audit':
            raise ValueError('A Lean result requires an actual Audit B receipt and a formalization request')
        if {p.name for p in (directory/'formalization').iterdir()}!={'Challenge.lean','Solution.lean','lakefile.toml','config.json','lean-toolchain','lake-manifest.json'}:
            raise ValueError('Incomplete Comparator package')
        endpoint=nl0.load(directory/'nl0/lean-endpoints.json')
        if nl0.load(directory/'formalization/config.json')!=comparator_config(endpoint['export']):
            raise ValueError('Comparator must check the published theorem and allowed axioms')
        challenge,expected=challenge_source(endpoint,endpoint['retained'],endpoint['export'])
        if (directory/'formalization/Challenge.lean').read_text()!=challenge or not entries or entries[0]['lean']!=expected:
            raise ValueError('Comparator challenge no longer expresses the independently frozen target')
        verify_lean_evidence(directory,endpoint,record,expected)
        if [e['id'] for e in entries]!=['P',*record['remaining_extra_premises']]:
            raise ValueError('Final theorem correspondence differs from the retained premises')
        retained=[p['id'] for p in endpoint['retained'] if p['kind']=='external']
        if retained!=record['remaining_extra_premises'] or entries[0]['original']!=nl0.load(directory/'nl0/spec.json')['full_target']:
            raise ValueError('The published endpoints differ from the frozen request')
        if scope=='UNCONDITIONAL_LEAN' and record['remaining_extra_premises']:
            raise ValueError('Unconditional delivery contains an additional premise')
    elif entries or list((directory/'formalization').iterdir()):
        raise ValueError('Unexpected Lean output in a non-formalized delivery')
    if scope=='STOPPED':
        decision=nl0.load(directory/'nl0/basis-decision.json')
        if decision['decision']!='stop' or not decision['unresolved'] or [row['id'] for row in decision['unresolved']]!=record['unresolved_foundations']:
            raise ValueError('Stopped run lacks the actual reviewed residuals and operator decision')
    qualified=False
    if record['audit_a']:
        base=directory/'nl0'
        if not (base/'global.json').is_file() or not (base/'review-evidence/execution').is_dir():
            raise ValueError('Missing portable global or review evidence')
        if (base/'global.json').is_file():
            from frozen_graph import shape
            frozen=nl0.load(base/'global.json')
            if frozen['graph']!=shape(nl0.load(base/'nl0.json')) or frozen['spec_sha256']!=nl0.sha(base/'spec.json'):
                raise ValueError('Delivered NL0 differs from its frozen global declarations')
        actual=nl0.validate(base/'nl0.json',base/'spec.json',base/'audit-a.json',allow_unresolved=True)[0]
        if (actual['audit_status']!=record['audit_a'] or not (actual['current_standard_receipt_valid']
                or actual.get('current_conditional_receipt_valid'))):
            raise ValueError('Actual Audit A receipt differs from published result')
        qualified=not actual['current_standard_receipt_valid']
        if scope in {'NL0','UNCONDITIONAL_LEAN'} and qualified:
            raise ValueError('Unqualified result requires a full source review')
    elif scope in LEAN | {'NL0','NL0_SOURCE_QUALIFIED'}:
        raise ValueError('Missing required Audit A receipt')
    verify_route(directory,record,scope,qualified)
    return {'status':'VERIFIED','scope':scope,'files':len(inventory),'run_id':record['run_id']}


def publish(job,result,scope,recorder):
    import phase_metrics
    root=Path(job['root'])
    final=root/'delivery'
    import hashlib
    outcome_digest=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def existing():
        verified=verify(final)
        receipt=nl0.load(final/'run.json')
        if verified['scope']!=scope or verified['run_id']!=job['run_id'] or receipt['outcome_sha256']!=outcome_digest:
            raise ValueError('Another outcome already owns this publication')
        return {'run_id':job['run_id'],'run_sha256':nl0.sha(final/'run.json'),'files':receipt['files']},receipt['remaining_extra_premises']
    if final.exists():return existing()
    with tempfile.TemporaryDirectory(dir=root,prefix='.publication-') as raw:
        stage=Path(raw)/'delivery'
        stage.mkdir()
        lean=stage/'formalization'
        lean.mkdir()
        natural=stage/'nl0'
        natural.mkdir()
        entries=[]
        audit_a=audit_b=None
        selection=root/'source-selection.json'
        if selection.is_file():
            authority=nl0.load(selection)
            data=export_nl0(authority,natural)
            audit_a=data[0]['audit_status']
            if scope in LEAN:
                entries,audit_b=export_lean(result,scope,Path(authority['graph']),lean)
        global_receipt=root/'global-selection.json'
        if global_receipt.is_file():
            from frozen_graph import read_working,shape
            selected=nl0.load(global_receipt)
            frozen=read_working(selected)
            if audit_a:
                from frozen_graph import check_assignment
                check_assignment(frozen,data[2],data[1])
                write(natural/'global.json',{'owner':nl0.load(selected['path'])['owner'],'graph':shape(frozen['graph']),
                                            'spec_sha256':nl0.sha(natural/'spec.json')})
            else:
                from nl0_review_loop import copy_source
                copy_source(Path(nl0.load(selected['path'])['graph']['path']).parent,natural/'frozen')
        if scope=='DIFFERENT_RESULT':
            from translation_reset import authorization
            authorization(result['user_decision'],'deliver-actual')
            # The accepted alternative is explicitly outside formalization of the original target.
            dest=natural/'alternative'
            dest.mkdir()
            copy_input(Path(result['proof']),dest/'Actual.lean')
            copy_input(Path(result['audit_b']['findings']),dest/'findings.json')
        unresolved=[]
        if scope=='STOPPED':
            import case_outcomes
            decision=case_outcomes.verify_basis_decision(root,result['user_decision'],'stop')
            registry=nl0.load(decision['checkpoint']['basis']['path'])
            unresolved=[{'id':d['id'],'port':d['port'],'statement':d['statement'],'origin':d['origin']['reference']}
                        for d in registry['dependencies'] if d['category']==4]
            write(natural/'basis-decision.json',{'decision':'stop','incident':decision['incident'],
                'full_target':registry['full_target'],'unresolved':unresolved,
                'basis_sha256':decision['checkpoint']['basis']['sha256'],
                'review_sha256':decision['checkpoint']['semantic_review']['sha256']})
        extra=[row['id'] for row in entries if row['id']!='P']
        write(stage/STATEMENTS,{'entries':entries})
        recorder.flush(force=True)
        observed=recorder.state['usage']
        end=getattr(recorder,'ended',None) or datetime.now(timezone.utc)
        elapsed=time.monotonic()-recorder.started
        started=recorder.state.get('started_at_utc')
        if started:
            elapsed=(end-datetime.fromisoformat(started)).total_seconds()
        entry='2basis' if job.get('formalization')=='unconditional' else 'nl0'
        exit_name='b2lean' if result.get('closure') else 'nl02lean' if result.get('audit_b') else 'nl0' if audit_a else entry
        timings=root/'handoffs/blocks.json'
        blocks=nl0.load(timings) if timings.is_file() else []
        for block in blocks:
            if block['elapsed_seconds'] is None:
                block['elapsed_seconds']=(end-datetime.fromisoformat(block['started_utc'])).total_seconds()
        record={'version':'yui-delivery-1','blocks':blocks,'outcome_sha256':outcome_digest,
                'last_phase':recorder.state.get('phase'),'elapsed_scope':'case start through delivery checks','run_id':job['run_id'],'requested_goal':'audit' if job['track']=='nl0' else job['formalization'],
                'actual_result':scope,'case_status':result['status'],'entry':entry,'exit':exit_name,
                'unresolved_foundations':[row['id'] for row in unresolved],
                'remaining_extra_premises':extra,'audit_a':audit_a,'audit_b':audit_b,'execution_fault':result.get('execution_fault'),
                'started_utc':started or (end-timedelta(seconds=elapsed)).isoformat(),'ended_utc':end.isoformat(),'elapsed_seconds':elapsed,
                'usage':{'status':observed.get('status','UNKNOWN'),'observed':observed.get('confirmed_tokens'),
                         'total':observed.get('confirmed_tokens') if observed.get('status')=='COMPLETE' else None},
                'stages':phase_metrics.summarize(root)['stages'],'files':files(stage)}
        write(stage/'run.json',record)
        verify(stage)
        anchor={'run_id':job['run_id'],'run_sha256':nl0.sha(stage/'run.json'),'files':record['files']}
        try:stage.rename(final)
        except OSError:
            if final.is_dir():return existing()
            raise
        return anchor,extra

def cleanup_anchor(root):
    """Verify the same blob released by the terminal protocol transition."""
    packet=root/'protocol/delivery'
    path=packet/'inventory.json'
    inventory=nl0.load(path)
    receipt=nl0.load(packet/'result.json')
    ref={'sha256':nl0.sha(path),'size':path.stat().st_size}
    state=nl0.load(root/'protocol/work/state.json')
    if state['status']!='completed' or receipt.get('inventory')!=ref or state['data']!=receipt:
        raise ValueError('Final protocol and retained inventory differ')
    if inventory.get('run_id')!=nl0.load(root/'job.json')['run_id']:
        raise ValueError('Final receipt belongs to another run')
    verification=verify(root/'delivery',anchor=inventory)
    if receipt['scope']!=verification['scope'] or receipt['extra_premises']!=nl0.load(root/'delivery/run.json')['remaining_extra_premises']:
        raise ValueError('The public result does not match the protocol exit')
    return inventory


def partial(job):
    """Keep an interrupted case readable without issuing a completion verdict."""
    from types import SimpleNamespace
    root=Path(job['root'])
    state=nl0.load(root/'execution-status.json')
    result=nl0.load(root/'case-result.json')['result'] if (root/'case-result.json').is_file() else {}
    if result.get('status') in {'DRAFT-AUDIT-PASSED','DRAFT-AUDIT-CONDITIONAL','WORKFLOW-PASSED','WORKFLOW-CONDITIONAL','STOPPED_BY_USER','DIFFERENT_RESULT_DELIVERED'}:
        raise ValueError('A terminal delivery is missing; preserve the accepted evidence')
    elapsed=state.get('elapsed_seconds',0)
    ended=datetime.fromisoformat(state['updated_at_utc']) if state.get('updated_at_utc') else None
    recorder=SimpleNamespace(state=state,started=time.monotonic()-elapsed,ended=ended,flush=lambda **_:None)
    retained=result.get('retained_error',{})
    result={**result,'status':result.get('status','INTERRUPTED'),'execution_fault':retained.get('error') or result.get('error')}
    return publish(job,result,'INTERRUPTED',recorder)[0]

def compare(directory, executable):
    """Run upstream Comparator on a disposable copy; never build in a sealed delivery."""
    directory=Path(directory)
    if verify(directory)['scope'] not in LEAN:
        raise ValueError('This delivery contains no accepted Lean export')
    return compare_package(directory/'formalization',executable)


def compare_package(package, executable):
    import os
    import subprocess
    from runtime_config import load_lock
    executable=Path(executable).resolve(strict=True)
    if not os.access(executable,os.X_OK):raise ValueError('Comparator is not executable')
    with tempfile.TemporaryDirectory(prefix='yui-comparator-') as raw:
        project=Path(raw)/'project'
        shutil.copytree(package,project)
        lib=Path(load_lock()['mathlib']['local_path'])
        (project/'.lake').mkdir()
        packages=project/'.lake/packages'
        packages.mkdir()
        (packages/'mathlib').symlink_to(lib,target_is_directory=True)
        for row in nl0.load(lib/'lake-manifest.json')['packages']:
            (packages/row['name']).symlink_to(lib/'.lake/packages'/row['name'],target_is_directory=True)
        cp=subprocess.run(['lake','env',str(executable),'config.json'],cwd=project,timeout=360,capture_output=True,text=True)
        if cp.returncode:raise ValueError('Comparator failed: '+(cp.stdout+'\n'+cp.stderr)[-2400:])
    return {'status':'COMPARATOR_PASSED','executable_sha256':nl0.sha(executable)}
