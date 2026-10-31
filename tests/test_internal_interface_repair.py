"""Deterministic internal-revision controls, separate from mathematical verdicts."""
import harness_support
import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import case_runner
import concurrency
import full_workflow
import internal_interface_repair as repair
import ir
from controller_common import write
from execution_health import StageFailure


class InternalInterfaceRepairTests(unittest.TestCase):
    def test_real_lean_delta_revision_reuse_and_machine_final_acceptance(self):
        import audit_b, final_acceptance, final_acceptance_fixtures as fixture
        import interface_review, translation_author, workflow, run_graph, proof_reuse
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);baseline=fixture.frozen_case(root/'baseline')
            parent=workflow.bound(baseline);context=repair.context(baseline)
            import shared_lemmas
            prior_report=ir.load(baseline/'proof-run/report.json')
            prior_report.update(contract_sha256=ir.digest(baseline/'proof-run/inputs/contract.json'),
                plan_digest=shared_lemmas.hashed(ir.load(baseline/'proof-run/inputs/plan.json')))
            ir.write(baseline/'proof-run/report.json',prior_report)
            source=Path(parent['authority']['graph']).parent
            author=root/'revision/interface'
            prior=root/'baseline/author/stage/accepted.json'
            translation_author.prepare(source,source,author,authority=parent['authority'],
                prior_interface=prior,diagnostics={'internal_repair':context})
            value=ir.load(prior);value['steps'][0]['statement']='@Eq ℕ b a'
            validator=translation_author.InterfaceContract(author)
            bad=copy.deepcopy(value);bad['premise_types']['H001']='True'
            with self.assertRaisesRegex(ValueError,'T steps only'):validator(bad)
            validator(value);fixture.qualified_artifact(author/'stage',value)
            reviewed=root/'revision/interface-review';interface_review.prepare(author,reviewed)
            self.assertIn('INTERNAL_INTERFACE_DELTA',(reviewed/'prompt.txt').read_text())
            checks={key:{'verdict':'PASS','notes':'SYNTHETIC unchanged public contract; delta is notation for the same equality.',
                'locations':[{'document':'spec.json','pointer':'/full_target'},
                             {'document':'plan.json','pointer':'/steps/0/statement'}]} for key in workflow.INTERFACE_CHECKS}
            fixture.qualified_artifact(reviewed/'stage',{'checks':checks,'findings':[]})
            interface_review.collect(reviewed);paths=ir.load(author/'accepted-interface-paths.json')
            receipt=interface_review.verify_receipt(reviewed/'review.json',paths['contract'],paths['plan'],ir.digest(source/'nl0.json'))
            self.assertEqual(receipt['review_scope'],'INTERNAL_INTERFACE_DELTA')
            self.assertEqual(receipt['internal_repair']['affected_steps'],['T001','T002'])
            out=root/'revision/workflow'
            manifest=workflow.freeze(**parent['authority'],contract=paths['contract'],plan=paths['plan'],
                interface_review=reviewed/'review.json',out=out,max_concurrency=1)
            previous=proof_reuse.candidate(baseline/'proof-run',manifest['contract'],ir.load(manifest['plan']),
                'T001',reviewed_interface=reviewed/'review.json')
            self.assertIsNotNone(previous)
            proof=out/'proof-run';proof.mkdir();cp,_=run_graph.package(Path(manifest['contract']),Path(manifest['plan']),proof)
            bodies={'T001':previous['body'],'T002':'simpa only [Nat.add_zero] using h_T001.symm'}
            checked=ir.check(cp,ir.load(proof/'inputs/plan.json'),bodies)
            self.assertEqual(checked['exit_code'],0,checked['stdout'])
            ir.write(proof/'proofs.json',{'contract_sha256':ir.digest(cp),'plan_sha256':ir.digest(proof/'inputs/plan.json'),'proofs':bodies})
            ir.write(proof/'report.json',{'status':'FRAGMENT_ASSEMBLED','concurrency':{'requested':1},'runner_wall_seconds':0})
            fixture.build(out);final_acceptance.finish(out)
            self.assertEqual(audit_b.check(out/'audit-b',out/'audit-b/machine-acceptance.json')['status'],'AUDIT-B-PASSED')
            modified=ir.load(reviewed/'review.json');modified['internal_repair']['affected_steps']=[]
            ir.write(reviewed/'review.json',modified)
            with self.assertRaises(ValueError):audit_b.check(out/'audit-b',out/'audit-b/machine-acceptance.json')

    def test_only_internal_steps_can_change(self):
        prior={'header':'fixed','parameters':[], 'premise_types':{'H001':'True'},
               'conclusion_type':'True','steps':[{'id':'T001','statement':'old'}]}
        updated=copy.deepcopy(prior);updated['steps'][0]['statement']='new'
        repair.protect_candidate(updated,prior)
        for field in ['header','parameters','premise_types','conclusion_type']:
            bad=copy.deepcopy(updated);bad[field]='changed'
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'T steps only'):
                repair.protect_candidate(bad,prior)
        with self.assertRaisesRegex(ValueError,'unchanged candidate'):repair.protect_candidate(prior,prior)

    def test_impact_uses_both_old_and_new_dependency_graphs(self):
        old={'steps':[{'id':'T001','statement':'old','inputs':[]},
             {'id':'T002','statement':'same','inputs':['T001']},
             {'id':'T003','statement':'same','inputs':['T002']},
             {'id':'T004','statement':'unrelated','inputs':[]}]}
        new=copy.deepcopy(old);new['steps'][0]['statement']='new';new['steps'][1]['inputs']=[]
        self.assertEqual(repair.delta(old,new),{'changed_steps':['T001','T002'],'affected_steps':['T001','T002','T003']})

    def test_protected_contract_and_source_cannot_change(self):
        old={k:k for k in repair.PROTECTED};old['source']={'sha256':'fixed'}
        with patch.object(ir,'contract',side_effect=[old,copy.deepcopy(old)]):
            repair.verify_contract({'contract':{'path':'old'}},'new')
        for field in repair.PROTECTED:
            new=copy.deepcopy(old);new[field]='modified'
            with self.subTest(field=field),patch.object(ir,'contract',side_effect=[old,new]),self.assertRaises(ValueError):
                repair.verify_contract({'contract':{'path':'old'}},'new')

    def test_internal_diagnosis_returns_to_preprocessing_after_handoff(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);proof={'status':'GRAPH_REPAIR_REQUIRED','repair_requests':{'T001':{}},'jobs':[]}
            write(root/'contract.json',{'shared_obligations':[]})
            def run(c,p,out,**kw):write(out/'report.json',proof);return proof
            with patch('run_graph.run',side_effect=run),patch.object(full_workflow.workflow,'bound'),\
                 patch.object(full_workflow,'stage_seconds',return_value=None),\
                 patch('proof_diagnosis.run',return_value={'route':'INTERNAL_INTERFACE_REPAIR'}),\
                 patch.object(repair,'context',return_value={'schema':repair.SCHEMA}):
                with self.assertRaises(StageFailure) as error:
                    full_workflow.prove_with_repair('neutral',{'contract':str(root/'contract.json'),'plan':'p'},root/'workflow',
                        root/'interface',SimpleNamespace(execution=None),None,lambda *a,**kw:None)
            self.assertEqual(error.exception.result['phase'],'internal-interface-repair')
            self.assertTrue((root/'workflow/diagnoses/0001/report.json').exists())

    def test_case_loop_preserves_repair_authority_through_rejected_review(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);authority={'graph':str(root/'source/nl0.json'),'spec':'spec','audit_a':'audit'}
            context={'schema':repair.SCHEMA,'fixture':'bound parent'};calls=[];managers=[]
            def translate(case,source,interface,destination,budget,progress,**kw):
                calls.append(kw);managers.append(kw['sessions']);write(interface/'stage/accepted.json',{'fixture':'own candidate'})
                if len(calls)==1:
                    evidence=destination/'diagnoses/0001/report.json';write(evidence,{'fixture':'internal diagnosis'})
                    raise StageFailure('INTERNAL_INTERFACE_REPAIR_REQUIRED','neutral internal defect',
                        phase='internal-interface-repair',evidence=evidence,
                        details={'internal_repair':context,'prior_proof_run':str(destination/'proof-run')})
                self.assertEqual(kw['diagnostics']['internal_repair'],context)
                self.assertIsNotNone(kw['prior_run'])
                if len(calls)==2:
                    write(interface.parent/'interface-review/report.json',{'all_checks_passed':False})
                    write(interface.parent/'interface-review/stage/accepted.json',{'findings':['fix internal input']})
                    raise StageFailure('INTERFACE_REVIEW_FAILED','neutral finding',phase='interface-review')
                receipt=destination/'audit-b/machine-acceptance.json';write(receipt,{'fixture':'not a scientific verdict'})
                return {'status':'WORKFLOW-PASSED','audit_b':{'status':'AUDIT-B-PASSED','receipt_path':str(receipt),'acceptance_basis':'SYNTHETIC_TEST_ONLY'}}
            with patch.object(case_runner.source_refactor,'run',return_value=authority),\
                 patch.object(case_runner.f,'translate',side_effect=translate):
                result=case_runner.translation_attempt({'root':str(root),'case':'neutral','policy':'normal'},
                    authority,concurrency.CaseBudgets(2),lambda *a,**kw:None)
            self.assertEqual(len(calls),3);self.assertTrue(all(m is managers[0] for m in managers))
            self.assertEqual(result['audit_b']['acceptance_basis'],'SYNTHETIC_TEST_ONLY')
            self.assertTrue((root/'nl0-to-lean/0001/workflow/diagnoses/0001/report.json').exists())


if __name__=='__main__':unittest.main()
