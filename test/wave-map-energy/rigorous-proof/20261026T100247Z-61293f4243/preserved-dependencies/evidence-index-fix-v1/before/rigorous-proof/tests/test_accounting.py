"""Accounting controls on actual provider shapes, without generating model calls."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import usage


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def stage(self, count=1):
        p = self.root / 'stage'
        p.mkdir()
        (p / 'requests.jsonl').write_text(''.join(json.dumps({'request_number': i+1})+'\n' for i in range(count)))
        return p

    def event(self, rid='one', **changes):
        u = {'input_tokens': 100, 'input_tokens_details': {'cached_tokens': 60},
             'output_tokens': 20, 'output_tokens_details': {'reasoning_tokens': 15}, 'total_tokens': 120}
        u.update(changes)
        return {'type': 'response.completed', 'response': {'id': rid, 'model': 'gpt-6-luna',
                'status': 'completed', 'service_tier': 'default', 'usage': u}}

    def write(self, p, index, events):
        (p / f'response-{index:04d}.sse').write_text(''.join('data: '+json.dumps(e)+'\n\n' for e in events))

    def test_subset_categories_are_not_added_twice(self):
        p = self.stage();self.write(p, 1, [self.event()])
        result = usage.summarize_stage(p)
        self.assertEqual(result['total_usage']['total_tokens'], 120)
        self.assertEqual(result['total_usage']['reasoning_tokens'], 15)
        self.assertTrue(result['complete'])

    def test_duplicate_response_events_count_once(self):
        p = self.stage();self.write(p, 1, [self.event(), self.event()])
        result = usage.summarize_stage(p)
        self.assertEqual(result['unique_responses'], 1)
        self.assertEqual(result['total_usage']['total_tokens'], 120)

    def test_failed_or_missing_usage_is_unknown(self):
        p = self.stage(2);self.write(p, 1, [self.event()])
        result = usage.summarize_stage(p)
        self.assertEqual(result['missing_requests'], [2])
        self.assertIsNone(result['total_usage'])
        self.assertEqual(result['observed_usage']['total_tokens'], 120)

    def test_created_auto_does_not_replace_actual_default(self):
        p = self.stage()
        self.write(p, 1, [{'type': 'response.created', 'response': {'id': 'one', 'service_tier': 'auto'}}, self.event()])
        self.assertEqual(usage.summarize_stage(p)['standard_speed_observation'], 'CONSISTENT')

    def test_provisional_created_usage_is_not_a_second_final_charge(self):
        p=self.stage();created=self.event(input_tokens=0,output_tokens=0,total_tokens=0,
            input_tokens_details={'cached_tokens':0},output_tokens_details={'reasoning_tokens':0})
        created['type']='response.created'
        self.write(p,1,[created,self.event()])
        result=usage.summarize_stage(p)
        self.assertTrue(result['complete'])
        self.assertEqual(result['total_usage']['total_tokens'],120)
        self.assertFalse(result['errors'])

    def test_actual_premium_tier_is_detected(self):
        p = self.stage();event = self.event();event['response']['service_tier'] = 'priority'
        self.write(p, 1, [event])
        self.assertEqual(usage.summarize_stage(p)['standard_speed_observation'], 'MISMATCH')

    def test_conflicting_usage_cannot_claim_complete(self):
        p = self.stage();self.write(p, 1, [self.event(), self.event(input_tokens=101, total_tokens=121)])
        self.assertFalse(usage.summarize_stage(p)['complete'])

    def test_inconsistent_total_is_rejected(self):
        p = self.stage();self.write(p, 1, [self.event(total_tokens=999)])
        self.assertEqual(usage.summarize_stage(p)['status'], 'NOT_RECORDED')

    def test_cross_stage_aggregate_includes_failures_and_all_agents(self):
        p = self.stage();self.write(p, 1, [self.event()])
        q = self.root / 'worker';q.mkdir()
        (q/'requests.jsonl').write_text('{"request_number":1}\n')
        self.write(q, 1, [self.event('two')])
        result = usage.aggregate(self.root)
        self.assertEqual(result['total_usage']['total_tokens'], 240)
        self.assertEqual(len(result['stages']), 2)


if __name__ == '__main__':
    unittest.main()
