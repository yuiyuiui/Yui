"""Translation native boundary, role handoff, repair and cooldown isolation."""
import harness_support
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import concurrency
import lean_timeout_policy as policy
import pilot_common
from native_fixture import NativeFixture


OK = dict(exit_code=0, stdout='checked', stderr='')
WALL = dict(exit_code=124, stdout='', stderr='native wall limit', timed_out=True,
            error_kind='LEAN_TIMEOUT', timeout_scope='native_call')


def judgment(category):
    return dict(category=category, line=1, quote='example', reason='Located elaboration cost in the example.',
                next_action='Inspect its typed application.')


class TranslationTimeouts(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root/'Proof.lean'
        self.source.write_text('example : True := by trivial\n')
        self.calls = []

    @contextmanager
    def native(self, results):
        results = iter(results)
        def invoke(file, work, **kwargs):
            self.calls.append((kwargs['timeout'], kwargs['reviewed_policy'], file.read_text()))
            return dict(next(results))
        with patch.object(pilot_common, '_run_lean', side_effect=invoke):
            yield

    def run_native(self, **kwargs):
        return pilot_common.run_lean(self.source, self.root, **kwargs)

    def test_every_rung_gets_its_own_source_bound_review_and_thirty_is_final(self):
        with self.native([WALL]*5), policy.scope(self.root/'log', None, key='T001'), \
                patch.object(policy, 'inspect_source', return_value=judgment('workload_only')) as review:
            result = self.run_native()
        self.assertEqual([t for t, scoped, _ in self.calls if scoped], [360,720,1080,1440,1800])
        self.assertEqual(review.call_count, 5)
        self.assertEqual(result['exit_code'], 124)
        self.assertEqual(result['timeout_reviews'][-1]['action'], 'limit')
        for receipt in result['timeout_reviews']:
            path = Path(receipt['evidence'])
            self.assertEqual((path/'inputs/Candidate.lean').read_text(), self.source.read_text())
            self.assertEqual(json.loads((path/'inputs/native.json').read_text())['exit_code'], 124)
            self.assertEqual(json.loads((path/'decision.json').read_text()), receipt)

    def test_repair_at_previous_allowance_then_compile_other_node_from_six(self):
        reviews = [judgment('workload_only'), judgment('code_issue')]
        with self.native([WALL,WALL,OK,OK]), patch.object(policy,'inspect_source',side_effect=reviews):
            with policy.scope(self.root/'log', None, key='T001'):
                failed = self.run_native()
                self.assertEqual(failed['timeout_reviews'][-1]['action'], 'repair')
                repeated = self.run_native()
                self.assertTrue(repeated['timeout_replayed'])
                self.assertEqual(len(self.calls), 2)
                self.source.write_text('example : True := True.intro\n')
                self.assertEqual(self.run_native()['exit_code'], 0)
            with policy.scope(self.root/'log', None, key='T002'):
                self.assertEqual(self.run_native()['exit_code'], 0)
        self.assertEqual([row[0] for row in self.calls], [360,720,720,360])
        self.assertNotEqual(self.calls[1][2], self.calls[2][2])

    def test_uncertainty_lower_cap_and_stage_or_external_stops(self):
        with self.native([WALL,WALL]), policy.scope(self.root/'short', None), \
                patch.object(policy,'inspect_source',side_effect=[judgment('uncertain'),judgment('workload_only')]):
            self.assertEqual(self.run_native(timeout=10)['timeout_reviews'][0]['action'],'inspect')
            self.assertEqual(self.run_native(timeout=10)['timeout_reviews'][0]['action'],'limit')
        other = [OK, dict(WALL,error_kind='CASE_DEADLINE',timeout_scope='whole_case'),
                 dict(WALL,error_kind='PROVIDER_ERROR'), dict(WALL,cancelled=True),
                 dict(exit_code=1,stdout='deterministic timeout at isDefEq',stderr=''), dict(exit_code=1,stdout='',stderr='type mismatch')]
        with self.native([*other, WALL, WALL]), patch.object(policy,'inspect_source',side_effect=AssertionError):
            with policy.scope(self.root/'normal',None):
                for expected in other:self.assertEqual(self.run_native(),expected)
            with policy.scope(self.root/'deadline',None,deadline=time.monotonic()+5):
                self.assertEqual(self.run_native()['error_kind'],'STAGE_DEADLINE')
            with policy.scope(None,None):
                self.assertEqual(self.run_native(),WALL)
        self.assertFalse(self.calls[-1][1])

    def test_diagnosis_requires_real_location_and_no_prior_compiler_error_for_volume(self):
        for value, native in [(dict(judgment('code_issue'),line=2), WALL),
                              (dict(judgment('workload_only'),quote='foreign'), WALL),
                              (judgment('workload_only'), dict(WALL,stdout='Proof.lean:1:2: error: invalid binder')),
                              (dict(judgment('workload_only'),seconds=9999), WALL)]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                policy.review_contract(self.source.read_text(),native)(value)

    def test_machine_translation_route_uses_policy_and_leaves_the_surrounding_run_alone(self):
        import case_runner
        budgets=concurrency.CaseBudgets()
        with self.native([WALL,OK]), patch.object(policy,'inspect_source',return_value=judgment('workload_only')), \
                patch.object(case_runner,'translation_attempt',side_effect=lambda *args:self.run_native()):
            result=case_runner.translation_work({'root':str(self.root)}, {}, budgets, None)
        self.assertEqual(result['exit_code'],0)
        self.assertEqual([row[0] for row in self.calls],[360,720])
        self.assertIsNone(policy.active.get())

    def test_standalone_audit_build_uses_the_same_native_policy(self):
        from contextlib import redirect_stdout
        import io
        import workflow
        with self.native([WALL,OK]), patch.object(policy,'inspect_source',return_value=judgment('workload_only')), \
                patch('sys.argv',['workflow.py','audit-build',str(self.root)]), \
                patch.object(workflow,'bound',return_value={}), \
                patch.object(workflow.audit_b,'build',side_effect=lambda *a,**k:self.run_native()), \
                redirect_stdout(io.StringIO()) as output:
            status=workflow.main()
        self.assertEqual(status,0,output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['exit_code'],0)
        self.assertEqual([row[0] for row in self.calls],[360,720])

    def test_diagnosis_fault_does_not_grant_retry_or_overwrite_prior_limit(self):
        with self.native([WALL]), policy.scope(self.root/'review-failure',None,key='T001'), \
                patch.object(policy,'inspect_source',side_effect=ConnectionError('review unavailable')):
            with self.assertRaisesRegex(ConnectionError,'review unavailable'):
                self.run_native()
        self.assertEqual(len(self.calls),1)
        self.assertEqual(list((self.root/'review-failure').rglob('allowance.json')),[])
        self.assertEqual(len(list((self.root/'review-failure').rglob('native.json'))),1)

    def test_native_client_reviews_before_real_lean_retry_in_single_occupied_lane(self):
        from fault_control import Gate
        def respond(fixture, handler, number, payload):
            fixture.tool(handler,number,'submit_draft',judgment('workload_only'))
        original = pilot_common._run_lean
        def first_timeout_then_lean(file, work, **kwargs):
            self.calls.append(kwargs['timeout'])
            if len(self.calls)==1:return dict(WALL)
            return original(file, work, **kwargs)
        lane=concurrency.Budget(concurrency.resolve(1),role='proof')
        work=self.root/'native';(work/'output').mkdir(parents=True)
        candidate=work/'output/Proof.lean';candidate.write_text('example : True := True.intro\n')
        with NativeFixture(self.root/'fixture',responder=respond) as fixture, \
                patch.object(Gate,'pause',side_effect=AssertionError('Unexpected review pause')), \
                patch.object(pilot_common,'_run_lean',side_effect=first_timeout_then_lean), \
                policy.scope(self.root/'reviews',lane,key='T001'), lane:
            result=pilot_common.run_lean(candidate,work)
            self.assertFalse(fixture.failures)
        self.assertEqual(self.calls,[360,720])
        self.assertEqual(result['exit_code'],0,result)
        self.assertEqual(result['native_limits']['timeout_seconds'],720)
        evidence=Path(result['timeout_reviews'][0]['evidence'])
        self.assertEqual(json.loads((evidence/'review/role-completion.json').read_text())['boundary'],'PRIVATE_WORK_DELIVERED')
        self.assertEqual(lane.report()['observed_peak_model_stages'],1)


if __name__=='__main__':
    unittest.main()
