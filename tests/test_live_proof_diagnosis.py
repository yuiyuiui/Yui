"""Retained-author diagnosis, concurrency, evidence and notification controls."""
import harness_support
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

import concurrency
import execution_state
import fault_control
import ir
import model_pilot
import proof_diagnosis
import proof_repair
from lean_fixtures import shared_fixture


class LiveDiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='yui-live-diagnosis-test-')
        self.root=Path(self.tmp.name);self.cp,self.plan=shared_fixture(self.root/'source');self.stages=[]

    def tearDown(self):
        for s in self.stages:shutil.rmtree(s.work,ignore_errors=True)
        self.tmp.cleanup()

    def stage(self,budget=None):
        s=model_pilot.Stage(self.root/f'worker-{len(self.stages)}',self.cp,'proof',None,self.plan,'T001',
                            budget=budget or concurrency.Budget(concurrency.resolve(1),role='proof'))
        self.stages.append(s);s.thread_id='same-native-author';return s

    def request(self,s):
        s.own_lean_drafts['proof'][1]={'proof':'exact missing_name','statement':'True',
            'check':{'exit_code':1,'stdout':'Unknown identifier'}}
        ir.write(s.logs/'lean-drafts/proof-0001.json',s.own_lean_drafts['proof'][1])
        return {'layer':'unknown','locations':['/target'],'explanation':'Uncertain implementation difficulty.',
                'candidates':[{'kind':'proof','candidate':1}]}

    def test_uncertain_diagnosis_keeps_author_and_deduplicates_identical_evidence(self):
        s=self.stage();value=self.request(s);calls=[]
        def diagnose(*args):calls.append(args);return {'route':'UNRESOLVED','repair_advice':'Check a small typed application.'}
        s.diagnose_obstruction=diagnose
        with s.budget:
            first=s.dispatch('report_proof_obstruction',value)
            second=s.dispatch('report_proof_obstruction',{**value,'explanation':'Reworded same issue.'})
            self.assertEqual(s.budget.report()['active_model_stages'],1)
        self.assertFalse(first['repair_requested']);self.assertFalse(second['repair_requested'])
        self.assertEqual(len(calls),1);self.assertEqual(s.thread_id,'same-native-author')
        self.assertFalse(s.submission_closed);self.assertIsNone(s.repair_request)
        self.assertEqual(len(s.own_lean_drafts['proof']),1)

    def test_repeated_same_candidate_with_new_timing_is_not_a_new_diagnosis(self):
        s=self.stage();value=self.request(s);calls=[]
        s.diagnose_obstruction=lambda *args:calls.append(args) or {'route':'UNRESOLVED'}
        first=s.dispatch('report_proof_obstruction',value)
        row=deepcopy(s.own_lean_drafts['proof'][1]);row['check']['wall_seconds']=9.1
        s.own_lean_drafts['proof'][2]=row
        second=s.dispatch('report_proof_obstruction',{**value,'candidates':[{'kind':'proof','candidate':2}]})
        self.assertEqual(len(calls),1);self.assertFalse(second['repair_requested'])

    def test_every_occupied_author_slot_can_request_diagnosis_without_deadlock(self):
        budget=concurrency.Budget(concurrency.resolve(4),role='proof');barrier=threading.Barrier(4)
        stages=[self.stage(budget) for _ in range(4)]
        active=0;peak=0;lock=threading.Lock()
        def diagnose(*args):
            nonlocal active,peak
            with budget:
                with lock:active+=1;peak=max(peak,active)
                with lock:active-=1
                return {'route':'LOCAL_PROOF_REPAIR','repair_advice':'Use explicit parameters.'}
        def work(s):
            s.diagnose_obstruction=diagnose
            with budget:
                barrier.wait(timeout=4)
                result=s.dispatch('report_proof_obstruction',self.request(s))
                self.assertFalse(result['repair_requested'])
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(work,s) for s in stages]
            for f in futures:f.result(timeout=8)
        self.assertLessEqual(budget.report()['observed_peak_model_stages'],4)
        self.assertEqual(budget.report()['active_model_stages'],0)
        self.assertTrue(all(not s.submission_closed for s in stages))

    def test_diagnosis_failure_does_not_lose_budget_or_author(self):
        s=self.stage();s.diagnose_obstruction=lambda *a:(_ for _ in ()).throw(RuntimeError('diagnostic service failed'))
        with s.budget:
            with self.assertRaisesRegex(RuntimeError,'diagnostic service'):
                s.dispatch('report_proof_obstruction',self.request(s))
            self.assertEqual(s.budget.report()['active_model_stages'],1)
        self.assertEqual(s.budget.report()['active_model_stages'],0)
        self.assertFalse(s.submission_closed)

    def test_resource_failures_cannot_be_relabelled_into_interface_escalation(self):
        s=self.stage();value=self.request(s)
        s.own_lean_drafts['proof'][1]['check']={'exit_code':1,
            'stdout':'Check.lean:2:0: error: (deterministic) timeout at isDefEq, maximum number of heartbeats (20000000) has been reached'}
        s.diagnose_obstruction=lambda *a:(_ for _ in ()).throw(AssertionError('No extra diagnosis for resource limits'))
        for layer in ['unknown','interface']:
            reply=s.dispatch('report_proof_obstruction',{**value,'layer':layer})
            self.assertFalse(reply['repair_requested'])
            self.assertEqual(reply['diagnosis']['basis'],'RECORDED_RESOURCE_LIMIT_ONLY')
        self.assertFalse(s.submission_closed)

    def test_timeout_does_not_hide_an_earlier_ordinary_error(self):
        check={'exit_code':1,'stdout':
            'Check.lean:2:0: error: unknown identifier\n'
            'Check.lean:4:0: error: (deterministic) timeout at isDefEq, maximum number of heartbeats (20000000) has been reached'}
        self.assertFalse(proof_repair.resource_only(check))

    def test_user_cancellation_of_author_propagates_to_its_diagnostic(self):
        from unittest.mock import Mock
        s=self.stage();s.execution=Mock();s.execution_task='diagnostic-child';s.parent_execution_task='T001'
        def check(task):
            if task=='T001':raise execution_state.Cancelled('User cancelled the owning node')
        s.execution.check.side_effect=check
        with self.assertRaises(execution_state.Cancelled):s.check_runtime_state()
        self.assertEqual([c.args[0] for c in s.execution.check.call_args_list],['diagnostic-child','T001'])

    def test_bare_inability_cannot_become_source_error(self):
        s=self.stage();value=self.request(s);value['layer']='source';value['locations']=['/source_steps/0/text']
        response=s.dispatch('report_proof_obstruction',value)
        self.assertIn('source issue needs',response['error']);self.assertIsNone(s.repair_request)

    def test_live_snapshot_is_one_node_and_cannot_change_while_reviewed(self):
        s=self.stage();request=proof_repair.obstruction(s,self.request(s))
        interface=self.root/'interface';ir.write(interface/'inputs/spec.json',{'target':'neutral'})
        ir.write(interface/'inputs/nl0.json',{'source':'neutral'})
        (interface/'inputs/foreign.txt').write_text('FOREIGN_PRIVATE_SENTINEL')
        out=self.root/'snapshot';proof_diagnosis.prepare_live(s,request,interface,out)
        self.assertNotIn('FOREIGN_PRIVATE_SENTINEL',''.join(p.read_text() for p in (out/'inputs').iterdir()))
        self.assertFalse(s.submission_closed)
        value={'route':'UNRESOLVED','explanation':'This evidence does not settle the cause.',
               'locations':[{'document':'local-packet.json','pointer':'/target'}],
               'repair_advice':'Check the particular application with explicit types.','comparison':None}
        proof_diagnosis.validate(value,out)
        value['route']='SOURCE_REVIEW_REQUIRED'
        with self.assertRaises(ValueError):proof_diagnosis.validate(value,out)
        request['candidate_evidence'][0]['sha256']='changed'
        with self.assertRaisesRegex(ValueError,'Changed live attempt'):
            proof_diagnosis.prepare_live(s,request,interface,self.root/'tampered')

    def test_pause_reuses_only_an_unchanged_sent_source_notice(self):
        out=self.root/'run';ir.write(out/'.yui-run.json',{})
        notice=out/'source-issues/one.json';ir.write(notice,{'notification':{'status':'QUEUED'}})
        from controller_common import bind
        gate=fault_control.Gate(out/'logs/errors',notify=lambda *a: (_ for _ in ()).throw(AssertionError('Duplicate notification')))
        gate.state={'notification':{'status':'PENDING'},'checkpoint':{'source_issue_notices':[bind(notice)]}}
        gate.persist=lambda:None
        gate.report()
        self.assertEqual(gate.state['notification']['status'],'QUEUED')
        self.assertIn('earlier_source_notice',gate.state['notification'])

    def test_source_notice_is_per_issue_not_per_failed_attempt_or_error_category(self):
        s=self.stage();source=ir.local_packet(self.cp,self.plan,'T001')['source_steps'][0]['text']
        comparison={'kind':'MISSING_JUSTIFICATION','source_quote':source,'hypotheses':'H',
                    'claim':'C','defect':'Missing test implication','why_not_lean_difficulty':'Synthetic test only'}
        result={'route':'SOURCE_REVIEW_REQUIRED','explanation':'Synthetic mathematical issue test.',
                'comparison':comparison}
        out=self.root/'notice';ir.write(out/'report.json',result)
        with patch.object(fault_control.Gate,'owner',return_value='test-owner'),\
             patch.object(fault_control,'queue_notification',return_value={'status':'QUEUED'}) as notify:
            first=proof_diagnosis.notice_source(self.cp,'T001',out,result)
            second=proof_diagnosis.notice_source(self.cp,'T001',out,result)
            self.assertEqual(first,second);self.assertEqual(notify.call_count,1)
            changed=deepcopy(result);changed['comparison']['defect']='Different mathematical implication'
            proof_diagnosis.notice_source(self.cp,'T001',out,changed)
            self.assertEqual(notify.call_count,2)


if __name__=='__main__':unittest.main()
