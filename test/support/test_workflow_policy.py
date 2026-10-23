"""End-to-end wiring controls with mocked model gates, never exercise passes."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import audit_a_campaign as a
import case_runner
import full_workflow as f
from execution_health import StageFailure
import execution_state as e


class WorkflowPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.results=self.root/'test/results';self.results.mkdir(parents=True)
        self.source=self.results/'source';self.source.mkdir()
        for name in ['spec.json','nl0.json']:(self.source/name).write_text('{}')

    def tearDown(self):self.tmp.cleanup()

    def test_case_owner_passes_serial_and_proof_budgets_separately(self):
        job={'kind':'translate','case':'neutral','source':'source','interface':'typed','workflow':'frozen','max_concurrency':5}
        def translate(case,source,interface,workflow,budget,progress,*,proof_budget):
            self.assertEqual(budget.configuration['effective'],1)
            self.assertEqual(proof_budget.configuration['effective'],5)
            self.assertIs(budget.execution,proof_budget.execution)
            with budget:pass
            with proof_budget:pass
            return {'status':'SYNTHETIC_CONTROL_ONLY_NOT_A_MATHEMATICAL_PASS'}
        with patch.object(a,'ROOT',self.root),patch.object(f,'translate',side_effect=translate):
            case_runner.execute(job,self.root/'run')
        row=json.loads((self.root/'run/case-result.json').read_text())
        self.assertEqual(row['concurrency']['proof']['effective'],5)
        self.assertEqual(row['concurrency']['preparation_review']['effective'],1)
        self.assertFalse(e.inspect(self.root/'run')['inspection']['residual_owned_processes'])

    def test_freeze_and_runner_receive_five_not_the_serial_limit(self):
        review=self.results/'typed-review';review.mkdir()
        contract=self.results/'contract.json';contract.write_text('{"shared_obligations":[]}')
        plan=self.results/'plan.json';plan.write_text('{}')
        copied=self.results/'interface-inputs';copied.mkdir()
        for name in ['nl0.json','spec.json']:(copied/name).write_bytes((self.source/name).read_bytes())
        a.write(review/'bindings.json',{'source_graph':a.bind(copied/'nl0.json'),'spec':a.bind(copied/'spec.json'),
                                     'contract':a.bind(contract),'plan':a.bind(plan)})
        recorder=e.Recorder(self.root/'execution','neutral',a.concurrency.resolve(5))
        budgets=a.concurrency.CaseBudgets(5,execution=recorder)
        try:
            with patch.object(a,'ROOT',self.root),patch.object(f.interface_review,'prepare'),patch.object(f.interface_review,'run'),\
                 patch.object(f.interface_review,'collect',return_value={'all_checks_passed':True}),\
                 patch.object(f.workflow,'freeze') as freeze,\
                 patch.object(f.workflow,'bound',return_value={'contract':str(contract),'plan':str(plan)}),\
                 patch.object(f.run_graph,'run',return_value={'status':'SYNTHETIC_UNFINISHED'}) as run:
                with self.assertRaises(StageFailure) as failed:
                    f.from_interface('neutral',self.source,'typed','frozen',budgets.serial,lambda *args,**kwargs:None,proof_budget=budgets.proof)
                self.assertEqual(failed.exception.result['phase'],'proof')
                self.assertEqual(freeze.call_args.kwargs['max_concurrency'],5)
                self.assertIs(run.call_args.kwargs['budget'],budgets.proof)
                freeze.reset_mock();(copied/'nl0.json').write_text('{"changed":true}')
                with self.assertRaisesRegex(ValueError,'exact source bytes'):
                    f.from_interface('neutral',self.source,'typed','frozen',budgets.serial,lambda *args,**kwargs:None,proof_budget=budgets.proof)
                freeze.assert_not_called()
        finally:recorder.close('SYNTHETIC_CONTROL_ONLY')

    def test_unchanged_accepted_source_does_not_launch_a_new_audit(self):
        (self.source/'audit-a.json').write_text('{}')
        with patch.object(a.nl0,'validate',return_value=({'current_standard_receipt_valid':True,'audit_status':'SYNTHETIC_ONLY'},)),\
             patch.object(a,'prepare') as prepare,patch.object(a,'run') as run,patch.object(a,'collect') as collect:
            result=f.audit_source('neutral',self.source,'new-audit',None,lambda *args,**kwargs:None)
        self.assertTrue(result['reused_unchanged_acceptance'])
        prepare.assert_not_called();run.assert_not_called();collect.assert_not_called()


if __name__=='__main__':unittest.main()
