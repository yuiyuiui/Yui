#!/usr/bin/env python3
"""Prepare/run fresh source reviews and serialize only actual model judgments.

This controller records actual assessments, not mathematical proofs. Review
coverage/source support and optional developer calibration have separate outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import sys

CORE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CORE / 'nl0/scripts'))
sys.path.insert(0, str(CORE / 'nl02lean/scripts'))
import nl0
import concurrency
from clean_stage import ArtifactStage
from review_contract import ReviewContract
from execution_health import require_review_execution
import audit_reuse
import foundations
import background
from review_contract import put
import artifact_protocol as protocol


from controller_common import write, bind, manifest


def global_location(directory, locator):
    """Resolve a global allegation in declared input bytes or pinned Mathlib."""
    directory=Path(directory).resolve()
    if not isinstance(locator,str):raise ValueError('AUDIT-LOCATION: use an exact document pointer or line span')
    match=re.fullmatch(r'([^#]+)#(/.*|)',locator)
    if match:
        document,pointer=match.groups()
        if pointer in {'','/'}:raise ValueError('AUDIT-LOCATION: choose the actual offending record or text, not the whole document')
        manifest=json.loads((directory/'inputs.json').read_text())
        rows={row['id']:row for row in manifest['inputs']}
        if document not in rows:raise ValueError('AUDIT-LOCATION: unknown input document '+document)
        path=(directory/rows[document]['path']).resolve()
        if not path.is_relative_to(directory):raise ValueError('AUDIT-LOCATION: document escapes stage')
        value=json.loads(path.read_text())
        return nl0.closure.resolve(value,pointer) if pointer else value
    match=re.fullmatch(r'([^:]+):(\d+)-(\d+)',locator)
    if not match:raise ValueError('AUDIT-LOCATION: use document.json#/exact/pointer or document:start-end; no commentary suffix')
    document,start,end=match.groups();start,end=int(start),int(end)
    if document.startswith('Mathlib/') and document.endswith('.lean'):
        from runtime_config import load_lock
        root=Path(load_lock()['mathlib']['local_path']).resolve();path=(root/document).resolve()
        if not path.is_relative_to(root/'Mathlib'):raise ValueError('AUDIT-LOCATION: library path escapes pin')
    else:
        manifest=json.loads((directory/'inputs.json').read_text())
        rows={row['id']:row for row in manifest['inputs']}
        if document not in rows:raise ValueError('AUDIT-LOCATION: unknown input document '+document)
        path=(directory/rows[document]['path']).resolve()
        if not path.is_relative_to(directory):raise ValueError('AUDIT-LOCATION: document escapes stage')
    lines=path.read_text().splitlines()
    if not 1<=start<=end<=len(lines) or end-start>=250:raise ValueError('AUDIT-LOCATION: choose at most 250 existing lines')
    return '\n'.join(lines[start-1:end])


def finding_fields():
    return {'explanation':protocol.TEXT,'locations':protocol.array(protocol.STRING,minItems=1),
            'quotation':protocol.obj({'location':protocol.STRING,'text':protocol.TEXT})}


def validate_finding(finding,directory,packet=None):
    """Check actual offending bytes, not the mathematical truth of an objection."""
    protocol.validate(finding,protocol.obj(finding_fields(),extra=True),'/finding')
    check_review({'verdict':'FAIL','notes':finding['explanation'],'locations':finding['locations']},packet)
    if packet is None:
        for location in finding['locations']:global_location(directory,location)
    quote=finding.get('quotation')
    if quote['location'] not in finding['locations']:raise ValueError('AUDIT-QUOTATION: quotation location must be one of the finding locations')
    value=nl0.closure.resolve(packet,quote['location']) if packet is not None else global_location(directory,quote['location'])
    text=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)
    if quote['text'] not in text:raise ValueError('AUDIT-QUOTATION: quoted text is absent from the exact supplied location')


def judgment_schema(*, external=False):
    extra={'citation_checks':protocol.obj({key:protocol.judgment() for key in nl0.EXTERNAL_CHECKS})} if external else {}
    return protocol.judgment(extra=extra)


def check_review(row, packet=None, *, external=False):
    protocol.validate(row,judgment_schema(external=external))
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


def review_shape(directory, global_stage):
    directory=Path(directory)
    findings=protocol.array(protocol.finding_schema(finding_fields()))
    if global_stage:
        selection=directory/'review-selection.json'
        scopes=set(json.loads(selection.read_text())['required_scopes']) if selection.is_file() else None
        spec=json.loads((directory/'spec.json').read_text());graph=json.loads((directory/'nl0.json').read_text())
        rows={k:judgment_schema() for k,s in [('target_review','target'),('structure_review','structure')]
              if scopes is None or s in scopes}
        groups={'definition_reviews':{d['id']:judgment_schema() for d in spec['definitions']
                                      if scopes is None or 'definition:'+d['id'] in scopes},
                'source_reviews':{p['id']:judgment_schema(external=p['kind']=='external') for p in graph['propositions']
                                  if p['kind'] in {'mathlib','external'} and (scopes is None or 'source:'+p['id'] in scopes)}}
        return protocol.ReviewShape(groups=groups,rows=rows,summary={'findings':findings})
    packet=json.loads((directory/'packet.json').read_text())
    groups={'checks':{key:judgment_schema() for key in nl0.CHECKS|nl0.closure.CLOSURE_CHECKS}}
    external={p['id']:p for p in packet['inputs'] if p['kind']=='external'}
    applications={app['id']:app for app in packet['inference']['applications'] if app['input'] in external}
    if applications:
        groups['external_applications']={key:protocol.obj({
            **judgment_schema()['properties'],'input':protocol.literal(app['input']),
            'bindings_review':judgment_schema(),'conclusion_review':judgment_schema(),
            'hypothesis_reviews':protocol.array(judgment_schema(),
                minItems=len(external[app['input']]['source_contract']['hypotheses']),
                maxItems=len(external[app['input']]['source_contract']['hypotheses'])),
            'bridges':protocol.array(protocol.STRING)}) for key,app in applications.items()}
    return protocol.ReviewShape(groups=groups,summary={
        'verdict':protocol.VERDICT,'notes':protocol.TEXT,'findings':findings},
        identities={'inference':packet['inference']['id'],'packet_sha256':packet['packet_sha256']},
        optional={'background_notes':protocol.array(background.note_schema())})


def validate_review(value, directory, global_stage):
    review_shape(directory,global_stage).validate(value)
    if global_stage:
        selection=directory/'review-selection.json'
        scopes=set(json.loads(selection.read_text())['required_scopes']) if selection.is_file() else None
        spec=json.loads((directory/'spec.json').read_text());graph=json.loads((directory/'nl0.json').read_text())
        sources={p['id']:p for p in graph['propositions'] if p['kind'] in {'mathlib','external'}}
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
        background.validate(value.get('background_notes', []), packet, directory/'stage')
        if value['inference']!=packet['inference']['id'] or value['packet_sha256']!=packet['packet_sha256']:
            raise ValueError('Review the exact supplied packet identity/hash')
        if set(value['checks'])!=nl0.CHECKS|nl0.closure.CLOSURE_CHECKS:
            raise ValueError('Supply the five actual grouped packet checks')
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
    for finding in value['findings']:
        if blocking_finding(finding):validate_finding(finding,directory,None if global_stage else packet)
    return {'scope':'Review completeness, location and internal consistency only; no mathematical judgment is generated.'}


GLOBAL = '''Perform independent global mathematical Audit A for the exact frozen
NL0 candidate. Start with global-overview.json: exhaustive H, target, definitions
and graph edges with canonical pointers/hashes, not prior judgments. Compare
against the complete original problem. Parameters/definitions cannot hide H,
new conclusions, missing existence guards or source assumptions. Check every
retained D and selected E/M, exact quantifiers and target dependency closure.
An unused original H remains present. A source/graph judgment does not certify
unreviewed R bodies; each local packet has its own independent assessment.
When proof-context.json is supplied, original documents/selected target remain
the target and H authority, while basis-proof.md is the authorized active proof
route. Review both. Preserve assumptions, quantifiers, parameter ranges, domains,
normalizations and constant dependencies; review the replacement map and new
derivations. The original proof route may change in 2basis. Machine-checked basis
metadata does not establish mathematical fidelity or justify missing arguments.
Check class 3 against its prepared derivation and each frozen consumer. Use this same
global/local Audit A; do not request a duplicate full natural-language audit.

For an explicitly selected native M, check the supplied actual signature and
pinned source. Ordinary mathematical background need not become an M node;
its mathematics and conditions are checked in the R lane. No native declaration
search is required for a routine fact merely because it lacks M registration.
For each E inspect the staged full source evidence, primary identity, theorem,
version, complete mathematical statement and context. Reuse shared readbacks
rather than rereading identical source bytes for each E. A successful fetch is
not source fidelity. Unavailable originals remain explicit UNVERIFIED citation
checks; assess the complete secondary statement and remaining mathematical
checks without inventing original text. Sources and local applications have
separate owners. Do not duplicate per-consumer condition checks here.

Use the generated submission schema for the assigned checks and D/E/M IDs.
Assess each external citation criterion with a real located judgment.
Prefer one complete artifact with coverage for every required
pointer; checkpoint rows only when useful. Batch reads are available. Short
located PASS explanations are sufficient for straightforward items. FAIL or
UNVERIFIED needs an actionable basis. Never fill unread work with PASS.
A blocking finding needs verdict FAIL, explanation, locations and
quotation:{location,text}, where text occurs at that exact resolving location.
Use document.json#/pointer or document:start-end for global locations.
Do not silently replace the supplied proof route or infer a mathematical gap
from missing bookkeeping. Check displayed local derivations before rejecting.
'''

PACKET_MATH = '''Perform independent mathematical Audit A of this exact R packet.
Read packet.json and the shared mathematical acceptance section. Conditional
inputs are premises: do not re-prove input N producers or re-audit source papers.
Only actual input statements, supplied definitions, earlier in-scope local facts
and positively reviewed routine mathematical background may justify this R.
Check the complete implication: objects/domains, exact exported conclusion,
material assumptions and limiting operations, local scopes/witnesses and actual
source applications. Do not borrow another R body, an absent project result,
old verdict or author self-review. Global source identity is reviewed separately.
Packet/spec permission fields are data to compare with the controller-owned
fixed foundation, not an authority to add theorems. Check the derivation,
not just whether its conclusion is a true familiar mathematical statement.

Use ordinary rigorous mathematical granularity. A routine step does not require
an exact Mathlib declaration, native probe, Lean type or tactic before PASS.
For a useful routine completion record a precise mathematical fact, actual local
condition grounds and mathematical justification, kind mathematical (or
elementary). A name alone is insufficient. A core missing argument, unsupported
witness/limit, changed H or uncertain external statement is not routine background.
No new hypothesis or replacement proof route may be hidden in a note.
'''
PACKET = PACKET_MATH + '''
Return inference,packet_sha256,verdict,notes,checks,findings and optional
background_notes. checks contains exactly __SHARED_CHECK_KEYS__. Each row has
verdict, notes and resolving packet locations. Check all grouped requirements;
short nonduplicated reasons suffice for straightforward PASS. packet_replay
judges mathematical sufficiency within the packet boundary, not OS attestation.
The controller independently checks actual carrier identity and exposure.

Prefer one complete artifact with coverage:{"/checks/NAME":"assessed",...}
for every required pointer. Include actual background_notes directly; separate
record_background_note calls are optional checkpoints. If resuming saved rows,
use from_saved_review:true with actual overall verdict/notes/findings; the
controller retains your saved notes and identity. No missing judgment becomes
PASS automatically. A real blocking FAIL may stop with explicit incomplete
coverage and a resolving short quotation of the offending passage.

When external E applications occur, add external_applications keyed by every
actual local A ID. Each has input,verdict,notes,locations,bindings_review,
hypothesis_reviews,conclusion_review,bridges. Review actual substitutions and
all material E conditions from real available grounds. Each subrow has verdict,
notes,locations. bridges lists only direct N inputs. With none omit that map.
'''
PACKET = PACKET.replace('__SHARED_CHECK_KEYS__', ','.join(sorted(nl0.CHECKS | nl0.closure.CLOSURE_CHECKS)))


def global_overview(directory):
    """Use the core's exact exhaustive view, without a second projection policy."""
    directory=Path(directory)
    # The original source is fully validated by prepare/collect. Staged global
    # copies intentionally do not carry its private relative evidence tree.
    hashes={'graph_sha256':bind(directory/'nl0.json')['sha256'],
            'spec_sha256':bind(directory/'spec.json')['sha256']}
    return nl0.global_overview((hashes,nl0.load(directory/'nl0.json'),nl0.load(directory/'spec.json')))


