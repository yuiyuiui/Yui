"""Supplement/provenance controls. Synthetic judgments are not proof certification."""
import harness_support
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
import background
import foundations
import nl0
from artifact_validation import signature_probe
from runtime_config import load_lock


class BackgroundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.probes=tempfile.TemporaryDirectory(prefix='yui-background-probe-')
        signature_probe(Path(cls.probes.name),'M901','Continuous.add',None,1)

    @classmethod
    def tearDownClass(cls):cls.probes.cleanup()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='yui-background-control-')
        self.base=Path(self.tmp.name)
        shutil.copytree(Path(self.probes.name)/'library',self.base/'library')
        (self.base/'problem.txt').write_text('For continuous real functions f,g, their pointwise sum is continuous.\n')
        lock=load_lock()
        self.spec={'format_version':2,'case_id':'background-format-control',
            'full_target':(self.base/'problem.txt').read_text(),'conclusion':'f+g is continuous.',
            'parameters':[{'symbol':x,'type':'function from real numbers to real numbers with their usual topology'} for x in ['f','g']],
            'hypotheses':[{'id':'H001','statement':'f is continuous.','origin':'problem.txt:1'},
                          {'id':'H002','statement':'g is continuous.','origin':'problem.txt:1'}],
            'definitions':[],'logic':{'classical':False,'rules':['direct']},
            'pins':{'lean_version':lock['lean']['version_number'],'mathlib_commit':lock['mathlib']['rev'],'mathlib_root':lock['mathlib']['local_path']},
            'inputs':[{'path':'problem.txt','sha256':nl0.sha(self.base/'problem.txt')}]}
        foundations.bind_author(self.spec['logic'])
        self.write('spec.json',self.spec)
        def prop(pid,kind,text,objects):return {'id':pid,'kind':kind,'statement':text,'definitions':[],'binders':[],'objects':objects}
        self.graph={'format_version':2,'case_id':self.spec['case_id'],'spec_sha256':nl0.sha(self.base/'spec.json'),
            'propositions':[prop('H001','hypothesis','f is continuous.',['f']),prop('H002','hypothesis','g is continuous.',['g']),
                            prop('P','target',self.spec['conclusion'],['f','g'])],
            'inferences':[{'id':'R001','inputs':['H001','H002'],'output':'P','definitions':[],
                          'rules':['direct'],'locals':[],'applications':[], 'argument':[
                              {'id':'S001','text':'H001 and H002 give continuity of f and g, so their pointwise sum is continuous.',
                               'uses':['H001','H002'],'uses_local':[],'objects':['f','g'],'produces':[],'introduces':[],'discharges':[]}]}]}
        self.write('nl0.json',self.graph)
        self.data=nl0.validate(self.base/'nl0.json',self.base/'spec.json')
        self.packet=nl0.packet(self.data,'R001')
        self.note={'id':'BG001','kind':'mathlib','at':'/inference/argument/0/text',
            'fact':'For continuous real-valued f and g, f+g is continuous.',
            'grounds':[{'location':'/inputs/0/statement','reason':'The first continuity premise.'},
                       {'location':'/inputs/1/statement','reason':'The second continuity premise.'},
                       {'location':'/parameters','reason':'The codomain is the usual real topological field.'}],
            'justification':'Routine closure under continuous addition; every condition is supplied. TEST ONLY synthetic judgment.',
            'source':background.source_from_probe(self.base,'M901'),'hint':'Apply Continuous.add.'}
        self.audit=nl0.closure.audit_template(self.data,nl0.CHECKS,nl0.EXTERNAL_CHECKS,'nl0.json','spec.json')
        self.audit['reviewer'].update(identity='TEST_ONLY_SYNTHETIC',mode='external_review',independent=True,
                                      disclosure='Synthetic receipt validation only; no actual model review.')
        def pass_row(row):row.update(verdict='PASS',notes='TEST ONLY synthetic located judgment.')
        pass_row(self.audit['target_review'])
        r=self.audit['inference_reviews']['R001'];pass_row(r)
        for row in r['checks'].values():pass_row(row);row['locations']=['/inputs','/inference','/output']
        r['background_notes']=[self.note]
        refs=self.note['source']['evidence']
        r['replay'].update(mode=background.MODE,carrier='TEST_ONLY_NOT_REAL_REPLAY',library_evidence=refs,
            read_materials=['packet:'+self.packet['packet_sha256']]+['mathlib-evidence:'+e['sha256'] for e in refs])

    def tearDown(self):self.tmp.cleanup()

    def write(self,name,value):(self.base/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

    def accepted(self):
        self.write('audit-test-only.json',self.audit)
        return nl0.validate(self.base/'nl0.json',self.base/'spec.json',self.base/'audit-test-only.json')

    def test_probe_and_notes_preserve_author_bytes_without_adding_a_premise(self):
        before=(self.base/'nl0.json').read_bytes()
        data=self.accepted();props,steps=__import__('background_inputs').effective(data)
        self.assertEqual(data[0]['background_note_count'],1)
        self.assertTrue(data[0]['current_standard_receipt_valid'])
        self.assertEqual((self.base/'nl0.json').read_bytes(),before)
        self.assertNotIn('M001',props)
        self.assertNotIn('M001',steps['R001']['inputs'])
        packet=nl0.packet(data,'R001')
        self.assertEqual(packet['accepted_background_notes'],[self.note])
        self.assertEqual(packet['reviewed_packet_sha256'],self.packet['packet_sha256'])
        self.assertNotEqual(packet['packet_sha256'],self.packet['packet_sha256'])

    def test_notes_require_declared_supported_policy(self):
        del self.audit['background_policy']
        with self.assertRaisesRegex(ValueError,'BACKGROUND-POLICY'):self.accepted()

    def test_cannot_call_background_enabled_review_old_packet_only(self):
        self.audit['inference_reviews']['R001']['replay']['mode']='fresh_packet_only'
        with self.assertRaisesRegex(ValueError,'REPLAY-BOUNDARY'):self.accepted()

    def test_unprobed_or_wrong_pin_is_rejected(self):
        self.note['source']['mathlib_commit']='0'*40
        with self.assertRaisesRegex(ValueError,'wrong library pin'):self.accepted()

    def test_changed_probe_bytes_are_rejected(self):
        path=self.base/self.note['source']['evidence'][0]['path'];path.write_text('{}')
        with self.assertRaisesRegex(ValueError,'changed source evidence'):self.accepted()

    def test_new_h_and_output_cannot_become_ground(self):
        self.note['grounds']=[{'location':'/output/statement','reason':'Assume the conclusion.'}]
        with self.assertRaisesRegex(ValueError,'not available local context') as failure:self.accepted()
        for part in ('/background_notes/0/grounds/0/location','BG001','/output/statement','/inputs'):
            self.assertIn(part,str(failure.exception))

    def test_missing_and_future_packet_locations_identify_the_failing_note_and_field(self):
        for field,location in [('at','/inference/argument/999/text'),
                               ('ground','/inputs/999'),('ground','/inference/argument/999')]:
            with self.subTest(field=field,location=location):
                note=copy.deepcopy(self.note)
                note['id']='BG002'
                if field=='at':note['at']=location
                else:note['grounds'][1]['location']=location
                with self.assertRaises(ValueError) as failure:
                    background.validate([self.note,note],self.packet,self.base)
                path='at' if field=='at' else 'grounds/1/location'
                self.assertIn(f'/background_notes/1/{path} (BG002)',str(failure.exception))
                self.assertIn(location,str(failure.exception))

    def test_note_cannot_erase_actual_failed_check(self):
        self.audit['inference_reviews']['R001']['checks']['argument']['verdict']='FAIL'
        with self.assertRaisesRegex(ValueError,'AUDIT-FAIL'):self.accepted()

    def test_supplement_hash_changes_when_actual_note_changes(self):
        first=self.accepted()[0]['background_supplement']['sha256']
        self.note['hint']='A changed implementation hint is a changed bound supplement.'
        self.assertNotEqual(first,self.accepted()[0]['background_supplement']['sha256'])

    def test_elementary_note_needs_no_extra_library_root(self):
        note=copy.deepcopy(self.note);note.update(kind='elementary',fact='Equality substitution preserves an identical expression.')
        note.pop('source');self.audit['inference_reviews']['R001']['background_notes']=[note]
        self.audit['inference_reviews']['R001']['replay'].update(library_evidence=[],read_materials=['packet:'+self.packet['packet_sha256']])
        self.assertEqual(set(__import__('background_inputs').effective(self.accepted())[0]),set(self.data[3]))


    def test_exercise_translation_adapter_keeps_notes_without_promoting_ports(self):
        self.accepted()
        import translation_author as author
        import interface_review
        out=self.base/'translation-adapter'
        __import__('shutil').copyfile(self.base/'audit-test-only.json',self.base/'audit-a.json')
        author.prepare(self.base,self.base,out)
        inputs=json.loads((out/'inputs/source-map.json').read_text())
        self.assertEqual([p['id'] for p in inputs['roots']],['H001','H002'])
        self.assertEqual(inputs['direct_boundaries']['R001']['background_notes'],['R001.BG001'])
        artifact={'header':'import Mathlib\n','parameters':[{'name':x,'type':'ℝ → ℝ'} for x in ['f','g']],
            'premise_types':{'H001':'Continuous f','H002':'Continuous g'},
            'conclusion_type':'Continuous (f + g)','representation':'Usual real functions.',
            'objects':[],'steps':[{'id':'T001','statement':'Continuous (f + g)',
                'inputs':['H001','H002'],'source_steps':['S001'],
                'background_notes':['R001.BG001'],'explanation':'Apply the permitted continuous addition input.'}],
            'terminal':'T001','source_outputs':{'P':'T001'},
            'endpoint_correspondence':{'P':{'mode':'direct','explanation':'For continuous real functions f and g the target is continuity of their pointwise sum.'}}}
        checked=author.InterfaceContract(out)(artifact)
        self.assertEqual(checked['status'],'IR-TYPES-CHECKED')
        contract=json.loads((out/'candidates/0001/contract.json').read_text())
        supplement=json.loads((out/'inputs/background-supplement.json').read_text())
        self.assertEqual(contract['source']['background_supplement'],supplement)
        self.assertEqual(contract['source']['background_mode'],'node_local_reference')
        review_inputs=self.base/'review-copy';review_inputs.mkdir()
        interface_review.copy_review_inputs(out,review_inputs)
        self.assertEqual((review_inputs/'background-supplement.json').read_bytes(),
                         (out/'inputs/background-supplement.json').read_bytes())
        # Compile an actual note use without introducing an M premise. These
        # are synthetic source receipts testing the adapter, not model evidence.
        import ir,audit_b
        cp=out/'candidates/0001/contract.json';pp=cp.parent/'plan.json'
        bp=cp.parent/'proofs.json'
        ir.write(bp,{'contract_sha256':ir.digest(cp),'plan_sha256':ir.digest(pp),
                     'proofs':{'T001':'exact h_H001.add h_H002'}})
        audit=out/'audit-b'
        audit_b.prepare(cp,pp,bp,audit,graph=self.base/'nl0.json',spec=self.base/'spec.json',
                        audit_a=self.base/'audit-a.json')
        self.assertEqual(set(ir.load(audit/'mapping.json')['entries']),{'P'})
        result=audit_b.build(audit)
        self.assertEqual(result['status'],'AUDIT-B-MECHANICAL-PASSED',result)
        mechanical=ir.load(audit/'mechanical.json')
        self.assertEqual(set(mechanical['required_review_locations']),{'P'})
        self.assertNotIn('dependency_correspondence',mechanical)
        self.assertEqual(ir.load(audit/'source-inventory.json')['background_supplement']['notes']['R001'][0]['source']['declaration'],'Continuous.add')
        with self.assertRaises(ir.Invalid):audit_b.check(audit,audit/'review-template.json')

    def test_clean_local_reviewer_can_save_notes_without_a_second_model(self):
        from clean_stage import ArtifactStage
        from review_contract import ReviewContract
        from execution_state import atomic
        inputs=self.base/'inputs';inputs.mkdir()
        atomic(inputs/'packet.json',self.packet)
        atomic(inputs/'inputs.json',{'inputs':[{'id':'packet.json','path':'packet.json','sha256':nl0.sha(inputs/'packet.json')}]})
        review=ReviewContract(self.base/'review-work',{'checks':{}},[],lambda value:{'test_only':True})
        stage=ArtifactStage(self.base/'stage','Neutral note-persistence software control.',
                            phase='audit-a-packet-replay',library=False,inputs=inputs/'inputs.json',validator=review)
        try:
            self.assertIn('record_background_note',stage.tool_names)
            self.assertFalse({'probe_background','search_mathlib','read_mathlib'} & stage.tool_names)
            self.assertNotIn('exec_command',stage.tool_names)
            args={k:copy.deepcopy(v) for k,v in self.note.items() if k!='source'}
            args['kind']='mathematical'
            result=stage.dispatch('record_background_note',args)
            self.assertEqual(result['recorded'],'BG001')
            self.assertEqual(review.base['background_notes'][0]['kind'],'mathematical')
            self.assertNotIn('source',review.base['background_notes'][0])
            second={**args,'id':'BG002'}
            stage.dispatch('record_background_note',second)
            stage.dispatch('record_background_note',args)
            progress=stage.dispatch('read_review_progress',{})
            self.assertEqual(progress['background_notes'],[args,second])
            attempt=stage.dispatch('submit_draft',{'artifact':{'from_saved_review':True,
                'summary':{'verdict':'PASS','notes':'TEST ONLY','background_notes':[]}}})
            self.assertFalse(attempt['accepted'])
            supplied={**args,'fact':'Updated synthetic observation.'}
            stage.dispatch('record_background_note',supplied)
            final=stage.dispatch('submit_draft',{'artifact':{'from_saved_review':True,'summary':{'verdict':'UNVERIFIED'}}})
            self.assertTrue(final['stage_complete'])
            self.assertEqual(stage.accepted['background_notes'],[supplied,second])
        finally:shutil.rmtree(stage.work,ignore_errors=True)

    def test_zero_extraction_preserves_notes_and_their_source_evidence(self):
        import source_preparation as source
        self.accepted()
        patch={'version':source.VERSION,'baseline_graph_sha256':nl0.sha(self.base/'nl0.json'),
               'spec_sha256':nl0.sha(self.base/'spec.json'),'candidates':[]}
        self.write('patch.json',patch)
        out=self.base/'revision'
        source.stage(self.base/'nl0.json',self.base/'spec.json',self.base/'patch.json',out,
                     audit_a=self.base/'audit-test-only.json')
        result=source.check(out)
        self.assertEqual(result['result']['background_note_count'],1)
        data,_=source.read_source(out/'case/nl0.json',out/'case/spec.json',incremental=out/'source-acceptance.json')
        self.assertEqual(data[0]['background_notes']['R001'][0]['source']['declaration'],'Continuous.add')
        self.assertTrue(data[0]['current_standard_receipt_valid'])


if __name__=='__main__':unittest.main()
