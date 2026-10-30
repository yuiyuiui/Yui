"""Semantic repair-boundary controls with synthetic judgments, never model passes."""
import harness_support
import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import full_workflow as full
import interface_controls
import interface_review as review
import ir
import workflow
import concurrency
from controller_common import bind
from execution_health import StageFailure


class InterfaceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        interface_controls.prepare(cls.root/'controls')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def setup_gate(self,name):
        author=self.root/name;author.mkdir();inputs=author/'inputs';inputs.mkdir()
        fixture=self.root/'controls/stronger-hypothesis/inputs'
        import shutil
        for file in fixture.iterdir():shutil.copyfile(file,inputs/file.name)
        ir.write(author/'accepted-interface-paths.json',{'contract':str(inputs/'contract.json'),'plan':str(inputs/'plan.json')})
        return author,inputs

    def test_well_typed_strengthened_assumption_cannot_start_proof_queue_after_failed_semantic_review(self):
        author,inputs=self.setup_gate('bad-interface')
        # The wrong encoding elaborates: typechecking cannot be the semantic gate.
        self.assertEqual(ir.check(inputs/'contract.json',ir.load(inputs/'plan.json'),types_only=True)['exit_code'],0)
        with patch.object(review,'prepare'),patch.object(review,'run'),\
                patch.object(review,'collect',return_value={'all_checks_passed':False,'review_status':'MATHEMATICAL_REVIEW_FAILED'}),\
                patch.object(full.workflow,'freeze') as freeze,patch.object(full.run_graph,'run') as prove:
            with self.assertRaises(StageFailure) as error:
                full.from_interface('neutral',inputs,author,author.parent/'bad-flow',concurrency.serial_budget(),
                    lambda *a,**k:None,proof_budget=SimpleNamespace(configuration={'requested':1}))
        self.assertEqual(error.exception.result['phase'],'interface-review');freeze.assert_not_called();prove.assert_not_called()

    def test_pass_is_read_back_before_freeze_and_proof_dispatch(self):
        author,inputs=self.setup_gate('corrected-interface');events=[]
        contract=ir.load(inputs/'contract.json');contract['premises'][0]['type']='p'
        ir.write(inputs/'contract.json',contract)
        plan=ir.load(inputs/'plan.json');plan['contract_sha256']=ir.digest(inputs/'contract.json');ir.write(inputs/'plan.json',plan)
        def record(event):
            def call(*a,**k):events.append(event)
            return call
        with patch.object(review,'prepare'),patch.object(review,'run',side_effect=record('fresh review')),\
                patch.object(review,'collect',return_value={'all_checks_passed':True}),\
                patch.object(review,'verify_receipt',side_effect=record('actual receipt')) as verify,\
                patch.object(workflow,'freeze',side_effect=record('freeze')),patch.object(workflow,'bound',return_value={}),\
                patch.object(full,'prove_with_repair',side_effect=StageFailure('OFFLINE_CONTROL','Reached proof dispatch')):
            with self.assertRaisesRegex(StageFailure,'Reached proof dispatch'):
                full.from_interface('neutral',inputs,author,author.parent/'good-flow',concurrency.serial_budget(),
                    lambda *a,**k:None,proof_budget=SimpleNamespace(configuration={'requested':1}))
        self.assertEqual(events,['fresh review','actual receipt','freeze']);verify.assert_called_once()

    def receipt(self,name):
        import shutil
        out=self.root/name;inputs=out/'inputs';inputs.mkdir(parents=True)
        original=self.root/'controls/different-carriers/inputs'
        for file in original.iterdir():shutil.copyfile(file,inputs/file.name)
        checks={key:{'verdict':'PASS','notes':'Synthetic validator fixture; no reviewer was called.',
            'locations':[{'document':'spec.json','pointer':'/conclusion'},
                         {'document':'contract.json','pointer':'/conclusion/type'}]} for key in workflow.INTERFACE_CHECKS}
        ir.write(out/'bindings.json',{'author':str(out/'author'),'adjudication':None,
            'contract':bind(inputs/'contract.json'),'plan':bind(inputs/'plan.json'),
            'source_graph':bind(inputs/'nl0.json'),'spec':bind(inputs/'spec.json'),
            'paragraph_mapping':{'S001':{'inference':'R001','paragraph':'S001'}},'source_outputs':{'P':'T001'}})
        ir.write(out/'stage/accepted.json',{'checks':checks,'findings':[]})
        ir.write(out/'stage/result.json',{'status':'ACCEPTED','model':__import__('run_pilot').MODEL,
            'execution_health':'NO_RECORDED_FAULT','temporary_workspace_removed':True,'isolation_violation':False,
            'usage':{'complete':False},'exposure':{'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED',
                'actual_model_ids':[__import__('run_pilot').MODEL],'standard_tier_verified':True}})
        for name in ['exposure-audit.json','execution-manifest.json']:ir.write(out/'stage'/name,{'fixture':'synthetic only'})
        review.collect(out)
        return out,inputs

    def test_hash_bound_actual_receipt_is_distinct_from_forged_or_stale_pass_wrapper(self):
        out,inputs=self.receipt('receipt')
        def verify():return review.verify_receipt(out/'review.json',inputs/'contract.json',inputs/'plan.json',ir.digest(inputs/'nl0.json'))
        value=verify();self.assertTrue(value['reviewer']['independent'])
        original=copy.deepcopy(value)
        value['reviewer']['independent']=False;ir.write(out/'review.json',value)
        with self.assertRaises(ValueError):verify()
        ir.write(out/'review.json',original)
        raw=ir.load(out/'stage/accepted.json');raw['checks']['source_route_and_coverage']['verdict']='UNVERIFIED'
        ir.write(out/'stage/accepted.json',raw)
        with self.assertRaises(ValueError):verify()

    def test_receipt_from_different_formal_types_does_not_unlock_reuse(self):
        out,inputs=self.receipt('stale-receipt');contract=ir.load(inputs/'contract.json')
        contract['header']+='def neutralChanged : Nat := 1\n';ir.write(inputs/'contract.json',contract)
        with self.assertRaisesRegex(ValueError,'stale'):
            review.verify_receipt(out/'review.json',inputs/'contract.json',inputs/'plan.json',ir.digest(inputs/'nl0.json'))

    def test_relabeling_wrapper_hashes_does_not_rebind_earlier_actual_review(self):
        out,inputs=self.receipt('relabeled-receipt');new=self.root/'unreviewed.json'
        value=ir.load(inputs/'contract.json');value['header']+='def anotherNeutral : Nat := 2\n';ir.write(new,value)
        wrapper=ir.load(out/'review.json');wrapper['contract_sha256']=ir.digest(new);ir.write(out/'review.json',wrapper)
        with self.assertRaisesRegex(ValueError,'stale'):
            review.verify_receipt(out/'review.json',new,inputs/'plan.json',ir.digest(inputs/'nl0.json'))

    def test_repaired_definition_can_reuse_only_as_candidate_after_new_actual_review_and_recheck(self):
        import shutil
        import proof_reuse
        out,inputs=self.receipt('definition-repair-receipt');plan=ir.load(inputs/'plan.json')
        previous=self.root/'prior-definition-round';shutil.copytree(inputs,previous/'inputs')
        oldc=previous/'inputs/contract.json';old=ir.load(oldc)
        old['header']+='def neutralOldDefinition : Nat := 1\n';ir.write(oldc,old)
        oldplan=ir.load(previous/'inputs/plan.json');oldplan['contract_sha256']=ir.digest(oldc)
        ir.write(previous/'inputs/plan.json',oldplan)
        body='exact h_H002 h_H001'
        ir.write(previous/'report.json',{'status':'FRAGMENT_ASSEMBLED','contract_sha256':ir.digest(oldc)})
        ir.write(previous/'proofs.json',{'contract_sha256':ir.digest(oldc),
            'plan_sha256':ir.digest(previous/'inputs/plan.json'),'proofs':{'T001':body}})
        self.assertIsNone(proof_reuse.candidate(previous,inputs/'contract.json',plan,'T001'))
        candidate=proof_reuse.candidate(previous,inputs/'contract.json',plan,'T001',reviewed_interface=out/'review.json')
        self.assertEqual(candidate['body'],body);self.assertIn('current native recheck',candidate['scope'])
        checked=ir.check(inputs/'contract.json',plan,{'T001':candidate['body']},only='T001')
        self.assertEqual(checked['exit_code'],0)
        changed=ir.load(out/'review.json');changed['reviewer']['independent']=False;ir.write(out/'review.json',changed)
        with self.assertRaises(ValueError):
            proof_reuse.candidate(previous,inputs/'contract.json',plan,'T001',reviewed_interface=out/'review.json')

    def test_frozen_interface_defect_waits_for_user_without_new_author_attempt(self):
        import case_runner
        root=self.root/'case';source=root/'source';source.mkdir(parents=True)
        authority={'graph':str(source/'nl0.json')};calls=[]
        prior=root/'nl0-to-lean/0001/interface/stage/accepted.json';ir.write(prior,{'interface':'old'})
        oldrun=root/'nl0-to-lean/0001/workflow/proof-run';summary=root/'diagnosis.json'
        ir.write(summary,{'source_unchanged':True,'diagnoses':{'T001':{'route':'INTERFACE_REPAIR_REQUIRED'}}})
        def translate(*args,**kwargs):
            calls.append(kwargs)
            if len(calls)==1:
                raise StageFailure('FROZEN_INTERFACE_REQUIRES_USER','Neutral located mismatch',phase='frozen-interface',
                    evidence=summary,details={'prior_proof_run':str(oldrun)})
            ir.write(root/'nl0-to-lean/0002/audit-b-review/review.json',{'fixture':'control only'})
            return {'status':'WORKFLOW-PASSED'} # Stub result only, never a scientific outcome.
        budgets=SimpleNamespace(serial=None,proof=None)
        with patch.object(case_runner.source_refactor,'run',return_value=authority),\
                patch.object(full,'translate',side_effect=translate):
            with self.assertRaises(StageFailure) as error:
                case_runner.translation_work({'root':str(root),'case':'neutral','policy':'normal'},authority,budgets,lambda *a,**k:None)
        self.assertEqual(len(calls),1);self.assertEqual(error.exception.result['phase'],'frozen-interface')
        self.assertEqual(ir.load(prior),{'interface':'old'})

    def test_located_incomplete_review_routes_to_repair_without_becoming_full_pass(self):
        author,inputs=self.setup_gate('incomplete-review');out=author.parent/'incomplete-flow'
        ir.write(out.parent/'interface-review/stage/accepted.json',{'status':'REVIEW_BLOCKED_INCOMPLETE','fixture':'located defect'})
        blocked=StageFailure('MATHEMATICAL_REVIEW_FAILED','Located synthetic semantic defect',
            details={'record_context_qualified':True})
        with patch.object(review,'prepare'),patch.object(review,'run'),patch.object(review,'collect',side_effect=blocked),\
                patch.object(workflow,'freeze') as freeze:
            with self.assertRaises(StageFailure) as error:
                full.from_interface('neutral',inputs,author,out,concurrency.serial_budget(),lambda *a,**k:None,
                    proof_budget=SimpleNamespace(configuration={'requested':1}))
        self.assertEqual(error.exception.result['phase'],'interface-review');freeze.assert_not_called()
        report=ir.load(out.parent/'interface-review/report.json')
        self.assertFalse(report['all_checks_passed']);self.assertEqual(report['review_coverage'],'INCOMPLETE')


if __name__=='__main__':unittest.main()
