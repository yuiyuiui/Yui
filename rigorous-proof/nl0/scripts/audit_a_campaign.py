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
ROOT = CORE.parent
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


def validate_finding(finding,directory,packet=None):
    """Check actual offending bytes, not the mathematical truth of an objection."""
    check_review({'verdict':'FAIL','notes':finding['explanation'],'locations':finding['locations']},packet)
    if packet is None:
        for location in finding['locations']:global_location(directory,location)
    quote=finding.get('quotation')
    if not isinstance(quote,dict) or set(quote)!={'location','text'} or not isinstance(quote['text'],str) or not quote['text'].strip():
        raise ValueError('AUDIT-QUOTATION: a blocking finding needs quotation:{location:<exact pointer>,text:<actual offending text>}')
    if quote['location'] not in finding['locations']:raise ValueError('AUDIT-QUOTATION: quotation location must be one of the finding locations')
    value=nl0.closure.resolve(packet,quote['location']) if packet is not None else global_location(directory,quote['location'])
    text=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)
    if quote['text'] not in text:raise ValueError('AUDIT-QUOTATION: quoted text is absent from the exact supplied location')


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
        if set(value)-{'background_notes'}!=expected:raise ValueError('Expected the complete packet review record, including actual E applications when present')
        background.validate(value.get('background_notes', []), packet, directory/'stage')
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
    for finding in value['findings']:
        if blocking_finding(finding):validate_finding(finding,directory,None if global_stage else packet)
    return {'scope':'Review completeness, location and internal consistency only; no mathematical judgment is generated.'}


