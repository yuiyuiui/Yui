"""Serial diagnosis of new own-node evidence, followed by an explicit repair route."""
from pathlib import Path
import shutil

import ir
from staging_storage import copy_input
import proof_repair
import artifact_protocol as protocol
from controller_common import bind, manifest, write
from execution_health import StageFailure, require_review_execution, record_qualification
import threading

_notice_lock=threading.Lock()

PROMPT='''Diagnose this located proof obstruction using only the declared source,
current typed interface/plan, local packet and this worker's actual own attempts.
Worker allegations are claims to check, not facts or previous review verdicts.
Inspect actual library definitions/types where relevant. A compile failure or
long computation does not by itself disprove the goal or establish an interface
error. Distinguish proof-body implementation difficulty from a source-to-formal
mismatch. Do not add premises, weaken the target or introduce a replacement proof
route. Do not produce a proof or grant Audit A/B or interface acceptance.
Return exactly route, explanation, locations, repair_advice, comparison.
route is LOCAL_PROOF_REPAIR, INTERNAL_INTERFACE_REPAIR, INTERFACE_REPAIR_REQUIRED, SOURCE_REVIEW_REQUIRED
or UNRESOLVED. locations are {document,pointer} resolving in the declared JSON
inputs. explanation and repair_advice are concrete bounded text. Advice identifies
the next local diagnostic/implementation correction, not new assumptions.
INTERNAL_INTERFACE_REPAIR and INTERFACE_REPAIR_REQUIRED need a paired actual quoted source/formal comparison
in the same form as the interface reviewer: {source:{document,pointer,quote},
formal:{document,pointer,quote},difference}. SOURCE_REVIEW_REQUIRED instead needs
comparison={kind,source_quote,hypotheses,claim,defect,why_not_lean_difficulty};
kind is FALSE_IMPLICATION or MISSING_JUSTIFICATION. Quote the actual local NL
step, identify the invalid implication or essential missing argument, and explain
why this is mathematical rather than missing Lean implementation. A long routine
formalization, resource limit, unavailable library lemma or failed tactic is not
such evidence. Distinguish an insufficient source argument from a false claim.
LOCAL_PROOF_REPAIR and UNRESOLVED use comparison:null and return actionable next
local diagnostics; uncertainty leaves the original author working.
For a faithful interface, prefer a located local repair preserving the obligation.
For an actual source gap, retain it explicitly and require the source review
boundary. If evidence cannot determine a safe route, return UNRESOLVED.
This separate diagnostic sees the worker's allegation and own failed candidates;
it is not an untouched independent interface review. Frozen E/P and their
meaning-determining definitions cannot be changed here. Report an actual frozen
contract defect for the user's decision; no automatic unfreeze is authorized.
Use INTERNAL_INTERFACE_REPAIR for a located T-statement or allowed-input defect
repairable while preserving the entire public header, original H/E/P and source.
Examples include a non-inferable argument in an internal statement or a missing
already-allowed direct input. This routes to reviewed preprocessing revision,
not user pause. Reserve INTERFACE_REPAIR_REQUIRED for evidence that the protected
public contract itself must change. Difficulty alone supports neither route.
'''


def prepare(proof_run,step,interface,out):
    proof_run,interface,out=map(lambda p:Path(p).resolve(),(proof_run,interface,out))
    report=ir.load(proof_run/'report.json');request=report['repair_requests'][step]
    cpath=proof_run/'inputs/contract.json';ppath=proof_run/'inputs/plan.json';plan=ir.load(ppath)
    worker=proof_run/'workers'/step
    result=ir.load(worker/'result.json')
    ir.need(result.get('status')=='REPAIR_REQUESTED' and result.get('repair_request')==request
            and record_qualification(result)['record_context_qualified'],
            'No qualified actual proof-worker repair request')
    ir.need(request['contract_sha256']==ir.digest(cpath) and request['plan_sha256']==proof_repair.digest(plan)
            and request['packet_sha256']==proof_repair.digest(ir.local_packet(cpath,plan,step)),
            'Stale proof obstruction context')
    out.mkdir(parents=True,exist_ok=False);inputs=out/'inputs';inputs.mkdir()
    origins=[bind(proof_run/'report.json'),bind(worker/'result.json')]
    for path,name in [(cpath,'contract.json'),(ppath,'plan.json'),
                      (interface/'inputs/spec.json','spec.json'),(interface/'inputs/nl0.json','nl0.json')]:
        copy_input(path,inputs/name);origins.append(bind(path))
    write(inputs/'local-packet.json',ir.local_packet(cpath,plan,step));write(inputs/'obstruction.json',request)
    attempts=[]
    for item in request['candidate_evidence']:
        path=worker/'lean-drafts'/f"{item['kind']}-{item['candidate']:04d}.json"
        ir.need(not path.is_symlink() and path.resolve().parent==worker/'lean-drafts','Unsafe own-attempt evidence')
        value=ir.load(path)
        ir.need(proof_repair.digest(value)==item['sha256'],'Changed own-attempt evidence')
        attempts.append({**item,'actual_attempt':value});origins.append(bind(path))
    write(inputs/'own-attempts.json',attempts);manifest(inputs)
    write(out/'bindings.json',{'step':step,'evidence_key':request['evidence_key'],'origins':origins,
                              'inputs':[bind(p) for p in inputs.iterdir() if p.is_file()]})
    (out/'prompt.txt').write_text(PROMPT)


