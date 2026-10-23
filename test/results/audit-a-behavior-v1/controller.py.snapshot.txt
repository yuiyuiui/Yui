#!/usr/bin/env python3
"""Run prepared neutral Audit A controls in separate fresh model contexts."""
import argparse
from concurrent.futures import ThreadPoolExecutor
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
from audit_a_campaign import write,bind,manifest


PROMPT='''Review the supplied packet.json under the declared Yui Audit A and
self-containment rules. Read the whole packet and relevant rules. This packet
is the only mathematical task material; no source/ancestor proof, old review,
labels or expected answer is supplied. Judge whether this exact argument is a
complete conditional proof from its stated inputs. Do not repair missing
content, undeclared objects, opaque formulas, unlisted theorems or unsupported
witnesses from memory or by finding another proof. Return exactly JSON
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


def run(directory,timeout,budget=None):
    directory=Path(directory).resolve()
    key=json.loads((directory/'owner/expected.json').read_text())
    shutil.copyfile(__file__,directory/'controller.py.snapshot.txt')
    budget=budget or concurrency.Budget(concurrency.resolve())
    def execute(pair):
        name,expected=pair
        source=directory/'reviewer'/name
        packet=json.loads(source.read_text())
        target=directory/'cases'/Path(name).stem
        target.mkdir(parents=True,exist_ok=False)
        shutil.copyfile(source,target/'packet.json')
        manifest(target);(target/'prompt.txt').write_text(PROMPT)
        stage=ArtifactStage(target/'stage',PROMPT,phase='audit-a-behavior',
            inputs=target/'inputs.json',library=False,timeout=timeout,budget=budget,
            validator=lambda value:validate_review(packet,value))
        result,actual=stage.execute()
        health=bool(result.get('measurement_valid') and result.get('exposure',{}).get('status')=='TRANSMITTED-EXPOSURE-CHECK-PASSED')
        matches=bool(actual and actual.get('verdict')==expected['expected_verdict'])
        located=expected['location'] is None or bool(actual and any(
            f['location']==expected['location'] or expected['location'].startswith(f['location']+'/')
            or f['location'].startswith(expected['location']+'/') for f in actual.get('findings',[])))
        return {'packet':name,'expected':expected,'actual':actual,'healthy':health,
                'detected_as_expected':bool(matches and located),
                'evidence':bind(target/'stage/accepted.json') if (target/'stage/accepted.json').exists() else None,
                'stage_result':bind(target/'stage/result.json')}
    with ThreadPoolExecutor(max_workers=budget.configuration['effective']) as pool:
        results=list(pool.map(execute,sorted(key['expected'].items())))
    report={'status':'BEHAVIORAL-CONTROLS-PASSED' if all(x['healthy'] and x['detected_as_expected'] for x in results) else 'BEHAVIORAL-CONTROLS-NOT-PASSED',
        'scope':'Five finite procedure controls; not a guarantee of all future mathematical review decisions.',
        'results':results,'concurrency':budget.report()}
    write(directory/'behavioral-summary.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared',required=True);parser.add_argument('--timeout-seconds',type=int,default=600)
    args=parser.parse_args();print(json.dumps(run(args.prepared,args.timeout_seconds),indent=2))
