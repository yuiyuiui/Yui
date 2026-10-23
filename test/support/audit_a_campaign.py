#!/usr/bin/env python3
"""Prepare/run fresh exercise reviews and serialize only actual model judgments.

This test controller is not a mathematical verifier. A receipt is withheld when
reviews, source support, or the separately run behavioral controls are incomplete.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / 'rigorous-proof'
sys.path.insert(0, str(CORE / 'scripts'))
sys.path.insert(0, str(CORE / 'translation/scripts'))
import nl0
import concurrency
from clean_stage import ArtifactStage
from review_contract import ReviewContract
from execution_health import require_review_execution
import audit_reuse
from review_contract import put


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def bind(path):
    return {'path': str(path), 'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def manifest(directory):
    rows = [{'id': p.name, **bind(p)} for p in sorted(directory.iterdir()) if p.is_file() and p.name!='inputs.json']
    for row in rows:
        row['path'] = Path(row['path']).name
    write(directory / 'inputs.json', {'inputs': rows})


def check_review(row, packet=None, *, external=False):
    expected={'verdict','notes','locations'}|({'citation_checks'} if external else set())
    if not isinstance(row,dict) or set(row)!=expected:
        raise ValueError('Each actual check needs exactly verdict, notes and locations')
    if row['verdict'] not in nl0.VERDICTS or not isinstance(row['notes'],str) or not row['notes'].strip():
        raise ValueError('Supply an actual specific judgment')
    if not isinstance(row['locations'],list) or not row['locations']:
        raise ValueError('Locate the actual judgment in the supplied material')
    for pointer in row['locations']:
        if not isinstance(pointer,str):raise ValueError('Locations must be strings')
        if packet is not None:nl0.closure.resolve(packet,pointer)
    if external:
        if set(row['citation_checks'])!=nl0.EXTERNAL_CHECKS:raise ValueError('Review every external citation criterion separately')
        for check in row['citation_checks'].values():check_review(check)
        if row['verdict']=='PASS' and any(v['verdict']!='PASS' for v in row['citation_checks'].values()):
            raise ValueError('External source PASS conflicts with an unresolved citation check')


def blocking_finding(finding):
    if not isinstance(finding,dict):raise ValueError('Each finding must be a structured record')
    return (finding.get('verdict')=='FAIL' or
            str(finding.get('severity','')).upper() in {'BLOCKING','FAIL','ERROR','FATAL'})


def validate_review(value, directory, global_stage):
    if global_stage:
        selection=directory/'review-selection.json'
        scopes=set(json.loads(selection.read_text())['required_scopes']) if selection.is_file() else None
        expected={'definition_reviews','source_reviews','findings'}|({k for k,s in [('target_review','target'),('structure_review','structure')] if scopes is None or s in scopes})
        if set(value)!=expected:
            raise ValueError('Expected the complete global review record')
        spec=json.loads((directory/'spec.json').read_text());graph=json.loads((directory/'nl0.json').read_text())
        sources={p['id']:p for p in graph['propositions'] if p['kind'] in {'mathlib','external'}}
        definitions={d['id'] for d in spec['definitions'] if scopes is None or 'definition:'+d['id'] in scopes}
        source_ids={key for key in sources if scopes is None or 'source:'+key in scopes}
        if set(value['definition_reviews'])!=definitions or set(value['source_reviews'])!=source_ids:
            raise ValueError('Review exactly every D and E/M; no missing or extra IDs')
        rows=[value[k] for k in ['target_review','structure_review'] if k in value]+list(value['definition_reviews'].values())
        for row in rows:check_review(row)
        for key,row in value['source_reviews'].items():check_review(row,external=sources[key]['kind']=='external')
        access=directory/'external-source-evidence.json'
        if access.is_file():
            staged=json.loads(access.read_text())
            for key,row in value['source_reviews'].items():
                if key in staged and not any(d['primary'] and d['readback_kind']!='UNAVAILABLE' for d in staged[key]['documents']):
                    if any(row['citation_checks'][name]['verdict']=='PASS' for name in ['result_location','statement_fidelity','context_completeness']):
                        raise ValueError('Primary source has no usable readback; blocked occurrence/statement/context checks remain UNVERIFIED')
        rows+=list(value['source_reviews'].values())
    else:
        packet=json.loads((directory/'packet.json').read_text())
        external={p['id']:p for p in packet['inputs'] if p['kind']=='external'}
        applications={app['id']:app for app in packet['inference']['applications'] if app['input'] in external}
        expected={'inference','packet_sha256','verdict','notes','checks','findings'}|({'external_applications'} if applications else set())
        if set(value)!=expected:raise ValueError('Expected the complete packet review record, including actual E applications when present')
        if value['inference']!=packet['inference']['id'] or value['packet_sha256']!=packet['packet_sha256']:
            raise ValueError('Review the exact supplied packet identity/hash')
        if set(value['checks'])!=nl0.CHECKS|nl0.closure.CLOSURE_CHECKS:
            raise ValueError('Supply all ten actual packet checks')
        rows=list(value['checks'].values())
        for row in rows:check_review(row,packet)
        if applications:
            if set(value['external_applications'])!=set(applications):raise ValueError('Review every actual E application exactly once')
            for aid,row in value['external_applications'].items():
                app=applications[aid]
                if set(row)!={'input','verdict','notes','locations','bindings_review','hypothesis_reviews','conclusion_review','bridges'}:
                    raise ValueError('E application needs binding, per-hypothesis, conclusion and bridge reviews')
                if row['input']!=app['input']:raise ValueError('E application refers to a different source')
                check_review({k:row[k] for k in ['verdict','notes','locations']},packet)
                check_review(row['bindings_review'],packet);check_review(row['conclusion_review'],packet)
                if len(row['hypothesis_reviews'])!=len(external[app['input']]['source_contract']['hypotheses']):
                    raise ValueError('Review every source hypothesis of this E application')
                for item in row['hypothesis_reviews']:check_review(item,packet)
                direct={p['id'] for p in packet['inputs'] if p['kind']=='internal'}
                if not isinstance(row['bridges'],list) or not set(row['bridges'])<=direct:raise ValueError('Bridges must be direct proved N inputs')
                children=[row['bindings_review'],row['conclusion_review'],*row['hypothesis_reviews']]
                if row['verdict']=='PASS' and any(x['verdict']!='PASS' for x in children):raise ValueError('E application summary conflicts with its actual checks')
                rows.append(row)
        if value['verdict']=='PASS' and any(r['verdict']!='PASS' for r in rows):
            raise ValueError('An overall PASS conflicts with a failed/unverified actual check; preserve the actual finding and correct the summary')
    if not isinstance(value['findings'],list):raise ValueError('findings must be a list')
    if any(blocking_finding(f) for f in value['findings']) and all(r['verdict']=='PASS' for r in rows):
        raise ValueError('A blocking FAIL finding conflicts with all-PASS summaries. Preserve the finding and give the relevant actual check its corresponding verdict; do not silently erase or repair the defect.')
    return {'scope':'Review completeness, location and internal consistency only; no mathematical judgment is generated.'}


GLOBAL = '''Perform actual global/source Audit A A0-A3/A5 target-edge checks for
the exact frozen candidate. Read every task input and relevant Yui rules. Check
the original problem against spec: full target, each H, all domains/quantifiers,
and edge cases. Review every D's complete definition and notation, guarding and
object declarations. Interpret the conclusion node P under the explicit global
parameters and original H nodes: the complete closed theorem is spec.full_target
with that context, not P's conclusion text read in isolation. Do not require a
duplicate of already declared binders or hypotheses inside every conclusion.
Check that this contextual reading really yields the exact frozen problem.
Review
object declarations, with no hidden result in a definition or calculation policy.
For each M inspect the supplied actual full-signature evidence AND the pinned
official source through read_mathlib: complete restatement, implicit/typeclass
conditions, relevant axioms and actual applications. A source probe alone is
not source fidelity or applicability. Check graph structure and AND closure;
per-inference packet replay is a separate stage, not yours to invent. Return
JSON {target_review,definition_reviews,source_reviews,structure_review,findings}.
Definition/source reviews are keyed by exactly all D / M IDs. Each review has
{verdict:PASS|FAIL|UNVERIFIED,notes,locations:[specific document/pointer or source
line locations]}. These must be your actual judgments. Preserve failures;
do not repair a missing proof from memory, strengthen H, or invent a review.
Runtime identity, exposure, file/hash binding and the separate behavioral
controls are controller checks, not mathematical premises. No prior verdict
or target reference proof is supplied. The graph's proof bodies are visible
for global consistency/application inspection, so this is not packet-only replay.
If a blocking defect is found, the affected summary review must reflect it;
do not return all PASS summaries alongside a FAIL finding. Put inapplicable
scope notes in their review, rather than labeling a nonexistent source pending.
'''
GLOBAL += '''For each external E, read its staged primary/source readbacks and
external-source-evidence.json. Apply all nine requirements in
references/external-theorems.md. Its source review adds citation_checks with
exactly literature_identity,result_location,statement_fidelity,
context_completeness,version_and_eligibility, each an actual located judgment.
Unavailable primary text remains assessed UNVERIFIED with the blocked checks
and user-notification reason. Continue the remaining checks. A source-access
record or PDF extraction is not proof of document authenticity or eligibility.
'''

PACKET = '''Perform an actual fresh packet-only Audit A replay. Read packet.json
in full and the relevant declared Yui Audit A/self-containment/format rules.
This packet is your only mathematical task material. Treat its inputs as the
allowed conditional premises; source fidelity is checked separately. Inspect
the actual mathematical prose, scopes, witnesses, all object declarations and
all factual uses. Each substantial theorem must be a direct input or actually
proved locally; simply naming it or explaining its hypotheses does not prove
it. Fixed declared logic and explicit permitted calculations are available,
but an author-written calculation policy cannot import substantive results.
Return JSON {inference,packet_sha256,verdict,notes,checks,findings}. checks has
exactly inputs,argument,dependency_accounting,output,scope,applicability,
statement_closure,object_closure,dependency_closure,packet_replay. Each is
{verdict:PASS|FAIL|UNVERIFIED,notes,locations:[resolving JSON pointers into this
packet]}. Give actual specific judgments. Locate the first unsupported
implication if present; do not repair the supplied argument or substitute a
different proof. For packet_replay judge sufficiency from this packet alone.
Carrier identity, canonical hash binding and transmitted-material readback
are checked outside your mathematical review. State your real input boundary,
without inventing runtime attestation or asking for extra source proofs.
The packet_replay verdict is the mathematical conditional: given the externally
checked carrier/input boundary, does this packet alone suffice? You do not
certify execution isolation. Missing access to runtime logs is therefore not a
mathematical UNVERIFIED finding for packet_replay. Preserve actual mathematical
uncertainty or insufficiency, and state your own read boundary honestly. The
controller separately rejects unqualified execution before accepting the review.
'''
PACKET += '''When E applications occur, add external_applications keyed by every
actual inference-local A ID. Each has input,verdict,notes,locations,
bindings_review,hypothesis_reviews,conclusion_review,bridges. The binding and
conclusion rows and each per-source-hypothesis row have verdict,notes,locations.
Review every condition from the packet's E contract and displayed derivations;
bridges lists only explicitly direct N inputs. These are conditional application
checks; the separate source lane checks the cited publication. With no E
applications omit external_applications.
'''


def prepare(case, problem, out, *, reuse_from=()):
    case, problem, out = [Path(p).resolve() for p in (case, problem, out)]
    data = nl0.validate(case/'nl0.json', case/'spec.json')
    hits=audit_reuse.select(data,reuse_from)
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, out/'controller.py.snapshot.txt')
    g = out/'global'; g.mkdir()
    for filename in ['problem.md','source-context.md','frozen-target.md']:
        if (problem/filename).exists(): shutil.copyfile(problem/filename,g/filename)
    for filename in ['nl0.json','spec.json']: shutil.copyfile(case/filename,g/filename)
    probes = {}
    for pid,p in data[3].items():
        if p['kind'] == 'mathlib':
            probes[pid] = [json.loads((case/e['path']).read_text()) for e in p['source']['evidence']]
    write(g/'signature-evidence.json', probes)
    externals={}
    from source_staging import stage_external
    for pid,p in data[3].items():
        if p['kind']=='external':externals[pid]=stage_external(case,p,g)
    if externals:write(g/'external-source-evidence.json',externals)
    scopes=['target','structure',*['definition:'+key for key in data[5]],
            *['source:'+key for key,p in data[3].items() if p['kind'] in {'external','mathlib'}]]
    required=[key for key in scopes if key not in hits]
    if hits:write(g/'review-selection.json',{'required_scopes':required,
        'instruction':'Review only these assigned items. Other judgments are inherited outside this fresh context; no prior verdicts are supplied.'})
    manifest(g); (g/'prompt.txt').write_text(GLOBAL)
    if hits:(g/'prompt.txt').write_text(GLOBAL+'\nReview only review-selection.json required_scopes; omit unassigned target/structure rows and leave unassigned D/E/M entries out of their maps.\n')
    jobs = [{'id':'global','library':True,'required_scopes':required}]
    for rid in sorted(data[4]):
        directory=out/rid;directory.mkdir()
        write(directory/'packet.json',nl0.packet(data,rid))
        manifest(directory);(directory/'prompt.txt').write_text(PACKET)
        jobs.append({'id':rid,'library':False})
    inherited={scope:audit_reuse.materialize(hit,case) for scope,hit in hits.items()}
    plan={'case':str(case),'graph':bind(case/'nl0.json'),'spec':bind(case/'spec.json'),
          'jobs':jobs,'inherited':inherited,'status':'PREPARED_NOT_REVIEWED',
          'reuse_policy':'Explicit same-case prior campaigns; warm costs retained, not a cold benchmark.'}
    write(out/'campaign.json',plan)
    return plan


def run(out, timeout, budget=None):
    out=Path(out).resolve(); plan=json.loads((out/'campaign.json').read_text())
    budget=concurrency.serial_budget(budget)
    def execute(job):
        directory=out/job['id']
        inherited=plan.get('inherited',{})
        if ('packet:'+job['id'] in inherited or (job['library'] and not job.get('required_scopes',['legacy-full']))):
            return {'id':job['id'],'model_worker_called':False,'status':'INHERITED_QUALIFIED_ITEMS'}
        if (directory/'stage/result.json').is_file():
            result=json.loads((directory/'stage/result.json').read_text())
            return {'id':job['id'],'result':result,'artifact_present':(directory/'stage/accepted.json').is_file(),
                    'reused_existing_stage':True}
        if job['library']:
            spec=json.loads((directory/'spec.json').read_text());graph=json.loads((directory/'nl0.json').read_text())
            base={'definition_reviews':{},'source_reviews':{}}
            required=['/target_review','/structure_review',
                *['/definition_reviews/'+d['id'] for d in spec['definitions']],
                *['/source_reviews/'+p['id'] for p in graph['propositions'] if p['kind'] in {'mathlib','external'}]]
            if 'required_scopes' in job:
                required=[{'target':'/target_review','structure':'/structure_review'}.get(scope,
                    '/definition_reviews/'+scope.split(':')[-1] if scope.startswith('definition:') else '/source_reviews/'+scope.split(':')[-1]) for scope in job['required_scopes']]
        else:
            packet=json.loads((directory/'packet.json').read_text())
            base={'inference':packet['inference']['id'],'packet_sha256':packet['packet_sha256'],'checks':{}}
            required=['/checks/'+key for key in nl0.CHECKS|nl0.closure.CLOSURE_CHECKS]
            external={p['id'] for p in packet['inputs'] if p['kind']=='external'}
            apps=[app['id'] for app in packet['inference']['applications'] if app['input'] in external]
            if apps:
                base['external_applications']={}
                required+=['/external_applications/'+key for key in apps]
        def row_check(pointer,row):
            if pointer.startswith('/external_applications/'):
                check_review({k:row[k] for k in ['verdict','notes','locations']},packet)
            else:
                check_review(row,None if job['library'] else packet,
                    external=job['library'] and pointer.startswith('/source_reviews/E'))
        contract=ReviewContract(directory/'review-work',base,required,
            lambda value:validate_review(value,directory,job['library']),
            row_validator=row_check,
            finding_validator=lambda finding:check_review({'verdict':'FAIL','notes':finding['explanation'],
                'locations':finding['locations']},None if job['library'] else packet))
        stage=ArtifactStage(directory/'stage',(directory/'prompt.txt').read_text(),
            phase='audit-a-global' if job['library'] else 'audit-a-packet-replay',
            inputs=directory/'inputs.json',library=job['library'],timeout=timeout,budget=budget,
            validator=contract)
        result,artifact=stage.execute()
        return {'id':job['id'],'result':result,'artifact_present':artifact is not None}
    results=[execute(job) for job in plan['jobs']]
    report={'results':results,'concurrency':budget.report(),
            'execution_policy':'One serial Audit A lane; packet contexts remain fresh and separate.'}
    write(out/'execution.json',report)
    return report


def collect(out, controls):
    out=Path(out).resolve(); plan=json.loads((out/'campaign.json').read_text())
    case=Path(plan['case'])
    for name in ['graph','spec']:
        if bind(plan[name]['path']) != plan[name]: raise ValueError('Source changed after review preparation')
    data=nl0.validate(case/'nl0.json',case/'spec.json')
    reports={};evidence={};qualifications=[]
    for job in plan['jobs']:
        directory=out/job['id']/'stage'
        if 'packet:'+job['id'] in plan.get('inherited',{}):
            inherited=plan['inherited']['packet:'+job['id']]
            cached=audit_reuse.validate(case,inherited,data,'packet:'+job['id'])
            reports[job['id']]=cached['raw']
            evidence[job['id']]=[inherited,*cached['record']['previous'].values()]
            qualifications.append(cached['record']['qualification'])
            continue
        if job['library'] and not job.get('required_scopes',['legacy-full']):
            reports['global']={'definition_reviews':{},'source_reviews':{},'findings':[]}
            continue
        result=json.loads((directory/'result.json').read_text())
        qualifications.append(require_review_execution(result,directory/'result.json',phase='audit-a'))
        report=json.loads((directory/'accepted.json').read_text())
        target=case/'review-evidence'/out.name/job['id'];target.mkdir(parents=True,exist_ok=True)
        trace=[]
        for path in sorted(directory.rglob('*')):
            if path.is_file():trace.append(bind(path))
        trace_record={'files':trace,'source_stage':str(directory)}
        if (target/'trace-manifest.json').exists():
            if json.loads((target/'trace-manifest.json').read_text())!=trace_record:raise ValueError('Previous review evidence changed')
        else:write(target/'trace-manifest.json',trace_record)
        for name in ['accepted.json','result.json','exposure-audit.json','execution-manifest.json']:
            if (target/name).exists():
                if (target/name).read_bytes()!=(directory/name).read_bytes():raise ValueError('Previous review evidence changed')
            else:shutil.copyfile(directory/name,target/name)
        reports[job['id']]=report
        evidence[job['id']]=[{**bind(p),'path':str(p.relative_to(case))} for p in sorted(target.iterdir())]
    global_=reports['global'];global_evidence={}
    for scope,inherited in plan.get('inherited',{}).items():
        if scope.startswith('packet:'):continue
        cached=audit_reuse.validate(case,inherited,data,scope)
        pointer={'target':'/target_review','structure':'/structure_review'}.get(scope,
            '/definition_reviews/'+scope.split(':')[-1] if scope.startswith('definition:') else '/source_reviews/'+scope.split(':')[-1])
        put(global_,pointer,cached['raw'])
        global_evidence[scope]=[inherited,*cached['record']['previous'].values()]
        qualifications.append(cached['record']['qualification'])
    if set(global_['definition_reviews'])!=set(data[5]) or set(global_['source_reviews'])!={k for k,p in data[3].items() if p['kind'] in {'mathlib','external'}}:
        raise ValueError('Incomplete global definition/source review coverage')
    receipt=nl0.closure.audit_template(data,nl0.CHECKS,nl0.EXTERNAL_CHECKS,'nl0.json','spec.json')
    receipt['reviewer']={'identity':'gpt-6-luna high Standard; separate fresh global and per-inference contexts',
        'mode':'split_clean_audit','independent':True,
        'disclosure':'New global checks saw original problem/spec/graph and actual source evidence. Each new replay saw only its exact packet and Yui rules, without source/ancestor proofs or old verdicts. Explicit inherited items retain their old actual judgments, execution evidence, context comparison and costs; they are not new fresh reviews. Actual transmitted exposure and stage logs are preserved. Provider internals are not independently attested. Behavioral-control evidence is recorded separately.'}
    def judgment(row,ev,located=False):
        if row['verdict'] not in nl0.VERDICTS or not row['notes'].strip():raise ValueError('Invalid actual judgment')
        answer={'verdict':row['verdict'],'notes':row['notes'],'evidence':ev}
        if located:answer['locations']=list(dict.fromkeys(row['locations']))
        else:answer['notes']+=' Actual locations: '+json.dumps(row.get('locations',[]),ensure_ascii=False)
        return answer
    def global_judgment(scope,row):
        answer=judgment(row,global_evidence.get(scope,evidence.get('global',[])))
        if scope in plan.get('inherited',{}):answer['inheritance']=plan['inherited'][scope]
        return answer
    receipt['target_review']=global_judgment('target',global_['target_review'])
    receipt['structure_review']=global_judgment('structure',global_['structure_review'])
    for group in ['definition_reviews','source_reviews']:
        kind='definition' if group=='definition_reviews' else 'source'
        receipt[group]={k:global_judgment(kind+':'+k,v) for k,v in global_[group].items()}
    for pid,p in data[3].items():
        if p['kind']=='external':
            receipt['source_reviews'][pid]['citation_checks']={k:judgment(v,global_evidence.get('source:'+pid,evidence.get('global',[]))) for k,v in global_['source_reviews'][pid]['citation_checks'].items()}
    for rid in data[4]:
        row=reports[rid];packet=nl0.packet(data,rid)
        inherited=plan.get('inherited',{}).get('packet:'+rid)
        if row['inference']!=rid or (not inherited and row['packet_sha256']!=packet['packet_sha256']):
            raise ValueError('Reviewer bound a different packet '+rid)
        actual=judgment(row,evidence[rid])
        actual['checks']={k:judgment(v,evidence[rid],True) for k,v in row['checks'].items()}
        actual['external_applications']={}
        for aid,app in row.get('external_applications',{}).items():
            actual['external_applications'][aid]={**judgment(app,evidence[rid]),'input':app['input'],
                'bindings_review':judgment(app['bindings_review'],evidence[rid]),
                'hypothesis_reviews':[judgment(v,evidence[rid]) for v in app['hypothesis_reviews']],
                'conclusion_review':judgment(app['conclusion_review'],evidence[rid]),'bridges':app['bridges']}
        actual['replay']={'packet_sha256':packet['packet_sha256'],'mode':'fresh_packet_only',
            'carrier':str(out/rid/'stage'),'prior_exposure':[],
            'read_materials':['packet:'+packet['packet_sha256']]}
        if inherited:
            actual['inheritance']=inherited
            actual['replay'].update(packet_sha256=row['packet_sha256'],carrier='inherited:'+audit_reuse.read_binding(case,inherited)[0]['previous_campaign'],
                                    read_materials=['packet:'+row['packet_sha256']])
        receipt['inference_reviews'][rid]=actual
    blocking_global = global_['structure_review']['verdict'] != 'PASS' or any(
        blocking_finding(f) for f in global_.get('findings', []))
    destination=case/('audit-a.pending.json' if controls is None or blocking_global else 'audit-a.json')
    if destination.exists():raise ValueError('Preserve previous audit receipt; use a new source/review version')
    if controls:
        controls=Path(controls).resolve(); control=json.loads(controls.read_text())
        if control.get('status')!='BEHAVIORAL-CONTROLS-PASSED':raise ValueError('Actual behavioral controls have not passed')
        write(out/'behavioral-control-binding.json',bind(controls))
    write(destination,receipt)
    inspection=nl0.validate(case/'nl0.json',case/'spec.json',destination,allow_unresolved=True)[0]
    inspection['global_structure_review']=global_['structure_review']
    inspection['global_findings']=global_.get('findings',[])
    inspection['behavioral_controls']='NOT_RUN' if controls is None else str(controls)
    inspection['full_acceptance']=bool(controls and inspection['current_standard_receipt_valid'] and not blocking_global)
    inspection['inherited_items']=sorted(plan.get('inherited',{}))
    inspection['measurement_complete']=bool(qualifications) and all(q['measurement_complete'] for q in qualifications)
    inspection['performance_scope']='WARM_REVIEW_REUSE_NOT_COLD_BENCHMARK' if plan.get('inherited') else 'RECORDED_STAGES_ONLY'
    write(out/'inspection.json',inspection)
    return inspection


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    prepare_=commands.add_parser('prepare');prepare_.add_argument('--case',required=True);prepare_.add_argument('--problem',required=True);prepare_.add_argument('--out',required=True);prepare_.add_argument('--reuse-from',action='append',default=[])
    run_=commands.add_parser('run');run_.add_argument('--out',required=True);run_.add_argument('--timeout-seconds',type=int,default=900)
    collect_=commands.add_parser('collect');collect_.add_argument('--out',required=True);collect_.add_argument('--controls')
    args=parser.parse_args()
    if args.command=='prepare':result=prepare(args.case,args.problem,args.out,reuse_from=args.reuse_from)
    elif args.command=='run':result=run(args.out,args.timeout_seconds)
    else:result=collect(args.out,args.controls)
    print(json.dumps(result,ensure_ascii=False,indent=2))