def artifact_schema():
    from interface_review import comparison_schema
    common={'explanation':{**protocol.TEXT,'maxLength':12000},
        'repair_advice':{**protocol.TEXT,'maxLength':12000},
        'locations':protocol.array(protocol.obj({'document':protocol.TEXT,'pointer':{'type':'string','pattern':'^/'}}),minItems=1,maxItems=20)}
    return protocol.choice(*[protocol.obj({**common,'route':{'enum':routes},'comparison':comparison}) for routes,comparison in [
        (['LOCAL_PROOF_REPAIR','UNRESOLVED'],{'type':'null'}),
        (['INTERNAL_INTERFACE_REPAIR','INTERFACE_REPAIR_REQUIRED'],comparison_schema()),
        (['SOURCE_REVIEW_REQUIRED'],proof_repair.source_issue_schema())]])


def validate(value,out):
    import audit_b
    from interface_review import validate_comparison
    protocol.validate(value,artifact_schema(),error_type=ir.Invalid)
    for key in ['explanation','repair_advice']:
        ir.need(isinstance(value[key],str) and 1<=len(value[key].strip())<=12000,'Provide bounded located diagnosis text')
    docs={p.name:ir.load(p) for p in (Path(out)/'inputs').glob('*.json') if p.name!='inputs.json'}
    ir.need(isinstance(value['locations'],list) and 1<=len(value['locations'])<=20,'Locate the actual obstruction')
    for loc in value['locations']:
        ir.need(isinstance(loc,dict) and set(loc)=={'document','pointer'} and loc['document'] in docs
                and isinstance(loc['pointer'],str) and loc['pointer'].startswith('/'),'Invalid diagnosis location')
        audit_b.resolve(docs[loc['document']],loc['pointer'])
    if value['route'] in {'INTERFACE_REPAIR_REQUIRED','INTERNAL_INTERFACE_REPAIR'}:validate_comparison(value['comparison'],docs)
    elif value['route']=='SOURCE_REVIEW_REQUIRED':
        proof_repair.validate_source_issue(value['comparison'],docs['local-packet.json'])
    else:ir.need(value['comparison'] is None,'A paired mismatch comparison is reserved for interface repair')
    return {'scope':'Located diagnostic advice only; no proof, premise or semantic acceptance.'}


def run(proof_run,step,interface,out,*,budget,timeout=None):
    prepare(proof_run,step,interface,out);out=Path(out)
    return run_prepared(out,step,budget=budget,timeout=timeout)


