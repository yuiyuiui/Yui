"""Mathematical-NL0 protocol controls with synthetic judgments, not model proof certification."""
import harness_support
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import audit_a_campaign as campaign
import background
import background_inputs
import nl0
import translation_author
from source_fixtures import synthetic_audit
from clean_stage import ArtifactStage
from controller_common import write, manifest
from review_contract import ReviewContract


class MathematicalNL0PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='yui-mathematical-policy-')
        self.root=Path(self.temp.name)
        self.case=self.root/'case'
        shutil.copytree(harness_support.FIXTURES/'closed-addition',self.case)
        self.data=nl0.validate(self.case/'nl0.json',self.case/'spec.json')
        self.packet=nl0.packet(self.data,'R001')
        self.note={'id':'BG001','kind':'mathematical',
            'at':'/inference/argument/0/text',
            'fact':'For elements a,b of the same type, a=b implies b=a.',
            'grounds':[{'location':'/inputs/0/statement','reason':'Supplies the equality.'},
                       {'location':'/parameters','reason':'The elements have the same real type.'}],
            'justification':'Equality symmetry. SYNTHETIC FORMAT CONTROL, not an actual model review.'}

    def tearDown(self):
        self.temp.cleanup()

    def audit(self):
        audit=json.loads(synthetic_audit(self.case/'nl0.json',self.case/'spec.json').read_text())
        row=audit['inference_reviews']['R001']
        row['background_notes']=[copy.deepcopy(self.note)]
        row['replay'].update(mode=background.MODE,library_evidence=[],
            read_materials=['packet:'+self.packet['packet_sha256']])
        return audit

    def validate_audit(self,audit):
        path=self.case/'audit-a.json';write(path,audit)
        return nl0.validate(self.case/'nl0.json',self.case/'spec.json',path)

    def test_math_only_supplement_is_hash_bound_and_not_a_lean_premise(self):
        before=(self.case/'nl0.json').read_bytes()
        with patch.object(background,'source_check',side_effect=AssertionError('No native source for this math note')):
            data=self.validate_audit(self.audit())
        self.assertEqual(data[0]['audit_format_version'],4)
        self.assertEqual(data[0]['background_note_count'],1)
        self.assertEqual(data[0]['harness_variant'],'rigorous-proof')
        self.assertEqual((self.case/'nl0.json').read_bytes(),before)
        self.assertEqual(background_inputs.effective(data)[0],self.data[3])
        out=self.root/'interface'
        translation_author.prepare(self.case,self.case,out)
        supplement=json.loads((out/'inputs/background-supplement.json').read_text())
        self.assertEqual(supplement['notes']['R001'],[self.note])
        source_map=json.loads((out/'inputs/source-map.json').read_text())
        self.assertEqual([p['id'] for p in source_map['roots']],['H001'])
        self.assertEqual(source_map['direct_boundaries']['R001']['background_notes'],['R001.BG001'])

    def test_another_variants_receipt_or_policy_is_not_current_authority(self):
        audit=self.audit();audit['format_version']=3
        with self.assertRaisesRegex(ValueError,'AUDIT-VERSION'):
            self.validate_audit(audit)
        audit=self.audit();audit['background_policy']='verified-background-1'
        with self.assertRaisesRegex(ValueError,'BACKGROUND-POLICY'):
            self.validate_audit(audit)

    def test_math_note_cannot_assert_native_provenance_or_use_its_conclusion(self):
        note=copy.deepcopy(self.note);note['source']={'declaration':'guessed'}
        with self.assertRaisesRegex(ValueError,'/background_notes/0.*BG001.*unexpected=.*source'):
            background.validate([note],self.packet,self.root)
        note=copy.deepcopy(self.note)
        note['grounds']=[{'location':'/output/statement','reason':'Assume the desired conclusion.'}]
        with self.assertRaisesRegex(ValueError,'available local context'):
            background.validate([note],self.packet,self.root)

    def test_notes_cannot_override_actual_failures_or_incomplete_coverage(self):
        for name in nl0.CHECKS | nl0.closure.CLOSURE_CHECKS:
            with self.subTest(check=name):
                audit=self.audit()
                audit['inference_reviews']['R001']['checks'][name]['verdict']='FAIL'
                with self.assertRaisesRegex(ValueError,'AUDIT-FAIL'):
                    self.validate_audit(audit)
        audit=self.audit();del audit['inference_reviews']['R001']['checks']['argument']
        with self.assertRaises(ValueError):self.validate_audit(audit)

    def test_review_trace_is_bound_separately_from_native_library_evidence(self):
        trace=self.case/'synthetic-review-tools.jsonl'
        trace.write_text('{"tool":"read_task_inputs","scope":"SYNTHETIC FORMAT CONTROL"}\n')
        audit=self.audit();replay=audit['inference_reviews']['R001']['replay']
        replay['review_trace']={'path':trace.name,'sha256':nl0.sha(trace)}
        result=self.validate_audit(audit)[0]
        self.assertEqual(result['background_note_count'],1)
        self.assertEqual(replay['library_evidence'],[])
        self.assertEqual(replay['read_materials'],['packet:'+self.packet['packet_sha256']])
        mistaken=copy.deepcopy(audit)
        mistaken['inference_reviews']['R001']['replay']['library_evidence']=[replay['review_trace']]
        with self.assertRaisesRegex(ValueError,'not library evidence'):
            self.validate_audit(mistaken)
        trace.write_text('changed')
        with self.assertRaisesRegex(ValueError,'HASH'):
            self.validate_audit(audit)

    def test_complete_review_submits_mathematical_notes_in_one_call(self):
        inputs=self.root/'inputs';inputs.mkdir()
        write(inputs/'packet.json',self.packet);manifest(inputs)
        required=['/checks/'+key for key in sorted(nl0.CHECKS | nl0.closure.CLOSURE_CHECKS)]
        contract=ReviewContract(self.root/'review-work',{},required,
            lambda value:campaign.validate_review(value,inputs,False))
        stage=ArtifactStage(self.root/'stage',campaign.PACKET,phase='audit-a-packet-replay',
            inputs=inputs/'inputs.json',library=False,validator=contract)
        try:
            row={'verdict':'PASS','notes':'Synthetic located record only.',
                 'locations':['/inference/argument/0/text']}
            artifact={'inference':'R001','packet_sha256':self.packet['packet_sha256'],
                'verdict':'PASS','notes':'SYNTHETIC, not an actual mathematical assessment.',
                'checks':{pointer.rsplit('/',1)[1]:copy.deepcopy(row) for pointer in required},
                'coverage':dict.fromkeys(required,'assessed'),
                'findings':[],'background_notes':[self.note]}
            result=stage.dispatch('submit_draft',{'artifact':artifact})
            self.assertTrue(result['stage_complete']);self.assertTrue(result['accepted'])
            self.assertEqual(stage.accepted['background_notes'],[self.note])
            self.assertFalse({'probe_background','search_mathlib','read_mathlib'} & stage.tool_names)
            self.assertIn('read_task_inputs',stage.tool_names)
            self.assertEqual((stage.api_calls,stage.lean_calls),(0,0))
        finally:
            shutil.rmtree(stage.work,ignore_errors=True)


if __name__=='__main__':unittest.main()
