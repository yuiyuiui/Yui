"""File/ownership/cancellation controls. These never call a model."""
import harness_support
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]/'nl0/scripts'
import execution_state as e
import concurrency
import pilot_common


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.r=e.Recorder(self.root/'run','neutral',concurrency.resolve(2))

    def tearDown(self):
        if not self.r.done.is_set():self.r.close('CONTROL_FINISHED')
        self.temp.cleanup()

    def test_atomic_coalescing_and_usage_unknown_until_reported(self):
        profile=__import__('runtime_config').model_profile('proof')
        self.assertEqual(self.r.state['model'],{'id':profile['id'],'effort':profile['reasoning_effort'],'speed':profile['speed']})
        with patch.object(e,'atomic',wraps=e.atomic) as writer:
            for n in range(50):self.r.task('T001',sequence=n);self.r.flush()
            self.assertEqual(writer.call_count,0)
            time.sleep(1.15)
            self.assertEqual(json.loads(self.r.path.read_text())['tasks']['T001']['sequence'],49)
            self.assertLessEqual(writer.call_count,1)
        self.r.native_event('T001','stage','turn/started');self.r.flush(force=True)
        self.assertIsNone(json.loads(self.r.path.read_text())['usage']['confirmed_tokens'])
        counts={'input_tokens':10,'output_tokens':3,'total_tokens':13,'cached_input_tokens':0,'reasoning_tokens':0}
        self.r.native_event('T001','stage','thread/tokenUsage/updated',counts)
        self.r.native_event('T001','stage','thread/tokenUsage/updated',counts)
        self.r.flush(force=True)
        value=json.loads(self.r.path.read_text())
        self.assertEqual(value['usage']['confirmed_tokens']['total_tokens'],13)
        self.assertIsNone(value['usage']['requests_with_usage'])
        observed=value['usage']['usage_last_observed_at_utc']
        self.r.close('CONTROL_FINISHED')
        value=json.loads(self.r.path.read_text())
        self.assertEqual(value['usage']['status'],'PARTIAL')
        self.assertIsNone(value['usage']['in_flight_or_unreported_requests'])
        self.assertEqual(value['usage']['usage_last_observed_at_utc'],observed)

    def test_concurrent_updates_are_atomic_and_preserve_all_tasks(self):
        failures=[];stop=threading.Event()
        def reader():
            while not stop.wait(.003):
                try:json.loads(self.r.path.read_text())
                except Exception as error:failures.append(str(error))
        thread=threading.Thread(target=reader);thread.start()
        try:
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda i:self.r.task(str(i),state='RUNNING'),range(100)))
            self.r.flush(force=True)
        finally:stop.set();thread.join()
        self.assertFalse(failures)
        self.assertEqual(len(json.loads(self.r.path.read_text())['tasks']),100)

    def test_heartbeat_does_not_invent_a_usage_observation(self):
        before=json.loads(self.r.path.read_text())['controller_heartbeat_at_utc']
        time.sleep(5.15)
        value=json.loads(self.r.path.read_text())
        self.assertNotEqual(value['controller_heartbeat_at_utc'],before)
        self.assertNotIn('usage_last_observed_at_utc',value['usage'])
        self.assertIsNone(value['usage']['confirmed_tokens'])

    def test_current_lean_check_is_distinct_from_last_completed_check(self):
        f=self.root/'Proof.lean';f.write_text('example : True := True.intro\n')
        self.r.task('T001')
        first=self.r.lean_started('T001',f)
        self.r.lean_finished('T001',first,{'exit_code':0,'wall_seconds':.1})
        second=self.r.lean_started('T001',f);self.r.flush(force=True)
        task=json.loads(self.r.path.read_text())['tasks']['T001']
        self.assertEqual(task['latest_lean_check']['check_id'],first['check_id'])
        self.assertEqual(task['current_lean_check']['check_id'],second['check_id'])
        self.assertNotIn('exit_code',task['current_lean_check'])

    def test_late_model_event_cannot_hide_an_active_native_check(self):
        f=self.root/'Proof.lean';f.write_text('example : True := True.intro\n')
        self.r.task('T001',role='proof')
        self.r.lean_started('T001',f)
        self.r.native_event('T001','stage','item/completed')
        self.assertEqual(self.r.state['tasks']['T001']['activity'],'LEAN_CHECKING')
        self.assertIn('last_model_event_at_utc',self.r.state['tasks']['T001'])

    def test_keepalive_is_transport_activity_and_not_proof_progress(self):
        self.r.task('T001',state='RUNNING',activity='AWAITING_PROVIDER_TERMINAL',
                    last_activity_at_utc='actual-old-tool-result')
        self.r.native_event('T001','stage','turn/started')
        row=self.r.state['tasks']['T001']
        self.assertEqual(row['last_activity_at_utc'],'actual-old-tool-result')
        self.assertEqual(row['activity'],'AWAITING_PROVIDER_TERMINAL')
        self.assertIn('last_transport_event_at_utc',row)
        self.r.native_event('T001','stage','item/agentMessage/delta')
        self.assertEqual(row['activity'],'AWAITING_PROVIDER_TERMINAL')
        self.assertIn('last_substantive_model_event_at_utc',row)


    def test_retained_task_revisions_keep_every_ledger_and_reconcile_distinct_responses_once(self):
        paths=[]
        for number in (1,2):
            stage=self.root/f'stage-{number}';stage.mkdir();usage=stage/'usage.json';paths.append(str(usage))
            counts={'input_tokens':10,'output_tokens':3,'total_tokens':13,'cached_input_tokens':0,'reasoning_tokens':0}
            self.r.native_event('retained-author',str(stage),'thread/tokenUsage/updated',counts)
            (stage/'usage-ledger.jsonl').write_text(json.dumps({'record_id':'native-stage:'+str(stage.resolve()),'usage':counts})+'\n')
            self.r.task('retained-author',usage_ledger=str(usage))
            self.r.task('retained-author',usage_ledger=str(usage))
        self.r.close('CONTROL_FINISHED');value=json.loads(self.r.path.read_text())
        reconciled=value['usage']['final_ledger_reconciliation']
        self.assertEqual(reconciled['status'],'MATCHED')
        self.assertEqual(set(reconciled['stage_usage_files']),set(paths))
        self.assertEqual(value['archived_usage_ledgers'],paths[:1])
        self.assertEqual(value['usage']['confirmed_tokens']['total_tokens'],26)
        self.assertEqual(value['usage']['status'],'PARTIAL')

    def test_queued_model_slot_can_be_cancelled_without_starting_model(self):
        b=concurrency.Budget(concurrency.resolve(1),execution=self.r)
        self.r.task('T001');self.r.task('T002');outcomes=[];started=threading.Event()
        self.r.flush(force=True)
        def waiting():
            with e.activate(self.r,'T002'):
                started.set()
                try:
                    with b:outcomes.append('MODEL_STARTED')
                except e.Cancelled:outcomes.append('CANCELLED')
        with b:
            t=threading.Thread(target=waiting);t.start();started.wait(1)
            e.request_cancel(self.r.root,'T002');t.join(2)
        self.assertEqual(outcomes,['CANCELLED'])
        self.assertFalse(self.r.cancelled('T001'))
        self.assertEqual(b.report()['active_model_stages'],0)

    def test_process_cleanup_requires_matching_start_identity(self):
        process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],start_new_session=True)
        record=self.r.register_process(process,'neutral-control','T001')
        try:
            bad={**record,'started':'different process'}
            self.assertFalse(e.terminate_owned(process,bad))
            self.assertIsNone(process.poll())
            self.assertTrue(self.r.stop_process(process))
            self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:process.kill();process.wait()

    def test_real_offline_lean_process_is_cancellable(self):
        work=self.root/'lean';(work/'input').mkdir(parents=True)
        file=work/'input/Wait.lean';file.write_text('import Mathlib\n#eval IO.sleep 30000\n')
        self.r.task('T001');result=[]
        self.r.flush(force=True)
        def check():
            with e.activate(self.r,'T001'):
                try:pilot_common.run_lean(file,work)
                except e.Cancelled:result.append('CANCELLED')
        t=threading.Thread(target=check);t.start()
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            if self.r.state['processes']:break
            time.sleep(.02)
        self.assertTrue(self.r.state['processes'])
        e.request_cancel(self.r.root,'T001');t.join(5)
        self.assertFalse(t.is_alive());self.assertEqual(result,['CANCELLED'])
        self.assertFalse([p for p in self.r.state['processes'].values() if p['state']=='ACTIVE'])

    def test_exiting_child_between_poll_and_identity_is_reaped_without_foreign_signal(self):
        process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True)
        record=e.identity(process.pid)
        def already_exiting(_):
            process.terminate()
            return False
        try:
            with patch.object(e,'same_process',side_effect=already_exiting), \
                    patch.object(e.os,'killpg',side_effect=AssertionError('Must not signal an unconfirmed identity')):
                self.assertTrue(e.terminate_owned(process,record))
            self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:process.kill();process.wait()

    def test_native_timeout_preserves_feedback_and_worker_can_check_again(self):
        work=self.root/'native-timeout';(work/'input').mkdir(parents=True)
        file=work/'input/Slow.lean'
        file.write_text('import Lean\n#eval IO.sleep 30000\n')
        self.r.task('T001',state='RUNNING',role='proof')
        with patch('runtime_config.configured_timeout',return_value=.5), e.activate(self.r,'T001'):
            result=pilot_common.run_lean(file,work)
        self.assertEqual(result['exit_code'],124)
        self.assertTrue(result['timed_out'])
        self.assertEqual(result['error_kind'],'LEAN_TIMEOUT')
        self.assertEqual(result['timeout_seconds'],.5)
        self.assertIn('Isolate a smaller typed application',result['stderr'])
        self.assertFalse(self.r.cancelled('T001'))
        self.assertEqual(self.r.state['tasks']['T001']['state'],'RUNNING')
        self.assertFalse([p for p in self.r.state['processes'].values() if p['state']=='ACTIVE'])
        self.assertEqual(Path(result['source_path']).read_bytes(),file.read_bytes())
        latest=self.r.state['tasks']['T001']['latest_lean_check']
        self.assertTrue(latest['timed_out'])
        self.assertEqual(json.loads(Path(latest['log_path']).read_text())['error_kind'],'LEAN_TIMEOUT')
        file.write_text('example : True := True.intro\n')
        with e.activate(self.r,'T001'):
            checked=pilot_common.run_lean(file,work,timeout=15)
        self.assertEqual(checked['exit_code'],0,checked['stderr'])
        self.assertFalse(self.r.cancelled('T001'))

    def test_explicit_native_deadline_is_shorter_and_unrecorded_path_is_bounded(self):
        work=self.root/'native-unrecorded';(work/'input').mkdir(parents=True)
        file=work/'input/Slow.lean';file.write_text('import Lean\n#eval IO.sleep 30000\n')
        with patch('runtime_config.configured_timeout',return_value=.5):
            result=pilot_common.run_lean(file,work,timeout=.2)
        self.assertEqual(result['exit_code'],124)
        self.assertEqual(result['timeout_seconds'],.2)
        self.assertTrue(result['timed_out'])
        self.assertLess(result['wall_seconds'],8)


