"""Independent examples for the private child/parent handoff inside translate."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('private_wire', Path(__file__).resolve().parents[1]/'blocks/private_proof_handoff.py')
wire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wire)


class PrivateDelivery(unittest.TestCase):
    def setUp(self):
        storage = tempfile.TemporaryDirectory()
        self.addCleanup(storage.cleanup)
        self.root = Path(storage.name).resolve()
        self.request = self.root/'request.json'
        self.result = self.root/'result-001.json'
        def artifact(name):
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name)
            return {'path':name, 'sha256':hashlib.sha256(name.encode()).hexdigest()}
        self.request.write_text(json.dumps({'schema':'yui-private-proof-request-1', 'run_id':'case-one',
            'parent_node':'T034', 'task_id':'helper-01','parent_context_sha256':'a'*64,
            'files':{name:artifact('input/'+name+'.json') for name in ('source','contract','plan')}}))
        self.record = {'schema':'yui-private-proof-result-1','attempt':1,'status':'checked',
            'request':{'path':'request.json','sha256':hashlib.sha256(self.request.read_bytes()).hexdigest()},
            'files':{k:artifact('attempt-001/'+k+'.json') for k in ('proof','check')}}
        self.result.write_text(json.dumps(self.record))

    def test_parent_finds_all_artifacts_from_the_issued_request_and_result(self):
        record, inputs = wire.read_request(self.request)
        self.assertEqual(record['parent_node'],'T034')
        self.assertEqual(inputs['source'].read_text(),'input/source.json')
        record, files = wire.read_result(self.result,self.request)
        self.assertEqual(record['attempt'],1)
        self.assertEqual(files['proof'].read_text(),'attempt-001/proof.json')
        self.assertEqual(files['check'].read_text(),'attempt-001/check.json')

    def test_wrong_request_or_changed_proof_cannot_cross_the_boundary(self):
        foreign = self.root/'other/request.json'
        foreign.parent.mkdir()
        foreign.write_bytes(self.request.read_bytes())
        with self.assertRaisesRegex(ValueError,'request'):
            wire.read_result(self.result,foreign)
        (self.root/'attempt-001/proof.json').write_text('different proof')
        with self.assertRaisesRegex(ValueError,'/files/proof'):
            wire.read_result(self.result,self.request)

    def test_every_status_has_exact_required_files(self):
        for status, field in [('needs_parent_repair','diagnosis'),('unfinished','progress'),('execution_error','error')]:
            row={**self.record,'status':status}
            with self.subTest(status=status):
                self.result.write_text(json.dumps(row))
                with self.assertRaisesRegex(ValueError,'/files'):
                    wire.read_result(self.result,self.request)
                row['files']={field:self.record['files']['proof']}
                self.result.write_text(json.dumps(row))
                self.assertEqual(set(wire.read_result(self.result,self.request)[1]),{field})

    def test_malformed_missing_or_linked_input_is_rejected_with_its_location(self):
        row=json.loads(self.request.read_text())
        ref=row['files']['source']
        (self.root/'input/link').symlink_to(self.root/'input/source.json')
        for target in ('../outside','/outside','input/link','input/missing'):
            with self.subTest(target=target):
                ref['path']=target
                self.request.write_text(json.dumps(row))
                with self.assertRaisesRegex(ValueError,'/files/source'):
                    wire.read_request(self.request)
        row['extra']=True
        self.request.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError,'extra'):
            wire.read_request(self.request)


if __name__=='__main__':unittest.main()
