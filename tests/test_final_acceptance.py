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
             patch.object(audit_b_review,'run',side_effect=AssertionError('Normal route must not dispatch B-final')),\
             patch.object(full_workflow.audit_b_mapping,'run',side_effect=AssertionError('No connection author needed')):
            result=full_workflow.from_interface('closed-addition',source,author,out,concurrency.serial_budget(),lambda *a,**k:None)
        self.assertEqual(preproof.call_count,1)
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
