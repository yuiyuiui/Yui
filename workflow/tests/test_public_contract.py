"""Independent delivery decisions and incompatible send/receive contracts."""
from pathlib import Path
import sys
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
