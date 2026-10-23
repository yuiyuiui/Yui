"""Native generic-field context/assembly controls; not a selected exercise proof."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ir
import audit_b
import shared_lemmas


class InstanceBinderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        ir.write(self.root/'source.json',{'mathematical_input':'Neutral arbitrary-field additive identity control.'})
        self.c={'version':2,'id':'generic_field_control','source':{'path':'source.json','sha256':ir.digest(self.root/'source.json')},
            'source_steps':[{'id':'S001','text':'Use the additive identity.'},{'id':'S002','text':'Retain the result.'}],
            'pins':{'lean_version':'4.32.2','mathlib_commit':ir.load_lock()['mathlib']['rev']},
            'header':'import Mathlib\n','parameters':[{'name':'K','type':'Type','binder_kind':'implicit'},
                {'name':'instK','type':'Field K','binder_kind':'instance'},{'name':'x','type':'K'}],
            'premises':[{'id':'H001','kind':'hypothesis','statement':'x=x.','type':'x = x'}],
            'conclusion':{'statement':'x+0=x.','type':'x + 0 = x'},'representation':'Arbitrary field with explicit instance context.',
            'objects':[],'shared_obligations':[],'review':{'mode':'development_owner_review'}}
        self.cp=self.root/'contract.json';ir.write(self.cp,self.c)
        self.plan={'version':2,'contract_sha256':ir.digest(self.cp),'representation_notes':'Keep field-instance binders throughout native type and assembly checks.',
            'steps':[{'id':'T001','statement':'x + 0 = x','inputs':['H001'],'source_steps':['S001'],'explanation':'Additive identity.'},
                     {'id':'T002','statement':'x + 0 = x','inputs':['T001'],'source_steps':['S002'],'explanation':'Retain proved equality.'}],'terminal':'T002'}

    def tearDown(self):self.temp.cleanup()

    def test_types_and_actual_multi_node_assembly_keep_implicit_and_instance_parameters(self):
        typed=ir.check(self.cp,self.plan,types_only=True)
        self.assertEqual(typed['exit_code'],0,typed['stdout'])
        proved=ir.check(self.cp,self.plan,{'T001':'simpa using h_H001','T002':'exact h_T001'})
        self.assertEqual(proved['exit_code'],0,proved['stdout'])
        self.assertIn('[instK : Field K]',audit_b.full_type(self.c,'x + 0 = x',[]))

    def test_shared_reuse_preserves_binder_kind_and_native_applications(self):
        value={'pins':self.c['pins'],'header':self.c['header'],'parameters':self.c['parameters'],
            'inputs':[{'id':'H001','binder':'h_H001','type':'x = x'}],'target':'x + 0 = x',
            'objects':[],'representations':[],'bridges':[],'route':'Finite additive identity.'}
        different=copy.deepcopy(value);different['parameters'][1]['binder_kind']='explicit'
        self.assertNotEqual(shared_lemmas.signature_key(value),shared_lemmas.signature_key(different))
        body=shared_lemmas.reuse_body({'obligation':value,'proof':'simpa using h_H001'},value)
        result=ir.check(self.cp,self.plan,{'T001':body},only='T001')
        self.assertEqual(result['exit_code'],0,result['stdout'])

    def test_unknown_binder_styles_fail_before_rendering(self):
        self.c['parameters'][0]['binder_kind']='untrusted'
        ir.write(self.cp,self.c)
        with self.assertRaisesRegex(ir.Invalid,'binder kind'):ir.contract(self.cp)


if __name__=='__main__':unittest.main()
