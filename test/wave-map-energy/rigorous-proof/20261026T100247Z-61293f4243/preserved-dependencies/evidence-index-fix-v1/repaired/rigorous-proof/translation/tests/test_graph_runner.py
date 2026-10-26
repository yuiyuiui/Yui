import shutil
import tempfile
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import ir
import run_graph
from test_shared_parallel import fixture,LIFT,SUP


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix='graph-package-'))
        self.cpath, self.plan = fixture(self.temp/'original')
        self.ppath = self.cpath.parent/'plan.json'
        ir.write(self.ppath, self.plan)

    def tearDown(self): shutil.rmtree(self.temp)

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
            packets[stage.step]=ir.local_packet(stage.cpath,stage.plan,stage.step)
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


if __name__ == '__main__': unittest.main()
