#!/usr/bin/env python3
"""Run prepared neutral Audit A controls in separate fresh model contexts."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'rigorous-proof/scripts'))
sys.path.insert(0,str(ROOT/'rigorous-proof/translation/scripts'))
import nl0
import concurrency
from clean_stage import ArtifactStage
from audit_a_campaign import write,bind,manifest,PACKET_MATH
import audit_a_campaign as actual_audit
from execution_health import record_qualification


PROMPT=PACKET_MATH+'''\nRead the whole packet and relevant rules. No old review,
labels or expected answer is supplied. Do not repair missing content,
undeclared objects, opaque formulas, unlisted theorems or unsupported witnesses
from memory or by finding another proof. For this stage's output format return exactly JSON
{verdict:PASS|FAIL|UNVERIFIED,findings:[{location,check,explanation}]}, with
resolving JSON pointers inside the packet and specific reasons. A valid proof
may have an empty findings list. Runtime identity and hashes are controller
checks, not extra mathematics. Submit only your actual review.
'''


def validate_review(packet,value):
    if set(value)!={'verdict','findings'} or value['verdict'] not in nl0.VERDICTS or not isinstance(value['findings'],list):
        raise ValueError('Expected actual verdict and findings list')
    for item in value['findings']:
        if set(item)!={'location','check','explanation'} or not item['check'].strip() or not item['explanation'].strip():
            raise ValueError('Each finding needs a location, check and actual explanation')
        nl0.closure.resolve(packet,item['location'])
    return {'scope':'Review shape and resolving locations only; no mathematical verdict is generated.'}


def matches_expected(expected, actual):
    """Compare recorded verdict/location only; never supply a mathematical judgment."""
    if not actual or actual.get('verdict')!=expected['expected_verdict']:return False
    if expected.get('kind')=='global' and actual.get('target_verdict')!=expected.get('expected_target_verdict'):return False
    if expected['location'] is None:return True
    allowed=expected.get('accepted_locations',[expected['location']])
    return any(finding['location']==pointer or finding['location'].startswith(pointer+'/')
               for finding in actual.get('findings',[]) for pointer in allowed)


def run_global_control(target,bundle,timeout,budget):
    """Use the actual global prompt/contract/overview; expected labels stay outside."""
    source=target/'source';problem=target/'problem'
    source.mkdir();problem.mkdir();(source/'inputs').mkdir()
    text=bundle['problem'];(problem/'problem.md').write_text(text)
    (source/'inputs/problem.md').write_text(text)
    spec=json.loads(json.dumps(bundle['spec']));graph=json.loads(json.dumps(bundle['graph']))
    spec['inputs']=[{'path':'inputs/problem.md',
        'sha256':bind(source/'inputs/problem.md')['sha256']}]
    write(source/'spec.json',spec);graph['spec_sha256']=bind(source/'spec.json')['sha256']
    write(source/'nl0.json',graph)
    nl0.validate(source/'nl0.json',source/'spec.json')
    campaign=target/'actual-global-review'
    plan=actual_audit.prepare(source,problem,campaign)
    plan['jobs']=[job for job in plan['jobs'] if job['id']=='global']
    plan['calibration_scope']='Global review only; not a whole-proof audit receipt.'
    write(campaign/'campaign.json',plan)
    actual_audit.run(campaign,timeout,budget=budget)
    stage=campaign/'global/stage';result=json.loads((stage/'result.json').read_text())
    raw=json.loads((stage/'accepted.json').read_text()) if (stage/'accepted.json').exists() else None
    return result,global_observation(raw),stage


def global_observation(raw):
    """Aggregate actual saved judgments only; an incomplete review cannot PASS."""
    if not raw:return None
    if raw.get('status')=='REVIEW_BLOCKED_INCOMPLETE':
        row=raw.get('coverage',{}).get('items',{}).get('/target_review',{})
        actual=row.get('judgment') or {}
        verdict=('FAIL' if row.get('coverage')=='assessed' and actual.get('verdict')=='FAIL'
            and raw.get('findings') else 'UNVERIFIED')
    else:
        rows=[raw.get('target_review',{}),raw.get('structure_review',{}),
              *raw.get('definition_reviews',{}).values(),*raw.get('source_reviews',{}).values()]
        verdict=('FAIL' if any(r.get('verdict')=='FAIL' for r in rows) else
                 'PASS' if rows and all(r.get('verdict')=='PASS' for r in rows) else 'UNVERIFIED')
        actual=raw.get('target_review',{})
    return {'verdict':verdict,'findings':raw.get('findings',[]),
        'target_verdict':actual.get('verdict'),
        'actual_global_record':raw,'scope':'Summary of actual saved global judgments; not whole-proof certification.'}


def run(directory,timeout,budget=None):
    directory=Path(directory).resolve()
    key=json.loads((directory/'owner/expected.json').read_text())
    shutil.copyfile(__file__,directory/'controller.py.snapshot.txt')
    budget=concurrency.serial_budget(budget)
    def execute(pair):
        name,expected=pair
        source=directory/'reviewer'/name
        packet=json.loads(source.read_text())
        target=directory/'cases'/Path(name).stem
        target.mkdir(parents=True,exist_ok=False)
        if expected.get('kind')=='global':
            result,actual,stage_dir=run_global_control(target,packet,timeout,budget)
        else:
            shutil.copyfile(source,target/'packet.json')
            manifest(target);(target/'prompt.txt').write_text(PROMPT)
            stage=ArtifactStage(target/'stage',PROMPT,phase='audit-a-behavior',
                inputs=target/'inputs.json',library=False,timeout=timeout,budget=budget,
                validator=lambda value:validate_review(packet,value))
            result,actual=stage.execute();stage_dir=target/'stage'
        health=bool(result.get('measurement_valid') and result.get('exposure',{}).get('status')=='TRANSMITTED-EXPOSURE-CHECK-PASSED')
        qualified=record_qualification(result,allow_blocked=expected.get('kind')=='global')
        return {'packet':name,'expected':expected,'actual':actual,'healthy':health,
                'record_qualification':qualified,
                'record_qualified':qualified['submitted_record_qualified'],
                'detected_as_expected':matches_expected(expected,actual),
                'evidence':bind(stage_dir/'accepted.json') if (stage_dir/'accepted.json').exists() else None,
                'stage_result':bind(stage_dir/'result.json')}
    results=[execute(pair) for pair in sorted(key['expected'].items())]
    report={'status':'BEHAVIORAL-CONTROLS-PASSED' if all(x['record_qualified'] and x['detected_as_expected'] for x in results) else 'BEHAVIORAL-CONTROLS-NOT-PASSED',
        'benchmark_timing_qualified':all(x['healthy'] for x in results),
        'scope':str(len(results))+' finite procedure controls; not a guarantee of all future mathematical review decisions.',
        'results':results,'concurrency':budget.report(),
        'qualification_scope':'Actual mathematical classification and submitted-record provenance are distinct from execution/timing health; faults and unknown usage remain in original stage records.'}
    write(directory/'behavioral-summary.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared',required=True);parser.add_argument('--timeout-seconds',type=int,default=600)
    args=parser.parse_args();print(json.dumps(run(args.prepared,args.timeout_seconds),indent=2))
