"""Linked real Lean -> B-final -> case child -> batch tests; synthetic judgments."""
import harness_support
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from final_acceptance_fixtures import frozen_case, build
import fault_control
import execution_state
import ir
import jobs
import queue_controller


class DeliveryPathTests(unittest.TestCase):
    def test_partial_and_complete_nonpass_deliver_through_real_case_child_and_batch(self):
        with tempfile.TemporaryDirectory(prefix='yui-delivery-path-') as raw:
            root = Path(raw)
            selected = []
            fixtures = {}
            for mode in ('incomplete', 'complete', 'incomplete-expired', 'recheck-then-deliver'):
                problem = root/mode/'problem.txt';problem.parent.mkdir()
                problem.write_bytes((harness_support.FIXTURES/'closed-addition/problem.txt').read_bytes())
                job = harness_support.direct_controller_job(problem, track='full',
                                   profiles=harness_support.PROFILES, max_concurrency=1,
                                   output=root/('run-'+mode),
                                   time_budget_seconds=60 if mode=='incomplete-expired' else None)
                out = frozen_case(Path(job['root'])/'nl0-to-lean/0001')
                build(out, 'unfaithful')
                selected.append(job);fixtures[job['root']] = (out, mode)
            helper = harness_support.TESTS/'tooling/delivery_control.py'
            processes = []
            owners = {}
            def launch(job_path, out):
                workflow, mode = fixtures[str(out)]
                with (out/'child-control.log').open('w') as log:
                    child = subprocess.Popen([sys.executable, '-B', str(helper), str(job_path),
                                              str(workflow), mode], start_new_session=True,
                                             stdout=log, stderr=subprocess.STDOUT)
                processes.append(child)
                owners[child.pid] = execution_state.capture_process(child,private_group=True)
                return child
            try:
                with patch.object(queue_controller, 'launch_case', side_effect=launch), \
                     patch.object(fault_control.Gate, 'pause', side_effect=AssertionError('Authorized delivery must not pause its batch')):
                    results = queue_controller.serve(selected, case_concurrency=2)
                self.assertEqual(len(results), 4)
                for job in selected:
                    run = Path(job['root']);result = results[job['id']]
                    mode = fixtures[job['root']][1]
                    self.assertEqual(result['status'], 'DIFFERENT_RESULT_DELIVERED', (run/'child-control.log').read_text())
                    self.assertFalse(result['original_goal_completed'])
                    self.assertFalse(result['completion']['acceptance_target_satisfied'])
                    self.assertEqual(result['audit_b']['review_coverage'], 'INCOMPLETE' if mode.startswith('incomplete') else 'COMPLETE')
                    summary = ir.load(run/'audit-b/0001.json')
                    self.assertIn('delivery', summary)
                    self.assertEqual(summary['delivery']['decision'], result['user_decision'])
                    for binding in summary['delivery'].values():
                        if isinstance(binding, dict) and 'sha256' in binding:
                            from controller_common import bind
                            self.assertEqual(bind(binding['path']), binding)
                    batch = ir.load(run/'batch-result.json')
                    self.assertFalse(batch['all_cases_accepted'])
                    self.assertTrue(batch['children_exited'])
                    self.assertEqual(ir.load(run/'execution-status.json')['cancellation']['cleanup'],
                                     'CONFIRMED_NO_OWNED_PROCESSES')
                    if mode=='recheck-then-deliver':
                        parent=fixtures[job['root']][0].parent
                        first=ir.load(parent/'audit-b-final/decision/error-state.json')
                        self.assertEqual(first['control']['action'],'recheck')
                        self.assertTrue((parent/'audit-b-final-rechecks/0002/review.json').is_file())
                self.assertTrue(all(child.returncode == 1 for child in processes), 'Non-goal completion is not a Python crash')
                partial = fixtures[selected[0]['root']][0].parent/'audit-b-final'
                self.assertFalse((partial/'review.json').exists(), 'Do not fabricate a completed semantic review')
                self.assertEqual(ir.load(partial/'report.json')['review_coverage'], 'INCOMPLETE')
            finally:
                unconfirmed=[]
                for child in processes:
                    if not execution_state.terminate_owned(child,owners[child.pid]):unconfirmed.append(child.pid)
                    child.wait(timeout=5)
                self.assertFalse(unconfirmed,'Test-owned case process groups must be confirmed gone')


if __name__ == '__main__': unittest.main()
