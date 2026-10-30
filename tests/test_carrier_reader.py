"""Native stdout faults must reach the controller, rather than die in a thread."""
import harness_support
import io
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from clean_stage import ArtifactStage
import run_pilot


class CarrierReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.stage=ArtifactStage(self.root/'stage','Synthetic reader only.',phase='control',library=False)
        self.addCleanup(shutil.rmtree,self.stage.work,True)

    def reader(self, lines):
        stage=self.stage;proc=Mock(stdin=io.StringIO(),stdout=iter(lines),pid=12345)
        stage.execution=None;stage.rpc=Mock(return_value={});stage.start_relay=Mock(return_value=12345)
        with patch.object(run_pilot,'system_https_proxy',return_value=None), \
                patch.object(run_pilot.subprocess,'Popen',return_value=proc), \
                patch('runtime_config.auth_home',return_value=self.root/'no-auth'), \
                patch('run_resources.register_child'),patch.object(threading,'Thread') as thread:
            stage.start_process()
        return thread.call_args.kwargs['target']

    def test_event_log_write_failure_reaches_control_loop_without_losing_original_cause(self):
        callback=self.reader([json.dumps({'method':'turn/completed','params':{'turn':{'id':'t','status':'completed'}}})])
        original=run_pilot.append
        def failed_log(path,value):
            if path.name=='events.jsonl':raise OSError('synthetic event disk failure')
            return original(path,value)
        with patch.object(run_pilot,'append',failed_log):callback()
        with self.assertRaisesRegex(RuntimeError,'synthetic event disk failure'):
            self.stage.check_argument_guard()
        self.assertFalse(self.stage.inbox.empty())

    def test_invalid_native_json_is_a_local_protocol_fault_instead_of_silent_wait(self):
        callback=self.reader(['not a JSON RPC event\n']);callback()
        with self.assertRaisesRegex(RuntimeError,'JSON'):
            self.stage.check_argument_guard()
        self.assertTrue((self.stage.logs/'invalid-events.jsonl').is_file())

    def test_valid_native_events_are_retained_before_delivery(self):
        expected={'method':'turn/started','params':{'turn':{'id':'t'}}}
        self.reader([json.dumps(expected)])()
        self.stage.check_argument_guard()
        self.assertEqual(self.stage.inbox.get_nowait(),expected)
        saved=json.loads((self.stage.logs/'events.jsonl').read_text())
        self.assertEqual({k:saved[k] for k in expected},expected)

    def test_reader_fault_wakes_an_already_waiting_receive_loop(self):
        callback=self.reader(['invalid native JSON\n'])
        original=self.stage.inbox.get
        def delivery(*args,**kwargs):
            callback();return original(*args,**kwargs)
        with patch.object(self.stage.inbox,'get',side_effect=delivery):
            with self.assertRaisesRegex(RuntimeError,'Invalid JSON'):
                self.stage.receive_until(lambda m:False,None)

    def test_nonobject_json_is_a_local_reader_fault(self):
        self.reader(['[]\n'])()
        with self.assertRaisesRegex(RuntimeError,'must be an object'):self.stage.check_argument_guard()

    def test_stdout_decode_failure_reaches_the_controller(self):
        class InvalidText:
            def __iter__(self):return self
            def __next__(self):raise UnicodeDecodeError('utf-8',b'\xff',0,1,'synthetic invalid native stdout')
        self.reader(InvalidText())()
        with self.assertRaisesRegex(RuntimeError,'synthetic invalid native stdout'):self.stage.check_argument_guard()

    def test_reader_fault_is_retained_even_when_diagnostic_storage_also_fails(self):
        callback=self.reader(['invalid native JSON\n'])
        with patch.object(run_pilot,'append',side_effect=OSError('synthetic storage unavailable')):callback()
        with self.assertRaisesRegex(RuntimeError,'synthetic storage unavailable'):self.stage.check_argument_guard()
        self.assertIn('evidence_error',self.stage.carrier_reader_fault)


if __name__=='__main__':unittest.main()
