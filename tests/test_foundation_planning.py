"""The current basis protocol, global graph authority, parallel frontier and failure boundaries."""
import harness_support
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import patch

import artifact_protocol
import basis
import basis_graph
import basis_planning
import basis_preapproval
import concurrency
import graph_workload
import ir
import proof_obligations
from basis_fixtures import TARGET, active_artifact, artifact, dependency
from controller_common import manifest, write


def mixed():
    up=dependency(category=2);up['port']=None
    return active_artifact(artifact(up,dependency('B002',3)))


class FrozenRoute(unittest.TestCase):
    def test_current_and_legacy_interpret_the_same_category_by_version(self):
        old=artifact(dependency(),dependency('B002',3));new=mixed()
        basis.validate(old,TARGET);basis.validate(new,TARGET)
        self.assertFalse(basis.prepared(old['dependencies'][1]))
        self.assertTrue(basis.prepared(new['dependencies'][1]))
        source,checks,roots=basis.declarations(new)
        self.assertEqual(roots,['YuiBasis.B001','YuiBasis.B002'])
        self.assertLess(source.index('theorem B001'),source.index('theorem B002'))
        self.assertEqual(len(checks),2)
        new['dependencies'][1]['lean']=None
        with self.assertRaises(ValueError):basis.validate(new,TARGET)

    def test_duplicate_missing_cycle_and_weakened_consumer_are_rejected(self):
        for kind in ('missing','cycle','no-producer','orphan','unmapped','duplicate','change-statement','duplicate-basis','residual'):
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                v=mixed();g=v['global_graph'];step=g['inferences'][-1];rows=v['dependencies']
                if kind=='missing':step['inputs'].append('N999')
                if kind=='cycle':step['inputs'].append('P')
                if kind=='no-producer':g['inferences'].pop(0)
                if kind=='orphan':g['propositions'].append({'id':'N009','statement':'Unused'})
                if kind=='unmapped':step['basis']=[]
                if kind=='duplicate':g['inferences'].append(deepcopy(step))
                if kind=='change-statement':next(p for p in g['propositions'] if p['id']=='E002')['statement']='Weaker'
                if kind=='duplicate-basis':rows.append(deepcopy(rows[0]))
                if kind=='residual':rows[1]['uses']=['B099'];rows.append(dependency('B099',4))
                basis.validate(v,TARGET)

    def test_shared_selected_dependencies_pruning_and_frozen_edges(self):
        v=mixed();g=v['global_graph']
        g['inferences'][0]['inputs'].append('E002');g['inferences'][0]['basis']=['B002']
        v['dependencies'].append(dependency('B177',4))
        optimized=basis_graph.optimize(v)
        self.assertEqual(len(v['dependencies']),3)
        self.assertEqual([r['id'] for r in optimized['dependencies']],['B001','B002'])
        basis.validate(optimized,TARGET)
        copy=deepcopy(g)
        basis_graph.verify_handoff(optimized,copy)
        copy['inferences'][0]['inputs'].remove('E002')
        with self.assertRaisesRegex(ValueError,'frozen'):basis_graph.verify_handoff(optimized,copy)
        for change in ['uses','statement','graph']:
            other=deepcopy(optimized)
            if change=='uses':other['dependencies'][1]['uses']=[]
            if change=='statement':other['dependencies'][0]['statement']+=' revised'
            if change=='graph':other['global_graph']['inferences'][0]['inputs'].remove('E002')
            self.assertNotEqual(basis_preapproval.plan_identity(optimized),basis_preapproval.plan_identity(other))
        with self.assertRaisesRegex(ValueError,'replacement'):
            v['replacements']=[{'original_dependency':'old','replacement':['B177'],'explanation':'try'}]
            basis_graph.optimize(v)

    def test_planning_null_is_only_a_draft_and_does_not_establish_native_acceptance(self):
        v=mixed();v['dependencies'][1]['lean']['proof']=None
        artifact_protocol.validate(v,basis.artifact_schema(basis_graph.VERSION,planning=True))
        with self.assertRaises(ValueError):basis.validate(v,TARGET)
        with tempfile.TemporaryDirectory() as raw:
            c=basis.BasisContract(Path(raw),TARGET,version=basis_graph.VERSION)
            with self.assertRaisesRegex(ValueError,'submit yui-basis-2'):c(artifact())
            self.assertIsNone(c.selected)

    def test_native_unlisted_dependency_is_rejected_after_successful_kernel_check(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);v=mixed()
            inspected={'dependencies':{'declarations':[{'name':n,'direct_constants':refs,'imported':False}
                for n,refs in [('YuiBasis.B001',[]),('YuiBasis.B002',['YuiBasis.B002._proof_1']),
                                ('YuiBasis.B002._proof_1',['YuiBasis.B001'])]]}}
            write(root/'elaborated.json',inspected)
            basis.verify_native_edges(v,root)
            v['dependencies'][1]['uses']=[]
            with self.assertRaisesRegex(ValueError,'B002.*B001'):basis.verify_native_edges(v,root)

    def test_workload_reports_witness_scope_and_critical_chain(self):
        r={'argument':[{'id':'S001'},{'id':'S002','uses_local':['L001']}],'locals':['L001']}
        self.assertEqual(graph_workload.local(r)['paragraphs_without_local_binders'],['S001'])
        nodes={k:{'inputs':inputs,'source_steps':list(range(n))} for k,inputs,n in
               [('T1',[],3),('T2',[],1),('T3',['T1','T2'],2)]}
        result=graph_workload.jobs(nodes,list(nodes))
        self.assertEqual(result['levels'],{1:2,2:1})
        self.assertEqual(result['jobs']['T3']['paragraphs_on_longest_chain'],5)