def prepare_live(author, request, interface, out):
    """Snapshot this request while the original author waits for its tool result."""
    out=Path(out);inputs=out/'inputs';inputs.mkdir(parents=True,exist_ok=False)
    interface=Path(interface)
    ir.need(request['packet_sha256']==proof_repair.digest(ir.local_packet(author.cpath,author.plan,author.step)),
            'Live diagnosis packet changed')
    origins=[]
    for path,name in [(Path(author.cpath),'contract.json'),
                      (interface/'inputs/spec.json','spec.json'),
                      (interface/'inputs/nl0.json','nl0.json')]:
        copy_input(path,inputs/name);origins.append(bind(path))
    write(inputs/'plan.json',author.plan)
    write(inputs/'local-packet.json',ir.local_packet(author.cpath,author.plan,author.step))
    write(inputs/'obstruction.json',request)
    attempts=[]
    for item in request['candidate_evidence']:
        path=author.logs/'lean-drafts'/f"{item['kind']}-{item['candidate']:04d}.json"
        ir.need(not path.is_symlink(),'Unsafe live attempt')
        value=ir.load(path)
        ir.need(proof_repair.digest(value)==item['sha256'],'Changed live attempt')
        attempts.append({**item,'actual_attempt':value});origins.append(bind(path))
    write(inputs/'own-attempts.json',attempts);manifest(inputs)
    write(out/'bindings.json',{'step':author.step,'evidence_key':request['evidence_key'],
        'origins':origins,'inputs':[bind(p) for p in inputs.iterdir() if p.is_file()],
        'scope':'Immutable own-node request; the author session remains alive.'})
    (out/'prompt.txt').write_text(PROMPT)


def run_live(author,request,interface,out,*,budget,timeout=None):
    prepare_live(author,request,interface,out)
    result=run_prepared(Path(out),author.step,budget=budget,timeout=timeout,
                        parent_task=getattr(author,'execution_task',None))
    if result['route']=='SOURCE_REVIEW_REQUIRED':
        notice_source(author.cpath,author.step,Path(out),result)
    return result


def notice_source(cpath,step,out,result):
    """Report a qualified mathematical issue once, independently of siblings."""
    import fault_control
    gate=fault_control.Gate(out)
    identity=proof_repair.digest([ir.contract(cpath)['source']['sha256'],step,result['comparison']])
    path=gate.root/'source-issues'/(identity+'.json')
    with _notice_lock:
        if path.exists():return bind(path)
        text=('[Yui 数学证明问题] 节点 '+step+'：独立诊断发现原证明存在错误或重要缺失步骤。'
            '这不是 Lean 尝试次数或计算额度超限的判定。该节点等待用户判断，其他节点不会因此被取消。\n'
            +result['explanation']+'\n证据：'+str(out/'report.json'))
        try:notification=gate.notify(gate.owner(),text)
        except Exception as error:notification={'status':'PENDING','error':str(error)}
        write(path,{'source_sha256':ir.contract(cpath)['source']['sha256'],'step':step,
            'comparison':result['comparison'],'diagnosis':bind(out/'report.json'),'notification':notification})
    return bind(path)


def run_prepared(out,step,*,budget,timeout=None,parent_task=None):
    from audit_b_mapping import AssemblyStage
    stage=AssemblyStage(out/'stage',PROMPT+'\nYou are WB-connect diagnosing a connection/ownership issue under the immutable public contract. Internal T defects return to reviewed preprocessing; protected public-contract defects require the user.',phase='interface-proof-diagnosis',inputs=out/'inputs/inputs.json',
        library=True,timeout=timeout,budget=budget,validator=protocol.Contract(artifact_schema(),lambda value:validate(value,out)))
    stage.parent_execution_task=parent_task
    try:stage.execute()
    except StageFailure as error:
        import basis_defect
        if not parent_task or error.result['status']!=basis_defect.STATUS:raise
        # Return through the live proof worker's regular handoff, after releasing its slot.
        # The case controller revalidates this original report outside the worker pool.
        result={'route':basis_defect.STATUS,'step':step,'evidence_key':ir.load(out/'bindings.json')['evidence_key'],
                'diagnosis_report':str(out/'report.json'),'basis_defect':error.result['basis_defect']}
        write(out/'report.json',result)
        return result
    if parent_task and getattr(budget,'execution',None):budget.execution.check(parent_task)
    qualification=require_review_execution(ir.load(out/'stage/result.json'),out/'stage/result.json',phase='proof-diagnosis')
    value=ir.load(out/'stage/accepted.json');validate(value,out)
    bindings=ir.load(out/'bindings.json')
    for item in bindings['origins']+bindings['inputs']:
        ir.need(ir.digest(item['path'])==item['sha256'],'Diagnosis evidence changed')
    result={**value,'step':step,'evidence_key':bindings['evidence_key'],
            'actual_diagnosis':bind(out/'stage/accepted.json'),'execution':qualification,
            'diagnosis_report':str(out/'report.json'),
            'scope':'Separate evidence-informed diagnostic; no Audit A/B, interface or proof acceptance.'}
    write(out/'report.json',result)
    return result
