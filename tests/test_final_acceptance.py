"""Actual Lean proof integrity plus synthetic semantic receipts, never proof certification."""
import harness_support
from final_acceptance_fixtures import frozen_case,build,qualified_artifact
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import audit_b
import audit_b_review
import final_acceptance as final
import ir
import workflow
import full_workflow
import concurrency


class FinalAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='yui-final-controls-');cls.root=Path(cls.temp.name)
        cls.normal=frozen_case(cls.root/'normal');build(cls.normal)
        cls.drift=frozen_case(cls.root/'faithful');build(cls.drift,'faithful')
        cls.unfaithful=frozen_case(cls.root/'unfaithful');build(cls.unfaithful,'unfaithful')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_timeout_flags_in_native_records_cannot_be_overridden_by_passed_summaries(self):
        out=self.normal/'audit-b';mechanical=out/'mechanical.json'
        original=mechanical.read_bytes()
        for name in ('compiler.json','assembly-compiler.json'):
            path=out/name;raw=path.read_bytes()
            try:
                native=ir.load(path);native.update(timed_out=True,error_kind='LEAN_TIMEOUT')
                ir.write(path,native)
                summary=ir.load(mechanical);summary['artifacts'][name]=ir.digest(path)
                ir.write(mechanical,summary)
                with self.subTest(name=name),self.assertRaises(ValueError):
                    final.proof_integrity(out)
            finally:
                path.write_bytes(raw);mechanical.write_bytes(original)

    def test_normal_gate_inherits_review_and_uses_no_final_model_or_native_rerun(self):
        with patch.object(ir,'run_lean',side_effect=AssertionError('No new native run')),patch.object(audit_b_review,'run',side_effect=AssertionError('No final model')):
            gate=final.check(self.normal)
            self.assertTrue(gate['interface_consistent']);self.assertTrue(gate['proof_integrity_passed'])
            receipt=final.finish(self.normal)
            checked=audit_b.check(self.normal/'audit-b',Path(receipt['receipt_path']))
        self.assertEqual(checked['acceptance_basis'],'FROZEN_INTERFACE_SEMANTICS_INHERITED')
        self.assertFalse(checked['final_semantic_model_called'])

    def test_compiled_drift_cannot_inherit_the_frozen_semantics(self):
        gate=final.check(self.drift)
        self.assertFalse(gate['interface_consistent']);self.assertTrue(gate['proof_integrity_passed'])
        with self.assertRaisesRegex(ValueError,'actual B-final'):final.finish(self.drift)

    def test_legacy_nonindependent_b_receipt_is_readable_but_never_full_acceptance(self):
        from audit_b_fixtures import synthetic_receipt
        receipt=synthetic_receipt(self.normal/'audit-b')
        verdict=audit_b.check(self.normal/'audit-b',receipt)
        self.assertEqual(verdict['status'],'DEVELOPMENT-AUDIT-B-PASSED')
        self.assertFalse(verdict['independent_semantic_acceptance'])
        with self.assertRaisesRegex(ValueError,'whole workflow requires'):
            workflow.finish(self.normal,receipt)

    def synthetic_final_review(self,out,passed):
        directory=out/'B-final-test-only';audit_b_review.prepare(out/'audit-b',directory,interface_deviation=True)
        mechanical=ir.load(directory/'mechanical.json');packet=ir.load(directory/'inputs/review-packet.json')
        def row(locations):return {'verdict':'PASS' if passed else 'FAIL',
            'notes':'SYNTHETIC actual-artifact fidelity judgment for software control only.','locations':locations}
        raw={'nodes':{key:row(locations) for key,locations in mechanical['required_review_locations'].items()},
             'checks':{key:row(audit_b.review_materials.locations(packet)) for key in audit_b.REVIEW_CHECKS},'findings':[]}
        qualified_artifact(directory/'stage',raw);audit_b_review.collect(directory)
        return directory

    def test_faithful_exception_is_warning_qualified_and_bound_to_actual_file(self):
        directory=self.synthetic_final_review(self.drift,True)
        receipt=final.finish(self.drift,exceptional_review=directory/'review.json')
        self.assertEqual(receipt['status'],'AUDIT-B-CONDITIONAL')
        self.assertTrue(receipt['freeze_deviation']);self.assertTrue((self.drift/'freeze-warning.md').is_file())
        final.validate_receipt(receipt['receipt_path'])

    def test_unfaithful_exception_cannot_be_marked_original_goal_complete(self):
        directory=self.synthetic_final_review(self.unfaithful,False)
        with self.assertRaises(ValueError):final.finish(self.unfaithful,exceptional_review=directory/'review.json')
        self.assertFalse((self.unfaithful/'audit-b/machine-acceptance.json').exists())

    def test_changed_compiled_file_or_native_evidence_cannot_reach_b_final(self):
        with tempfile.TemporaryDirectory() as raw:
            copy=Path(raw)/'audit';shutil.copytree(self.normal/'audit-b',copy)
            file=copy/'Proof.lean';file.write_text(file.read_text()+'\n-- changed delivery\n')
            with self.assertRaisesRegex(ValueError,'Changed native audit artifact'):final.proof_integrity(copy)
            with self.assertRaises(ValueError):audit_b_review.prepare(copy,Path(raw)/'review',interface_deviation=True)

    def test_incomplete_native_trust_never_becomes_a_semantic_override(self):
        with tempfile.TemporaryDirectory() as raw:
            copy=Path(raw)/'audit';shutil.copytree(self.normal/'audit-b',copy)
            row=ir.load(copy/'mechanical.json');row.update(passed=False,errors=['UNPERMITTED_AXIOM:sorryAx'])
            ir.write(copy/'mechanical.json',row)
            with self.assertRaisesRegex(ValueError,'Proof integrity failed'):final.proof_integrity(copy)

    def test_normal_controller_finishes_actual_native_assembly_without_a_final_model(self):
        source=self.normal.parent/'source';author=self.normal.parent/'author';out=self.root/'normal-controller/workflow'
        raw=ir.load(self.normal.parent/'interface-review/stage/accepted.json')
        def review(directory,*args,**kwargs):qualified_artifact(Path(directory)/'stage',raw)
        def proof(case,frozen,destination,*args,**kwargs):
            import run_graph
            directory=Path(destination)/'proof-run';directory.mkdir()
            cp,_=run_graph.package(Path(frozen['contract']),Path(frozen['plan']),directory)
            ir.write(directory/'proofs.json',{'contract_sha256':ir.digest(cp),'plan_sha256':ir.digest(directory/'inputs/plan.json'),
                'proofs':{'T001':'exact h_H001.symm','T002':'simpa only [Nat.add_zero] using h_T001.symm'}})
            row={'status':'FRAGMENT_ASSEMBLED','concurrency':{'requested':1},'runner_wall_seconds':0}
            ir.write(directory/'report.json',row);return row,directory
        with patch.object(full_workflow.interface_review,'run',side_effect=review) as preproof,\
             patch.object(full_workflow,'prove_with_repair',side_effect=proof),\
             patch.object(final,'proof_integrity',wraps=final.proof_integrity) as integrity,\
             patch.object(audit_b_review,'run',side_effect=AssertionError('Normal route must not dispatch B-final')),\
             patch.object(full_workflow.audit_b_mapping,'run',side_effect=AssertionError('No connection author needed')):
            result=full_workflow.from_interface('closed-addition',source,author,out,concurrency.serial_budget(),lambda *a,**k:None)
        self.assertEqual(preproof.call_count,1)
        integrity.assert_called_once()
        self.assertEqual(result['status'],'WORKFLOW-PASSED')
        self.assertEqual(result['audit_b']['acceptance_basis'],'FROZEN_INTERFACE_SEMANTICS_INHERITED')
        self.assertFalse(result['audit_b']['final_semantic_model_called'])

    def test_connection_author_can_repair_internal_bodies_but_not_the_contract(self):
        import audit_b_mapping
        out=frozen_case(self.root/'connection-control');workflow.prepare_audit(out)
        mapping_dir=out.parent/'connection-author';audit_b_mapping.prepare(out,mapping_dir)
        validator=audit_b_mapping.MappingContract(mapping_dir)
        mapping=ir.load(mapping_dir/'inputs/mapping.json')
        bad={**mapping,'proof_patches':{'T099':'exact True.intro'}}
        from copy import deepcopy
        original=deepcopy(bad)
        with self.assertRaisesRegex(ValueError,'/proof_patches:.*unexpected=.*T099'):validator(bad)
        self.assertEqual(bad,original,'Rejected tool arguments must remain intact for provenance')
        with self.assertRaises(ValueError):validator({**mapping,'header':'import Mathlib\ndef changed := True\n'})
        fixed={**mapping,'proof_patches':{'T002':'simpa only [Nat.add_zero] using h_T001.symm'}}
        result=validator(fixed)
        self.assertEqual(result['status'],'AUDIT-B-MECHANICAL-PASSED')
        self.assertEqual(ir.load(workflow.bound(out)['contract']),ir.load(mapping_dir/'inputs/contract.json'))


class ValidationReductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='yui-validation-reduction-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name).resolve()
        cls.original=frozen_case(cls.root/'fixture')

    def arguments(self):
        base=self.original.parent;source=base/'source';author=base/'author'
        paths=ir.load(author/'accepted-interface-paths.json')
        return {'graph':source/'nl0.json','spec':source/'spec.json','contract':Path(paths['contract']),
                'plan':Path(paths['plan']),'interface_review':base/'interface-review/review.json',
                'audit_a':source/'audit-a.json','max_concurrency':1}

    def test_freeze_reuses_the_exact_author_check_and_runs_the_actual_review_gate_once(self):
        import interface_review
        arguments=self.arguments();out=self.root/'reused-at-freeze'
        with patch.object(ir,'check',wraps=ir.check) as compiler, \
             patch.object(interface_review,'verify_receipt',wraps=interface_review.verify_receipt) as verify:
            result=workflow.freeze(**arguments,out=out)
        self.assertEqual((verify.call_count,compiler.call_count),(1,0))
        self.assertEqual(result['types_check']['lean_sha256'],ir.digest(out/'interface-types/Check.lean'))

    def test_freeze_rejects_changed_check_receipt_plan_and_forged_review_without_recompiling(self):
        arguments=self.arguments();types=arguments['contract'].parent/'types'
        with patch.object(ir,'check',side_effect=AssertionError('Invalid authority cannot be replaced by compilation')):
            for name in ('Check.lean','result.json','receipt.json'):
                path=types/name;original=path.read_bytes()
                try:
                    path.write_bytes(original+b' ')
                    with self.subTest(name=name),self.assertRaisesRegex(ValueError,'type check evidence'):
                        workflow.freeze(**arguments,out=self.root/('changed-'+name))
                finally:path.write_bytes(original)
            plan=ir.load(arguments['plan']);plan['representation_notes']+=' Changed without independent review.'
            changed_plan=self.root/'changed-plan.json';ir.write(changed_plan,plan)
            with self.assertRaisesRegex(ValueError,'stale interface review'):
                workflow.freeze(**{**arguments,'plan':changed_plan},out=self.root/'plan-mismatch')
            review=ir.load(arguments['interface_review'])
            next(iter(review['checks'].values()))['notes']='An invented passing review.'
            forged=arguments['interface_review'].with_name('forged.json');ir.write(forged,review)
            with self.assertRaisesRegex(ValueError,'No complete actual passing interface review'):
                workflow.freeze(**{**arguments,'interface_review':forged},out=self.root/'forged-review')

    def test_full_queue_assembles_two_real_lean_nodes_once_before_independent_audit_b(self):
        import run_graph
        import scheduler
        out=self.root/'real-queue';frozen=workflow.freeze(**self.arguments(),out=out)
        bodies={'T001':'exact h_H001.symm','T002':'simpa only [Nat.add_zero] using h_T001.symm'}
        def actor(*args,**kwargs):
            from types import SimpleNamespace
            return SimpleNamespace(execute=lambda:({'status':'ACCEPTED'},{'proof':bodies[args[5]]}))
        with patch.object(run_graph.pilot,'Stage',side_effect=actor),patch.object(ir,'check',wraps=ir.check) as native:
            result=workflow.run(out)
        self.assertEqual(result['status'],'FRAGMENT_ASSEMBLED',result)
        types=sum(call.kwargs.get('types_only',False) for call in native.call_args_list)
        assemblies=sum(not call.kwargs.get('types_only') and not call.kwargs.get('only')
                       for call in native.call_args_list)
        self.assertEqual((types,assemblies),(0,1))
        self.assertFalse((out/'proof-run/graph/fresh-verifier').exists())
        mechanical=build(out)
        self.assertEqual(mechanical['status'],'AUDIT-B-MECHANICAL-PASSED',mechanical)
        self.assertTrue((out/'audit-b/compiler.json').is_file())
        self.assertTrue((out/'audit-b/assembly-compiler.json').is_file())
        with patch.object(ir,'check',wraps=ir.check) as independent:
            standalone=scheduler.prove_graph(frozen['contract'],ir.load(frozen['plan']),
                lambda sid,packet:{'proof':bodies[sid] if sid=='T001' else 'exact absentProof'})
        self.assertEqual(sum(call.kwargs.get('types_only',False) for call in independent.call_args_list),1)
        self.assertIsNone(standalone['assembly'])
        self.assertNotEqual(standalone['status'],'FRAGMENT_ASSEMBLED')
        broken=ir.load(out/'proof-run/proofs.json');broken['proofs']['T002']='exact absentProof'
        broken_path=out/'unclosed-proof.json';ir.write(broken_path,broken)
        rejected=out/'unclosed-audit'
        audit_b.prepare(frozen['contract'],frozen['plan'],broken_path,rejected,**frozen['authority'])
        self.assertEqual(audit_b.build(rejected)['status'],'AUDIT-B-MECHANICAL-FAILED')
        self.assertIn('LOCAL_INPUT_CLOSURE_FAILED',ir.load(rejected/'mechanical.json')['errors'])


