import harness_support
import shutil
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import ir
import run_graph
from lean_fixtures import shared_fixture as fixture, LIFT, SUP


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix='graph-package-'))
        self.cpath, self.plan = fixture(self.temp/'original')
        self.ppath = self.cpath.parent/'plan.json'
        ir.write(self.ppath, self.plan)

    def tearDown(self): shutil.rmtree(self.temp)

    def test_body_repair_reuses_only_identical_case_owned_native_checks(self):
        import concurrency,execution_state
        problem=self.temp/'problem.md';problem.write_text('Synthetic local repair cache test.')
        job=harness_support.direct_controller_job(problem,track='full',profiles=harness_support.PROFILES,output=self.temp/'owned')
        recorder=execution_state.Recorder(Path(job['root']),'synthetic',concurrency.resolve(1))
        self.addCleanup(recorder.done.set)
        with execution_state.activate(recorder,'T001'),patch.object(ir,'run_lean',wraps=ir.run_lean) as native:
            first=ir.check(self.cpath,self.plan,{'T001':LIFT},only='T001')
            repeat=ir.check(self.cpath,self.plan,{'T001':LIFT},only='T001')
            self.assertEqual(native.call_count,1);self.assertTrue(repeat['native_reused'])
            self.assertEqual(repeat['axioms'],first['axioms'])
            ir.check(self.cpath,self.plan,{'T002':SUP},only='T002')
            failed=ir.check(self.cpath,self.plan,{'T001':'exact True.intro'},only='T001')
            self.assertNotEqual(failed['exit_code'],0)
            ir.check(self.cpath,self.plan,{'T002':SUP},only='T002')
            self.assertEqual(native.call_count,3)
            file=Path(repeat['reused_native']['path']);file.write_text('{}')
            with self.assertRaises(ValueError):ir.check(self.cpath,self.plan,{'T001':LIFT},only='T001')

    def test_retained_draft_edit_checks_the_whole_result_with_real_lean(self):
        import model_pilot
        stage = model_pilot.Stage(self.temp/'edit', self.cpath, 'proof', None, self.plan, 'T001')
        self.addCleanup(stage.release_resources, 'USER_CANCELLED')
        broken = '\n  have h : True := True.intro\n  exact True.intro'
        failure = stage.dispatch('check_transition', {'proof': broken})
        self.assertFalse(failure['accepted'])
        self.assertEqual(failure['draft_errors'][0]['draft_line'], 3)
        # The end-to-end native path must still reject an unresolved suffix.
        missing = stage.dispatch('submit_transition', {'edit': {'base': 1, 'old': 'exact True.intro', 'new': 'done'}})
        self.assertFalse(missing['stage_complete'])
        self.assertIsNone(stage.accepted)
        fixed = stage.dispatch('check_transition', {'edit': {'base': 1, 'old': 'exact True.intro', 'new': LIFT}})
        self.assertTrue(fixed['accepted'])
        self.assertFalse(fixed['stage_complete'])
        final = stage.dispatch('submit_transition', {'edit': {'base': fixed['candidate']}})
        self.assertTrue(final['stage_complete'])
        self.assertEqual(stage.own_lean_drafts['proof'][1]['proof'], broken)
        expected = broken.replace('exact True.intro', LIFT)
        self.assertEqual(stage.accepted['proof'], expected)
        independent = ir.check(self.cpath, self.plan, {'T001': expected}, only='T001')
        self.assertEqual(independent['lean_sha256'],
                         stage.own_lean_drafts['proof'][final['candidate']]['check']['lean_sha256'])

    def test_private_proof_constructor_connects_diagnosis_to_the_actual_owner_path(self):
        import proof_obligations,proof_diagnosis,model_pilot,concurrency,private_handoff
        observed=[]
        class StopBeforeModel(BaseException):pass
        def execute(stage):
            self.assertIsNotNone(stage.diagnose_obstruction)
            with patch.object(proof_diagnosis,'run_private',return_value={'route':'UNRESOLVED'}) as diagnostic:
                self.assertEqual(stage.diagnose_obstruction(stage,{'located':'actual'},stage.logs/'diagnostic'),{'route':'UNRESOLVED'})
                observed.append(diagnostic.call_args.args[1])
            stage.release_resources('USER_CANCELLED')
            raise StopBeforeModel()
        with patch.object(model_pilot.Stage,'execute',execute),self.assertRaises(StopBeforeModel):
            request=private_handoff.issue(self.temp/'private',identity='B001',header='import Mathlib\n',parameters=[],
                premises=[],target='True',statement='Truth.',route='Use True.intro.')
            proof_obligations.deliver(request,concurrency.Budget(concurrency.resolve(1)))
        self.assertEqual(observed,[{'located':'actual'}])

    def test_packaged_graph_keeps_exact_input_binding(self):
        copied, plan = run_graph.package(self.cpath, self.ppath, self.temp/'run')
        self.assertEqual(ir.digest(copied), ir.digest(self.cpath))
        self.assertEqual(ir.validate(copied, plan)[2], ['T001','T002'])
        self.assertEqual(ir.local_packet(copied, plan, 'T002'), ir.local_packet(self.cpath, self.plan, 'T002'))

    def test_packaging_rejects_source_path_escape(self):
        shutil.copyfile(self.cpath.parent/'source.json', self.temp/'source.json')
        c = ir.load(self.cpath)
        c['source']['path'] = '../source.json'
        ir.write(self.cpath, c)
        self.plan['contract_sha256'] = ir.digest(self.cpath)
        ir.write(self.ppath, self.plan)
        with self.assertRaisesRegex(ir.Invalid, 'stage the source'):
            run_graph.package(self.cpath, self.ppath, self.temp/'run')

    def test_native_assembly_records_fresh_node_stages_without_model_calls(self):
        objects=[];packets={}
        def fake_execute(stage):
            objects.append(stage)
            packets[stage.step]=stage.proof_packet()
            self.assertEqual(packets[stage.step],ir.local_packet(stage.cpath,stage.plan,stage.step))
            path=Path(stage.task_request['path'])
            self.assertEqual(path.name,stage.step+'.json')
            self.assertEqual(ir.load(path)['node'],stage.step)
            self.assertEqual(stage.own_lean_drafts,{'proof':{},'auxiliary':{}})
            shutil.rmtree(stage.work)
            return {'status':'NEUTRAL_SOFTWARE_CONTROL','api_calls':0},{'proof':LIFT if stage.step=='T001' else SUP}
        out=self.temp/'native-control'
        with patch.object(run_graph.pilot.Stage,'execute',fake_execute):
            result=run_graph.run(self.cpath,self.ppath,out)
        self.assertEqual(result['status'],'FRAGMENT_ASSEMBLED')
        self.assertEqual(len({id(x) for x in objects}),2)
        self.assertEqual(len({str(x.work) for x in objects}),2)
        self.assertEqual([x['id'] for x in packets['T002']['inputs']],['T001'])
        self.assertNotIn('execution-status',str(packets))
        state=ir.load(out/'execution-status.json')
        self.assertEqual(state['controller']['state'],'FINALIZED')
        self.assertEqual(state['counts']['LOCAL_CHECKED'],2)
        self.assertIsNone(state['usage']['confirmed_tokens'])
        self.assertIn('execution_state.py',ir.load(out/'configuration.json')['script_sha256'])

    def test_same_case_exact_bodies_are_natively_rechecked_without_a_model_stage(self):
        previous=self.temp/'prior-software-fixture'
        oldc,_=run_graph.package(self.cpath,self.ppath,previous)
        ir.write(previous/'report.json',{'status':'FRAGMENT_ASSEMBLED','contract_sha256':ir.digest(oldc)})
        ir.write(previous/'proofs.json',{'contract_sha256':ir.digest(oldc),
            'plan_sha256':ir.digest(previous/'inputs/plan.json'),'proofs':{'T001':LIFT,'T002':SUP}})
        out=self.temp/'current-native-recheck'
        with patch.object(run_graph.pilot,'Stage',side_effect=AssertionError('No model stage for an identical checked program')):
            result=run_graph.run(self.cpath,self.ppath,out,prior_run=previous)
        self.assertEqual(result['status'],'FRAGMENT_ASSEMBLED')
        self.assertEqual(result['worker_calls'],0)
        self.assertEqual(len(list((out/'reused').glob('*/origin.json'))),2)

    def test_rejected_reuse_reaches_own_worker_with_current_failure_and_retained_body(self):
        import proof_reuse
        previous=self.temp/'explicit-prior';previous.mkdir();observed={}
        candidate={'body':'exact True.intro','previous_run':str(previous),
                   'scope':'Synthetic cache candidate; eligibility tested separately.'}
        def lookup(prior,cpath,plan,step,**kwargs):return candidate if step=='T001' else None
        def execute(stage):
            if stage.step=='T001':
                row=stage.own_lean_drafts['proof'][1]
                observed.update(row);self.assertNotEqual(row['check']['exit_code'],0)
                self.assertEqual(row['proof'],candidate['body']);self.assertIsNone(stage.accepted)
            else:self.assertEqual(stage.own_lean_drafts,{'proof':{},'auxiliary':{}})
            shutil.rmtree(stage.work)
            return {'status':'NEUTRAL_SOFTWARE_CONTROL','api_calls':0},{'proof':LIFT if stage.step=='T001' else SUP}
        with patch.object(proof_reuse,'candidate',side_effect=lookup),patch.object(run_graph.pilot.Stage,'execute',execute):
            result=run_graph.run(self.cpath,self.ppath,self.temp/'reuse-repair',prior_run=previous,max_concurrency=1)
        self.assertEqual(result['status'],'FRAGMENT_ASSEMBLED');self.assertTrue(observed)


if __name__ == '__main__': unittest.main()