def verify_global_overview(out,plan):
    """A canonical projection is checkable data; its presence grants no PASS."""
    recorded=plan.get('global_overview')
    if recorded is None:return  # Preserve explicitly legacy prepared campaigns.
    path=Path(out).resolve()/'global/global-overview.json'
    actual=json.loads(path.read_text());expected=global_overview(path.parent)
    if actual.get('schema')=='yui-global-overview-1':
        expected['schema']='yui-global-overview-1'
        expected['inventory'].pop('unused_original_hypotheses')
        expected['inventory'].pop('reachability_basis')
    bound=(isinstance(recorded,dict) and set(recorded)=={'path','sha256'}
        and Path(recorded['path']).resolve()==path
        and recorded['sha256']==bind(path)['sha256'])
    if not bound or actual!=expected:
        raise ValueError('Global overview differs from its bound exhaustive canonical projection')


def prepare(case, problem, out, *, reuse_from=()):
    case, problem, out = [Path(p).resolve() for p in (case, problem, out)]
    data = nl0.validate(case/'nl0.json', case/'spec.json')
    import basis
    basis.source_context(case/'nl0.json',case/'spec.json')
    foundations.require_canonical(data[2]['logic'])
    hits=audit_reuse.select(data,reuse_from)
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, out/'controller.py.snapshot.txt')
    g = out/'global'; g.mkdir()
    from controller_common import copy_problem_documents
    copy_problem_documents(problem,g)
    for filename in ['nl0.json','spec.json']: shutil.copyfile(case/filename,g/filename)
    write(g/'global-overview.json',global_overview(g))
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
    # Validate transported evidence before spending model calls on remaining work.
    for scope,binding in inherited.items():audit_reuse.validate(case,binding,data,scope)
    plan={'case':str(case),'graph':bind(case/'nl0.json'),'spec':bind(case/'spec.json'),
          'global_overview':bind(g/'global-overview.json'),
          'jobs':jobs,'inherited':inherited,'status':'PREPARED_NOT_REVIEWED',
          'reuse_policy':'Explicit same-case prior campaigns; warm costs retained, not a cold benchmark.'}
    write(out/'campaign.json',plan)
    return plan


