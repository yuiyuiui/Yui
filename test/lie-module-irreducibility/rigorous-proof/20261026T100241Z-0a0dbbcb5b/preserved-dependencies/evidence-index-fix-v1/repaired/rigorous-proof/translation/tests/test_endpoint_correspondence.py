"""Lightweight endpoint-note and source-boundary controls; no model calls."""
import copy
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE/'scripts'))
import correspondence
import ir
import workflow


class EndpointCorrespondenceTests(unittest.TestCase):
    def test_only_externals_and_complete_target_are_required(self):
        props=[{'id':k,'kind':v} for k,v in [
            ('H001','hypothesis'),('E001','external'),('M001','mathlib'),
            ('N001','internal'),('P','target')]]
        self.assertEqual(correspondence.endpoint_ids(props),['E001','P'])

    def test_short_direct_and_explained_equivalent_forms_are_accepted(self):
        correspondence.validate_notes({
            'E001':{'mode':'direct','explanation':'The same universal quantifiers and inequality.'},
            'P':{'mode':'equivalent','explanation':'Invariance under the basis implies invariance under every linear combination; the converse evaluates at each basis vector.'},
        },['E001','P'])

    def test_absent_empty_or_extra_explanations_are_rejected(self):
        for notes in ({}, {'P':{'mode':'direct','explanation':''}},
                      {'P':{'mode':'unknown','explanation':'a'}},
                      {'P':{'mode':'direct','explanation':'a'},'M001':{'mode':'direct','explanation':'b'}}):
            with self.subTest(notes=notes), self.assertRaises(ir.Invalid):
                correspondence.validate_notes(notes,['P'])

    def source_boundary(self):
        props={p['id']:p for p in [
            {'id':'H001','kind':'hypothesis','statement':'p'},
            {'id':'M001','kind':'mathlib','statement':'A library result'},
            {'id':'P','kind':'target','statement':'p'}]}
        inference={'R001':{'inputs':['H001','M001'],'output':'P',
            'argument':[{'id':'S001','text':'Use the hypothesis.'}]}}
        data=({},None,None,props,inference)
        contract={'source':{'background_mode':'node_local_reference'},
            'premises':[props['H001']], 'conclusion':{'statement':'p'},
            'source_steps':[{'id':'S001','text':'Use the hypothesis.'}]}
        plan={'steps':[{'id':'T001','inputs':['H001'],'source_steps':['S001']}], 'terminal':'T001'}
        mapping={'S001':{'inference':'R001','paragraph':'S001'}}
        return data,contract,plan,mapping,{'P':'T001'}

    def test_mathlib_ports_can_be_omitted_without_changing_source(self):
        result=workflow.check_source_boundary(*self.source_boundary())
        self.assertEqual(result['status'],'SOURCE_BOUNDARIES_CHECKED')

    def test_missing_project_hypothesis_still_fails(self):
        args=copy.deepcopy(self.source_boundary());args[2]['steps'][0]['inputs']=[]
        with self.assertRaisesRegex(ir.Invalid,'source input boundary changed'):
            workflow.check_source_boundary(*args)


if __name__ == '__main__':
    unittest.main()
