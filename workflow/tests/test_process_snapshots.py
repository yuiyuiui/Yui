"""Independent process-query timeout, exhaustion and malformed-snapshot rules."""
import importlib.util
from pathlib import Path
import subprocess
import unittest

PATH=Path(__file__).resolve().parents[1]/'blocks/process_snapshots.py'
SPEC=importlib.util.spec_from_file_location('process_rules_under_test',PATH)
rules=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(rules)


class FreshSnapshots(unittest.TestCase):
    def test_native_cleanup_timeout_then_fresh_success(self):
        calls=[];events=[];fresh={27:{'pid':27,'started':'Sat Nov 14 04:00:00 2026'}}
        def query():
            calls.append(len(calls)+1)
            if len(calls)==1:raise subprocess.TimeoutExpired('ps',2)
            return fresh
        self.assertIs(rules.retry(query,observe=events.append),fresh)
        self.assertEqual(calls,[1,2]);self.assertTrue(events[0]['query_completed'])
        self.assertEqual([r['outcome'] for r in events[0]['attempts']],['TIMEOUT','COMPLETE'])

    def test_explicit_cleanup_retries_a_second_timeout_without_repeating_proof_work(self):
        calls=[];events=[]
        def query():
            calls.append('fresh ps and parse only')
            if len(calls)<3:raise subprocess.TimeoutExpired('ps',10)
            return {31:{'pid':31}}
        self.assertEqual(rules.retry(query,observe=events.append),{31:{'pid':31}})
        self.assertEqual(len(calls),3)
        self.assertEqual([r['outcome'] for r in events[0]['attempts']],['TIMEOUT','TIMEOUT','COMPLETE'])

    def test_exhausted_queries_raise_uncertainty_instead_of_an_empty_snapshot(self):
        calls=[];events=[]
        def timeout():
            calls.append(True);raise subprocess.TimeoutExpired('ps',2)
        with self.assertRaises(subprocess.TimeoutExpired) as caught:
            rules.retry(timeout,observe=events.append)
        self.assertEqual(len(calls),3)
        self.assertFalse(events[0]['query_completed'])
        self.assertEqual(len(caught.exception.process_query_attempts),3)

    def test_malformed_snapshot_after_timeout_is_not_reported_as_recovered(self):
        calls=[];events=[]
        def malformed():
            calls.append(True)
            if len(calls)==1:raise subprocess.TimeoutExpired('ps',2)
            raise ValueError('Incomplete process snapshot')
        with self.assertRaises(ValueError):rules.retry(malformed,observe=events.append)
        self.assertEqual(len(calls),2);self.assertFalse(events[0]['query_completed'])

    def test_non_timeout_errors_and_explicit_cancellation_do_not_retry(self):
        for error in (ValueError('malformed'),OSError('unavailable'),KeyboardInterrupt()):
            calls=[]
            def query():calls.append(True);raise error
            with self.subTest(error=type(error).__name__),self.assertRaises(type(error)):
                rules.retry(query)
            self.assertEqual(len(calls),1)

    def test_process_start_identity_requires_a_real_complete_os_timestamp(self):
        self.assertEqual(rules.started(' Sat Nov  14 04:00:00 2026 '),'Sat Nov 14 04:00:00 2026')
        for value in ('','partial snapshot','Sat Nov 14 04:00:00','Sat Nov 14 04:00:00 xxxx',None):
            with self.subTest(value=value),self.assertRaises(ValueError):rules.started(value)


if __name__=='__main__':unittest.main()
