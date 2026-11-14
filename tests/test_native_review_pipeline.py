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

from audit_a_fixtures import canonical_propositional_case
import audit_a_campaign as campaign
from clean_stage import ArtifactStage
import concurrency
import execution_state
import fault_control
import native_client
from native_fixture import NativeFixture
from review_contract import put
import runtime_config
import subprocess


@unittest.skipUnless(harness_support.native_available(),'Codex executable required')
class NativeReviewPipelineTests(unittest.TestCase):
    def exercise(self, global_verdict, *, malformed_global=False, preview_notes=False):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);source=canonical_propositional_case(root/'source')
            problem=root/'problem';problem.mkdir()
            (problem/'problem.md').write_text('Synthetic controller fixture only.')
            out=root/'campaign';plan=campaign.prepare(source,problem,out)
            original=ArtifactStage._execute;seen=[];results=[];stages={};guard=threading.Lock()
            job_numbers={job['id']:i+1 for i,job in enumerate(plan['jobs'])};attempts={}
            probe_role=next(job['id'] for job in plan['jobs'] if not job['library'])
            notes=[{'id':f'BG{i:03d}','kind':'mathematical','at':'/inference/argument/0/text',
                    'fact':f'Synthetic observation {i}.','justification':'Synthetic fixture.',
                    'grounds':[{'location':'/inputs','reason':'Given packet inputs.'}]} for i in range(1,9)]
            local_count=sum(not job['library'] for job in plan['jobs'])
            barrier=threading.Barrier(local_count,timeout=10)
            before=(subprocess.Popen,fault_control.queue_notification,
                    native_client.configuration,runtime_config.auth_home)

            def respond(f,handler,number,payload):
                serialized=json.dumps(payload)
                with guard:
                    matches=[(key,stage) for key,stage in stages.items()
                             if 'YUI_TEST_REVIEW_'+key in serialized]
                self.assertEqual(len(matches),1)
                key,stage=matches[0]
                with guard:attempts[key]=attempts.get(key,0)+1
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
                    # All three real native requests must overlap, rather than
                    # merely occupying slots around serial fixture execution.
                    if attempts[key]==1:barrier.wait()
                artifact['coverage']={p:'assessed' for p in contract.required}
                if malformed_global and key=='global' and attempts[key]==1:
                    artifact.update(verdict='PASS',notes='Misplaced top-level fields in a synthetic response.')
                if preview_notes and key==probe_role:
                    if attempts[key]==1:
                        probes=deepcopy(notes)
                        probes[3]['grounds'][0]['location']='/output'
                        code=('const draft='+json.dumps(artifact)+'; const notes='+json.dumps(probes)+'; '
                              'text(await Promise.allSettled(notes.map(note => tools.check_draft('
                              '{artifact:{...draft,background_notes:[note]}}))));')
                        f.code(handler,job_numbers[key]*100+1,code)
                        return
                    self.assertIn('preview_valid',serialized)
                    self.assertIn('/background_notes/0/grounds/0/location (BG004)',serialized)
                    self.assertIsNone(stage.accepted)
                    artifact['background_notes']=notes
                    args=json.dumps({'artifact':artifact})
                    f.code(handler,job_numbers[key]*100+2,'const a='+args+'; '
                           'text(await tools.check_draft(a)); text(await tools.submit_draft(a));')
                    return
                f.code(handler,job_numbers[key]*100+attempts[key],'text(await tools.submit_draft('+json.dumps({'artifact':artifact})+'));')

            # One fixture owns the process-global test patches. Separate
            # concurrent fixtures can restore each other's stale replacements.
            with NativeFixture(root/'native',responder=respond) as f:
                f.stage.release_resources('USER_CANCELLED')
                budgets=concurrency.CaseBudgets(execution=f.recorder)
                def execute(stage):
                    key=stage.logs.parent.name
                    with guard:
                        seen.append(stage.mode);stages[key]=stage
                        if key=='global':f.stage=stage
                    stage.input_prompt+='\nSynthetic routing marker: YUI_TEST_REVIEW_'+key
                    result=original(stage)
                    self.assertEqual(result[0]['status'],'ACCEPTED',result[0])
                    self.assertEqual(result[0]['exposure']['status'],'NATIVE-CODEX-CONTEXT-CHECK-PASSED')
                    with guard:results.append(result[0])
                    return result
                def target():
                    try:
                        with execution_state.activate(f.recorder):
                            f.outcomes.append(campaign.run(out,budget=budgets.serial,audit_budget=budgets.audit))
                    except BaseException as error:f.exceptions.append(error)
                with patch.object(ArtifactStage,'_execute',execute):
                    f.worker=threading.Thread(target=copy_context().run,args=(target,),daemon=True)
                    f.worker.start();f.wait(seconds=45);f.worker.join(5)
                self.assertFalse(f.worker.is_alive())
                self.assertFalse(f.notifications);self.assertFalse(f.failures)
                report=f.outcomes[0]
                self.assertEqual(report['r_concurrency']['effective'],local_count)
                self.assertEqual(report['r_concurrency']['observed_peak_model_stages'],
                                 local_count if global_verdict=='PASS' else 0)
                self.assertEqual(len(f.calls),(len(plan['jobs']) if global_verdict=='PASS' else 1)+int(malformed_global)+int(preview_notes))
                if malformed_global:
                    events=[json.loads(line) for line in (out/'global/stage/tools.jsonl').read_text().splitlines()]
                    rejected=[e for e in events if e['result'].get('feedback_kind')=='candidate_rejected']
                    self.assertEqual(len(rejected),1)
                    self.assertIn("unexpected=['notes', 'verdict']",rejected[0]['result']['error'])
            self.assertEqual(before,(subprocess.Popen,fault_control.queue_notification,
                                    native_client.configuration,runtime_config.auth_home))
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
                if preview_notes:
                    self.assertEqual(receipt['inference_reviews'][probe_role]['background_notes'],notes)
                    rows=[json.loads(s) for s in (out/probe_role/'stage/tools.jsonl').read_text().splitlines()]
                    self.assertEqual([r['tool'] for r in rows],['check_draft']*9+['submit_draft'])
                    self.assertEqual(sum(r['result'].get('stage_complete',False) for r in rows),1)
            self.assertTrue(all(not r['measurement_complete'] for r in results))

    def test_native_global_fail_does_not_dispatch_local_review(self):
        self.exercise('FAIL')

    def test_native_global_and_local_submissions_reach_actual_bound_A_collection(self):
        self.exercise('PASS')

    def test_native_format_correction_then_parallel_reviews_and_bound_collection(self):
        self.exercise('PASS',malformed_global=True)

    def test_parallel_note_previews_and_correction_reach_the_audit_collector(self):
        self.exercise('PASS',preview_notes=True)
