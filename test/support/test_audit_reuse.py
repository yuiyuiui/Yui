"""Synthetic inheritance controls. No actual model judgment is produced here."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import audit_a_campaign as a
import audit_reuse as reuse


class AuditReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.old=self.root/'old';shutil.copytree(a.CORE/'tests/fixtures/closed-addition',self.old)
        self.problem=self.root/'problem';self.problem.mkdir();(self.problem/'problem.md').write_text('Synthetic controller fixture only.')
        self.campaign=self.root/'previous';self.plan=a.prepare(self.old,self.problem,self.campaign)
        for job in self.plan['jobs']:
            directory=self.campaign/job['id'];stage=directory/'stage';stage.mkdir()
            row={'verdict':'PASS','notes':'SYNTHETIC inheritance test judgment, not a mathematical audit.','locations':['/inference/argument']}
            if job['library']:
                raw={'target_review':row,'structure_review':row,'definition_reviews':{},'source_reviews':{},'findings':[]}
                docs={name:reuse.sha(directory/name) for name in ['spec.json','nl0.json']}
            else:
                packet=a.nl0.load(directory/'packet.json')
                raw={'inference':job['id'],'packet_sha256':packet['packet_sha256'],'verdict':'PASS',
                     'notes':row['notes'],'checks':{key:row for key in a.nl0.CHECKS|a.nl0.closure.CLOSURE_CHECKS},'findings':[]}
                docs={'packet.json':reuse.sha(directory/'packet.json')}
            exposure={'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED','actual_model_ids':[__import__('run_pilot').MODEL],'standard_tier_verified':True}
            result={'status':'ACCEPTED','execution_health':'NO_RECORDED_FAULT','usage':{'complete':True},'exposure':exposure}
            for name,value in [('accepted.json',raw),('result.json',result),('exposure-audit.json',exposure),
                               ('execution-manifest.json',{'rule_documents':reuse.rules(),'task_documents':docs})]:a.write(stage/name,value)
        self.new=self.root/'new';shutil.copytree(self.old,self.new)
        self.data=a.nl0.validate(self.new/'nl0.json',self.new/'spec.json')

    def tearDown(self):self.tmp.cleanup()

    def test_unrelated_graph_change_reuses_only_identical_item_context(self):
        graph=a.nl0.load(self.new/'nl0.json');graph['inferences'][1]['argument'][0]['text']+=' This is the same local additive-identity calculation.'
        a.write(self.new/'nl0.json',graph)
        data=a.nl0.validate(self.new/'nl0.json',self.new/'spec.json')
        hits=reuse.select(data,[self.campaign])
        self.assertIn('packet:R001',hits);self.assertNotIn('packet:R002',hits);self.assertNotIn('structure',hits)
        inherited=reuse.materialize(hits['packet:R001'],self.new)
        checked=reuse.validate(self.new,inherited,data,'packet:R001')
        self.assertNotEqual(checked['previous_packet_sha256'],a.nl0.packet(data,'R001')['packet_sha256'])
        record=reuse.read_binding(self.new,inherited)[0]
        self.assertIn('Warm',record['cost_policy'])

    def test_changed_assumptions_domains_logic_inputs_output_or_scope_miss(self):
        hit=reuse.select(self.data,[self.campaign])['packet:R001']
        inherited=reuse.materialize(hit,self.new)
        changes=[lambda d:d[2]['parameters'][0].update(type='integer'),
                 lambda d:d[2]['hypotheses'][0].update(statement='a=b and a=0.'),
                 lambda d:d[2]['logic'].update(classical=True),
                 lambda d:d[2]['pins'].update(mathlib_commit='changed'),
                 lambda d:d[4]['R001']['argument'][0].update(text='Different inference.'),
                 lambda d:d[3]['H001'].update(statement='a=b and b=0.'),
                 lambda d:d[3]['N001'].update(statement='b=a and a=0.')]
        for change in changes:
            data=deepcopy(self.data);change(data)
            with self.assertRaisesRegex(ValueError,'context changed'):reuse.validate(self.new,inherited,data,'packet:R001')

    def test_changed_relevant_definition_guard_invalidates(self):
        data=deepcopy(self.data)
        data[5]['D001']={'id':'D001','symbol':'z','definition':'z=0.','type':'natural number','depends_on':[],'requires':[], 'binders':[],'objects':['0']}
        data[3]['H001']['definitions']=['D001']
        # The fixture closure was captured over the original definition map;
        # reconstruct the evidence-backed view before comparing guarded data.
        spec=deepcopy(data[2]);spec['definitions']=[data[5]['D001']]
        a.write(self.new/'spec.json',spec)
        graph=deepcopy(data[1]);graph['spec_sha256']=reuse.sha(self.new/'spec.json');a.write(self.new/'nl0.json',graph)
        guarded=reuse.data_from_files(self.new/'nl0.json',self.new/'spec.json')
        before=reuse.context(guarded,'packet:R001')
        guarded[5]['D001']['requires']=['H001']
        self.assertNotEqual(before,reuse.context(guarded,'packet:R001'))

    def test_changed_provenance_evidence_or_judgment_cannot_pass(self):
        hit=reuse.select(self.data,[self.campaign])['packet:R001'];inherited=reuse.materialize(hit,self.new)
        raw=reuse.raw_from_binding(self.new,inherited)
        row={'verdict':'PASS','notes':raw['notes'],'checks':raw['checks']}
        reuse.validate(self.new,inherited,self.data,'packet:R001',row)
        changed=deepcopy(row);changed['notes']='A different judgment.'
        with self.assertRaisesRegex(ValueError,'notes changed'):reuse.validate(self.new,inherited,self.data,'packet:R001',changed)
        record,paths=reuse.read_binding(self.new,inherited);paths['raw'].write_text('{}')
        with self.assertRaisesRegex(ValueError,'Stale'):reuse.validate(self.new,inherited,self.data,'packet:R001')

    def test_identity_or_rule_mismatch_never_qualifies(self):
        path=self.campaign/'R001/stage/result.json';result=a.nl0.load(path)
        result['exposure']['actual_model_ids']=['wrong-model'];a.write(path,result)
        self.assertNotIn('packet:R001',reuse.select(self.data,[self.campaign]))
        path=self.campaign/'R002/stage/execution-manifest.json';manifest=a.nl0.load(path)
        manifest['rule_documents']['references/audit-a.md']='changed';a.write(path,manifest)
        self.assertNotIn('packet:R002',reuse.select(self.data,[self.campaign]))

    def test_reused_packet_receipt_is_accepted_only_with_checked_inheritance(self):
        hits=reuse.select(self.data,[self.campaign]);inheritance=reuse.materialize(hits['packet:R001'],self.new)
        receipt=a.nl0.closure.audit_template(self.data,a.nl0.CHECKS,a.nl0.EXTERNAL_CHECKS,'nl0.json','spec.json')
        raw=hits['packet:R001']['row'];row=receipt['inference_reviews']['R001']
        row.update(verdict='PASS',notes=raw['notes'],inheritance=inheritance)
        record=reuse.read_binding(self.new,inheritance)[0]
        evidence=[inheritance,*record['previous'].values()];row['evidence']=evidence
        row['checks']={key:{**value,'evidence':evidence} for key,value in raw['checks'].items()}
        row['replay'].update(mode='fresh_packet_only',carrier='synthetic fixture only',
            read_materials=['packet:'+raw['packet_sha256']])
        path=self.new/'diagnostic-audit.json';a.write(path,receipt)
        result=a.nl0.validate(self.new/'nl0.json',self.new/'spec.json',path,allow_unresolved=True)[0]
        self.assertFalse(result['current_standard_receipt_valid'])
        self.assertNotIn('R001',{r['review'] for r in result['unresolved_reviews']})
        row['checks']['argument']['notes']='Changed actual review.';a.write(path,receipt)
        with self.assertRaisesRegex(ValueError,'notes changed'):
            a.nl0.validate(self.new/'nl0.json',self.new/'spec.json',path,allow_unresolved=True)

    def test_partial_source_preparation_exposes_only_remaining_work(self):
        graph=a.nl0.load(self.new/'nl0.json');graph['inferences'][1]['argument'][0]['text']+=' Same declared local calculation.'
        a.write(self.new/'nl0.json',graph)
        out=self.root/'next';plan=a.prepare(self.new,self.problem,out,reuse_from=[self.campaign])
        self.assertEqual(plan['jobs'][0]['required_scopes'],['structure'])
        self.assertIn('packet:R001',plan['inherited'])
        ids={r['id'] for r in a.nl0.load(out/'global/inputs.json')['inputs']}
        self.assertNotIn('accepted.json',ids);self.assertIn('review-selection.json',ids)

    def test_source_fidelity_context_does_not_depend_on_consumer_proof_text(self):
        data=deepcopy(self.data)
        data[3]['M001']={'id':'M001','kind':'mathlib','statement':'Synthetic source context only.',
            'definitions':[],'source':{'declaration':'Nat.add_comm','signature':'synthetic full type'}}
        before=reuse.context(data,'source:M001')
        packet_before=reuse.context(data,'packet:R001')
        data[4]['R001']['argument'][0]['text']+=' A changed local argument.'
        self.assertEqual(before,reuse.context(data,'source:M001'))
        self.assertNotEqual(packet_before,reuse.context(data,'packet:R001'))
        data[3]['M001']['source']['signature']='a changed source contract'
        self.assertNotEqual(before,reuse.context(data,'source:M001'))


if __name__=='__main__':unittest.main()
