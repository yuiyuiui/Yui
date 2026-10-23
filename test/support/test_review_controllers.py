"""Controller integrity tests with synthetic judgments; no mathematical audit is run."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest

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
        self.assertEqual(ids,{'problem.md','spec.json','nl0.json','signature-evidence.json'})
        for job in self.plan['jobs'][1:]:
            ids={x['id'] for x in json.loads((self.out/job['id']/'inputs.json').read_text())['inputs']}
            self.assertEqual(ids,{'packet.json'})

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

    def test_behavioral_control_findings_must_point_to_actual_packet_content(self):
        packet=json.loads((self.out/'R001/packet.json').read_text())
        b.validate_review(packet,{'verdict':'FAIL','findings':[{'location':'/inference/argument','check':'argument','explanation':'Synthetic only.'}]})
        with self.assertRaises(ValueError):
            b.validate_review(packet,{'verdict':'FAIL','findings':[{'location':'/absent','check':'argument','explanation':'Synthetic only.'}]})

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
        validator=t.InterfaceContract(out)
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
        changed=copy.deepcopy(draft);changed['premise_types']['H001']='True'
        with self.assertRaisesRegex(ValueError,'differs from the actual model'):
            i.verify_candidate_artifact(changed,contract,json.loads(Path(paths['plan']).read_text()),draft['source_outputs'])
        bad=copy.deepcopy(draft);bad['conclusion_type']=bad['steps'][-1]['statement']='unboundTarget'
        with self.assertRaisesRegex(ValueError,'Actual Lean type check failed'):validator(bad)
        bad=copy.deepcopy(draft);bad['header']='import Mathlib\naxiom forged : False\n'
        with self.assertRaisesRegex(ValueError,'not execute code'):validator(bad)

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
