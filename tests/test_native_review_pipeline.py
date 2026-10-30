"""Real native handoff through actual A collectors, using synthetic judgments.

This tests software wiring and receipt bindings, not mathematical correctness.
No live provider, credentials or owner-task notification is used.
"""
import harness_support
from copy import deepcopy
from contextvars import copy_context
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

import audit_a_campaign as campaign
from clean_stage import ArtifactStage
from native_fixture import NativeFixture
from review_contract import put


@unittest.skipUnless(shutil.which('codex'),'Codex executable required')
class NativeReviewPipelineTests(unittest.TestCase):
    def exercise(self, global_verdict):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);source=root/'source';source.mkdir()
            for name in ('nl0.json','spec.json','problem.txt'):
                shutil.copyfile(harness_support.FIXTURES/'closed-addition'/name,source/name)
            problem=root/'problem';problem.mkdir()
            (problem/'problem.md').write_text('Synthetic controller fixture only.')
            out=root/'campaign';plan=campaign.prepare(source,problem,out)
            original=ArtifactStage._execute;seen=[];results=[]

            def execute(stage):
                seen.append(stage.mode)
                def respond(f,handler,number,payload):
                    contract=stage.validator;artifact=deepcopy(contract.base)
                    for pointer in contract.required:
                        global_stage=stage.mode=='audit-a-global'
                        location=('spec.json#/full_target' if pointer=='/target_review' else 'nl0.json#/inferences') if global_stage else '/inference/argument'
                        verdict=global_verdict if pointer=='/target_review' else 'PASS'
                        put(artifact,pointer,{'verdict':verdict,
                            'notes':'SYNTHETIC software fixture judgment only.', 'locations':[location]})
                    artifact['findings']=[]
                    if stage.mode!='audit-a-global':
                        artifact.update(verdict='PASS',notes='SYNTHETIC software fixture judgment only.')
                    artifact['coverage']={p:'assessed' for p in contract.required}
                    f.tool(handler,number,'submit_draft',artifact)
                with NativeFixture(root/('native-'+str(len(seen))),responder=respond) as f:
                    unused=f.stage;f.stage=stage;unused.release_resources('USER_CANCELLED')
                    def target():
                        try:f.outcomes.append(original(stage))
                        except BaseException as error:f.exceptions.append(error)
                    context=copy_context()
                    f.worker=threading.Thread(target=lambda:context.run(target),daemon=True)
                    f.worker.start();f.wait()
                    result=f.outcomes[0]
                    self.assertEqual(result[0]['status'],'ACCEPTED',result[0])
                    self.assertEqual(result[0]['exposure']['status'],'NATIVE-CODEX-CONTEXT-CHECK-PASSED')
                    self.assertEqual(len(f.calls),1)
                    self.assertFalse(f.notifications);self.assertFalse(f.failures)
                    results.append(result[0]);return result

            with patch.object(ArtifactStage,'_execute',execute):
                campaign.run(out)
            self.assertEqual(seen[0],'audit-a-global')
            acceptance=campaign.global_acceptance(out)
            if global_verdict=='FAIL':
                self.assertFalse(acceptance['accepted'])
                self.assertEqual(seen,['audit-a-global'])
                self.assertFalse(any((out/job['id']/'stage').exists() for job in plan['jobs'] if not job['library']))
            else:
                self.assertTrue(acceptance['accepted'])
                self.assertEqual(len(seen),len(plan['jobs']))
                inspection=campaign.collect(out,None)
                self.assertTrue(inspection['current_standard_receipt_valid'])
                self.assertFalse(inspection['measurement_complete'])
                receipt=json.loads((source/'audit-a.json').read_text())
                self.assertEqual(set(receipt['inference_reviews']),{j['id'] for j in plan['jobs'] if not j['library']})
            self.assertTrue(all(not r['measurement_complete'] for r in results))

    def test_native_global_fail_does_not_dispatch_local_review(self):
        self.exercise('FAIL')

    def test_native_global_and_local_submissions_reach_actual_bound_A_collection(self):
        self.exercise('PASS')
