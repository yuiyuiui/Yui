"""Owned T204-style recovery: actual exit evidence outranks AI advice."""
import harness_support
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import concurrency
import entrypoint
import execution_state as execution
import fault_control
import ir
import process_recovery as recovery
import process_queries
from controller_common import bind,write,verify_bindings
from lean_fixtures import norm_plan,LIFT


class ProcessRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        problem=self.root/'problem.md';problem.write_text('Synthetic software control only.\n')
        self.job=harness_support.direct_controller_job(problem,track='full',profiles=harness_support.PROFILES,
            output=self.root/'case')
        self.case=Path(self.job['root'])
        self.rec=execution.Recorder(self.case,'synthetic',concurrency.resolve(1))
        self.rec.task('T001',state='RUNNING')
        write(self.case/'owner-context.json',{'thread_id':'synthetic-owner'})
        self.work=self.root/'work';self.work.mkdir()
        self.source=self.work/'Proof.lean';self.source.write_text('example : True := True.intro\n')
        self.process=SimpleNamespace(pid=99999999,poll=lambda:0)
        self.owner={'pid':99999999,'pgid':99999999,'started':'Sat Nov 14 04:00:00 2026'}
        self.messages=[]

    def tearDown(self):
        self.rec.done.set()
        if self.rec.thread.is_alive():self.rec.thread.join(2)

    def owner_action(self,gate,action='recheck',**changes):
        d=recovery.diagnose(self.case,gate.state['incident'])
        file=self.owner_report(gate,d,action,**changes)
        return recovery.decide(self.case,gate.state['incident'],file)

    def owner_report(self,gate,d,action='recheck',**changes):
        row={'version':'yui-process-diagnosis-1','incident':gate.state['incident'],'checkpoint_sha256':d['checkpoint_sha256'],
             'observation_sha256':d['observation']['sha256'],'assessment':'UNKNOWN',
             'observations':['native-checkpoint.json: '+json.dumps(d['parent_observation'])],
             'unknowns':['The first ps timeout has no established root cause.'],
             'options':['Freshly confirm owned group exit before continuing.'],'action':action,**changes}
        file=self.root/'owner-diagnosis.json';write(file,row)
        return file

    def gate(self,confirm,wait):
        gate=fault_control.Gate(self.case/'logs/process-recovery/unit',recorder=self.rec,task='T001',
            notify=lambda owner,message:(self.messages.append(message) or {'status':'QUEUED'}),wait=lambda delay:wait(gate))
        operation=recovery.Recovery(self.process,self.owner,self.work,self.source,{'exit_code':0},self.rec,'T001',confirm)
        return gate,operation

    def test_owner_ai_gets_bound_evidence_and_resumes_only_after_real_confirmation(self):
        confirmations=[]
        gate,operation=self.gate(lambda:(confirmations.append(True) or True),lambda g:self.owner_action(g))
        gate.pause('cleanup pending',resumable=False,operation=operation)
        self.assertEqual(gate.state['state'],'RESOLVED');self.assertEqual(confirmations,[True])
        self.assertIn('Owning AI: take responsibility',self.messages[0])
        self.assertIn('process-diagnose',self.messages[0]);self.assertNotIn('no model response is required',self.messages[0])
        self.assertTrue(self.source.is_file());self.assertEqual(operation.process.poll(),0)

    def test_whole_file_recovery_without_a_local_task_does_not_create_a_phantom_node(self):
        gate,operation=self.gate(lambda:True,lambda g:self.owner_action(g))
        gate.task=None;operation.task=None
        gate.pause('whole-file cleanup',resumable=False,operation=operation)
        self.assertEqual(gate.state['state'],'RESOLVED');self.assertNotIn(None,self.rec.state['tasks'])

    def test_one_automatic_recheck_does_not_need_human_or_repeat_diagnosis(self):
        with patch.object(recovery,'AUTO_RECHECK_SECONDS',0):
            gate,operation=self.gate(lambda:True,lambda g:self.fail('Should resolve before waiting'))
        gate.pause('cleanup pending',resumable=False,operation=operation)
        self.assertTrue(gate.state['cleanup_rechecks'][0]['automatic']);self.assertEqual(len(self.messages),1)

    def test_owner_wait_schedules_a_real_later_recheck_without_restarting_work(self):
        now=[0];turns=[]
        def wait(g):
            if not turns:turns.append(True);self.owner_action(g,'wait',delay_seconds=15)
            else:now[0]=15
        gate,operation=self.gate(lambda:True,wait)
        operation.clock=lambda:now[0];operation.auto_due=60
        gate.pause('pending',resumable=False,operation=operation)
        self.assertEqual(now[0],15);self.assertFalse(gate.state['cleanup_rechecks'][0]['automatic'])

    def test_ai_cannot_turn_unknown_process_ownership_into_pass(self):
        calls=[]
        def wait(g):
            if not calls:calls.append(True);self.owner_action(g)
            else:write(self.case/'cancel-request.json',{})
        gate,operation=self.gate(lambda:False,wait)
        with self.assertRaises(execution.Cancelled):gate.pause('pending',resumable=False,operation=operation)
        self.assertEqual(gate.state['state'],'CANCELLED')
        self.assertFalse(gate.state['cleanup_rechecks'][0]['confirmed']);self.assertTrue(self.source.is_file())

    def test_recheck_failure_retains_the_stack_instead_of_escaping_the_recovery(self):
        turns=[]
        def wait(g):
            if not turns:turns.append(True);self.owner_action(g)
            else:
                self.assertIn('snapshot unavailable',g.state['recheck_error'])
                write(self.case/'cancel-request.json',{})
        gate,operation=self.gate(lambda:(_ for _ in ()).throw(OSError('snapshot unavailable')),wait)
        with self.assertRaises(execution.Cancelled):gate.pause('pending',resumable=False,operation=operation)
        self.assertTrue(self.source.is_file())

    def test_cancellation_racing_confirmation_does_not_deliver_a_resolved_result(self):
        def confirm():write(self.case/'cancel-request.json',{});return True
        gate,operation=self.gate(confirm,lambda g:self.owner_action(g))
        with self.assertRaises(execution.Cancelled):gate.pause('pending',resumable=False,operation=operation)
        self.assertEqual(gate.state['state'],'CANCELLED')

    def test_explicit_case_deadline_is_not_extended_by_operational_recovery(self):
        import time
        self.rec.deadline=time.monotonic()-1
        gate,operation=self.gate(lambda:self.fail('Budget expired'),lambda g:self.fail('No automatic budget extension'))
        with self.assertRaises(execution.CaseDeadlineExceeded):gate.pause('pending',resumable=False,operation=operation)
        self.assertTrue(self.source.is_file())

    def test_stale_diagnosis_changed_source_and_blind_pass_are_rejected(self):
        def wait(g):
            for changes in ({'version':'unknown'},{'incident':'0'*32},{'checkpoint_sha256':'0'*64},
                            {'observation_sha256':'0'*64},{'action':'pass'}):
                with self.subTest(changes=changes),self.assertRaises(ValueError):self.owner_action(g,**changes)
            self.source.write_text('changed source\n')
            with self.assertRaises(ValueError):recovery.diagnose(self.case,g.state['incident'])
            write(self.case/'cancel-request.json',{})
        gate,operation=self.gate(lambda:self.fail('No check may run on changed source'),wait)
        with self.assertRaises(execution.Cancelled):gate.pause('pending',resumable=False,operation=operation)

    def test_wait_and_escalation_preserve_the_live_case_and_show_concrete_options(self):
        turns=[]
        def wait(g):
            if not turns:turns.append(True);self.owner_action(g,'escalate')
            else:
                self.assertTrue(g.state['needs_user_decision'])
                self.assertTrue(self.source.is_file());write(self.case/'cancel-request.json',{})
        gate,operation=self.gate(lambda:self.fail('Escalation cannot authorize cleanup'),wait)
        with self.assertRaises(execution.Cancelled):gate.pause('pending',resumable=False,operation=operation)
        self.assertTrue(gate.state['owner_diagnosis'])

    def test_missing_owner_or_failed_delivery_remains_visible_not_success(self):
        (self.case/'owner-context.json').unlink()
        gate,operation=self.gate(lambda:self.fail('No blind resume'),lambda g:write(self.case/'cancel-request.json',{}))
        gate.notify=lambda owner,message:{'status':'PENDING','reason':'Owner unavailable'}
        with self.assertRaises(execution.Cancelled):gate.pause('pending',resumable=False,operation=operation)
        self.assertEqual(gate.state['notification']['status'],'PENDING')

    def test_diagnostic_probe_timeouts_are_preserved_and_never_accepted_as_absence(self):
        def wait(g):
            actual=subprocess.run
            def query(command,*args,**kwargs):
                if command[0]=='ps':raise subprocess.TimeoutExpired(command,kwargs['timeout'])
                return actual(command,*args,**kwargs)
            with patch.object(subprocess,'run',side_effect=query):
                result=recovery.diagnose(self.case,g.state['incident'])
            self.assertEqual([r['status'] for r in result['probes']],['TimeoutExpired']*3)
            write(self.case/'cancel-request.json',{})
        gate,operation=self.gate(lambda:self.fail('No fresh exit evidence'),wait)
        with self.assertRaises(execution.Cancelled):gate.pause('pending',resumable=False,operation=operation)

    def test_one_observation_cannot_queue_duplicate_or_foreign_decisions(self):
        def wait(g):
            self.owner_action(g)
            report=self.root/'owner-diagnosis.json'
            with self.assertRaises(ValueError):recovery.decide(self.case,g.state['incident'],report)
            with self.assertRaises(ValueError):recovery.decide(self.root,'0'*32,report)
        gate,operation=self.gate(lambda:True,wait)
        gate.pause('pending',resumable=False,operation=operation)

    def test_public_operator_parser_and_current_format_diagnostic_dispatch(self):
        parser=argparse.ArgumentParser();entrypoint.parsers(parser.add_subparsers(dest='command'))
        def wait(g):
            args=parser.parse_args(['process-diagnose',str(self.case),'--incident',g.state['incident']])
            result=entrypoint.dispatch(args)
            self.assertEqual(result['status'],'PROCESS_DIAGNOSIS_PREPARED');self.owner_action(g)
        gate,operation=self.gate(lambda:True,wait)
        gate.pause('pending',resumable=False,operation=operation)
        with self.assertRaises(ValueError):recovery.diagnose(self.case,gate.state['incident'])

    def test_actual_public_cli_reads_the_checkpoint_and_queues_bound_owner_advice(self):
        def wait(g):
            args=[sys.executable,'-B',str(harness_support.CORE/'nl0/scripts/yui.py')]
            tail=[str(self.case),'--incident',g.state['incident']]
            result=subprocess.run([*args,'process-diagnose',*tail],capture_output=True,text=True,timeout=45)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            report=self.owner_report(g,json.loads(result.stdout))
            result=subprocess.run([*args,'process-decision',*tail,'--report',str(report)],capture_output=True,text=True,timeout=45)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'],'PROCESS_DECISION_QUEUED')
        gate,operation=self.gate(lambda:True,wait)
        gate.pause('pending',resumable=False,operation=operation)

    def test_real_lean_compile_ps_exhaustion_owner_diagnosis_and_remaining_axiom_check(self):
        armed=[];timeouts=[];compile_count=[];original_run=subprocess.run
        finish=self.rec.lean_finished
        def finished(*args):finish(*args);armed.append(True);compile_count.append(True)
        def ps(command,*args,**kwargs):
            if armed and command[:2]==['ps','-ax'] and len(timeouts)<3:
                timeouts.append(kwargs['timeout']);raise subprocess.TimeoutExpired(command,kwargs['timeout'])
            return original_run(command,*args,**kwargs)
        gate_init=fault_control.Gate.__init__
        def init(g,*args,**kwargs):
            gate_init(g,*args,**kwargs)
            g.notify=lambda owner,message:(self.messages.append(message) or {'status':'QUEUED'})
            g.wait=lambda delay:self.owner_action(g)
        for name in ('contract.json','source.json'):
            shutil.copyfile(harness_support.FIXTURES/'lean/examples/case1_norm_sup'/name,self.work/name)
        cp=self.work/'contract.json';plan=norm_plan(cp)
        with execution.activate(self.rec,'T001'),patch.object(self.rec,'lean_finished',side_effect=finished), \
                patch.object(subprocess,'run',side_effect=ps),patch.object(fault_control.Gate,'__init__',init):
            result=ir.check(cp,plan,{'T001':LIFT},only='T001')
        self.assertEqual(timeouts,[5,15,30]);self.assertEqual(len(compile_count),1)
        self.assertEqual(result['status'],'LOCAL-PROOF-CHECKED',result)
        self.assertFalse(set(result.get('axioms',[]))-{'propext','Classical.choice','Quot.sound'})
        states=list((self.case/'logs/process-recovery').glob('*/error-state.json'))
        self.assertEqual(len(states),1);self.assertEqual(json.loads(states[0].read_text())['state'],'RESOLVED')
        checkpoint=json.loads(states[0].read_text())['checkpoint']['binding']
        verify_bindings([checkpoint])
        retained=json.loads(Path(checkpoint['path']).read_text())
        verify_bindings(retained['bindings'])  # Normal scratch cleanup leaves durable recovery evidence.
        self.assertTrue(retained['queries'])
        self.assertEqual([r['timeout_seconds'] for r in retained['queries'][-1]['attempts']],[5,15,30])

    def test_initial_identity_query_failure_keeps_the_original_native_child(self):
        register=self.rec.register_process;calls=[]
        def capture(*args,**kwargs):
            calls.append(True)
            if len(calls)==1:raise execution.ProcessIdentityUnconfirmed('Cannot establish child process ownership')
            return register(*args,**kwargs)
        gate_init=fault_control.Gate.__init__
        def init(g,*args,**kwargs):
            gate_init(g,*args,**kwargs)
            g.notify=lambda owner,message:{'status':'QUEUED'}
            g.wait=lambda delay:self.owner_action(g)
        from pilot_common import run_lean
        (self.work/'input').mkdir();(self.work/'output').mkdir()
        source=self.work/'output/Proof.lean';source.write_text('example : True := True.intro\n')
        with execution.activate(self.rec,'T001'),patch.object(self.rec,'register_process',side_effect=capture), \
                patch.object(fault_control.Gate,'__init__',init):
            result=run_lean(source,self.work)
        self.assertEqual(result['exit_code'],0);self.assertEqual(len(calls),2)
        states=list((self.case/'logs/process-recovery').glob('*/error-state.json'))
        self.assertEqual(json.loads(states[0].read_text())['resolution'],'FRESH_NATIVE_IDENTITY_CONFIRMED')

    def test_cleanup_recovery_never_promotes_a_timed_out_compilation(self):
        original=self.rec.stop_process;calls=[]
        def stop(process):
            calls.append(True)
            return False if len(calls)==1 else original(process)
        gate_init=fault_control.Gate.__init__
        def init(g,*args,**kwargs):
            gate_init(g,*args,**kwargs)
            g.notify=lambda owner,message:{'status':'QUEUED'}
            g.wait=lambda delay:self.owner_action(g)
        from pilot_common import run_lean,native_succeeded
        (self.work/'input').mkdir();(self.work/'output').mkdir()
        source=self.work/'output/Proof.lean';source.write_text('import Lean\n#eval IO.sleep 1000\n')
        with execution.activate(self.rec,'T001'),patch.object(self.rec,'stop_process',side_effect=stop), \
                patch.object(fault_control.Gate,'__init__',init):
            result=run_lean(source,self.work,timeout=.01)
        self.assertTrue(result['timed_out']);self.assertEqual(result['exit_code'],124)
        self.assertFalse(native_succeeded(result))


if __name__=='__main__':unittest.main()
