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
    def test_auto_discloses_unknown_backend_cap(self):
        value=concurrency.resolve()
        self.assertEqual(value['effective'],2)
        self.assertIsNone(value['known_backend_limit'])
        self.assertIn('not a maximum',value['reason'])

    def test_known_hard_limit_constrains_user_request(self):
        self.assertEqual(concurrency.resolve(10,known_limit=3)['effective'],3)
        self.assertEqual(concurrency.resolve('auto',known_limit=3)['effective'],3)
        self.assertEqual(concurrency.resolve(5)['effective'],5)

    def test_invalid_limits_rejected(self):
        for value in (0,-1,'3.5',True,'unknown'):
            with self.assertRaises(ir.Invalid):concurrency.resolve(value)

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
