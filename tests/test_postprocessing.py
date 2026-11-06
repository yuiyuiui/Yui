"""Postprocessing feedback/isolation and exact native-check reuse; no models."""
import harness_support

import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import audit_b_mapping as mapping

from audit_b_fixtures import fixture


class PostprocessingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='yui-postprocessing-control-')
        self.root=Path(self.temp.name)

    def tearDown(self):self.temp.cleanup()

    def test_error_tail_is_visible_ahead_of_printed_signatures(self):
        candidate=self.root/'candidate';candidate.mkdir()
        text='A very long printed signature\n'*1500+'Audit.lean:648:0: error: unresolved universe\nactual diagnostic tail\n'
        mapping.ir.write(candidate/'compiler.json',{'stdout':text,'stderr':''})
        shown=mapping.diagnostics(candidate)
        self.assertIn('unresolved universe',shown)
        self.assertIn('actual diagnostic tail',shown)
        self.assertLess(len(shown),14000)

    def test_feedback_tool_is_registered_and_confined_to_own_candidate(self):
        out=self.root/'author';validator=SimpleNamespace(out=out,attempt=1)
        mapping.ir.write(out/'drafts/0001.json',{'own':'saved input'})
        candidate=out/'candidates/0001';candidate.mkdir(parents=True)
        mapping.ir.write(out/'feedback/0001.json',{'native_candidate':str(candidate)})
        mapping.ir.write(candidate/'compiler.json',{'stdout':'\n'.join(str(i) for i in range(600)),'stderr':''})
        stage=mapping.AssemblyStage(out/'stage','Synthetic assembly control.',phase='audit-b-assembly',
                                    library=False,validator=validator)
        try:
            self.assertIn('read_assembly_feedback',stage.tool_names)
            self.assertTrue(any(t['name']=='read_assembly_feedback' for t in stage.tools))
            page=stage.dispatch('read_assembly_feedback',{'candidate':1,'kind':'compiler_stdout','start':1,'end':1000})
            self.assertEqual(page['end'],250);self.assertEqual(page['next_start'],251)
            self.assertIsNone(stage.accepted)
            for args in [{'candidate':0,'kind':'mapping','start':1,'end':2},
                         {'candidate':1,'kind':'../../outside','start':1,'end':2}]:
                self.assertFalse(stage.dispatch('read_assembly_feedback',args)['accepted'])
            mapping.ir.write(out/'feedback/0001.json',{'native_candidate':str(self.root/'another-case')})
            bad=stage.dispatch('read_assembly_feedback',{'candidate':1,'kind':'proof_source','start':1,'end':2})
            self.assertFalse(bad['accepted']);self.assertIsNone(stage.accepted)
        finally:shutil.rmtree(stage.work)

    def prepared(self):
        directory=self.root/'workflow';inputs=directory/'proof-run/inputs'
        cp,pp,bp,ip=fixture(inputs,'mathlib')
        shutil.copyfile(bp,directory/'proof-run/proofs.json')
        mapping.audit_b.prepare(cp,pp,bp,directory/'audit-b',fragment=ip)
        value=mapping.ir.load(directory/'audit-b/mapping.json')
        value['library_terms']['M001']='exact Nat.add_comm a b'
        out=self.root/'author';mapping.ir.write(out/'authority.json',{'workflow':str(directory)})
        frozen={'authority':{'fragment':str(ip)},'contract':str(cp)}
        return mapping.MappingContract(out),value,frozen

    def test_check_then_identical_submit_reuses_only_unchanged_native_evidence(self):
        validator,value,frozen=self.prepared()
        original=mapping.audit_b.build
        with patch.object(mapping.workflow,'bound',return_value=frozen),patch.object(mapping.audit_b,'build',wraps=original) as build:
            first=validator(value)
            second=validator(json.loads(json.dumps(value)))
            self.assertEqual(first['status'],'AUDIT-B-MECHANICAL-PASSED')
            self.assertTrue(second['reused_exact_native_check'])
            self.assertEqual(build.call_count,1)
            self.assertEqual(second['semantic_review'],'UNVERIFIED')
            accepted=mapping.ir.load(validator.out/'accepted-mapping-path.json')
            proof=Path(accepted['candidate'])/'Proof.lean';proof.write_text(proof.read_text()+'\n-- changed artifact\n')
            third=validator(value)
            self.assertEqual(third['status'],'AUDIT-B-MECHANICAL-PASSED')
            self.assertEqual(build.call_count,2)
            self.assertNotIn('reused_exact_native_check',third)
            selected=validator.out.parent/'workflow/proof-run/proofs.json'
            bundle=mapping.ir.load(selected);bundle['proofs']['T001']='simpa using h_M001'
            mapping.ir.write(selected,bundle)
            fourth=validator(value)
            self.assertEqual(fourth['status'],'AUDIT-B-MECHANICAL-PASSED')
            self.assertEqual(build.call_count,3,'Changed effective proof input must be checked, even with identical mapping')
            self.assertNotIn('reused_exact_native_check',fourth)

    def test_rejected_mapping_is_saved_with_located_feedback(self):
        validator,value,frozen=self.prepared()
        def duplicate():return json.loads(json.dumps(value))
        explanation=duplicate();explanation['entries']['P']['correspondence']['explanation']=''
        extra=duplicate();extra['unregistered_field']=True
        term=duplicate();term['library_terms']['M001']=False
        node=duplicate();node['proof_patches']={'T099':'exact True.intro'}
        variants=[(explanation,'/entries/P/correspondence/explanation'),
                  (extra,'unregistered_field'),(term,'/library_terms/M001'),(node,'T099')]
        with patch.object(mapping.workflow,'bound',return_value=frozen):
            for number,(invalid,location) in enumerate(variants,1):
                with self.subTest(location=location):
                    before=json.loads(json.dumps(invalid))
                    with self.assertRaisesRegex(ValueError,f'Candidate {number}:'):
                        validator(invalid)
                    self.assertEqual(invalid,before)
                    self.assertEqual(mapping.ir.load(validator.out/'drafts'/f'{number:04d}.json'),before)
                    self.assertIn(location,mapping.ir.load(validator.out/'feedback'/f'{number:04d}.json')['error'])
                    self.assertFalse((validator.out/'accepted-mapping-path.json').exists())
            result=validator(value)
            self.assertEqual(result['status'],'AUDIT-B-MECHANICAL-PASSED')
            self.assertTrue((validator.out/'accepted-mapping-path.json').is_file())


if __name__=='__main__':unittest.main()