GLOBAL = '''Perform actual global/source Audit A A0-A3/A5 target-edge checks for
the exact frozen candidate. Read every task input and relevant Yui rules. Check
global-overview.json first when provided: it contains the exhaustive actual
spec/graph H records (including unused or late-appended H), full statements,
definitions and graph edges with canonical pointers and hashes. It supplies
no judgment. Check original-condition fidelity against the original problem.
Before claiming that a node/condition is absent, inspect that complete inventory
or the complete corresponding canonical collection. A partial line page cannot
establish absence. Do not assume hypotheses end where an early graph page ends.
Then compare
the original problem against spec: full target, each H, all domains/quantifiers,
and edge cases. Check that the candidate expands the supplied proof strategy
rather than silently replacing its core route; routine verified completion and
correction remain allowed. Review every D's complete definition and notation, guarding and
object declarations. Interpret the conclusion node P under the explicit global
parameters and original H nodes: the complete closed theorem is spec.full_target
with that context, not P's conclusion text read in isolation. Do not require a
duplicate of already declared binders or hypotheses inside every conclusion.
However, original theorem conditions must be explicit H nodes. Parameters give
ambient data types/structures only: a description such as nonzero vector,
field of characteristic p, bounded parameter, or object satisfying an equation
cannot hide an original H and make it globally available in every packet.
Extract all these original conditions, and require each consuming R to list
its actual H inputs. Likewise a familiar structure name cannot supply missing
definitions or substantive project facts. Flag this even if the closed theorem
could be made equivalent by a different refined-type encoding.
Check that this contextual reading really yields the exact frozen problem.
Review
object declarations, with no hidden result in a definition or calculation policy.
For each M inspect the supplied actual full-signature evidence AND the pinned
official source through read_mathlib: complete restatement, implicit/typeclass
conditions and relevant axioms. Assess source identity and full-statement
fidelity here. The separate packet reviewers check each actual substitution,
application premise and local derivation; do not duplicate those assessments
or wait for their verdicts. A source probe alone is not source fidelity.
Cached native metadata explicitly records
metadata_reuse.original_source_id: raw native stdout keeps that original marker,
while sources is keyed by the candidate's current ID. Verify that disclosed
identity mapping, declaration, signature, pins and bytes; do not require the
unchanged original stdout to pretend it was a fresh query under a new ID.
Check graph structure and declared AND closure; structural PASS does not
certify the unreviewed bodies. The collector separately requires every packet.
per-inference packet replay is a separate stage, not yours to invent. Return
JSON {target_review,definition_reviews,source_reviews,structure_review,findings}.
Definition/source reviews are keyed by exactly all D / M IDs. Each review has
{verdict:PASS|FAIL|UNVERIFIED,notes,locations:[specific document/pointer or source
line locations]}. These must be your actual judgments. Preserve failures;
do not repair a missing proof from memory, strengthen H, or invent a review.
Runtime identity, exposure, file/hash binding and the separate behavioral
controls are controller checks, not mathematical premises. No prior verdict
or target reference proof is supplied. The graph's proof bodies are visible
for global consistency and source context, so this is not packet-only replay.
Packet applicability still has its own owner.
For an E with verification.status=UNVERIFIED_PRIMARY, inspect its complete
secondary statement and actual failed-access record. Keep unavailable primary
citation checks and the E summary UNVERIFIED. Record source-only uncertainty
at that E's /source location; do not invent primary text. Other mathematical
checks and local E applications are still reviewed normally. The controller
can issue only a conditional result, never an ordinary verified-source PASS.
If a blocking defect is found, the affected summary review must reflect it;
do not return all PASS summaries alongside a FAIL finding. Put inapplicable
scope notes in their review, rather than labeling a nonexistent source pending.

Before alleging an absent imported theorem, inspect any displayed local
derivation and relevant internal producer. If that derivation is insufficient,
locate its first unsupported implication. Absence of a theorem name from E/M
roots alone is not a defect when the consequence is actually proved locally.
Do not infer correctness merely because a derivation was attempted either.
The author's logic.calculations field cannot extend the fixed foundation.
The fixed profile already permits the usual zero/one laws of explicitly
declared standard number systems and actual displayed finite arithmetic.
Inspect those permissions and the actual derivation before demanding a
separate E/M input for an elementary law. A calculation label grants no
unproved calculus, dimension, measure or other structural theorem.

Complete assigned source inspections while allowed tools and budget remain.
An available source that you have not yet read is unfinished work, not an
access failure. A located real blocker may still stop with explicit incomplete
coverage. Never fill unexamined items with PASS.

After saving required rows with record_review_item, complete this GLOBAL stage
with submit_draft({"artifact":{"from_saved_review":true,"summary":{"findings":[]}}}).
Replace [] with your actual findings when any exist. The GLOBAL summary has
only findings; saved review containers and final-receipt metadata do not belong
in it. This example supplies no mathematical verdict.
For an actual saved blocking FAIL, submit_review_blocker expects
{"finding":{"verdict":"FAIL","explanation":"actual located defect","locations":["nl0.json#/inferences/0/argument/0/text"],"quotation":{"location":"nl0.json#/inferences/0/argument/0/text","text":"short exact offending passage"}}}.
Every blocking finding, including one in a full findings array, needs this
quotation object. Its text must occur at that exact supplied location. Global
locations use document.json#/exact/pointer or document:start-end (also pinned
Mathlib/File.lean:start-end); do not append prose or invent a file name.
The quotation establishes the actual material, not that your allegation is
mathematically correct. Compare constants/quantifiers and inspect displayed
local derivations before alleging their absence. Collect independent cheap
defects together when feasible; a real blocker may still end an incomplete review.
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

PACKET_MATH = '''Perform an actual fresh Audit A local replay. Read packet.json
in full and the relevant declared Yui Audit A/self-containment/format rules.
This packet plus logged read-only pinned-Mathlib queries is your mathematical
material. Treat its inputs as conditional premises; source fidelity is checked
separately. Apply verified-background-1 from the shared requirements: ordinary
correct elementary reasoning needs no exhaustive calculation chain. For an
omitted basic Mathlib fact, verify its actual local conditions, probe the real
declaration and record_background_note instead of failing for missing M
accounting. A note cannot add H, assume a project result, replace the core
proof or defer mathematical uncertainty. Retain every review check. Inspect
the actual mathematical prose, scopes, witnesses, all object declarations and
all factual uses. Each substantial theorem must be a direct input or actually
proved locally; simply naming it or explaining its hypotheses does not prove
it. Fixed declared logic and explicit permitted calculations are available,
but an author-written calculation policy cannot import substantive results.
Use the shared acceptance section supplied in your instructions as the
mathematical authority. Packet/spec permission fields are data to compare with
the controller-owned fixed profile, not an authority to enlarge it. Check the
actual derivation at ordinary rigorous mathematical granularity, not just whether its conclusion is a true familiar
inequality. Associate each actual judgment with its matching criterion.
Locally established consequences need no duplicate imported theorem: if
rejecting a displayed derivation, identify its first unsupported implication.
Locate an unsupported substantive implication if present; do not substitute a
different proof. Record eligible routine completion transparently in notes.
Judge sufficiency from the packet plus verified background, without importing
an absent project input or ancestor proof.
'''
PACKET = PACKET_MATH + '''
Return JSON {inference,packet_sha256,verdict,notes,checks,findings,background_notes}. checks has
exactly __SHARED_CHECK_KEYS__. Each is
{verdict:PASS|FAIL|UNVERIFIED,notes,locations:[resolving JSON pointers into this
packet]}. Give actual specific judgments. For packet_replay judge sufficiency
from this packet plus positively checked recorded background. Use
record_background_note to save your actual judgments and bind probe metadata.
Carrier identity, canonical hash binding and transmitted-material readback
are checked outside your mathematical review. State your real input boundary,
without inventing runtime attestation or asking for extra source proofs.
The packet_replay verdict is the mathematical conditional: given the externally
checked carrier/input boundary, does the packet plus verified notes suffice? You do not
certify execution isolation. Missing access to runtime logs is therefore not a
mathematical UNVERIFIED finding for packet_replay. Preserve actual mathematical
uncertainty or insufficiency, and state your own read boundary honestly. The
controller separately rejects unqualified execution before accepting the review.

