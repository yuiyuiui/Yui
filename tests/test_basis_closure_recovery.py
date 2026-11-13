"""Actual native final-only recovery and hostile recovery-boundary controls."""
import harness_support
from pathlib import Path
from copy import deepcopy
import tempfile
import os
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from basis_fixtures import artifact,dependency,checked_context,TARGET
from final_acceptance_fixtures import frozen_case,build
from test_b2lean import attach
from controller_common import bind,write,manifest
import basis
import basis_native
import basis_closure_recovery as recovery
import b2lean
import case_runner
import ir
import jobs
import delivery
import cleanup
import owner_observation
import target_selection
import workflow


class FinalOnlyRecovery(unittest.TestCase):
    def setUp(self):
        import fault_control
        guard=patch.object(fault_control.Gate,'pause',side_effect=lambda error,**kwargs:
                           self.fail('Unexpected retained pause: '+json.dumps(error,default=str)))
        guard.start();self.addCleanup(guard.stop)

    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.base=Path(cls.temp.name).resolve()
        problem=cls.base/'proof.md';problem.write_bytes((harness_support.FIXTURES/'closed-addition/problem.txt').read_bytes())
        cls.old=jobs.prepare(problem,track='full',formalization='unconditional',profiles=harness_support.PROFILES,
            target=target_selection.resolve(problem,requested=TARGET),output=cls.base/'prior')
        cls.root=Path(cls.old['root'])
        value=artifact(dependency(category=2,typ='∀ (A : Type u) (B : Type v), True',proof='intro A B; trivial'))
        value['lean_header']+='universe u v\n'
        cls.context=checked_context(cls.root/'2basis/0001',value,documents=cls.root/'inputs')
        active=cls.root/'active-inputs';write(active/basis.CONTEXT,cls.context);manifest(active)
        write(cls.root/'basis-selection.json',{'context':bind(active/basis.CONTEXT),'inputs':bind(active/'inputs.json')})
        def transform(payload):
            payload['header']=value['lean_header'];payload['premise_types']['E001']=value['dependencies'][0]['lean']['type']
            payload['steps'][-1]['inputs'].append('E001')
            payload['endpoint_correspondence']['E001']={'mode':'direct','explanation':'Synthetic polymorphic proposition.'}
        cls.workflow=frozen_case(cls.root/'nl0-to-lean/0001',prepare_source=lambda s:attach(s,cls.context),
            transform_interface=transform,bodies={'T001':'exact h_H001.symm',
                'T002':'have h := h_E001 (ULift.{u} Unit) (ULift.{v} Unit)\ncases h\nsimpa only [Nat.add_zero] using h_T001.symm'})
        build(cls.workflow);cls.intermediate=workflow.finish(cls.workflow,machine=True)
        frozen=workflow.bound(cls.workflow)
        source,expected,_=b2lean.render(ir.contract(frozen['contract']),cls.context,
            (cls.workflow/'audit-b/Proof.lean').read_text(),ir.load(cls.workflow/'audit-b/assembly.json')['universe_parameters'],legacy=True)
        native=basis_native.check(source,[('P','YuiClosed.P',expected)],['YuiClosed.P'],cls.root/'b2lean')
        assert not native['passed']
        cls.failure={'status':'BASIS_FINAL_CLOSURE_FAILED','phase':'basis-final-closure',
            'evidence':str(cls.root/'b2lean/check.json'),'errors':native['errors']}
        write(cls.root/'case-result.json',{'result':{'status':'CANCELLED','retained_error':cls.failure,
            'usage':{'status':'PARTIAL','confirmed_tokens':1234}}})
        write(cls.root/'execution-status.json',{'controller':{'pid':99999991,'pgid':99999991,'started':'synthetic exited'},
            'processes':{},'tasks':{}})

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_real_owned_case_repeats_only_native_closure(self):
        before={p:ir.digest(p) for p in self.root.rglob('*') if p.is_file()}
        import runtime_config
        from contextlib import nullcontext
        selected=os.environ.get('YUI_TEST_ALTERNATE_ENVIRONMENT')
        context=(runtime_config.use_environment(ir.load(selected)) if selected else nullcontext())
        with context:job=recovery.prepare(self.root)
        self.assertEqual(job['lean_environment'],self.old['lean_environment'])
        with patch.object(basis,'run',side_effect=AssertionError('unexpected basis author')) as author, \
                patch.object(case_runner,'nl0_work',side_effect=AssertionError('unexpected NL0')) as nl0, \
                patch.object(case_runner,'translation_work',side_effect=AssertionError('unexpected proof generation')) as lean:
            result=case_runner.execute(job)
        author.assert_not_called();nl0.assert_not_called();lean.assert_not_called()
        self.assertEqual(result['status'],'WORKFLOW-PASSED')
        self.assertTrue(result['completion']['acceptance_target_satisfied'])
        self.assertEqual(delivery.verify(Path(job['root'])/'delivery')['scope'],'UNCONDITIONAL_LEAN')
        out=Path(job['root']);b2lean.validate_receipt(out/'b2lean');jobs.validate(job)
        self.assertFalse(result['recovery']['new_model_calls'])
        self.assertEqual(ir.load(out/'closure-recovery.json')['prior_case_result'],bind(self.root/'case-result.json'))
        self.assertEqual(before,{p:ir.digest(p) for p in self.root.rglob('*') if p.is_file()})
        self.assertFalse((out/'nl0-to-lean').exists())
        with self.assertRaisesRegex(ValueError,'Preserve this run'):case_runner.execute(job)

    def test_recovered_native_delivery_survives_owned_cleanup_and_standalone_readback(self):
        code=("import sys;sys.path.insert(0,"+repr(str(harness_support.TESTS))+ ");import harness_support;"
              "import basis_closure_recovery as r,case_runner,json,fault_control;"
              "fault_control.Gate.pause=lambda self,error,**kwargs:(_ for _ in ()).throw(AssertionError(json.dumps(error,default=str)));"
              "job=r.prepare("+repr(str(self.root))+");result=case_runner.execute(job);"
              "print(json.dumps({'root':job['root'],'result':result}))")
        child=subprocess.run([sys.executable,'-B','-c',code],text=True,capture_output=True,timeout=150)
        self.assertEqual(child.returncode,0,(child.stdout+child.stderr)[-5000:])
        value=json.loads(child.stdout);root=Path(value['root'])
        self.assertTrue(value['result']['completion']['workflow_completed'])
        anchor=delivery.finalization_anchor(root)
        record=ir.load(root/'delivery/run.json')
        self.assertEqual(record['recovery']['prior_observed_usage']['confirmed_tokens'],1234)
        result=cleanup.clean(apply=True,grace=0,outputs=[root])
        self.assertEqual(result['status'],'CLEANED',result)
        self.assertEqual({p.name for p in root.iterdir()},{'delivery'})
        self.assertEqual(delivery.verify(root/'delivery',anchor=anchor)['scope'],'UNCONDITIONAL_LEAN')
        self.assertTrue((self.root/'case-result.json').is_file())

    def test_packaging_retry_reuses_the_checked_native_closure(self):
        import fault_control
        original=delivery.publish
        calls=[];writes=[];original_write=delivery.write
        def storage(path,value):
            if Path(path).name in {'delivery-input.json','pending-delivery.json'} and Path(path).name not in writes:
                writes.append(Path(path).name);raise OSError('Synthetic checkpoint storage interruption')
            return original_write(path,value)
        def flaky(*args,**kwargs):
            calls.append(True)
            if len(calls)==1:raise OSError('Synthetic publication storage interruption')
            return original(*args,**kwargs)
        job=recovery.prepare(self.root)
        with patch.object(delivery,'publish',side_effect=flaky),patch.object(delivery,'write',side_effect=storage), \
                patch.object(fault_control.Gate,'pause',return_value=None) as pause, \
                patch.object(b2lean,'finish',wraps=b2lean.finish) as native:
            result=case_runner.execute(job)
        self.assertTrue(result['completion']['workflow_completed'],result)
        self.assertEqual(native.call_count,1);self.assertEqual(len(calls),2)
        self.assertEqual(writes,['delivery-input.json','pending-delivery.json']);self.assertEqual(pause.call_count,2)
        self.assertTrue(pause.call_args.kwargs['resumable'])
        self.assertFalse((Path(job['root'])/'pending-delivery.json').exists())
        delivery.verify(Path(job['root'])/'delivery')

    def test_cancelled_packaging_preserves_proof_without_claiming_workflow_completion(self):
        import execution_state
        import fault_control
        job=recovery.prepare(self.root)
        with patch.object(delivery,'publish',side_effect=OSError('Synthetic publication failure')), \
                patch.object(fault_control.Gate,'pause',side_effect=execution_state.Cancelled('Explicit packaging stop')), \
                patch.object(b2lean,'finish',wraps=b2lean.finish) as native:
            result=case_runner.execute(job)
        self.assertEqual(native.call_count,1)
        self.assertEqual(result['status'],'CANCELLED')
        self.assertFalse(result['completion']['workflow_completed'])
        root=Path(job['root']);pending=ir.load(root/'pending-delivery.json')
        self.assertEqual(pending['proof_component_status'],'WORKFLOW-PASSED')
        self.assertFalse(pending['workflow_completed'])
        b2lean.validate_receipt(root/'b2lean')

    def test_failed_recovery_pauses_then_cancels_without_false_success(self):
        import execution_state
        import fault_control
        from execution_health import StageFailure
        job=recovery.prepare(self.root)
        failure=StageFailure('BASIS_FINAL_CLOSURE_FAILED','synthetic native failure',phase='basis-final-closure')
        with patch.object(b2lean,'finish',side_effect=failure), \
                patch.object(fault_control.Gate,'pause',side_effect=execution_state.Cancelled('explicit fixture cancellation')) as pause:
            result=case_runner.execute(job)
        self.assertEqual(result['status'],'CANCELLED')
        self.assertEqual(result['retained_error']['status'],'BASIS_FINAL_CLOSURE_FAILED')
        self.assertFalse(pause.call_args.kwargs['resumable'])
        self.assertFalse(result['completion']['acceptance_target_satisfied'])
        self.assertFalse((Path(job['root'])/'b2lean/report.json').exists())

    def test_live_owner_child_group_pending_error_or_os_failure_blocks(self):
        for exited,terminal in ((False,True),(True,False),(False,False)):
            with self.subTest(exited=exited,terminal=terminal),patch.object(owner_observation,'snapshot',
                    return_value={'all_process_exits_verified':exited,'all_terminal':terminal}):
                with self.assertRaisesRegex(ValueError,'Cancel the prior'):recovery.qualify(self.root)

    def test_unrelated_or_missing_failed_evidence_is_rejected(self):
        path=self.root/'case-result.json';original=path.read_bytes()
        for change in ({'status':'EXECUTION_FAULT'},{'evidence':'/missing/check.json'},{'errors':[]},{'phase':'proof'}):
            try:
                value=ir.load(path);value['result']['retained_error'].update(change);write(path,value)
                with self.subTest(change=change),self.assertRaises(ValueError):recovery.qualify(self.root)
            finally:path.write_bytes(original)

    def test_changed_proof_basis_receipt_and_original_document_are_rejected(self):
        for path in (self.workflow/'audit-b/Proof.lean',Path(self.context['basis']['path']),
                self.workflow/'audit-b/machine-acceptance.json',Path(self.old['problem']),self.root/'b2lean/compiler.json'):
            original=path.read_bytes()
            try:
                path.write_bytes(original+b'\n')
                with self.subTest(path=path),self.assertRaises(ValueError):recovery.qualify(self.root)
            finally:path.write_bytes(original)

    def test_changed_recovery_scope_and_missing_bound_evidence_are_rejected(self):
        job=recovery.prepare(self.root)
        for change in ({'max_concurrency':5},{'formalization':'conditional'},
                {'root':str(self.root)},{'authority_bindings':[]},{'time_budget_seconds':60}):
            bad=deepcopy(job);bad.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):recovery.validate_descriptor(bad)

    def test_cli_prepares_only_the_explicit_final_recovery(self):
        import entrypoint
        import argparse
        parser=argparse.ArgumentParser();entrypoint.parsers(parser.add_subparsers(dest='command',required=True))
        args=parser.parse_args(['resume',str(self.root),'--repair-basis-closure','--prepare-only'])
        with patch.object(recovery,'prepare',return_value={'root':'synthetic-new-run'}) as prepare:
            result=entrypoint.dispatch(args)
        prepare.assert_called_once_with(self.root)
        self.assertEqual(result['status'],'PREPARED_NOT_STARTED')


if __name__=='__main__':unittest.main()