class ControllerSignalTests(unittest.TestCase):
    def test_sigterm_reaps_owned_children_and_sigkill_is_reported_unknown(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);script=root/'controller.py'
            script.write_text('import sys,time,subprocess\nfrom pathlib import Path\nsys.path.insert(0,'+repr(str(SCRIPTS))+')\n'
                'import execution_state as e\nr=e.Recorder(Path(sys.argv[1]),"control",{"effective":1})\n'
                'try:\n with r.signals():\n  p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"],start_new_session=True) if len(sys.argv)>2 else None\n'
                '  if p:r.register_process(p,"neutral-child")\n  (r.root/"ready").touch()\n  while True:r.check();time.sleep(.02)\n'
                'except e.Cancelled:pass\nfinally:r.close("CANCELLED")\n')
            for hard in [False,True]:
                directory=root/str(hard)
                process=subprocess.Popen([sys.executable,str(script),str(directory)]+([] if hard else ['child']),start_new_session=True)
                try:
                    deadline=time.monotonic()+5
                    while not (directory/'ready').exists() and time.monotonic()<deadline:time.sleep(.02)
                    self.assertTrue((directory/'ready').exists())
                    process.send_signal(signal.SIGKILL if hard else signal.SIGTERM);process.wait(timeout=5)
                    state=e.inspect(directory)
                    if hard:self.assertEqual(state['inspection']['state'],'STALE_UNKNOWN_CLEANUP')
                    else:
                        self.assertEqual(state['result']['status'],'CANCELLED')
                        self.assertEqual(state['inspection']['residual_owned_processes'],[])
                finally:
                    if process.poll() is None:process.kill();process.wait()


if __name__=='__main__':unittest.main()
