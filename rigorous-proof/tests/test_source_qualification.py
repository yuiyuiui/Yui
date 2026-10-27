"""Synthetic source uncertainty never upgrades to ordinary mathematical PASS."""
import harness_support
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import nl0
import source_access
import source_qualification as sq
import source_preparation
import source_refactor


class SourceQualificationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        original=harness_support.CORE/'tests/fixtures/closed-addition'
        self.spec=json.loads((original/'spec.json').read_text());self.graph=json.loads((original/'nl0.json').read_text())
        (self.root/'problem.txt').write_bytes((original/'problem.txt').read_bytes())
        self.spec['hypotheses']=[]
        source={k:'Synthetic source metadata only.' for k in ['author','title','version','identifier','locator','notation_map','errata',
            'source_kind','origin','retrieved_at','source_statement','context','qualification','version_check']}
        folder=self.root/'external-sources';folder.mkdir()
        self.access=folder/'access-test.json'
        self.access.write_text(json.dumps({'version':source_access.VERSION,'origin':'controller_https',
            'url':'https://example.org/unavailable','status':'HTTP_ERROR','http_status':403}))
        ref=source_access.defer(self.root,source_id='E001',statement='a=b.',input_id='secondary.txt',quote='a=b.',
            inputs={'secondary.txt':'a=b.'},attempts=['external-sources/access-test.json'])
        record=json.loads((self.root/ref['path']).read_text())
        binding={k:ref[k] for k in ['path','sha256']}
        source.update(statement='a=b.',hypotheses=[],primary_evidence=[],
            evidence=[binding,record['basis'],*record['attempts']],
            verification={'status':'UNVERIFIED_PRIMARY','record':binding})
        p=self.graph['propositions'][0];p['id']='E001';p['kind']='external';p['source']=source
        r=self.graph['inferences'][0];r['inputs']=['E001'];r['argument'][0]['uses']=['E001']
        r['argument'][0]['text']=r['argument'][0]['text'].replace('H001','E001')
        r['applications']=[{'id':'A001','input':'E001','at':'S001','bindings':'Synthetic fixed parameters.',
                            'hypothesis_checks':[]}]
        self.write_source()
        self.make_audit()

    def make_audit(self):
        """Fresh synthetic reviews for this control's current graph/packets."""
        data=nl0.validate(self.root/'nl0.json',self.root/'spec.json')
        self.audit=nl0.closure.audit_template(data,nl0.CHECKS,nl0.EXTERNAL_CHECKS,'nl0.json','spec.json')
        def mark(v):
            if isinstance(v,dict):
                if 'verdict' in v:v.update(verdict='PASS',notes='Synthetic control only; no real mathematical review.')
                if 'locations' in v:v['locations']=['/output/statement']
                for x in v.values():mark(x)
            elif isinstance(v,list):
                for x in v:mark(x)
        mark(self.audit)
        for r in self.audit['inference_reviews'].values():
            r['replay'].update(mode='fresh_packet_only',carrier='synthetic-controller',prior_exposure=[],
                read_materials=['packet:'+r['replay']['packet_sha256']])
        entry=self.audit['source_reviews']['E001'];entry['verdict']='UNVERIFIED'
        for r in entry['citation_checks'].values():r['verdict']='UNVERIFIED'
        self.write_audit()
    def tearDown(self):self.temp.cleanup()

    def write_source(self):
        (self.root/'spec.json').write_text(json.dumps(self.spec))
        self.graph['spec_sha256']=nl0.sha(self.root/'spec.json')
        (self.root/'nl0.json').write_text(json.dumps(self.graph))

    def write_audit(self):
        self.audit.update(graph_sha256=nl0.sha(self.root/'nl0.json'),spec_sha256=nl0.sha(self.root/'spec.json'))
        (self.root/'audit-a.json').write_text(json.dumps(self.audit))

    def data(self):
        return nl0.validate(self.root/'nl0.json',self.root/'spec.json',self.root/'audit-a.json',allow_unresolved=True)

    def test_complete_conditional_receipt_stays_nonstandard_and_emits_bound_warning(self):
        data=self.data();result=data[0]
        self.assertTrue(result['current_conditional_receipt_valid'])
        self.assertFalse(result['current_standard_receipt_valid'])
        self.assertFalse(result['audit_receipt_valid'])
        payload=sq.publish(self.root,data)
        self.assertEqual(payload['warnings'][0]['statement'],'a=b.')
        self.assertFalse(payload['unqualified_pass'])
        self.assertTrue((self.root/'warn.md').is_file())

    def test_any_failed_or_unverified_mathematical_check_still_blocks(self):
        for verdict in ['FAIL','UNVERIFIED']:
            self.audit['target_review']['verdict']=verdict;self.write_audit()
            self.assertFalse(self.data()[0]['current_conditional_receipt_valid'])

    def test_known_source_mismatch_cannot_be_deferred(self):
        self.audit['source_reviews']['E001']['citation_checks']['statement_fidelity']['verdict']='FAIL'
        self.write_audit();self.assertFalse(self.data()[0]['current_conditional_receipt_valid'])

    def test_unavailable_primary_cannot_be_reported_as_pass(self):
        row=self.audit['source_reviews']['E001'];row['verdict']='PASS'
        for value in row['citation_checks'].values():value['verdict']='PASS'
        self.write_audit()
        with self.assertRaisesRegex(ValueError,'incorrectly reported'):self.data()

    def test_missing_or_modified_access_evidence_invalidates_the_source(self):
        self.access.write_text('{}')
        with self.assertRaisesRegex(ValueError,'changed|HASH'):self.data()

    def test_conditional_authority_can_enter_translation_without_losing_warning(self):
        data,paths=source_preparation.read_source(self.root/'nl0.json',self.root/'spec.json',self.root/'audit-a.json')
        self.assertTrue(sq.usable(data[0]));self.assertIn(self.access.resolve(),paths)
        authority={k:str(self.root/v) for k,v in [('graph','nl0.json'),('spec','spec.json'),('audit_a','audit-a.json')]}
        with patch.object(source_refactor,'ArtifactStage') as stage:
            result=source_refactor.run(authority,self.root/'preparation',None)
        self.assertEqual(result,authority);stage.assert_not_called()

    def test_only_source_located_uncertainty_can_be_nonblocking(self):
        data=self.data()
        self.assertTrue(sq.source_only_finding({'verdict':'UNVERIFIED',
            'locations':['nl0.json#/propositions/0/source/verification']},data,self.root))
        for row in [{'verdict':'FAIL','locations':['nl0.json#/propositions/0/source']},
                    {'verdict':'UNVERIFIED','locations':['nl0.json#/inferences/0']},
                    {'verdict':'UNVERIFIED','locations':[]}]:
            self.assertFalse(sq.source_only_finding(row,data,self.root))

    def test_conditional_authority_survives_frozen_ir_native_build_and_final_b(self):
        """Actual toy Lean build with synthetic review receipts, never a paper run."""
        import ir,workflow,run_graph,audit_b,case_status
        from audit_b_fixtures import synthetic_receipt
        source_steps=[];mapping={}
        for r in self.graph['inferences']:
            for p in r['argument']:
                sid=f'S{len(source_steps)+1:03d}'
                source_steps.append({'id':sid,'text':p['text']})
                mapping[sid]={'inference':r['id'],'paragraph':p['id']}
        c={'version':1,'id':'conditional_software_control',
           'source':{'path':'nl0.json','sha256':ir.digest(self.root/'nl0.json')},
           'source_steps':source_steps,'pins':{'lean_version':'4.32.2','mathlib_commit':ir.load_lock()['mathlib']['rev']},
           'header':'import Mathlib\n','parameters':[{'name':n,'type':'ℕ'} for n in ['a','b']],
           'premises':[{'id':'E001','kind':'external','type':'a = b','statement':'a=b.'}],
           'conclusion':{'type':'a + 0 = b','statement':'a+0=b.'},
           'endpoint_correspondence':{sid:{'mode':'direct','explanation':'Exact natural-number equality with the displayed binders.'}
                                      for sid in ['E001','P']},
           'representation':{'scope':'Natural-number equality.'},
           'review':{'mode':'deferred_semantic_review','status':'PENDING_AUDIT_B'}}
        cp=self.root/'contract.json';ir.write(cp,c)
        plan={'version':1,'contract_sha256':ir.digest(cp),'representation_notes':'Natural numbers with exact equality.',
              'steps':[{'id':'T001','statement':'b = a','inputs':['E001'],'source_steps':['S001'],
                        'explanation':'Symmetry of the supplied equality.'},
                       {'id':'T002','statement':'a + 0 = b','inputs':['T001'],'source_steps':['S002','S003'],
                        'explanation':'Symmetry and the additive identity.'}],'terminal':'T002'}
        pp=self.root/'plan.json';ir.write(pp,plan)
        interface=self.root/'interface-binding.json'
        ir.write(interface,{'contract_sha256':ir.digest(cp),'plan_sha256':ir.digest(pp),
            'source_graph_sha256':ir.digest(self.root/'nl0.json'),'paragraph_mapping':mapping,
            'source_outputs':{'N001':'T001','P':'T002'},'status':'IR_TYPES_CHECKED_SEMANTIC_REVIEW_PENDING_AUDIT_B'})
        out=self.root/'workflow'
        workflow.freeze(self.root/'nl0.json',self.root/'spec.json',cp,pp,None,out,
            audit_a=self.root/'audit-a.json',interface_binding=interface,max_concurrency=2)
        frozen=workflow.bound(out);proof_run=out/'proof-run';proof_run.mkdir()
        actual_cp,actual_plan=run_graph.package(Path(frozen['contract']),Path(frozen['plan']),proof_run)
        bodies={'T001':'exact h_E001.symm','T002':'simpa using h_T001.symm'}
        checked=ir.check(actual_cp,actual_plan,bodies,out=proof_run/'native-control')
        self.assertEqual(checked['exit_code'],0,checked)
        ir.write(proof_run/'proofs.json',{'contract_sha256':ir.digest(actual_cp),
            'plan_sha256':ir.digest(proof_run/'inputs/plan.json'),'proofs':bodies})
        ir.write(proof_run/'report.json',{'status':'FRAGMENT_ASSEMBLED','concurrency':{'test_only':True},'runner_wall_seconds':0})
        workflow.prepare_audit(out)
        self.assertEqual(audit_b.build(out/'audit-b')['status'],'AUDIT-B-MECHANICAL-PASSED')
        review=synthetic_receipt(out/'audit-b')
        result=workflow.finish(out,review)
        self.assertEqual(result['status'],'WORKFLOW-CONDITIONAL')
        self.assertEqual(result['audit_b']['status'],'AUDIT-B-CONDITIONAL')
        self.assertFalse(result['audit_b']['whole_nl0_and_current_audit_a'])
        self.assertEqual(result['audit_b']['source_warnings'][0]['source_id'],'E001')
        status=case_status.project(self.root,workflow=out)
        self.assertEqual(status['gates']['audit_a'],'CONDITIONAL')
        self.assertEqual(status['gates']['audit_b'],'CONDITIONAL')
        self.assertFalse(status['full_acceptance'])
        import audit_b_continuation
        def save_review(directory,**kwargs):
            directory=Path(directory)
            receipt=synthetic_receipt(directory.parent/'native')
            (directory/'review.json').write_bytes(receipt.read_bytes())
            (directory/'test-only-evidence.txt').write_bytes((receipt.parent/'test-only-evidence.txt').read_bytes())
        with patch.object(audit_b_continuation.reviewer,'run',side_effect=save_review),\
             patch.object(audit_b_continuation.reviewer,'collect',return_value={'all_checks_passed':True}):
            continued=audit_b_continuation.run(out/'audit-b',self.root/'review-only')
        self.assertEqual(continued['status'],'AUDIT-B-CONDITIONAL')
        self.assertEqual(continued['actual_audit_b_verdict'],'CONDITIONAL')
        self.assertFalse(continued['native_checks_rerun'])
        self.access.write_text('{}')
        with self.assertRaises(ValueError):workflow.bound(out)

    def test_forged_or_changed_secondary_statement_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'preserve'):
            source_access.defer(self.root,source_id='E002',statement='Invented stronger statement.',input_id='secondary.txt',quote='a=b.',
                inputs={'secondary.txt':'a=b.'},attempts=['external-sources/access-test.json'])
        forged=self.root/'inputs/access-forged.json';forged.parent.mkdir();forged.write_bytes(self.access.read_bytes())
        with self.assertRaisesRegex(ValueError,'own source-access'):
            source_access.defer(self.root,source_id='E002',statement='a=b.',input_id='secondary.txt',quote='a=b.',
                inputs={'secondary.txt':'a=b.'},attempts=['inputs/access-forged.json'])

    def test_browser_failures_support_only_the_same_bound_conditional_route(self):
        from controller_common import bind
        original=self.graph['propositions'][0]['source']['verification']['record']
        deferred_path=self.root/original['path']
        for status in ['HUMAN_ACCESS_REQUIRED','BROWSER_UNAVAILABLE','BROWSER_ERROR']:
            with self.subTest(status=status):
                self.access.write_text(json.dumps({'version':source_access.VERSION,'origin':'controller_browser',
                    'url':'https://example.org/unavailable','status':status}))
                record=json.loads(deferred_path.read_text());old_attempt=record['attempts'][0]
                new_attempt={'path':old_attempt['path'],'sha256':bind(self.access)['sha256']}
                record['attempts']=[new_attempt];deferred_path.write_text(json.dumps(record))
                new_ref={'path':original['path'],'sha256':bind(deferred_path)['sha256']}
                source=self.graph['propositions'][0]['source']
                source['evidence']=[new_ref,record['basis'],new_attempt]
                source['verification']['record']=new_ref
                self.write_source();self.make_audit()
                result=self.data()[0]
                self.assertTrue(result['current_conditional_receipt_valid'])
                self.assertFalse(result['current_standard_receipt_valid'])
                self.assertEqual(sq.publish(self.root,self.data())['warnings'][0]['access_outcomes'][0]['status'],status)


if __name__=='__main__':unittest.main()
