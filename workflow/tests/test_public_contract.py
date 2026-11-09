"""Independent delivery decisions and incompatible send/receive contracts."""
from pathlib import Path
import sys
import json
import shutil
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'scripts'))
from blocks.routing import after_audit, after_translation, classify
from wfcore.model import Model


class PublicContractTests(unittest.TestCase):
    def setUp(self):
        self.model=Model(ROOT)
        self.ref={'path':'owned/file','sha256':'3'*64}

    def test_same_binding_type_on_every_evidence_port(self):
        for tag,contract in self.model.spec['contracts'].items():
            if tag in ('Delivery@1','Binding@1'): continue
            for name,field in contract['properties'].items():
                if name!='goal':self.assertEqual(field,{'$ref':'urn:workflow:Binding@1'})
        for ref in ({'path':'owned/file'},{**self.ref,'sha256':'wrong'},{**self.ref,'extra':True}):
            with self.subTest(ref=ref),self.assertRaises(ValueError):
                self.model.check('Request@1',{'job':ref},'public input')
        self.model.check('Request@1',{'job':self.ref},'public input')

    def test_graph_repairs_have_one_foundation_freeze_and_one_final_audit_seal(self):
        from wfcore import storage
        from wfcore.engine import start
        for entry,label in [('unconditional','local-edge'),('audit','audit-edge')]:
            with self.subTest(entry=entry),tempfile.TemporaryDirectory() as raw:
                temp=Path(raw)
                src=temp/'package'
                storage.snapshot(ROOT,src)
                # The builder's disposable audit package already installs the fixture as adapters.py.
                twin=ROOT/'test_adapters.py'
                if twin.is_file():shutil.copyfile(twin,src/'adapters.py')
                dest=temp/'run'
                result=start(src,dest,entry,{'job':{**self.ref,'path':label}})
                self.assertEqual(result['status'],'completed')
                trace=json.loads((dest/'work/state.json').read_text())['trace']
                nodes=[r['node'] for r in trace]
                self.assertEqual(nodes.count('basis/reduce'),int(entry=='unconditional'))
                self.assertEqual(nodes.count('basis/freeze-basis'),int(entry=='unconditional'))
                self.assertEqual(nodes.count('nl0-local/detail'),2)
                self.assertEqual(nodes.count('nl0-local/revise-graph'),1)
                self.assertEqual(nodes.count('nl0-local/audit'),1 if entry=='unconditional' else 2)
                self.assertEqual(nodes.count('nl0-local/seal-audit'),1)
                repair=next(r for r in trace if r['port']=='repair')
                revised=next(r for r in trace if r['node']=='nl0-local/revise-graph')
                seal=next(r for r in trace if r['node']=='nl0-local/seal-audit')
                self.assertEqual(repair['data'],revised['input'])
                self.assertNotEqual(repair['data']['global'],revised['data']['global'])
                self.assertEqual(seal['input']['global'],revised['data']['global'])
                self.assertEqual(seal['input']['authority'],seal['data']['authority'])

    def test_an_incompatible_outer_definition_never_launches_an_old_prepared_job(self):
        import hashlib
        from types import SimpleNamespace
        from blocks.prepared_case import invoke
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw).resolve()
            job=root/'job.json'
            job.write_text(json.dumps({'root':str(root),'workflow_protocol':'yui-workflow-1','track':'nl0'}))
            captured=root/'runtime/workflow/workflow.json'
            captured.parent.mkdir(parents=True)
            captured.write_text('{"name":"an earlier definition"}')
            data={'job':{'path':str(job),'sha256':hashlib.sha256(job.read_bytes()).hexdigest()}}
            with self.assertRaisesRegex(ValueError,'snapshotted workflow CLI'):
                invoke(SimpleNamespace(node='request-audit'),data)
            self.assertFalse((root/'execution-status.json').exists())
            self.assertFalse((root/'protocol').exists())

    def test_stop_and_untested_mathematics_cannot_be_promoted(self):
        for goal in self.model.entries:
            self.assertEqual(classify(goal,'STOPPED_BY_USER',closed=False,qualified=False),('stopped','STOPPED'))
            for status in ('CANCELLED','ACCEPTED','QUEUED','GAP','STRUCTURE-PASSED'):
                with self.subTest(goal=goal,status=status),self.assertRaises(ValueError):
                    classify(goal,status,closed=True,qualified=False)
        with self.assertRaises(ValueError):
            classify('unconditional','WORKFLOW-PASSED',closed=False,qualified=False)
        self.assertEqual(classify('unconditional','WORKFLOW-CONDITIONAL',closed=True,qualified=True)[1],'CLOSED_LEAN_SOURCE_QUALIFIED')

    def test_qualified_sources_and_different_results_keep_separate_exits(self):
        data={'job':self.ref,'global':self.ref,'local':self.ref}
        for goal in ['audit','conditional','unconditional']:
            packet={**data,'goal':goal}
            self.assertEqual(after_audit(packet,self.ref,self.ref)['port'],'finish' if goal=='audit' else 'formalize')
            for different in (True,False):
                port=after_translation(packet,self.ref,different=different)['port']
                self.assertEqual(port,'discharge' if goal=='unconditional' and not different else 'finish')
        self.assertEqual(classify('audit','DRAFT-AUDIT-CONDITIONAL',closed=False,qualified=True)[1],'NL0_SOURCE_QUALIFIED')


if __name__=='__main__':unittest.main()
