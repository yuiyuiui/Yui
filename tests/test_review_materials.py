"""Synthetic material/provenance controls, not mathematical audit judgments."""
import harness_support
import copy
import json
from pathlib import Path
import tempfile
import unittest

import ir
import review_materials as views


class ReviewMaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.inventory={'scope':'development_fragment','full_target':'For all p, if p then p.',
            'parameters':[{'name':'p','type':'Prop'}],
            'definitions':[{'id':'D001','definition':'Synthetic context definition, including a proof field.'}],
            'logic':{'classical':False},'propositions':[
                {'id':'H001','kind':'hypothesis','statement':'p'},
                {'id':'P','kind':'target','statement':'p'}]}
        self.mapping={'entries':{'P':{'selector':'decl:AuditBExport.P','expected_type':'DO NOT SUBSTITUTE THIS FOR THE ACTUAL TYPE',
            'correspondence':{'mode':'direct','explanation':'Synthetic explanation only.'}}}}
        self.evidence={'comparisons':[{'id':'P','selector':'decl:AuditBExport.P','actual_type':'∀ p : Prop, p → p',
            'expected_type':'UNTRUSTED EXPECTED STRING','definitionally_equal':True}],
            'dependencies':{'truncated':False,'declarations':[{'name':'AuditBExport.P','imported':False,
                'kind':'theorem','axioms':[],'type':'Large native program detail. '*200000}]}}
        self.mechanical={'passed':True,'errors':[],'compiler_exit_code':0,'local_checks':{'T001':{'exit_code':0}},
            'assembly':{'status':'ASSEMBLY-PASSED'},'inspection':{'status':'KERNEL_INSPECTION_PASSED'}}
        for name,value in [('source-inventory.json',self.inventory),('mapping.json',self.mapping),
                           ('elaborated.json',self.evidence),('compiler.json',{'exit_code':0,'stdout':json.dumps(self.evidence)}),
                           ('mechanical.json',self.mechanical)]:ir.write(self.root/name,value)
        (self.root/'Proof.lean').write_text('Synthetic text fixture, not a Lean proof.\n')
        self.source=self.root/'original.txt';self.source.write_text('Original synthetic statement with all assumptions.\n')

    def tearDown(self):self.temp.cleanup()

    def project(self):
        return views.project(self.root,self.inventory,self.mapping,self.evidence,self.mechanical,
            source_file=self.source,foundations={'propext'})

    def test_large_native_dump_stays_raw_and_the_review_view_uses_actual_types(self):
        raw={name:ir.digest(self.root/name) for name in ['compiler.json','elaborated.json']}
        packet=self.project()
        self.assertLess((self.root/'review-packet.json').stat().st_size,12000)
        self.assertEqual(packet['endpoints']['P']['actual']['type'],'∀ p : Prop, p → p')
        self.assertNotIn('UNTRUSTED EXPECTED STRING',json.dumps(packet))
        self.assertEqual(raw,{name:ir.digest(self.root/name) for name in raw})
        self.assertEqual(views.verify_projection(self.root,foundations={'propext'}),packet)

    def test_complete_target_hypotheses_and_all_definition_context_remain_accessible(self):
        packet=self.project();context=ir.load(self.root/'source-context.json')
        self.assertEqual(packet['scope']['full_target'],self.inventory['full_target'])
        self.assertEqual(packet['scope']['hypotheses'],[self.inventory['propositions'][0]])
        self.assertEqual(context['definitions'],self.inventory['definitions'])
        self.assertEqual((self.root/'source-original.txt').read_bytes(),self.source.read_bytes())
        self.assertIn('/scope/hypotheses',views.required_locations(packet)['P'])
        self.assertEqual(packet['mechanical_summary']['semantic_review'],'NOT_PERFORMED')

    def test_modified_actual_type_is_rejected(self):
        packet=self.project();packet['endpoints']['P']['actual']['type']='True';ir.write(self.root/'review-packet.json',packet)
        with self.assertRaisesRegex(ir.Invalid,'actual inspected type'):views.verify_projection(self.root,foundations={'propext'})

    def test_changed_raw_or_context_bytes_invalidate_the_view(self):
        self.project();ir.write(self.root/'compiler.json',{'exit_code':0,'stdout':'changed'})
        with self.assertRaisesRegex(ir.Invalid,'stale review projection'):views.verify_projection(self.root,foundations={'propext'})

    def test_missing_or_duplicate_actual_endpoint_is_rejected(self):
        self.evidence['comparisons']=[]
        with self.assertRaisesRegex(ir.Invalid,'actual inspected endpoint'):self.project()
        row={'id':'P','selector':'decl:AuditBExport.P','actual_type':'True','definitionally_equal':True}
        self.evidence['comparisons']=[row,copy.deepcopy(row)]
        with self.assertRaisesRegex(ir.Invalid,'duplicate'):self.project()

    def test_external_endpoint_keeps_its_full_source_and_stable_id(self):
        external={'id':'E001','kind':'external','statement':'For every q, under the supplied condition C(q), Q(q).',
            'binders':[{'name':'q','type':'Synthetic domain'}],'source':{'hypotheses':['C(q)']}}
        self.inventory['propositions'].insert(0,external)
        self.mapping['entries']['E001']={'selector':'premise:E001','expected_type':'EXPECTED ONLY',
            'correspondence':{'mode':'equivalent','explanation':'Synthetic explanation, not a verified mathematical equivalence.'}}
        self.evidence['comparisons'].append({'id':'E001','selector':'premise:E001','actual_type':'ACTUAL EXTERNAL TYPE',
            'definitionally_equal':True})
        packet=self.project()
        self.assertEqual(packet['endpoints']['E001']['source'],external)
        self.assertEqual(packet['endpoints']['E001']['actual']['type'],'ACTUAL EXTERNAL TYPE')
        self.assertEqual(set(packet['endpoints']),{'E001','P'})
        self.assertIn('/endpoints/E001/source',views.required_locations(packet)['E001'])


if __name__=='__main__':unittest.main()
