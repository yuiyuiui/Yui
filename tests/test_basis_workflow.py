"""Full-route wiring and basis author lifecycle; model judgments are deterministic fixtures."""
import harness_support
from basis_fixtures import artifact, dependency, TARGET
from final_acceptance_fixtures import qualified_artifact
from copy import deepcopy
from contextlib import ExitStack
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import basis
import basis_author
import b2lean
import case_runner
import clean_stage
import execution_state
from execution_health import StageFailure
import fault_control
import jobs
import ir
import role_sessions
import target_selection
from controller_common import bind,write,manifest
from harness_support import PROFILES


class BasisAuthorWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.problem=self.root/'proof.md';self.problem.write_text(TARGET)
        selected=target_selection.resolve(self.problem,requested=TARGET)
        self.job=jobs.prepare(self.problem,track='full',profiles=PROFILES,
            formalization='unconditional',target=selected)
        self.run=Path(self.job['root']);self.progress=[]
    def tearDown(self):self.temp.cleanup()

    def author(self,values):
        called=[];iterator=iter(values)
        class LocalStage:
            def __init__(own,logs,prompt,**kwargs):
                own.logs=Path(logs);own.logs.mkdir(parents=True);own.validator=kwargs['validator']
                own.prompt=prompt;own.inputs=Path(kwargs['inputs'])
            def execute(own):
                called.append({'role':role_sessions.current()[1],'inputs':own.inputs,'prompt':own.prompt})
                value=next(iterator);own.validator(value)
                qualified_artifact(own.logs,value)
                return ir.load(own.logs/'result.json'),value
        return patch.object(basis_author,'BasisStage',LocalStage),called

    def run_basis(self):
        return basis.run(self.job,None,lambda *args,**kwargs:self.progress.append((args,kwargs)))

    def test_original_inputs_are_immutable_and_basis_is_staged_once(self):
        inputs=self.run/'inputs';before={p.name:p.read_bytes() for p in inputs.iterdir()}
        author,calls=self.author([artifact(dependency(),dependency('B002',3))])
        with author:context=self.run_basis()
        self.assertEqual(before,{p.name:p.read_bytes() for p in inputs.iterdir()})
        active=basis.problem_inputs(self.job)
        self.assertEqual((active/'basis-proof.md').read_text(),artifact()['proof'])
        self.assertEqual(len(calls),1);self.assertEqual(calls[0]['role'],'basis-author')
        self.assertIn('problem.md',{r['id'] for r in ir.load(active/'inputs.json')['inputs']})
        self.assertEqual(context['full_target'],TARGET)

    def test_continue_reuses_prior_basis_and_role_without_audit(self):
        author,calls=self.author([artifact(dependency(category=4)),artifact(dependency())])
        chosen={'control':{'action':'continue'}}
        with author,patch.object(basis,'decision',side_effect=[chosen,None]) as decide:
            context=self.run_basis()
        self.assertEqual(len(calls),2);self.assertEqual(decide.call_count,2)
        self.assertEqual(calls[0]['role'],calls[1]['role'])
        self.assertTrue((calls[1]['inputs'].parent/'prior-basis.json').exists())
        self.assertEqual(context['residual_class4'],[])
        self.assertTrue((self.run/'2basis/0001/stage/accepted.json').is_file())

    def test_explicit_stop_never_advances_to_NL0(self):
        author,calls=self.author([artifact(dependency(category=4))])
        with author,patch.object(basis,'decision',return_value={'control':{'action':'stop'}}):
            with self.assertRaises(StageFailure) as caught:self.run_basis()
        self.assertEqual(caught.exception.result['status'],'STOPPED_BY_USER')
        self.assertFalse((self.run/'active-inputs').exists())

    def test_conditional_approval_is_bound_to_exact_retained_artifact(self):
        author,calls=self.author([artifact(dependency(category=4))])
        def approve(out,value,budget):
            return {'state':'USER_DECIDED','incident':'SYNTHETIC exact choice',
                'control':{'incident':'SYNTHETIC exact choice','action':'accept-conditional'},
                'checkpoint':{'basis':bind(out/'stage/accepted.json'),'residual_class4':['B001']}}
        with author,patch.object(basis,'decision',side_effect=approve):context=self.run_basis()
        basis.verify_context(context)
        self.assertEqual(context['residual_class4'],['B001'])
        self.assertTrue(any(p.name.startswith('basis-evidence-') for p in (self.run/'active-inputs').iterdir()))

    def test_operational_recovery_copies_prepared_basis_without_new_author_or_choice(self):
        author,calls=self.author([artifact(dependency())])
        with author:self.run_basis()
        newroot=self.root/'recovered';newroot.mkdir()
        recovered={**self.job,'root':str(newroot),'resume':{'prior_run':str(self.run),'mode':'audit-a'}}
        with patch.object(basis_author,'BasisStage',side_effect=AssertionError('No new basis author')), \
             patch.object(basis,'decision',side_effect=AssertionError('No repeated user choice')):
            basis.run(recovered,None,lambda *args,**kwargs:None)
        self.assertTrue((basis.problem_inputs(recovered)/basis.CONTEXT).is_file())
        self.assertEqual(ir.load(newroot/'active-inputs'/basis.CONTEXT),ir.load(self.run/'active-inputs'/basis.CONTEXT))

    def test_changed_active_target_original_document_and_staging_fail_closed(self):
        author,calls=self.author([artifact()])
        with author:self.run_basis()
        active=basis.problem_inputs(self.job)
        path=active/'basis-proof.md';original=path.read_bytes()
        path.write_text('changed proof')
        with self.assertRaises(ValueError):basis.problem_inputs(self.job)
        path.write_bytes(original)
        changed=deepcopy(self.job);changed['target_selection']['full_target']='True'
        with self.assertRaises(ValueError):basis.problem_inputs(changed)
        changed=deepcopy(self.job);changed['documents'][0]['sha256']='other'
        with self.assertRaises(ValueError):basis.problem_inputs(changed)


class BasisCaseRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.problem=self.root/'proof.md';self.problem.write_text(TARGET)
        self.selection=target_selection.resolve(self.problem,requested=TARGET)
    def tearDown(self):self.temp.cleanup()

    def job(self,mode='unconditional'):
        return jobs.prepare(self.problem,track='full',profiles=PROFILES,formalization=mode,target=self.selection)

    def routed(self,job,*,closure=True,residual=False,stop=None,different=False):
        events=[];run=Path(job['root'])
        authority={'graph':str(run/'source/nl0.json'),'spec':str(run/'source/spec.json'),'audit_a':str(run/'source/audit-a.json')}
        intermediate={'status':'WORKFLOW-PASSED','audit_b':{'receipt_path':str(run/'workflow/audit-b/machine-acceptance.json')}}
        if different:intermediate={'status':'DIFFERENT_RESULT_DELIVERED','audit_b':{},'user_decision':{'action':'deliver-actual'}}
        final={'status':'WORKFLOW-CONDITIONAL' if residual else 'WORKFLOW-PASSED','audit_b':{},
            'closure':{'unconditional':closure and not residual}}
        def begin(*args,**kwargs):
            events.append('basis')
            if stop:raise stop
        def nl0(*args,**kwargs):events.append('shared-A');return authority
        def lean(*args,**kwargs):events.append('shared-Lean-B');return intermediate
        def close(*args,**kwargs):events.append('b2lean');return final
        with ExitStack() as stack:
            for owner,name,side in [(basis,'run',begin),(case_runner,'nl0_work',nl0),
                    (case_runner,'translation_work',lean),(b2lean,'finish',close)]:
                stack.enter_context(patch.object(owner,name,side_effect=side))
            stack.enter_context(patch.object(case_runner,'ir_context',return_value={'test':'context'}))
            stack.enter_context(patch.object(case_runner.source_preparation,'read_source',
                return_value=([{'current_standard_receipt_valid':True}],[])))
            stack.enter_context(patch.object(fault_control.Gate,'pause',side_effect=AssertionError('Unexpected controller pause')))
            if different:
                import translation_reset
                stack.enter_context(patch.object(translation_reset,'authorization',return_value={'scope':'SYNTHETIC user-choice routing control'}))
            result=case_runner.execute(job)
        return events,result

    def test_unconditional_has_one_shared_A_and_one_shared_Lean_B(self):
        events,result=self.routed(self.job())
        self.assertEqual(events,['basis','shared-A','shared-Lean-B','b2lean'])
        self.assertTrue(result['completion']['acceptance_target_satisfied'])

    def test_conditional_default_skips_both_optional_stages(self):
        events,result=self.routed(self.job('conditional'))
        self.assertEqual(events,['shared-A','shared-Lean-B']);self.assertEqual(result['formalization_goal'],'conditional')

    def test_approved_residual_is_complete_conditional_delivery_but_unmet_original_goal(self):
        events,result=self.routed(self.job(),residual=True)
        self.assertEqual(result['status'],'WORKFLOW-CONDITIONAL')
        self.assertTrue(result['completion']['workflow_completed'])
        self.assertFalse(result['completion']['acceptance_target_satisfied'])
        self.assertTrue(result['completion']['follow_up_required'])

    def test_stop_and_cancellation_never_dispatch_later_stages(self):
        for stopped in (StageFailure('STOPPED_BY_USER','explicit user stop'),execution_state.Cancelled('user cancellation')):
            events,result=self.routed(self.job(),stop=stopped)
            self.assertEqual(events,['basis']);self.assertFalse(result['completion']['workflow_completed'])
            self.assertIn(result['status'],{'STOPPED_BY_USER','CANCELLED'})

    def test_user_selected_different_result_does_not_attempt_unconditional_closure(self):
        events,result=self.routed(self.job(),different=True)
        self.assertEqual(events,['basis','shared-A','shared-Lean-B'])
        self.assertEqual(result['status'],'DIFFERENT_RESULT_DELIVERED')
        self.assertFalse(result['completion']['acceptance_target_satisfied'])
        self.assertFalse(result['completion']['workflow_completed'])


if __name__=='__main__':unittest.main()