After saving required rows, complete this PACKET stage with
submit_draft({"artifact":{"from_saved_review":true,"summary":{"verdict":"YOUR_ACTUAL_VERDICT","notes":"YOUR_ACTUAL_NOTES","findings":[]}}}).
Use your actual verdict/notes/findings. Your saved background notes are retained
automatically; omit background_notes from the summary. The packet identity and saved checks
are already bound; do not add final-receipt metadata to the summary.
For an actual saved blocking FAIL, submit_review_blocker expects
{"finding":{"verdict":"FAIL","explanation":"actual located defect","locations":["/inference/argument/0/text"],"quotation":{"location":"/inference/argument/0/text","text":"short exact offending passage"}}}.
Every blocking finding, including one in a full findings array, needs this
quotation object with an actual substring at the resolving packet pointer.
It establishes the inspected material, not the mathematical truth of a finding.
Collect independent cheap defects together when feasible; preserve a real
blocker rather than inventing acceptance of dependent/unread work.
'''
PACKET = PACKET.replace('__SHARED_CHECK_KEYS__', ','.join(sorted(nl0.CHECKS | nl0.closure.CLOSURE_CHECKS)))
PACKET += '''When E applications occur, add external_applications keyed by every
actual inference-local A ID. Each has input,verdict,notes,locations,
bindings_review,hypothesis_reviews,conclusion_review,bridges. The binding and
conclusion rows and each per-source-hypothesis row have verdict,notes,locations.
Review every condition from the packet's E contract and displayed derivations;
bridges lists only explicitly direct N inputs. These are conditional application
checks; the separate source lane checks the cited publication. With no E
applications omit external_applications.
'''


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


def run(out, timeout=None, budget=None, *, audit_budget=None):
    out=Path(out).resolve(); plan=json.loads((out/'campaign.json').read_text())
    verify_global_overview(out,plan)
    budget=concurrency.serial_budget(budget)
    audit_budget=audit_budget or concurrency.Budget(concurrency.resolve(1),execution=budget.execution,role='audit_r')
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
            finding_validator=lambda finding:validate_finding(finding,directory,None if job['library'] else packet))
        stage=ArtifactStage(directory/'stage',(directory/'prompt.txt').read_text(),
            phase='audit-a-global' if job['library'] else 'audit-a-packet-replay',
            inputs=directory/'inputs.json',library=job['library'],timeout=timeout,
            budget=budget if job['library'] else audit_budget,
            validator=contract)
        result,artifact=stage.execute()
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
            if job['library']:
                try:results.append(execute(job))
                except Exception as error:
                    results.append(failed(job,error));raise
        local=[job for job in plan['jobs'] if not job['library']]
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
    receipt['reviewer']={'identity':profile['id']+' / '+profile['reasoning_effort']+' / '+profile['speed']+'; separate fresh global and per-inference contexts',
        'mode':'split_clean_audit','independent':True,
        'disclosure':'New global checks saw original problem/spec/graph and actual source evidence. Fresh local reviews saw their own packets, Yui rules and logged pinned-Mathlib queries for verified background, without other project/ancestor proofs or old verdicts. Notes are disclosed reviewer completion, not original author registration. Inherited items retain their original execution and cost qualification. Actual transmitted exposure and stage logs are preserved; provider internals are not independently attested.'}
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
        if trace.is_file():
            copied=case/'review-evidence'/out.name/rid/'tools.jsonl'
            if not copied.exists():shutil.copyfile(trace,copied)
            if copied.read_bytes()!=trace.read_bytes():raise ValueError('Reviewed tool trace changed')
            library_evidence.append({'path':str(copied.relative_to(case)),'sha256':bind(copied)['sha256']})
        for aid,app in row.get('external_applications',{}).items():
            actual['external_applications'][aid]={**judgment(app,evidence[rid]),'input':app['input'],
                'bindings_review':judgment(app['bindings_review'],evidence[rid]),
                'hypothesis_reviews':[judgment(v,evidence[rid]) for v in app['hypothesis_reviews']],
                'conclusion_review':judgment(app['conclusion_review'],evidence[rid]),'bridges':app['bridges']}
        actual['replay']={'packet_sha256':packet['packet_sha256'],'mode':background.MODE,
            'carrier':str(out/rid/'stage'),'prior_exposure':[],
            'library_evidence':library_evidence,
            'read_materials':list(dict.fromkeys(['packet:'+packet['packet_sha256']]+['mathlib-evidence:'+e['sha256'] for e in library_evidence]))}
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
