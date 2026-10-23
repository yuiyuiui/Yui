"""Explicit job-schema/path controls; no model or mathematical acceptance."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import queue_controller as q


class QueueControllerTests(unittest.TestCase):
    def test_jobs_keep_the_frozen_case_and_explicit_result_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);case=root/'test/results/neutral/case';case.mkdir(parents=True)
            for name in ['spec.json','nl0.json']:(case/name).write_text('{}')
            job={'id':'neutral-control','kind':'translate','case':'lie-module-irreducibility',
                 'source':'neutral/case','interface':'neutral-interface','workflow':'neutral-workflow'}
            with patch.object(q.a,'ROOT',root):
                q.validate_job(job)
                with self.assertRaisesRegex(ValueError,'exact staged case'):
                    q.validate_job({**job,'source':'../../outside'})
                with self.assertRaisesRegex(ValueError,'frozen exercise'):
                    q.validate_job({**job,'case':'a-substituted-easy-theorem'})
                with self.assertRaisesRegex(ValueError,'schema'):
                    q.validate_job({**job,'shell_command':'not-permitted'})

    def test_nl0_jobs_name_every_next_gate(self):
        job={'id':'neutral-control','kind':'nl0','case':'wave-map-energy','run':'neutral-nl0',
             'audit':'neutral-audit','interface':'neutral-interface','workflow':'neutral-workflow'}
        q.validate_job(job)
        with self.assertRaisesRegex(ValueError,'schema'):
            q.validate_job({k:v for k,v in job.items() if k!='audit'})

    def test_checked_interface_recovery_requires_an_explicit_real_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);case=root/'test/results/neutral/case';case.mkdir(parents=True)
            for name in ['spec.json','nl0.json']:(case/name).write_text('{}')
            job={'id':'neutral-control','kind':'checked_interface','case':'lie-module-irreducibility',
                'source':'neutral/case','interface':'neutral-interface','workflow':'neutral-workflow','candidate':1}
            with patch.object(q.a,'ROOT',root):
                q.validate_job(job)
                with self.assertRaisesRegex(ValueError,'positive candidate'):
                    q.validate_job({**job,'candidate':True})


if __name__=='__main__':unittest.main()
