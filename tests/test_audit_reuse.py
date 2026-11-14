"""Synthetic inheritance controls. No actual model judgment is produced here."""
import harness_support
from audit_a_fixtures import AuditReuseFixture

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import threading
from unittest.mock import patch
import unittest

import audit_a_campaign as a
import audit_reuse as reuse


class AuditReuseTests(AuditReuseFixture, unittest.TestCase):

    def test_concurrent_evidence_publication_never_exposes_a_partial_file(self):
        source=self.root/'large-evidence';source.write_bytes(b'evidence'*10000)
        target=self.root/'shared-cache';digest=hashlib.sha256(source.read_bytes()).hexdigest()
        writers=threading.Barrier(5);release=threading.Event()
        def copying(src,dst):
            Path(dst).write_bytes(b'partial')
            writers.wait(timeout=5);release.wait(timeout=5)
            Path(dst).write_bytes(Path(src).read_bytes())
        with patch.object(reuse.shutil,'copyfile',copying),ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(reuse.publish_evidence,source,target,digest) for _ in range(4)]
            try:
                writers.wait(timeout=5)
                self.assertFalse(target.exists(),'Readers must not see any in-progress copy')
            finally:release.set()
            for future in futures:future.result(timeout=5)
        self.assertEqual(target.read_bytes(),source.read_bytes())
        self.assertFalse(list(self.root.glob('.evidence-*')))


    def test_unrelated_graph_change_reuses_only_identical_item_context(self):
        graph=a.nl0.load(self.new/'nl0.json');graph['inferences'][1]['argument'][0]['text']+=' This is the same local additive-identity calculation.'
        a.write(self.new/'nl0.json',graph)
        data=a.nl0.validate(self.new/'nl0.json',self.new/'spec.json')
        hits=reuse.select(data,[self.campaign])
        self.assertIn('packet:R001',hits);self.assertNotIn('packet:R002',hits);self.assertIn('structure',hits)
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
        result['exposure']['configured_model']='wrong-model';a.write(path,result)
        self.assertNotIn('packet:R001',reuse.select(self.data,[self.campaign]))
        path=self.campaign/'R002/stage/execution-manifest.json';manifest=a.nl0.load(path)
        manifest['rule_documents']['nl0/references/audit-a.md']='changed';a.write(path,manifest)
        self.assertNotIn('packet:R002',reuse.select(self.data,[self.campaign]))

    def test_complete_recovered_review_is_reused_with_fault_measurement_preserved(self):
        path=self.campaign/'R001/stage/result.json';result=a.nl0.load(path)
        result.update(transport='native-codex-stdio-v1',execution_health='FAULT',temporary_workspace_removed=True,
            transport_health={'status':'FAULT','faults':[{'kind':'NATIVE_PROVIDER_ERROR',
                'details':{'codexErrorInfo':'serverOverloaded'}}],'uncertainty':[]})
        a.write(path,result)
        hit=reuse.select(self.data,[self.campaign])['packet:R001']
        self.assertFalse(hit['measurement']['execution_qualified'])
        self.assertFalse(hit['measurement']['measurement_valid'])
        inherited=reuse.materialize(hit,self.new)
        reuse.validate(self.new,inherited,self.data,'packet:R001')
        for field,value in [('execution_fault','Local controller failure'),('isolation_violation',True)]:
            changed={**result,field:value};a.write(path,changed)
            self.assertNotIn('packet:R001',reuse.select(self.data,[self.campaign]))

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
        self.assertEqual(plan['jobs'][0]['required_scopes'],[])
        self.assertIn('packet:R001',plan['inherited'])
        ids={r['id'] for r in a.nl0.load(out/'global/inputs.json')['inputs']}
        self.assertNotIn('accepted.json',ids);self.assertIn('review-selection.json',ids)

    def test_changed_public_graph_edge_invalidates_global_structure(self):
        before=reuse.context(self.data,'structure',structure_policy='public_graph')
        data=deepcopy(self.data);data[1]['inferences'][1]['inputs']=[]
        self.assertNotEqual(before,reuse.context(data,'structure',structure_policy='public_graph'))

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
