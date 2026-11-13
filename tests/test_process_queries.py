"""Actual process-query consumers recover locally and retain malformed uncertainty."""
import harness_support
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import cleanup
import execution_state as execution
import owner_observation
import process_queries

STAMP='Sat Nov 14 04:00:00 2026'


class ProcessQueryTests(unittest.TestCase):
    def minimal(self):return str(os.getpid())+' '+str(os.getpgrp())+' R '+STAMP+'\n'
    def complete(self):return str(os.getpid())+' 1 '+str(os.getpgrp())+' R '+STAMP+' python test-fixture\n'
    def observation(self):return str(os.getpid())+' '+str(os.getpgrp())+' '+STAMP+'\n'

    def test_native_snapshot_timeout_then_success_is_fresh_and_bounded(self):
        calls=[]
        def ps(*args,**kwargs):
            calls.append((args,kwargs))
            if len(calls)==1:raise subprocess.TimeoutExpired('ps',2)
            return SimpleNamespace(stdout=self.minimal(),returncode=0)
        with patch.object(subprocess,'run',side_effect=ps):rows=execution.process_table()
        self.assertIn(os.getpid(),rows);self.assertEqual(len(calls),2)
        self.assertTrue(process_queries.history()[-1]['query_completed'])

    def test_cleanup_and_owner_observation_share_fresh_retry_without_inventing_exit(self):
        for consumer,text in ((cleanup.process_table,self.complete()),
                              (owner_observation.process_table,self.observation())):
            with self.subTest(consumer=consumer.__module__),patch.object(subprocess,'run',side_effect=[
                    subprocess.TimeoutExpired('ps',10),SimpleNamespace(stdout=text,returncode=0)]) as run:
                rows=consumer()
                self.assertIn(os.getpid(),rows);self.assertEqual(run.call_count,2)

    def test_exhausted_queries_and_malformed_data_do_not_become_empty_tables(self):
        for consumer in (execution.process_table,cleanup.process_table,owner_observation.process_table):
            with self.subTest(consumer=consumer.__module__),patch.object(subprocess,'run',
                    side_effect=subprocess.TimeoutExpired('ps',2)) as run:
                with self.assertRaises(subprocess.TimeoutExpired):consumer()
                self.assertEqual(run.call_count,3)
            for text in ('','incomplete row\n',str(os.getpid())+' not-a-group R '+STAMP+'\n'):
                with self.subTest(consumer=consumer.__module__,text=text),patch.object(subprocess,'run',
                        return_value=SimpleNamespace(stdout=text,returncode=0)):
                    with self.assertRaises(ValueError):consumer()

    def test_completed_native_handle_needs_only_cleanup_retry_not_a_new_proof(self):
        child=subprocess.Popen([sys.executable,'-B','-c','pass'],start_new_session=True)
        child.wait(timeout=10)
        record=execution.capture_process(child,private_group=True)
        actual=subprocess.run;calls=[]
        def transient(command,*args,**kwargs):
            if command[:2]==['ps','-ax'] and not calls:
                calls.append(True);raise subprocess.TimeoutExpired('ps',2)
            return actual(command,*args,**kwargs)
        with patch.object(subprocess,'run',side_effect=transient):
            self.assertTrue(execution.terminate_owned(child,record))
        self.assertEqual(calls,[True]);self.assertEqual(child.returncode,0)

    def test_exhausted_snapshot_cannot_authorize_a_signal(self):
        child=subprocess.Popen([sys.executable,'-B','-c','pass'],start_new_session=True)
        child.wait(timeout=10);record=execution.capture_process(child,private_group=True)
        with patch.object(subprocess,'run',side_effect=subprocess.TimeoutExpired('ps',2)), \
                patch.object(execution.os,'kill',side_effect=AssertionError('No identified target')):
            self.assertFalse(execution.terminate_owned(child,record))
            self.assertIn('cleanup_uncertainty',record)


if __name__=='__main__':unittest.main()
