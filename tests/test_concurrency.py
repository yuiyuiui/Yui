import harness_support
import concurrent.futures
from pathlib import Path
import threading
import time
import unittest
import tempfile

import concurrency
import ir
import execution_state


class ConcurrencyTests(unittest.TestCase):
    def test_auto_waits_for_phase_nodes_without_a_fixed_fallback(self):
        value=concurrency.resolve()
        self.assertIsNone(value['effective'])
        self.assertIsNone(value['known_backend_limit'])
        self.assertIn('awaiting',value['reason'])
        self.assertNotIn('fallback',value)

    def test_auto_uses_each_phase_node_count_including_empty_and_large_queues(self):
        for count in (0,1,3,7,31):
            with self.subTest(count=count):
                value=concurrency.resolve(node_count=count)
                self.assertEqual(value['requested'],'auto')
                self.assertEqual(value['effective'],count)
                self.assertEqual(value['node_count'],count)

    def test_known_hard_limit_constrains_user_request(self):
        self.assertEqual(concurrency.resolve(10,known_limit=3)['effective'],3)
        self.assertIsNone(concurrency.resolve('auto',known_limit=3)['effective'])
        self.assertEqual(concurrency.resolve('auto',node_count=9,known_limit=3)['effective'],3)
        self.assertEqual(concurrency.resolve('auto',node_count=1,known_limit=3)['effective'],1)
        self.assertEqual(concurrency.resolve(5)['effective'],5)

    def test_explicit_limit_is_preserved_independently_of_node_count(self):
        for count in (0,1,3,11):
            self.assertEqual(concurrency.resolve(5,node_count=count)['effective'],5)

    def test_invalid_limits_rejected(self):
        for value in (0,-1,'3.5',True,'unknown'):
            with self.assertRaises(ir.Invalid):concurrency.resolve(value)
        for value in (-1,True,'3',2.5):
            with self.assertRaisesRegex(ir.Invalid,'node count'):concurrency.resolve(node_count=value)

    def test_unresolved_or_empty_auto_lane_cannot_start_a_model(self):
        budget=concurrency.Budget(concurrency.resolve(),role='proof')
        for count in (None,0):
            if count is not None:budget.configure(count)
            with self.assertRaisesRegex(ir.Invalid,'phase node count'):
                with budget:pass
        self.assertEqual(budget.report()['model_stages'],[])

    def test_auto_rebinds_between_revisions_and_retains_its_history(self):
        budget=concurrency.Budget(concurrency.resolve(),role='audit_r')
        budget.configure(7)
        with budget:
            budget.configure(7) # Nested per-R dispatch keeps the phase-wide bound.
            with self.assertRaisesRegex(ir.Invalid,'active model lane'):budget.configure(3)
        budget.configure(3)
        with budget:pass
        report=budget.report()
        self.assertEqual(report['effective'],3)
        self.assertEqual([c['effective'] for c in report['configuration_history']],[None,7,3])
        self.assertEqual(len(report['model_stages']),2)

    def test_auto_audit_and_proof_lanes_have_distinct_real_peaks_and_records(self):
        with tempfile.TemporaryDirectory() as raw:
            recorder=execution_state.Recorder(Path(raw),'automatic-phases',concurrency.resolve())
            budgets=concurrency.CaseBudgets(execution=recorder)
            try:
                for lane,count in ((budgets.audit,3),(budgets.proof,5)):
                    lane.configure(count)
                    barrier=threading.Barrier(count,timeout=3)
                    def job(_):
                        with lane:barrier.wait()
                    with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
                        list(pool.map(job,range(count)))
                    self.assertEqual(lane.report()['observed_peak_model_stages'],count)
                    self.assertEqual(recorder.state['concurrency']['roles'][lane.role]['configuration']['effective'],count)
                self.assertEqual(budgets.serial.configuration['effective'],1)
                self.assertEqual(recorder.state['concurrency']['effective'],5)
                self.assertEqual(recorder.state['concurrency']['resolved_role'],'proof')
                self.assertEqual(recorder.state['concurrency']['roles']['audit_r']['observed_peak'],3)
                self.assertEqual(recorder.state['concurrency']['roles']['proof']['observed_peak'],5)
            finally:recorder.close('CONTROL_FINISHED')

    def test_global_budget_bounds_real_concurrent_stages_and_records_wait(self):
        budget=concurrency.Budget(concurrency.resolve(2));barrier=threading.Barrier(6)
        def job():
            barrier.wait()
            with budget:time.sleep(0.015)
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(lambda _:job(),range(6)))
        report=budget.report()
        self.assertEqual(report['observed_peak_model_stages'],2)
        self.assertEqual(len(report['model_stages']),6)
        self.assertGreater(report['summed_queue_seconds'],0)
        self.assertEqual(report['active_model_stages'],0)

    def test_slot_released_after_fault_and_nested_calls_rejected(self):
        budget=concurrency.Budget(concurrency.resolve(1))
        with self.assertRaises(RuntimeError):
            with budget:raise RuntimeError('fault')
        with budget:
            with self.assertRaises(ir.Invalid):
                with budget:pass
        self.assertEqual(budget.report()['observed_peak_model_stages'],1)

    def test_case_roles_are_serial_or_five_proof_slots_and_never_overlap(self):
        with tempfile.TemporaryDirectory() as raw:
            recorder=execution_state.Recorder(Path(raw),'neutral',concurrency.resolve(5))
            budgets=concurrency.CaseBudgets(5,execution=recorder)
            try:
                with budgets.serial:
                    with self.assertRaisesRegex(ValueError,'cannot overlap'):
                        with budgets.proof: pass
                barrier=threading.Barrier(5)
                def proof(_):
                    with budgets.proof:
                        barrier.wait(timeout=3)
                        time.sleep(.01)
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                    list(pool.map(proof,range(5)))
                with budgets.serial: pass
                self.assertEqual(budgets.proof.report()['observed_peak_model_stages'],5)
                self.assertEqual(budgets.serial.report()['observed_peak_model_stages'],1)
                self.assertEqual(recorder.state['concurrency']['roles']['proof']['active'],0)
                self.assertEqual(recorder.state['concurrency']['roles']['preparation_review']['active'],0)
            finally: recorder.close('CONTROL_FINISHED')

    def test_standalone_review_cannot_borrow_proof_concurrency(self):
        self.assertEqual(concurrency.serial_budget().configuration['effective'],1)
        legacy=concurrency.Budget(concurrency.resolve(1))
        self.assertIs(concurrency.serial_budget(legacy),legacy)
        self.assertEqual(legacy.role,'preparation_review')
        with self.assertRaises(ir.Invalid):concurrency.serial_budget(concurrency.Budget(concurrency.resolve(5)))
        with self.assertRaises(ir.Invalid):concurrency.serial_budget(concurrency.Budget(concurrency.resolve(1),role='proof'))


if __name__=='__main__':unittest.main()
