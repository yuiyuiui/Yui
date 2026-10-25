"""Supplement/provenance controls. Synthetic judgments are not proof certification."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
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
            'pins':{'lean_version':'4.32.2','mathlib_commit':lock['mathlib']['rev'],'mathlib_root':lock['mathlib']['local_path']},
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
        self.audit['reviewer'].update(identity='TEST_ONLY_SYNTHETIC',mode='same_context_self_audit',independent=False,
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

    def test_probe_and_notes_preserve_author_bytes_and_supply_effective_library_port(self):
        before=(self.base/'nl0.json').read_bytes()
        data=self.accepted();props,steps=background.effective(data)
        self.assertEqual(data[0]['background_note_count'],1)
        self.assertTrue(data[0]['current_standard_receipt_valid'])
        self.assertEqual((self.base/'nl0.json').read_bytes(),before)
        self.assertEqual(props['M001']['source']['declaration'],'Continuous.add')
        self.assertIn('M001',steps['R001']['inputs'])
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
        with self.assertRaisesRegex(ValueError,'not available local context'):self.accepted()

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
        self.assertEqual(set(background.effective(self.accepted())[0]),set(self.data[3]))

    def test_translation_and_audit_b_cannot_drop_the_accepted_supplement(self):
        sys.path.insert(0,str(ROOT/'translation/scripts'))
        import ir, workflow, audit_b
        data=self.accepted();props,_=background.effective(data)
        cp=self.base/'contract.json';pp=self.base/'plan.json';rp=self.base/'interface-review.json'
        c={'version':2,'id':'background_handoff_control',
           'source':{'path':'nl0.json','sha256':nl0.sha(self.base/'nl0.json')},
           'pins':{'lean_version':'4.32.2','mathlib_commit':self.spec['pins']['mathlib_commit']},
           'source_steps':[{'id':'S001','text':self.graph['inferences'][0]['argument'][0]['text']}],
           'header':'import Mathlib\n','parameters':[{'name':x,'type':'ℝ → ℝ'} for x in ['f','g']],
           'premises':[{'id':pid,'kind':props[pid]['kind'],'statement':props[pid]['statement'],'type':typ}
                       for pid,typ in [('H001','Continuous f'),('H002','Continuous g'),
                                       ('M001','Continuous f → Continuous g → Continuous (f + g)')]],
           'conclusion':{'type':'Continuous (f + g)','statement':self.spec['conclusion']},
           'representation':{'space':'Real-valued continuous functions.'},
           'review':{'mode':'upstream_audited_packet','scope':'TEST ONLY synthetic source/interface judgments.'}}
        ir.write(cp,c)
        plan={'version':2,'contract_sha256':ir.digest(cp),'representation_notes':'All functions are real-valued on the real line.',
              'steps':[{'id':'T001','statement':'Continuous (f + g)','inputs':['H001','H002','M001'],
                        'source_steps':['S001'],'explanation':'Apply the actual background library source to the two continuous functions.'}],
              'terminal':'T001'}
        ir.write(pp,plan)
        with self.assertRaisesRegex(ValueError,'omitted or changed accepted background'):
            workflow.freeze(self.base/'nl0.json',self.base/'spec.json',cp,pp,rp,self.base/'bad-freeze',audit_a=self.base/'audit-test-only.json')
        c['source']['background_supplement_sha256']=data[0]['background_supplement']['sha256']
        c['source']['background_supplement']=data[0]['background_supplement'];ir.write(cp,c)
        plan['steps'][0]['background_notes']=['R001.BG001']
        plan['contract_sha256']=ir.digest(cp);ir.write(pp,plan)
        review={'version':workflow.VERSION,'source_graph_sha256':nl0.sha(self.base/'nl0.json'),
                'contract_sha256':ir.digest(cp),'plan_sha256':ir.digest(pp),
                'reviewer':{'identity':'TEST_ONLY','mode':'same_context_self_audit','independent':False,
                            'disclosure':'Synthetic format control, not real review.'},
                'checks':{key:{'verdict':'PASS','notes':'Synthetic TEST ONLY judgment.'} for key in workflow.INTERFACE_CHECKS},
                'paragraph_mapping':{'S001':{'inference':'R001','paragraph':'S001'}},'source_outputs':{'P':'T001'},
                'evidence':[{'path':'problem.txt','sha256':nl0.sha(self.base/'problem.txt')}]}
        ir.write(rp,review)
        result=workflow.freeze(self.base/'nl0.json',self.base/'spec.json',cp,pp,rp,self.base/'freeze',audit_a=self.base/'audit-test-only.json')
        self.assertEqual(result['background_supplement']['sha256'],c['source']['background_supplement_sha256'])
        self.assertEqual(ir.local_packet(cp,plan,'T001')['accepted_background_notes']['R001.BG001']['fact'],self.note['fact'])
        inventory,_=audit_b.source_data(cp,graph=self.base/'nl0.json',spec=self.base/'spec.json',audit_a=self.base/'audit-test-only.json')
        self.assertEqual(next(p for p in inventory['propositions'] if p['id']=='M001')['source']['declaration'],'Continuous.add')

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
            self.assertTrue({'probe_background','record_background_note','search_mathlib','read_mathlib'} <= stage.tool_names)
            self.assertNotIn('exec_command',stage.tool_names)
            shutil.copytree(self.base/'library',stage.logs/'library')
            args={k:copy.deepcopy(v) for k,v in self.note.items() if k!='source'};args['source_id']='M901'
            result=stage.dispatch('record_background_note',args)
            self.assertEqual(result['recorded'],'BG001')
            self.assertEqual(review.base['background_notes'][0]['source']['declaration'],'Continuous.add')
            progress=stage.dispatch('read_review_progress',{})
            self.assertEqual(progress['background_notes'][0]['id'],'BG001')
            attempt=stage.dispatch('submit_draft',{'artifact':{'from_saved_review':True,
                'summary':{'verdict':'PASS','notes':'TEST ONLY','background_notes':[]}}})
            self.assertFalse(attempt['accepted'])
        finally:shutil.rmtree(stage.work,ignore_errors=True)

    def test_zero_extraction_preserves_notes_and_their_source_evidence(self):
        sys.path.insert(0,str(ROOT/'translation/scripts'))
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