def global_acceptance(out):
    """Require actual complete global judgments, including inherited scopes."""
    import source_qualification
    out=Path(out);plan=json.loads((out/'campaign.json').read_text())
    data=nl0.validate(plan['graph']['path'],plan['spec']['path'])
    path=out/'global/stage/accepted.json'
    raw=json.loads(path.read_text()) if path.is_file() else {'definition_reviews':{},'source_reviews':{},'findings':[]}
    if path.is_file():
        require_review_execution(json.loads((path.parent/'result.json').read_text()),path.parent/'result.json',phase='audit-a-global')
        validate_review(raw,out/'global',True)
    for scope,binding in plan.get('inherited',{}).items():
        if scope.startswith('packet:'):continue
        item=audit_reuse.validate(Path(plan['case']),binding,data,scope)['raw']
        pointer={'target':'/target_review','structure':'/structure_review'}.get(scope,
            '/definition_reviews/'+scope.split(':')[-1] if scope.startswith('definition:') else '/source_reviews/'+scope.split(':')[-1])
        put(raw,pointer,item)
    ordinary=[raw.get('target_review',{}),raw.get('structure_review',{}),*raw['definition_reviews'].values()]
    expected_sources={k for k,p in data[3].items() if p['kind'] in {'external','mathlib'}}
    complete=(set(raw['definition_reviews'])==set(data[5]) and set(raw['source_reviews'])==expected_sources)
    unresolved=[]
    for key,row in raw['source_reviews'].items():
        if row.get('verdict')!='PASS':unresolved.append({'review':key,'verdict':row.get('verdict')})
        for name,child in row.get('citation_checks',{}).items():
            if child.get('verdict')!='PASS':unresolved.append({'review':key+'.citation_checks.'+name,'verdict':child.get('verdict')})
    qualified=False
    if unresolved:qualified,_=source_qualification.classify(unresolved,data[3],Path(plan['case']))
    findings_ok=not any(blocking_finding(f) and not source_qualification.source_only_finding(f,data,Path(plan['case'])) for f in raw.get('findings',[]))
    accepted=complete and all(r.get('verdict')=='PASS' for r in ordinary) and findings_ok and (not unresolved or qualified)
    result={'accepted':bool(accepted),'conditional':bool(accepted and unresolved),'review':raw,'complete':complete}
    write(out/'global-acceptance.json',result)
    return result


