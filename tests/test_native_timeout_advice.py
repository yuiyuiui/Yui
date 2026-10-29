"""Native failure routing controls; no provider, model or compiler is started."""
import harness_support
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import controller_common
import ir
import model_pilot
import run_graph
import strategy_bank as bank
from lean_fixtures import norm_plan


def wall_timeout():
    return dict(exit_code=124,stdout='',stderr='Retained native timeout diagnostic.',
                timed_out=True,error_kind='LEAN_TIMEOUT',timeout_scope='native_call',
                timeout_seconds=300,status='LEAN-CHECK-FAILED')


def heartbeat_timeout():
    return dict(exit_code=1,stdout=('Check.lean:20:4: error: (deterministic) timeout at '
        '`isDefEq`, maximum number of heartbeats (200000) has been reached\n'),stderr='',
        status='LEAN-CHECK-FAILED')


class NativeTimeoutAdviceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='native-timeout-advice-')
        self.root=Path(self.temp.name);self.stages=[]
        for name in ('source.json','contract.json'):
            shutil.copyfile(harness_support.FIXTURES/'lean/examples/case1_norm_sup'/name,
                            self.root/name)
        self.cp=self.root/'contract.json';self.plan=norm_plan(self.cp)

    def tearDown(self):
        for stage in self.stages:shutil.rmtree(stage.work,ignore_errors=True)
        self.temp.cleanup()

    def stage(self,arm='yui',**kwargs):
        stage=model_pilot.Stage(self.root/f'stage-{len(self.stages)}',self.cp,'proof',None,
                               self.plan,'T001',instruction_arm=arm,**kwargs)
        self.stages.append(stage);return stage

    def test_wall_timeout_delivers_advice_and_repair_stays_in_same_worker(self):
        stage=self.stage();proof='exact fun r => (enorm_eq_iff_norm_eq).2 (h_H001 r)'
        with patch.object(ir,'check',return_value=wall_timeout()), \
                patch.object(stage,'rpc',side_effect=AssertionError('No extra model call')):
            failed=stage.dispatch('submit_transition',{'proof':proof})
        self.assertFalse(failed['accepted']);self.assertFalse(failed['stage_complete'])
        self.assertIsNone(stage.accepted)
        advice=failed['repair_advice']
        self.assertEqual(advice['status'],'ADVICE_DELIVERED')
        self.assertEqual(advice['strategy']['id'],'ST020')
        self.assertEqual(advice['card_sha256'],stage.native_timeout_snapshot['card_sha256'])
        saved=json.loads((stage.logs/'lean-drafts/proof-0001.json').read_text())
        self.assertEqual(saved['check']['repair_advice'],advice)
        logged=json.loads((stage.logs/'tools.jsonl').read_text().splitlines()[-1])
        self.assertEqual(logged['result']['repair_advice'],advice)
        self.assertEqual(stage.api_calls,0)
        passed=dict(exit_code=0,stdout='',stderr='',status='LOCAL-PROOF-CHECKED')
        with patch.object(ir,'check',return_value=passed):
            accepted=stage.dispatch('submit_transition',{'proof':proof})
        self.assertTrue(accepted['stage_complete'])
        self.assertEqual(stage.accepted,{'proof':proof})
        self.assertNotIn('repair_advice',accepted)

    def test_auxiliary_heartbeat_failure_receives_same_local_advice(self):
        stage=self.stage();result=heartbeat_timeout()
        with patch.object(ir,'check_auxiliary',return_value=result):
            failed=stage.dispatch('check_auxiliary',{'statement':'True','proof':'trivial'})
        self.assertEqual(failed['repair_advice']['trigger'],'NATIVE_HEARTBEAT_EXHAUSTED')
        self.assertIsNone(stage.accepted)
        self.assertEqual(failed['stdout'],result['stdout'])
        self.assertEqual(stage.own_lean_drafts['auxiliary'][1]['check'],failed)

    def test_success_ordinary_error_and_cancel_do_not_search(self):
        stage=self.stage()
        cases=[dict(exit_code=0,stdout='',stderr=''),
               dict(exit_code=1,stdout='Check.lean:1:1: error: type mismatch',stderr=''),
               dict(wall_timeout(),exit_code=130,cancelled=True)]
        with patch.object(bank,'search',side_effect=AssertionError('No advice lookup')):
            for result in cases:
                with self.subTest(result=result),patch.object(ir,'check',return_value=deepcopy(result)):
                    reply=stage.dispatch('check_transition',{'proof':'trivial'})
                    self.assertNotIn('repair_advice',reply)

    def test_provider_cleanup_and_unstructured_timeouts_are_not_native_routing(self):
        cases=[dict(wall_timeout(),error_kind='PROVIDER_ERROR'),
               dict(exit_code=124,stdout='',stderr='timeout'),
               dict(exit_code=1,stdout='RuntimeError: Native process cleanup could not be confirmed',stderr=''),
               dict(heartbeat_timeout(),exit_code=0),
               dict(heartbeat_timeout(),feedback_kind='candidate_rejected')]
        with patch.object(bank,'search',side_effect=AssertionError('No advice lookup')):
            for result in cases:
                with self.subTest(result=result):
                    self.assertIsNone(bank.native_timeout_feedback(result,'4.32.2',None))
        stage=self.stage()
        with patch.object(ir,'check',side_effect=RuntimeError('Native process cleanup could not be confirmed')):
            with self.assertRaisesRegex(RuntimeError,'cleanup'):stage.dispatch('check_transition',{'proof':'trivial'})

    def test_direct_arm_gets_no_timeout_strategy_or_snapshot(self):
        stage=self.stage(arm='direct')
        with patch.object(bank,'search',side_effect=AssertionError('Direct arm cannot query advice')), \
                patch.object(ir,'check',return_value=wall_timeout()):
            failed=stage.dispatch('check_transition',{'proof':'trivial'})
        self.assertNotIn('repair_advice',failed)
        self.assertIsNone(stage.native_timeout_snapshot)
        self.assertNotIn('ST020',stage.system)
        self.assertFalse((stage.logs/'harness-snapshot/nl02lean/bank').exists())

    def test_frozen_card_survives_live_bank_change_and_is_manifest_bound(self):
        live=self.root/'live-bank';shutil.copytree(bank.BANK,live)
        with patch.object(bank,'BANK',live):stage=self.stage()
        (live/'cards/ST020.json').write_text('damaged after stage entry')
        with patch.object(ir,'check',return_value=wall_timeout()):
            failed=stage.dispatch('check_transition',{'proof':'trivial'})
        self.assertEqual(failed['repair_advice']['status'],'ADVICE_DELIVERED')
        with patch.object(stage,'start_process',side_effect=RuntimeError('OFFLINE_PROCESS_BOUNDARY')), \
                patch.object(stage,'pause_error',side_effect=__import__('execution_state').Cancelled('Synthetic user cancellation')):
            stage._execute()
        manifest=json.loads((stage.logs/'execution-manifest.json').read_text())
        card=next(row for row in manifest['runtime_files'] if row['path']=='nl02lean/bank/cards/ST020.json')
        self.assertEqual(card['sha256'],stage.native_timeout_snapshot['card_sha256'])
        self.assertEqual(manifest['native_timeout_policy']['policy'],bank.NATIVE_TIMEOUT_POLICY)

    def test_missing_tampered_or_wrong_version_advice_keeps_failure_unaccepted(self):
        missing=bank.freeze_native_timeout_policy(self.root/'missing-snapshot',bank=self.root/'absent-bank')
        self.assertEqual(missing['status'],'UNAVAILABLE')
        stage=self.stage();snapshot=stage.native_timeout_snapshot
        wrong_version=bank.native_timeout_feedback(wall_timeout(),'4.99.0',snapshot)
        self.assertEqual(wrong_version['status'],'UNAVAILABLE')
        self.assertNotIn('strategy',wrong_version)
        path=Path(snapshot['bank_root'])/'cards/ST020.json';path.write_bytes(path.read_bytes()+b' ')
        with patch.object(ir,'check',return_value=wall_timeout()):
            failed=stage.dispatch('submit_transition',{'proof':'trivial'})
        self.assertEqual(failed['repair_advice']['status'],'UNAVAILABLE')
        self.assertIn('changed',failed['repair_advice']['reason'])
        self.assertEqual(failed['exit_code'],124)
        self.assertEqual(failed['stderr'],wall_timeout()['stderr'])
        self.assertFalse(failed['accepted']);self.assertIsNone(stage.accepted)

    def test_new_job_runtime_bindings_include_strategy_data(self):
        core=self.root/'runtime';(core/'toolchain').mkdir(parents=True)
        for name in ('SKILL.md','config.json','toolchain/lock.json'):
            (core/name).write_text('{}')
        shutil.copytree(bank.BANK,core/'nl02lean/bank')
        with patch.object(controller_common,'CORE',core):rows=controller_common.runtime_bindings()
        card=core/'nl02lean/bank/cards/ST020.json'
        row=next(row for row in rows if row['path']==str(card.resolve()))
        card.write_bytes(card.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'changed'):controller_common.verify_bindings([row])

    def test_full_queue_delivers_phase_frozen_advice_with_free_form_bank_off(self):
        live=self.root/'queue-live-bank';shutil.copytree(bank.BANK,live)
        plan_path=self.root/'plan.json';ir.write(plan_path,self.plan)
        replies=[]

        def execute(stage):
            self.stages.append(stage)
            with patch.object(ir,'check',return_value=wall_timeout()):
                replies.append(stage.dispatch('check_transition',{'proof':'trivial'}))
            return {'status':'NO_ACCEPTED_ARTIFACT'},None

        def queue(cpath,plan,worker,**kwargs):
            # Phase entry has already frozen the card; later library edits must
            # not alter the newly started worker's advice.
            (live/'cards/ST020.json').write_text('changed after queue entry')
            worker('T001',{})
            return {'status':'GRAPH_UNFINISHED','proofs':{}}

        out=self.root/'queue'
        with patch.object(bank,'BANK',live),patch.object(model_pilot.Stage,'execute',execute), \
                patch.object(run_graph.scheduler,'prove_graph',side_effect=queue):
            result=run_graph.run(self.cp,plan_path,out,max_concurrency=1,bank=False)
        self.assertEqual(result['status'],'GRAPH_UNFINISHED')
        self.assertEqual(replies[0]['repair_advice']['status'],'ADVICE_DELIVERED')
        config=json.loads((out/'configuration.json').read_text())
        self.assertFalse(config['bank_enabled'])
        self.assertEqual(config['native_timeout_policy']['status'],'READY')


if __name__=='__main__':unittest.main()
