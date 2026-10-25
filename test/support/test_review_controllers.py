"""Controller integrity tests with synthetic judgments; no mathematical audit is run."""
import copy
import json
import importlib.util
from pathlib import Path
import tempfile
import time
import unittest
import shutil
from unittest.mock import patch

import audit_a_campaign as a
import behavioral_controls as b
import translation_author as t
import interface_review as i
import audit_b_review as br


class ReviewControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.fixture=a.CORE/'tests/fixtures/closed-addition'
        self.problem=self.root/'problem';self.problem.mkdir()
        (self.problem/'problem.md').write_text('Neutral controller fixture, not an exercise result.\n')
        (self.problem/'hidden-author-notes.json').write_text('{"verdict":"PASS"}')
        self.out=self.root/'review'
        self.plan=a.prepare(self.fixture,self.problem,self.out)

    def tearDown(self):self.temp.cleanup()

    def judgment(self,verdict='PASS',pointer='/inference/argument'):
        return {'verdict':verdict,'notes':'Synthetic controller-test judgment only.','locations':[pointer]}

    def test_packet_and_global_inputs_do_not_include_author_material(self):
        ids={x['id'] for x in json.loads((self.out/'global/inputs.json').read_text())['inputs']}
        self.assertEqual(ids,{'problem.md','spec.json','nl0.json','signature-evidence.json','global-overview.json'})
        for job in self.plan['jobs'][1:]:
            ids={x['id'] for x in json.loads((self.out/job['id']/'inputs.json').read_text())['inputs']}
            self.assertEqual(ids,{'packet.json'})

    def test_rebuilding_an_input_manifest_never_hashes_itself(self):
        directory=self.out/'global'
        (directory/'new-explicit-source.txt').write_text('Synthetic manifest control only.\n')
        a.manifest(directory)
        rows=json.loads((directory/'inputs.json').read_text())['inputs']
        self.assertNotIn('inputs.json',{r['id'] for r in rows})
        for row in rows:self.assertEqual(a.bind(directory/row['path'])['sha256'],row['sha256'])

    def test_global_overview_is_exhaustive_and_tampering_is_rejected(self):
        overview=json.loads((self.out/'global/global-overview.json').read_text())
        self.assertEqual(overview['inventory']['spec_H_ids'],overview['inventory']['graph_H_ids'])
        spec=json.loads((self.out/'global/spec.json').read_text())
        self.assertEqual([r['record'] for r in overview['spec_hypotheses']],spec['hypotheses'])
        self.assertNotIn('verdict',json.dumps(overview))
        a.verify_global_overview(self.out,self.plan)
        overview['graph_hypotheses']=[];a.write(self.out/'global/global-overview.json',overview)
        with self.assertRaisesRegex(ValueError,'exhaustive canonical projection'):
            a.verify_global_overview(self.out,self.plan)

    def test_global_controls_use_actual_prompt_contract_and_late_h_inventory(self):
        module=self.locator_controls();positive,negative=module.global_hypothesis_controls()
        for index,(bundle,verdict,_,_) in enumerate([positive,negative]):
            target=self.root/f'global-control-{index}';target.mkdir()
            def fake_run(campaign,timeout,budget=None):
                # Synthetic row shapes only; no mathematical review/model occurs.
                self.assertEqual((campaign/'global/prompt.txt').read_text(),a.GLOBAL)
                self.assertEqual([j['id'] for j in a.json.loads((campaign/'campaign.json').read_text())['jobs']],['global'])
                view=json.loads((campaign/'global/global-overview.json').read_text())
                self.assertEqual('H002' in view['inventory']['graph_H_ids'],verdict=='PASS')
                self.assertEqual(view['inventory']['unused_original_hypotheses'],['H002'] if verdict=='PASS' else [])
                if verdict=='PASS':
                    lines=(campaign/'global/nl0.json').read_text().splitlines()
                    self.assertGreater(next(i for i,l in enumerate(lines) if '"id": "H002"' in l),500)
                stage=campaign/'global/stage';stage.mkdir()
                a.write(stage/'result.json',{'status':'ACCEPTED'})
                a.write(stage/'accepted.json',{'target_review':self.judgment(verdict),
                    'structure_review':self.judgment(),'definition_reviews':{},'source_reviews':{},'findings':[]})
            with patch.object(a,'run',side_effect=fake_run):
                _,actual,_=b.run_global_control(target,bundle,60,None)
            self.assertEqual(actual['target_verdict'],verdict)
            self.assertEqual(actual['verdict'],verdict)

    def test_global_control_cannot_pass_from_an_incomplete_or_wrong_scope_record(self):
        blocked={'status':'REVIEW_BLOCKED_INCOMPLETE','coverage':{'items':{
            '/target_review':{'coverage':'assessed','judgment':self.judgment('FAIL')}}},
            'findings':[{'verdict':'FAIL','explanation':'Synthetic original-H fidelity defect.'}]}
        expected={'kind':'global','expected_verdict':'FAIL','expected_target_verdict':'FAIL','location':None}
        self.assertTrue(b.matches_expected(expected,b.global_observation(blocked)))
        blocked['coverage']['items']['/target_review']['coverage']='unread'
        self.assertFalse(b.matches_expected(expected,b.global_observation(blocked)))
        wrong={'target_review':self.judgment(),'structure_review':self.judgment('FAIL'),
               'definition_reviews':{},'source_reviews':{},'findings':[]}
        self.assertFalse(b.matches_expected(expected,b.global_observation(wrong)))
        self.assertIsNone(b.global_observation({}))

    def test_calibration_separates_real_record_shape_from_faulty_timing(self):
        packet=json.loads((self.out/'R001/packet.json').read_text())
        for index,(status,verdict,expected_status) in enumerate([
                ('ACCEPTED','PASS','BEHAVIORAL-CONTROLS-PASSED'),
                ('ACCEPTED','FAIL','BEHAVIORAL-CONTROLS-NOT-PASSED'),
                ('UNFINISHED',None,'BEHAVIORAL-CONTROLS-NOT-PASSED')]):
            directory=self.root/f'qualification-control-{index}'
            (directory/'reviewer').mkdir(parents=True);(directory/'owner').mkdir()
            a.write(directory/'reviewer/neutral.json',packet)
            a.write(directory/'owner/expected.json',{'expected':{'neutral.json':{
                'kind':'packet','expected_verdict':'PASS','location':None}}})
            def fake_execute(stage):
                # Synthetic temp-only protocol records, not a model/audit result.
                actual={'verdict':verdict,'findings':[]} if verdict else None
                if actual is not None:b.validate_review(packet,actual)
                row={'status':status,'measurement_valid':False,'execution_health':'FAULT',
                    'temporary_workspace_removed':True,'isolation_violation':False,'usage':{'complete':False},
                    'exposure':{'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED','actual_model_ids':[__import__('run_pilot').MODEL],
                                'standard_tier_verified':True},
                    'transport_health':{'status':'FAULT','faults':[{'kind':'RELAY_ERROR','request_number':2}],
                        'uncertainty':[{'kind':'HTTP_EVIDENCE_INCOMPLETE','missing_requests':[2]}]}}
                a.write(stage.logs/'result.json',row)
                if actual is not None:a.write(stage.logs/'accepted.json',actual)
                shutil.rmtree(stage.work)
                return row,actual
            with patch.object(b.ArtifactStage,'execute',fake_execute):report=b.run(directory,60)
            self.assertEqual(report['status'],expected_status)
            self.assertFalse(report['benchmark_timing_qualified'])
            self.assertFalse(report['results'][0]['healthy'])
            self.assertEqual(report['results'][0]['record_qualified'],status=='ACCEPTED')

    def test_legacy_global_projection_verifies_only_its_exact_older_shape(self):
        path=self.out/'global/global-overview.json';view=json.loads(path.read_text())
        view['schema']='yui-global-overview-1';view['inventory'].pop('unused_original_hypotheses')
        view['inventory'].pop('reachability_basis')
        a.write(path,view);self.plan['global_overview']=a.bind(path)
        a.verify_global_overview(self.out,self.plan)
        view['inventory']['graph_H_ids']=[];a.write(path,view);self.plan['global_overview']=a.bind(path)
        with self.assertRaises(ValueError):a.verify_global_overview(self.out,self.plan)

    def test_a_failure_finding_cannot_be_hidden_by_all_pass_summary_fields(self):
        spec=json.loads((self.out/'global/spec.json').read_text())
        value={'target_review':self.judgment(),'structure_review':self.judgment(),
               'definition_reviews':{d['id']:self.judgment() for d in spec['definitions']},
               'source_reviews':{},'findings':[{'verdict':'FAIL','location':'graph','explanation':'Synthetic blocking defect'}]}
        original=copy.deepcopy(value)
        with self.assertRaisesRegex(ValueError,'conflicts with all-PASS'):
            a.validate_review(value,self.out/'global',True)
        self.assertEqual(value,original)
        value['findings']=[{'severity':'BLOCKING','location':'graph','explanation':'Synthetic blocking defect without a verdict field'}]
        with self.assertRaisesRegex(ValueError,'conflicts with all-PASS'):
            a.validate_review(value,self.out/'global',True)

    def test_packet_review_must_bind_the_right_packet_and_resolving_locations(self):
        directory=self.out/'R001';packet=json.loads((directory/'packet.json').read_text())
        value={'inference':'R001','packet_sha256':packet['packet_sha256'],'verdict':'PASS','notes':'Synthetic only',
               'checks':{k:self.judgment() for k in a.nl0.CHECKS|a.nl0.closure.CLOSURE_CHECKS},'findings':[]}
        a.validate_review(value,directory,False)
        value['checks']['argument']['verdict']='FAIL'
        with self.assertRaisesRegex(ValueError,'conflicts'):a.validate_review(value,directory,False)
        value['verdict']='FAIL';value['checks']['argument']['locations']=['/missing']
        with self.assertRaises(ValueError):a.validate_review(value,directory,False)
        value['packet_sha256']='different'
        with self.assertRaisesRegex(ValueError,'identity/hash'):a.validate_review(value,directory,False)

    def test_global_blocking_findings_bind_actual_input_bytes(self):
        directory=self.out/'global';graph=json.loads((directory/'nl0.json').read_text())
        location='nl0.json#/inferences/0/argument/0/text'
        text=graph['inferences'][0]['argument'][0]['text']
        finding={'verdict':'FAIL','explanation':'Synthetic locator control only.',
            'locations':[location],'quotation':{'location':location,'text':text}}
        a.validate_finding(finding,directory)
        finding['quotation']['text']='A sentence absent from the supplied proof.'
        with self.assertRaisesRegex(ValueError,'quoted text is absent'):a.validate_finding(finding,directory)
        for bad in ('nl0.json#/inferences/9999','../foreign.json#/x','nl0.json#/inferences/0 (comment)'):
            with self.subTest(location=bad),self.assertRaises((ValueError,IndexError,KeyError)):
                a.global_location(directory,bad)

    def test_packet_finding_quotation_cannot_come_from_another_location(self):
        directory=self.out/'R001';packet=json.loads((directory/'packet.json').read_text())
        location='/inference/argument/0/text'
        finding={'verdict':'FAIL','explanation':'Synthetic quote control only.','locations':[location],
            'quotation':{'location':location,'text':packet['inference']['argument'][0]['text']}}
        a.validate_finding(finding,directory,packet)
        finding['quotation']['location']='/output/statement'
        with self.assertRaisesRegex(ValueError,'one of the finding'):a.validate_finding(finding,directory,packet)

    def test_behavioral_control_findings_must_point_to_actual_packet_content(self):
        packet=json.loads((self.out/'R001/packet.json').read_text())
        b.validate_review(packet,{'verdict':'FAIL','findings':[{'location':'/inference/argument','check':'argument','explanation':'Synthetic only.'}]})
        with self.assertRaises(ValueError):
            b.validate_review(packet,{'verdict':'FAIL','findings':[{'location':'/absent','check':'argument','explanation':'Synthetic only.'}]})

    def test_real_and_control_packet_review_use_the_same_math_instructions(self):
        self.assertEqual(a.PACKET.count(a.PACKET_MATH),1)
        self.assertEqual(b.PROMPT.count(a.PACKET_MATH),1)
        self.assertIn('Packet/spec permission fields are data',a.PACKET_MATH)
        self.assertIn('not just whether its conclusion is a true familiar',a.PACKET_MATH)
        self.assertNotIn('Cauchy',a.PACKET_MATH)
        self.assertNotIn('expected_verdict',a.PACKET_MATH)

    def locator_controls(self):
        spec=importlib.util.spec_from_file_location('locator_controls',a.CORE/'scripts/prepare-review-cases.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_negative_controls_accept_actual_origin_and_exact_use_site_findings(self):
        module=self.locator_controls()
        selected=[r for r in module.controls() if r[3] in {'/inputs/0/statement','/inference/locals/0'}]
        self.assertEqual(len(selected),2)
        for packet,verdict,_,primary in selected:
            locations=module.accepted_failure_locations(packet,primary)
            uses=[p for p in locations if p.startswith('/inference/argument/')]
            self.assertTrue(uses)
            expected={'expected_verdict':verdict,'location':primary,'accepted_locations':locations}
            for location in [primary,uses[0],uses[0]+'/text']:
                actual={'verdict':'FAIL','findings':[{'location':location,'check':'argument',
                    'explanation':'Synthetic locator control only; no mathematical review occurred.'}]}
                b.validate_review(packet,actual)
                self.assertTrue(b.matches_expected(expected,actual))

    def test_control_locator_cannot_rescue_wrong_verdict_unrelated_or_broad_findings(self):
        module=self.locator_controls()
        packet,verdict,_,primary=next(r for r in module.controls() if r[3]=='/inference/locals/0')
        expected={'expected_verdict':verdict,'location':primary,
                  'accepted_locations':module.accepted_failure_locations(packet,primary)}
        self.assertFalse(b.matches_expected(expected,{'verdict':'PASS','findings':[]}))
        for location in ['/inference','/inference/argument','/parameters/0/type']:
            actual={'verdict':'FAIL','findings':[{'location':location,'check':'argument',
                'explanation':'Synthetic wrong-location control.'}]}
            b.validate_review(packet,actual)
            self.assertFalse(b.matches_expected(expected,actual))

    def test_declaration_locators_follow_exact_parameter_definition_and_scoped_object_uses(self):
        module=self.locator_controls()
        packet,verdict,_,primary=next(r for r in module.controls() if r[3]=='/parameters/0/type')
        locations=module.accepted_failure_locations(packet,primary)
        self.assertIn('/inference/argument/0',locations)
        expected={'expected_verdict':verdict,'location':primary,'accepted_locations':locations}
        actual={'verdict':'FAIL','findings':[{'location':'/inference/argument/0/text',
            'check':'dependency_closure','explanation':'Synthetic locator regression only.'}]}
        b.validate_review(packet,actual);self.assertTrue(b.matches_expected(expected,actual))
        packet=copy.deepcopy(packet)
        packet['definitions']=[{'symbol':'q','definition':'A neutral declared object.'}]
        packet['inference']['argument'][0]['objects'].append('q')
        self.assertIn('/inference/argument/0',module.accepted_failure_locations(packet,'/definitions/0/definition'))
        packet['inference']['argument'].append(copy.deepcopy(packet['inference']['argument'][0]))
        packet['inference']['argument'][1]['id']='S002'
        for step in packet['inference']['argument']:step['objects'].append('w')
        packet['inference']['locals']=[{'symbol':'w','kind':'definition','start':'S001','end':'S001',
            'from_inputs':[],'from_local':[]}]
        locations=module.accepted_failure_locations(packet,'/inference/locals/0')
        self.assertIn('/inference/argument/0',locations)
        self.assertNotIn('/inference/argument/1',locations)

    def test_arbitrary_addition_control_accepts_recorded_r23_location_and_origin(self):
        module=self.locator_controls()
        packet,verdict,_,primary=next(r for r in module.controls()
            if r[0].get('case_id')=='neutral-pointwise-structure')
        before=copy.deepcopy(packet)
        locations=module.accepted_failure_locations(packet,primary)
        self.assertEqual(set(locations),{
            '/parameters/0/type','/parameters/0','/inference/argument/0'})
        self.assertEqual(packet,before)
        expected={'expected_verdict':verdict,'location':primary,'accepted_locations':locations}
        for location in [primary,'/parameters/0','/inference/argument/0/text']:
            # Replays the observed R23 finding location; no new review occurs.
            actual={'verdict':'FAIL','findings':[{'location':location,'check':'argument',
                'explanation':'Arbitrary addition need not be continuous, so continuity of f and g does not imply continuity of their pointwise sum.'}],
                'background_notes':[]}
            b.validate_review(packet,actual)
            self.assertTrue(b.matches_expected(expected,actual))

    def test_arbitrary_addition_control_still_rejects_wrong_verdicts_and_locations(self):
        module=self.locator_controls()
        packet,_,_,primary=next(r for r in module.controls()
            if r[0].get('case_id')=='neutral-pointwise-structure')
        expected={'expected_verdict':'FAIL','location':primary,
                  'accepted_locations':module.accepted_failure_locations(packet,primary)}
        finding={'location':'/inference/argument/0/text','check':'argument',
                 'explanation':'Synthetic matching-location guard; not a mathematical judgment.'}
        for verdict in ['PASS','UNVERIFIED']:
            self.assertFalse(b.matches_expected(expected,{'verdict':verdict,'findings':[finding]}))
        for actual in [None,{}, {'status':'ERROR'}]:
            self.assertFalse(b.matches_expected(expected,actual))
        for location in ['/inputs/0/statement','/parameters/1/type',
                         '/inference','/inference/argument']:
            actual={'verdict':'FAIL','findings':[{**finding,'location':location}]}
            b.validate_review(packet,actual)
            self.assertFalse(b.matches_expected(expected,actual))

    def test_explicit_failure_use_sites_do_not_broaden_unrelated_controls(self):
        module=self.locator_controls()
        packet,_,_,primary=next(r for r in module.controls()
            if r[0].get('case_id')=='neutral-pointwise-structure')
        packet=copy.deepcopy(packet);packet['case_id']='unrelated-neutral-control'
        self.assertNotIn('/inference/argument/0',module.accepted_failure_locations(packet,primary))

    def test_explicit_failure_use_sites_stay_in_owner_key_only(self):
        module=self.locator_controls();directory=self.root/'prepared-neutral-controls'
        module.prepare(directory)
        expected=json.loads((directory/'owner/expected.json').read_text())['expected']
        selected=[]
        for path in (directory/'reviewer').glob('*.json'):
            packet=json.loads(path.read_text())
            self.assertNotIn('accepted_locations',packet)
            self.assertNotIn('expected_verdict',packet)
            if packet.get('case_id')=='neutral-pointwise-structure':
                selected.append(path)
                self.assertIn('/inference/argument/0',expected[path.name]['accepted_locations'])
        self.assertEqual(len(selected),1)

    def test_interface_adapter_copies_source_bytes_and_returns_real_type_feedback(self):
        out=self.root/'interface'
        # The neutral fixture has no actual audit. Verify the acceptance guard,
        # then stage controller-only type data without fabricating a PASS receipt.
        with self.assertRaisesRegex(ValueError,'AUDIT-FAIL'):
            t.prepare(self.fixture,self.problem,out)
        (out/'inputs').mkdir(parents=True)
        for name in ['spec.json','nl0.json']:
            (out/'inputs'/name).write_bytes((self.fixture/name).read_bytes())
        data=a.nl0.validate(self.fixture/'nl0.json',self.fixture/'spec.json')
        paragraphs=[];mapping={}
        for rid,r in data[4].items():
            for s in r['argument']:
                key='S'+str(len(paragraphs)+1).zfill(3)
                paragraphs.append({'id':key,'text':s['text']});mapping[key]={'inference':rid,'paragraph':s['id']}
        a.write(out/'inputs/source-map.json',{'source_steps':paragraphs,'paragraph_mapping':mapping,
            'roots':[{'id':'H001','kind':'hypothesis','statement':'a=b.'}],
            'source_outputs':{'N001':'b=a.','P':'a+0=b.'}})
        source=json.loads((out/'inputs/source-map.json').read_text())
        self.assertEqual(len(source['paragraph_mapping']),len(source['source_steps']))
        a.write(out/'authority.json',{'case':str(self.fixture),
            **{key:a.bind(self.fixture/name) for key,name in [('graph','nl0.json'),('spec','spec.json'),('audit_a','audit-a.json')]}})
        # This injected acceptance bit tests only adapter mechanics, not a real audit.
        data[0]['current_standard_receipt_valid']=True
        with patch.object(t.nl0,'validate',return_value=data):validator=t.InterfaceContract(out)
        draft={'header':'import Mathlib\n','parameters':[{'name':'a','type':'ℕ'},{'name':'b','type':'ℕ'}],
            'premise_types':{'H001':'a = b'},'conclusion_type':'a + 0 = b',
            'representation':'Natural-number equality in the neutral controller fixture.',
            'objects':[], 'steps':[{'id':'T001','statement':'b = a','inputs':['H001'],
                'source_steps':[source['source_steps'][0]['id']],'explanation':'Equality symmetry.'},
                {'id':'T002','statement':'a + 0 = b','inputs':['T001'],
                 'source_steps':[s['id'] for s in source['source_steps'][1:]],'explanation':'Substitution and additive identity.'}],
            'terminal':'T002','source_outputs':{'N001':'T001','P':'T002'}}
        self.assertFalse(validator(draft)['mathematical_acceptance'])
        paths=json.loads((out/'accepted-interface-paths.json').read_text())
        contract=json.loads(Path(paths['contract']).read_text())
        self.assertEqual(contract['source_steps'],source['source_steps'])
        i.verify_candidate_artifact(draft,contract,json.loads(Path(paths['plan']).read_text()),draft['source_outputs'])
        # Qualified result shapes below are synthetic controller inputs, not a
        # real model run or an actual semantic verdict.
        stage=out/'stage';stage.mkdir()
        exposure={'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED','actual_model_ids':[__import__('run_pilot').MODEL],'standard_tier_verified':True}
        result={'status':'ACCEPTED','execution_health':'NO_RECORDED_FAULT','usage':{'complete':False},'exposure':exposure}
        a.write(stage/'result.json',result);a.write(stage/'accepted.json',draft)
        first=self.root/'first-review';i.prepare(out,first)
        (first/'stage').mkdir();a.write(first/'stage/result.json',result)
        a.write(first/'stage/accepted.json',{'synthetic':'prior disputed judgment; not an actual review'})
        dispute=self.root/'dispute.json'
        a.write(dispute,{'comparison':{
            'source':{'document':'nl0.json','pointer':'/propositions/0/statement','quote':'a=b.'},
            'formal':{'document':'contract.json','pointer':'/premises/0/type','quote':'a = b'},
            'difference':'Synthetic located dispute only; this does not assert a real mathematical mismatch.'}})
        second=self.root/'adjudicated';i.prepare(out,second,adjudicate=first,dispute=dispute)
        self.assertIsNotNone(a.nl0.load(second/'bindings.json')['adjudication'])
        self.assertTrue((second/'inputs/prior-disputed-review.json').is_file())
        with self.assertRaisesRegex(ValueError,'One targeted adjudication'):
            i.prepare(out,self.root/'third',adjudicate=second,dispute=dispute)
        changed=copy.deepcopy(draft);changed['premise_types']['H001']='True'
        with self.assertRaisesRegex(ValueError,'differs from the actual model'):
            i.verify_candidate_artifact(changed,contract,json.loads(Path(paths['plan']).read_text()),draft['source_outputs'])
        bad=copy.deepcopy(draft);bad['conclusion_type']=bad['steps'][-1]['statement']='unboundTarget'
        with self.assertRaisesRegex(ValueError,'Actual Lean type check failed'):validator(bad)
        bad=copy.deepcopy(draft);bad['header']='import Mathlib\naxiom forged : False\n'
        with self.assertRaisesRegex(ValueError,'not proof/result declarations'):validator(bad)

    def test_interface_reviews_require_resolving_source_and_formal_locations(self):
        out=self.root/'interface-review';inputs=out/'inputs';inputs.mkdir(parents=True)
        a.write(inputs/'spec.json',{'conclusion':'Synthetic source only.'})
        a.write(inputs/'contract.json',{'conclusion':{'type':'True'}})
        row={'verdict':'PASS','notes':'Synthetic controller integrity test only.',
             'locations':[{'document':'spec.json','pointer':'/conclusion'},
                          {'document':'contract.json','pointer':'/conclusion/type'}]}
        value={'checks':{name:copy.deepcopy(row) for name in i.workflow.INTERFACE_CHECKS},'findings':[]}
        i.validate(value,out)
        value['findings']=[{'severity':'BLOCKING','explanation':'Synthetic inconsistent summary.'}]
        with self.assertRaisesRegex(ValueError,'conflict'):i.validate(value,out)
        value['findings']=[]
        value['checks']['parameters_and_allowed_inputs']['locations']=[{'document':'spec.json','pointer':'/conclusion'}]
        with self.assertRaisesRegex(ValueError,'both original source'):i.validate(value,out)
        value['checks']['parameters_and_allowed_inputs']['locations'][0]['pointer']='/missing'
        with self.assertRaises(KeyError):i.validate(value,out)

    def test_interface_out_of_range_pointer_is_candidate_feedback(self):
        out=self.root/'bad-pointer';inputs=out/'inputs';inputs.mkdir(parents=True)
        a.write(inputs/'spec.json',{'parameters':[]})
        a.write(inputs/'contract.json',{'conclusion':{'type':'True'}})
        row={'verdict':'UNVERIFIED','notes':'Synthetic invalid-location control.',
             'locations':[{'document':'spec.json','pointer':'/parameters/5'},
                          {'document':'contract.json','pointer':'/conclusion/type'}]}
        value={'checks':{name:copy.deepcopy(row) for name in i.workflow.INTERFACE_CHECKS},'findings':[]}
        with self.assertRaisesRegex(ValueError,'array index is out of range'):i.validate(value,out)

    def test_interface_review_excludes_author_repair_history(self):
        author=self.root/'author';(author/'inputs').mkdir(parents=True)
        inputs=self.root/'review-inputs';inputs.mkdir()
        permitted={'spec.json','nl0.json','source-map.json','problem.md','source-context.md','frozen-target.md'}
        for name in permitted|{'prior-interface.json','actual-interface-review.json','author-notes.txt','inputs.json'}:
            (author/'inputs'/name).write_text('Synthetic controller control only.')
        i.copy_review_inputs(author,inputs)
        self.assertEqual({p.name for p in inputs.iterdir()},permitted)

    def test_interface_data_edits_preserve_the_actual_immutable_base(self):
        base={'conclusion_type':'a = b','header':'import Mathlib\n','parameters':[]}
        documents={'prior-interface.json':json.dumps(base)}
        changed,receipt=t.expand_interface({'base_input':'prior-interface.json','patches':[
            {'op':'replace','path':'/conclusion_type','value':'b = a'}]},documents,{})
        self.assertEqual(changed['conclusion_type'],'b = a')
        self.assertEqual(json.loads(documents['prior-interface.json']),base)
        resumed,_=t.expand_interface({'accept_candidate':1},documents,{1:changed})
        self.assertEqual(resumed,changed)
        with self.assertRaisesRegex(ValueError,'same stage|same-stage'):
            t.expand_interface({'accept_candidate':2},documents,{1:changed})

    def test_partial_type_probes_do_not_accept_an_interface_or_proof(self):
        stage=t.InterfaceStage(self.root/'type-stage','Neutral controller test only.',phase='interface-authoring',library=False)
        stage.started=time.monotonic()
        result=stage.dispatch('check_lean_types',{'header':'import Mathlib\n',
            'parameters':[{'name':'K','type':'Type','binder_kind':'implicit'},
                          {'name':'fieldK','type':'Field K','binder_kind':'instance'}],
            'types':['∀ x : K, x = x']})
        self.assertTrue(result['types_checked']);self.assertFalse(result['stage_complete']);self.assertIsNone(stage.accepted)
        term=stage.dispatch('check_lean_types',{'header':'import Mathlib\n','parameters':[{'name':'n','type':'ℕ'}],
            'types':['n + 1']})
        self.assertTrue(term['types_checked']);self.assertIsNone(stage.accepted)
        bad=stage.dispatch('check_lean_types',{'header':'import Mathlib\naxiom forged : False\n','parameters':[],'types':['False']})
        self.assertFalse(bad['types_checked']);self.assertIsNone(stage.accepted)

    def test_audit_b_requires_all_paired_native_locations_even_for_failed_reviews(self):
        out=self.root/'audit-b-review';inputs=out/'inputs';inputs.mkdir(parents=True)
        packet={'inventory':{'propositions':[{'id':'P'}]},'actual_elaborated_evidence':{'comparisons':[{'id':'P'}]}}
        expected=['/inventory/propositions/0','/actual_elaborated_evidence/comparisons/0']
        a.write(inputs/'review-packet.json',packet)
        a.write(inputs/'mechanical.json',{'required_review_locations':{'P':expected}})
        row={'verdict':'UNVERIFIED','notes':'Synthetic controller test only.','locations':expected}
        value={'nodes':{'P':copy.deepcopy(row)},'checks':{name:{**row,'locations':['/inventory','/actual_elaborated_evidence']} for name in br.audit_b.REVIEW_CHECKS},'findings':[]}
        br.validate(value,out)
        value['nodes']['P']['locations']=['/inventory/propositions/0']
        with self.assertRaisesRegex(ValueError,'paired actual'):br.validate(value,out)


if __name__=='__main__':unittest.main()
