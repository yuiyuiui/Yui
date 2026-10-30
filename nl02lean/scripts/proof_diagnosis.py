"""Serial diagnosis of new own-node evidence, followed by an explicit repair route."""
from pathlib import Path
import shutil

import ir
import proof_repair
from controller_common import bind, manifest, write
from execution_health import require_review_execution, record_qualification

PROMPT='''Diagnose this located proof obstruction using only the declared source,
current typed interface/plan, local packet and this worker's actual own attempts.
Worker allegations are claims to check, not facts or previous review verdicts.
Inspect actual library definitions/types where relevant. A compile failure or
long computation does not by itself disprove the goal or establish an interface
error. Distinguish proof-body implementation difficulty from a source-to-formal
mismatch. Do not add premises, weaken the target or introduce a replacement proof
route. Do not produce a proof or grant Audit A/B or interface acceptance.
Return exactly route, explanation, locations, repair_advice, comparison.
route is LOCAL_PROOF_REPAIR, INTERFACE_REPAIR_REQUIRED, SOURCE_REVIEW_REQUIRED
or UNRESOLVED. locations are {document,pointer} resolving in the declared JSON
inputs. explanation and repair_advice are concrete bounded text. Advice identifies
the next local diagnostic/implementation correction, not new assumptions.
INTERFACE_REPAIR_REQUIRED needs a paired actual quoted source/formal comparison
in the same form as the interface reviewer: {source:{document,pointer,quote},
formal:{document,pointer,quote},difference}. Other routes use comparison:null.
For a faithful interface, prefer a located local repair preserving the obligation.
For an actual source gap, retain it explicitly and require the source review
boundary. If evidence cannot determine a safe route, return UNRESOLVED.
This separate diagnostic sees the worker's allegation and own failed candidates;
it is not an untouched independent interface review. Frozen E/P and their
meaning-determining definitions cannot be changed here. Report an actual frozen
contract defect for the user's decision; no automatic unfreeze is authorized.
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
        shutil.copyfile(path,inputs/name);origins.append(bind(path))
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


def validate(value,out):
    import audit_b
    from interface_review import validate_comparison
    ir.need(isinstance(value,dict) and set(value)=={'route','explanation','locations','repair_advice','comparison'},
            'Return exactly the diagnosis schema')
    ir.need(value['route'] in {'LOCAL_PROOF_REPAIR','INTERFACE_REPAIR_REQUIRED','SOURCE_REVIEW_REQUIRED','UNRESOLVED'},
            'Unknown repair route')
    for key in ['explanation','repair_advice']:
        ir.need(isinstance(value[key],str) and 1<=len(value[key].strip())<=12000,'Provide bounded located diagnosis text')
    docs={p.name:ir.load(p) for p in (Path(out)/'inputs').glob('*.json') if p.name!='inputs.json'}
    ir.need(isinstance(value['locations'],list) and 1<=len(value['locations'])<=20,'Locate the actual obstruction')
    for loc in value['locations']:
        ir.need(isinstance(loc,dict) and set(loc)=={'document','pointer'} and loc['document'] in docs
                and isinstance(loc['pointer'],str) and loc['pointer'].startswith('/'),'Invalid diagnosis location')
        audit_b.resolve(docs[loc['document']],loc['pointer'])
    if value['route']=='INTERFACE_REPAIR_REQUIRED':validate_comparison(value['comparison'],docs)
    else:ir.need(value['comparison'] is None,'A paired mismatch comparison is reserved for interface repair')
    return {'scope':'Located diagnostic advice only; no proof, premise or semantic acceptance.'}


def run(proof_run,step,interface,out,*,budget,timeout=None):
    from audit_b_mapping import AssemblyStage
    prepare(proof_run,step,interface,out);out=Path(out)
    stage=AssemblyStage(out/'stage',PROMPT+'\nYou are WB-connect diagnosing a connection/ownership issue under the immutable E/P contract. A contract defect is report-only and requires the user; no automatic unfreeze is authorized.',phase='interface-proof-diagnosis',inputs=out/'inputs/inputs.json',
        library=True,timeout=timeout,budget=budget,validator=lambda value:validate(value,out))
    stage.execute()
    qualification=require_review_execution(ir.load(out/'stage/result.json'),out/'stage/result.json',phase='proof-diagnosis')
    value=ir.load(out/'stage/accepted.json');validate(value,out)
    bindings=ir.load(out/'bindings.json')
    for item in bindings['origins']+bindings['inputs']:
        ir.need(ir.digest(item['path'])==item['sha256'],'Diagnosis evidence changed')
    result={**value,'step':step,'evidence_key':bindings['evidence_key'],
            'actual_diagnosis':bind(out/'stage/accepted.json'),'execution':qualification,
            'scope':'Separate evidence-informed diagnostic; no Audit A/B, interface or proof acceptance.'}
    write(out/'report.json',result)
    return result