class ParallelWork(unittest.TestCase):
    def test_private_task_cancellation_does_not_cancel_its_siblings(self):
        import execution_state
        with tempfile.TemporaryDirectory() as raw:
            ledger=execution_state.Recorder(Path(raw),'bounded',concurrency.resolve(1))
            ledger.task('T001',state='RUNNING')
            ledger.task('T002',state='RUNNING')
            ledger.task('child',parent_task='T001',state='RUNNING')
            ledger.task('nested',parent_task='child',state='RUNNING')
            ledger._cancel_tasks.add('T001')
            self.assertTrue(ledger.cancelled('nested'))
            with self.assertRaises(execution_state.Cancelled):ledger.check('child')
            self.assertFalse(ledger.cancelled('T002'))

    def test_auto_expands_a_single_hard_node_and_restores_its_lane(self):
        b=concurrency.Budget(concurrency.resolve('auto',node_count=1),role='proof')
        barrier=threading.Barrier(3,timeout=5)
        def solve(i,child):
            self.assertIs(child,b)
            with child:
                barrier.wait()
                return i*i
        with b:
            self.assertEqual(proof_obligations.parallel(SimpleNamespace(budget=b),[1,2,3],solve,role='proof'),[1,4,9])
            self.assertEqual(b.capacity(),1)
        self.assertEqual(b.report()['observed_peak_model_stages'],3)

    def test_explicit_cap_and_backend_bound_survive_nested_jobs_and_fault(self):
        for req,known in [(1,None),('auto',1)]:
            b=concurrency.Budget(concurrency.resolve(req,node_count=1,known_limit=known),role='proof')
            def fail(i,child):
                with child:
                    if i==2:raise OSError('native unavailable')
                    return i
            with b,self.assertRaisesRegex(OSError,'unavailable'):
                proof_obligations.parallel(SimpleNamespace(budget=b),[1,2,3],fail,role='proof')
            self.assertEqual(b.report()['observed_peak_model_stages'],1)
            self.assertEqual(b.report()['active_model_stages'],0)

    def test_two_search_roles_bind_every_consumer_and_cache_only_complete_results(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);inputs=root/'inputs';inputs.mkdir();(inputs/'source.txt').write_text('Frozen source')
            manifest(inputs);stage=SimpleNamespace(logs=root/'stage',budget=None,
                validator=SimpleNamespace(out=root,concurrency='auto'))
            barrier=threading.Barrier(2,timeout=10)
            items=[{'id':key,'statement':'Required '+key,'consumers':[{'id':'R001','required_use':'Use here'}]}
                   for key in ('B001','B002')]
            def execute(worker):
                item=ir.load(worker.logs.parent/'inputs/frontier-item.json')
                self.assertEqual((worker.logs.parent/'inputs/source.txt').read_text(),'Frozen source')
                barrier.wait()
                value={'route':'derivation','statement':item['statement'],'argument':'Apply the supplied premise',
                       'source':'Frozen source','consumer_uses':[{'id':'R001','application':'Direct'}],'evidence':[]}
                with self.assertRaisesRegex(ValueError,'every actual consumer'):worker.validator({**value,'consumer_uses':[]})
                worker.validator(value)
                return {},value
            with patch('clean_stage.ArtifactStage.execute',execute),patch('execution_health.require_review_execution'),patch('proof_obligations.complete_private'):
                result=basis_planning.investigate(stage,{'obligations':items})
                self.assertEqual([r['id'] for r in result['proposals']],['B001','B002'])
                with patch('clean_stage.ArtifactStage.execute',side_effect=AssertionError):
                    self.assertEqual(result,basis_planning.investigate(stage,{'obligations':items}))
                path=next(stage.logs.glob('frontier/B001/*/attempt-*/proposal.json'));path.write_text('{}')
                with self.assertRaisesRegex(ValueError,'changed'):
                    basis_planning.investigate(stage,{'obligations':items})
