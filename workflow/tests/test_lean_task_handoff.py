"""Independent Workflow Builder examples for the global plan to local author port."""
import hashlib
import json
from pathlib import Path
import runpy
import tempfile
import unittest


read_local_task = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                                     'blocks/private_proof_handoff.py'))['read_local_task']


class LocalAuthor(unittest.TestCase):
    def setUp(self):
        storage = tempfile.TemporaryDirectory()
        self.addCleanup(storage.cleanup)
        self.root = Path(storage.name)
        self.request = self.root / 'T012.json'
        self.owner = {'run_id': 'sample-run', 'sender': 'frozen-lean-plan', 'node': 'T012',
                      'contract_sha256': 'a' * 64, 'plan_sha256': 'b' * 64}
        files = {}
        for field, value in {
            'goal': {'target': 'HeightGlobal'},
            'inputs': {'inputs': [{'id': 'E102', 'binder': 'h_E102', 'type': 'VolumeBound'}]},
            'source': {'source_steps': [{'id': 'S082', 'text': 'The height argument uses the private regions.'}]},
            'review': {'status': 'REVIEWED_LOCAL_TASKS'},
        }.items():
            path = self.root / f'{field}.json'
            path.write_text(json.dumps(value))
            files[field] = {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        self.row = {'schema': 'yui-lean-local-task-1', **self.owner, 'files': files}
        self.request.write_text(json.dumps(self.row))

    def test_author_finds_each_required_file_in_one_manifest(self):
        artifacts = read_local_task(self.request, self.owner)
        self.assertEqual(set(artifacts), {'goal', 'inputs', 'source', 'review'})
        source = json.loads(artifacts['source'].read_text())['source_steps']
        self.assertEqual(source[0]['id'], 'S082')
        self.assertIn('height argument', source[0]['text'])

    def test_other_node_run_or_broken_source_is_rejected(self):
        for key, value in [('node', 'T077'), ('run_id', 'different-run')]:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, '/' + key):
                read_local_task(self.request, {**self.owner, key: value})
        source = self.root / 'source.json'
        source.write_text('{}')
        with self.assertRaisesRegex(ValueError, '/files/source/sha256'):
            read_local_task(self.request, self.owner)
        source.unlink()
        with self.assertRaisesRegex(ValueError, '/files/source/path'):
            read_local_task(self.request, self.owner)


if __name__ == '__main__':
    unittest.main()