class FrozenExternalNativeTests(unittest.TestCase):
    def test_native_frozen_external_comparison_includes_preceding_hypotheses(self):
        from audit_b_fixtures import fixture
        from copy import deepcopy
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);cp,pp,bp,inventory=fixture(root/'case','weakened_external')
            contract=ir.load(cp)
            contract['premises'].insert(0,{'id':'H001','kind':'hypothesis','type':'True','statement':'Synthetic preceding hypothesis.'})
            ir.write(cp,contract)
            plan=ir.load(pp);plan['contract_sha256']=ir.digest(cp);plan['steps'][0]['inputs'].insert(0,'H001');ir.write(pp,plan)
            bundle=ir.load(bp);bundle.update(contract_sha256=ir.digest(cp),plan_sha256=ir.digest(pp));ir.write(bp,bundle)
            source=ir.load(inventory);source['propositions'].insert(0,{'id':'H001','kind':'hypothesis','statement':'Synthetic preceding hypothesis.'});ir.write(inventory,source)
            expected=deepcopy(contract);expected['premises'][1]['type']='p'
            frozen=root/'expected-contract.json';ir.write(frozen,expected)
            shutil.copyfile(cp.parent/contract['source']['path'],root/contract['source']['path'])
            out=root/'audit';audit_b.prepare(cp,pp,bp,out,fragment=inventory)
            result=audit_b.build(out,frozen_contract=frozen)
            self.assertIn('FROZEN_INTERFACE_MISMATCH',ir.load(out/'mechanical.json')['errors'])
            checks={row['id']:row for row in ir.load(out/'elaborated.json')['frozen_comparisons']}
            self.assertEqual(set(checks),{'__frozen__E001','__frozen__P'})
            self.assertFalse(checks['__frozen__E001']['definitionally_equal'])
            self.assertIn('h_H001',audit_b.frozen_endpoints(expected,source)['E001'][1])
            final.proof_integrity(out)


if __name__=='__main__':unittest.main()