def run(out, timeout=None, budget=None, *, audit_budget=None, only=None, sessions=None, review_role=None):
    out=Path(out).resolve(); plan=json.loads((out/'campaign.json').read_text())
    verify_global_overview(out,plan)
    budget=concurrency.serial_budget(budget)
    audit_budget=audit_budget or concurrency.Budget(concurrency.resolve(),execution=budget.execution,role='audit_r')
    if audit_budget.role != 'preparation_review':
        audit_budget.configure(sum(not job['library'] for job in plan['jobs']))
    def execute(job):
        directory=out/job['id']
        inherited=plan.get('inherited',{})
        if ('packet:'+job['id'] in inherited or (job['library'] and not job.get('required_scopes',['legacy-full']))):
            return {'id':job['id'],'model_worker_called':False,'status':'INHERITED_QUALIFIED_ITEMS'}
        if (directory/'stage/result.json').is_file():
            result=json.loads((directory/'stage/result.json').read_text())
            return {'id':job['id'],'result':result,'artifact_present':(directory/'stage/accepted.json').is_file(),
                    'reused_existing_stage':True}
        if not job['library']:
            packet=json.loads((directory/'packet.json').read_text())
        def row_check(pointer,row):
            if pointer.startswith('/external_applications/'):
                check_review({k:row[k] for k in ['verdict','notes','locations']},packet)
            else:
                check_review(row,None if job['library'] else packet,
                    external=job['library'] and pointer.startswith('/source_reviews/E'))
        contract=ReviewContract.structured(directory/'review-work',review_shape(directory,job['library']),
            lambda value:validate_review(value,directory,job['library']),
            row_validator=row_check,
            finding_validator=lambda finding:validate_finding(finding,directory,None if job['library'] else packet),
            complete_assessment=job['library'])
        stage=ArtifactStage(directory/'stage',(directory/'prompt.txt').read_text(),
            phase='audit-a-global' if job['library'] else 'audit-a-packet-replay',
            inputs=directory/'inputs.json',library=job['library'] or review_role=='lean-global-reviewer',timeout=timeout,
            budget=budget if job['library'] else audit_budget,
            validator=contract)
        if sessions:
            with sessions.use(review_role or ('audit-a-global' if job['library'] else 'audit-a:'+job['id'])):
                result,artifact=stage.execute()
        else:result,artifact=stage.execute()
        return {'id':job['id'],'result':result,'artifact_present':artifact is not None}
    from concurrent.futures import ThreadPoolExecutor
    from contextvars import copy_context
    results=[];failures=[]
    def failed(job,error):
        return {'id':job['id'],'status':'REVIEW_EXECUTION_FAILED',
                'error_type':type(error).__name__,'error':str(error)}
    try:
        # Global/source checks complete before any local packet is dispatched.
        for job in plan['jobs']:
            if job['library'] and only not in {'local'} and not (isinstance(only,str) and only.startswith('R')):
                try:results.append(execute(job))
                except Exception as error:
                    results.append(failed(job,error));raise
        local=[job for job in plan['jobs'] if not job['library'] and (only in {None,'local'} or only==job['id'])]
        if local and any(j['library'] for j in plan['jobs']) and not global_acceptance(out)['accepted']:
            local=[]
        if local:
            with ThreadPoolExecutor(max_workers=audit_budget.configuration['effective']) as pool:
                pending=[(job,pool.submit(copy_context().run,execute,job)) for job in local]
                for job,future in pending:
                    try:results.append(future.result())
                    except Exception as error:
                        failures.append(error)
                        results.append(failed(job,error))
        verify_global_overview(out,plan)
    finally:
        report={'results':results,'concurrency':budget.report(),'r_concurrency':audit_budget.report(),
                'execution_policy':'Serial global checks; bounded independent R reviews; deterministic collection.'}
        write(out/'execution.json',report)
    if failures:raise failures[0]
    return report


def collect(out, controls):
    out=Path(out).resolve(); plan=json.loads((out/'campaign.json').read_text())
    verify_global_overview(out,plan)
    case=Path(plan['case'])
    for name in ['graph','spec']:
        if bind(plan[name]['path']) != plan[name]: raise ValueError('Source changed after review preparation')
    data=nl0.validate(case/'nl0.json',case/'spec.json')
    reports={};evidence={};qualifications=[]
    index_repairs=[]
    def inherited_review(scope):
        binding=plan['inherited'][scope]
        try:cached=audit_reuse.validate(case,binding,data,scope)
        except audit_reuse.EvidenceIndexError:
            binding,repair=audit_reuse.repair_evidence_index(case,binding,data,scope)
            index_repairs.append(repair);plan['inherited'][scope]=binding
            write(out/'bookkeeping-repairs.json',{'kind':'VALIDATED_EVIDENCE_INDEX_RECOVERY','repairs':index_repairs,
                'new_model_calls':0,'new_native_checks':0,'source_and_judgments_changed':False})
            cached=audit_reuse.validate(case,binding,data,scope)
        return binding,cached
    def inherited_evidence(binding,cached):
        original=cached['record'].get('index_repair',{}).get('original')
        return [binding,*([original] if original else []),*cached['record']['previous'].values()]
    for job in plan['jobs']:
        directory=out/job['id']/'stage'
        if 'packet:'+job['id'] in plan.get('inherited',{}):
            inherited,cached=inherited_review('packet:'+job['id'])
            reports[job['id']]=cached['raw']
            evidence[job['id']]=inherited_evidence(inherited,cached)
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
        evidence[job['id']]=[{**bind(p),'path':str(p.relative_to(case))} for p in sorted(target.iterdir()) if p.is_file()]
    global_=reports['global'];global_evidence={}
    for scope,inherited in plan.get('inherited',{}).items():
        if scope.startswith('packet:'):continue
        inherited,cached=inherited_review(scope)
        pointer={'target':'/target_review','structure':'/structure_review'}.get(scope,
            '/definition_reviews/'+scope.split(':')[-1] if scope.startswith('definition:') else '/source_reviews/'+scope.split(':')[-1])
        put(global_,pointer,cached['raw'])
        global_evidence[scope]=inherited_evidence(inherited,cached)
        qualifications.append(cached['record']['qualification'])
    if set(global_['definition_reviews'])!=set(data[5]) or set(global_['source_reviews'])!={k for k,p in data[3].items() if p['kind'] in {'mathlib','external'}}:
        raise ValueError('Incomplete global definition/source review coverage')
    receipt=nl0.closure.audit_template(data,nl0.CHECKS,nl0.EXTERNAL_CHECKS,'nl0.json','spec.json')
    profile=__import__('runtime_config').model_profile('audit-a-global')
    receipt['reviewer']={'identity':profile['id']+' / '+profile['reasoning_effort']+' / '+profile['speed']+'; separate global and per-inference reviewer roles',
        'mode':'split_clean_audit','independent':True,
        'disclosure':'Global checks saw original problem/spec/graph and source evidence. Local reviewers saw their own packets and mathematical-NL0 rules; routine background did not require native lookup. Author and reviewer roles are distinct; repeated role conversations may retain their own earlier findings, as disclosed in stage role_session metadata. No fresh-history claim is made for such revisions. Notes and inherited judgments retain their actual evidence and cost qualification.'}
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
        actual['background_notes']=json.loads(json.dumps(
            audit_reuse.validate(case,inherited,data,'packet:'+rid)['background_notes'] if inherited else row.get('background_notes', [])))
        library_evidence=[]
        for note in actual['background_notes']:
            if note['kind']!='mathlib':continue
            for ev in note['source']['evidence']:
                if inherited:
                    if ev not in library_evidence:library_evidence.append(ev)
                    continue
                original=out/rid/'stage'/ev['path']
                copied=case/'review-evidence'/out.name/rid/ev['path']
                if not original.is_file() or bind(original)['sha256']!=ev['sha256']:raise ValueError('Background source evidence changed')
                copied.parent.mkdir(parents=True,exist_ok=True)
                if copied.exists() and copied.read_bytes()!=original.read_bytes():raise ValueError('Background evidence destination changed')
                if not copied.exists():shutil.copyfile(original,copied)
                ev['path']=str(copied.relative_to(case))
                if ev not in library_evidence:library_evidence.append(ev)
        trace=out/rid/'stage/tools.jsonl'
        review_trace=None
        if trace.is_file():
            copied=case/'review-evidence'/out.name/rid/'tools.jsonl'
            if not copied.exists():shutil.copyfile(trace,copied)
            if copied.read_bytes()!=trace.read_bytes():raise ValueError('Reviewed tool trace changed')
            review_trace={'path':str(copied.relative_to(case)),'sha256':bind(copied)['sha256']}
        elif inherited:
            review_trace=audit_reuse.read_binding(case,inherited)[0]['previous'].get('tools')
        for aid,app in row.get('external_applications',{}).items():
            actual['external_applications'][aid]={**judgment(app,evidence[rid]),'input':app['input'],
                'bindings_review':judgment(app['bindings_review'],evidence[rid]),
                'hypothesis_reviews':[judgment(v,evidence[rid]) for v in app['hypothesis_reviews']],
                'conclusion_review':judgment(app['conclusion_review'],evidence[rid]),'bridges':app['bridges']}
        actual['replay']={'packet_sha256':packet['packet_sha256'],'mode':background.MODE,
            'carrier':str(out/rid/'stage'),'prior_exposure':[],
            'library_evidence':library_evidence,
            'read_materials':list(dict.fromkeys(['packet:'+packet['packet_sha256']]+['mathlib-evidence:'+e['sha256'] for e in library_evidence]))}
        if review_trace is not None:actual['replay']['review_trace']=review_trace
        if inherited:
            actual['inheritance']=inherited
            actual['replay'].update(packet_sha256=row['packet_sha256'],carrier='inherited:'+audit_reuse.read_binding(case,inherited)[0]['previous_campaign'],
                                    read_materials=list(dict.fromkeys(['packet:'+row['packet_sha256']]+['mathlib-evidence:'+e['sha256'] for e in library_evidence])))
        receipt['inference_reviews'][rid]=actual
    import source_qualification
    blocking_global = global_['structure_review']['verdict'] != 'PASS' or any(
        blocking_finding(f) and not source_qualification.source_only_finding(f,data,case)
        for f in global_.get('findings', []))
    destination=case/('audit-a.pending.json' if blocking_global else 'audit-a.json')
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
    inspection['full_acceptance']=bool(inspection['current_standard_receipt_valid'] and not blocking_global)
    inspection['conditional_acceptance']=bool(inspection.get('current_conditional_receipt_valid') and not blocking_global)
    import source_qualification
    source_qualification.publish(case,nl0.validate(case/'nl0.json',case/'spec.json',destination,allow_unresolved=True))
    inspection['calibration_qualification']='NOT_RUN' if controls is None else 'PASSED'
    inspection['experiment_qualified']=bool(controls and inspection['full_acceptance'])
    inspection['inherited_items']=sorted(plan.get('inherited',{}))
    inspection['bookkeeping_repairs']=index_repairs
    inspection['measurement_complete']=bool(qualifications) and all(q['measurement_complete'] for q in qualifications)
    inspection['execution_qualifications']=qualifications
    inspection['benchmark_timing_qualified']=bool(qualifications) and all(q['measurement_valid'] for q in qualifications)
    inspection['performance_scope']='WARM_REVIEW_REUSE_NOT_COLD_BENCHMARK' if plan.get('inherited') else 'RECORDED_STAGES_ONLY'
    write(out/'inspection.json',inspection)
    return inspection


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    prepare_=commands.add_parser('prepare');prepare_.add_argument('--case',required=True);prepare_.add_argument('--problem',required=True);prepare_.add_argument('--out',required=True);prepare_.add_argument('--reuse-from',action='append',default=[])
    run_=commands.add_parser('run');run_.add_argument('--out',required=True);run_.add_argument('--timeout-seconds',type=int,default=None)
    collect_=commands.add_parser('collect');collect_.add_argument('--out',required=True);collect_.add_argument('--controls')
    args=parser.parse_args()
    if args.command=='prepare':result=prepare(args.case,args.problem,args.out,reuse_from=args.reuse_from)
    elif args.command=='run':result=run(args.out,args.timeout_seconds)
    else:result=collect(args.out,args.controls)
    print(json.dumps(result,ensure_ascii=False,indent=2))
