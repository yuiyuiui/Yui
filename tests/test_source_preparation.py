import harness_support
from pathlib import Path
import shutil
import tempfile
import unittest

from source_fixtures import case,synthetic_audit,synthetic_local_reviews,interface,synthetic_interface_review
import ir
import source_preparation as source
import workflow
import audit_b


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.base=Path(tempfile.mkdtemp(prefix='nl0-revision-control-'))
        self.g,self.s,self.p=case(self.base/'original')
        self.audit=synthetic_audit(self.g,self.s)

    def tearDown(self):shutil.rmtree(self.base)

    def stage(self,audit=True):
        out=self.base/'revision'
        source.stage(self.g,self.s,self.p,out,audit_a=self.audit if audit else None)
        return out

    def test_canonical_inventory_uses_real_edges(self):
        result=source.inventory(self.g,self.s)
        self.assertEqual(result['direct_consumers']['H001'],['R001','R002'])
        self.assertEqual(result['direct_consumers']['N001'],['R003'])

    def test_untouched_proof_and_all_old_statements_preserved(self):
        out=self.stage();old=ir.load(self.g);new=ir.load(out/'case/nl0.json')
        self.assertEqual(new['propositions'][:len(old['propositions'])],old['propositions'])
        self.assertEqual(new['inferences'][2],old['inferences'][2])
        self.assertEqual(ir.digest(out/'case/spec.json'),ir.digest(self.s))

    def test_pending_reviews_cannot_pass(self):
        with self.assertRaisesRegex(ir.Invalid,'unperformed'):source.check(self.stage())

    def test_real_parent_producer_rules_and_delta_coverage_are_used(self):
        out=self.stage();synthetic_local_reviews(out)
        result=source.check(out)
        self.assertTrue(result['result']['current_standard_receipt_valid'])
        self.assertEqual(result['coverage']['new_full_reviews'],['R004'])
        self.assertEqual(result['coverage']['substitution_reviews'],['R001','R002'])
        self.assertEqual(result['coverage']['inherited_inferences'],['R003'])
        self.assertEqual(result['coverage']['new_full_consumer_replays'],[])
        data,_=source.read_source(out/'case/nl0.json',out/'case/spec.json',incremental=out/'source-acceptance.json')
        self.assertTrue(data[0]['current_standard_receipt_valid'])

    def test_missing_baseline_audit_is_not_promoted(self):
        out=self.stage(False);synthetic_local_reviews(out)
        result=source.check(out)
        self.assertFalse(result['result']['current_standard_receipt_valid'])

    def test_changed_old_target_rejected(self):
        patch=ir.load(self.p);patch['candidates'][0]['proposition']['id']='P'
        ir.write(self.p,patch)
        with self.assertRaisesRegex(ir.Invalid,'fresh N'):self.stage()

    def test_unrelated_new_input_rejected(self):
        patch=ir.load(self.p);patch['candidates'][0]['consumers'][0]['inputs'].append('N002')
        ir.write(self.p,patch)
        with self.assertRaisesRegex(ir.Invalid,'unrelated consumer input'):self.stage()

    def test_local_fact_or_assumption_lifetime_cannot_be_rewritten(self):
        patch=ir.load(self.p);patch['candidates'][0]['consumers'][0]['replacements'][0]['after']['introduces']=['L1']
        ir.write(self.p,patch)
        with self.assertRaisesRegex(ir.Invalid,'assumption lifetime'):self.stage()

    def test_stale_paragraph_rejected(self):
        patch=ir.load(self.p);patch['candidates'][0]['consumers'][0]['replacements'][0]['before_sha256']='0'*64
        ir.write(self.p,patch)
        with self.assertRaisesRegex(ir.Invalid,'stale/unknown replacement'):self.stage()

    def test_short_splices_preserve_every_other_character(self):
        patch=ir.load(self.p)
        for consumer in patch['candidates'][0]['consumers']:
            row=consumer['replacements'][0];row.pop('after')
            row.update(splices=[{'old':'H001 gives p ∧ q. Its first conjunct is p.','new':'N003 gives p.'}],uses_after=['N003'])
        ir.write(self.p,patch);out=self.stage()
        old=ir.load(self.g)['inferences'][0]['argument'][0]['text']
        new=ir.load(out/'case/nl0.json')['inferences'][0]['argument'][0]['text']
        self.assertEqual(new,old.replace('H001 gives p ∧ q. Its first conjunct is p.','N003 gives p.'))

    def test_ambiguous_splice_rejected(self):
        patch=ir.load(self.p);row=patch['candidates'][0]['consumers'][0]['replacements'][0]
        row.pop('after');row.update(splices=[{'old':'p','new':'q'}],uses_after=['N003'])
        ir.write(self.p,patch)
        with self.assertRaisesRegex(ir.Invalid,'match exactly once'):self.stage()

    def test_existing_export_is_not_reextracted(self):
        patch=ir.load(self.p);patch['candidates'][0]['proposition']['statement']='p ∧ p.';ir.write(self.p,patch)
        with self.assertRaisesRegex(ir.Invalid,'existing exported N'):self.stage()

    def test_complete_cut_packets_include_inputs_and_global_context(self):
        out=self.stage();packet=ir.load(out/'case/cut-packets/C001-R001.json')
        self.assertEqual(packet['input_statements_before'][0]['statement'],'p ∧ q.')
        self.assertEqual(packet['input_statements_after'][0]['statement'],'p.')
        self.assertEqual(packet['global_context']['parameters'],ir.load(self.s)['parameters'])
        second=ir.load(out/'case/cut-packets/C001-R002.json')
        self.assertEqual(second['old_derivation']['inference'],'R002')
        self.assertEqual(second['producer_source_derivation']['inference'],'R001')

    def test_unverified_baseline_judgment_is_carried_forward(self):
        audit=ir.load(self.audit);audit['inference_reviews']['R003']['checks']['argument']['verdict']='UNVERIFIED'
        ir.write(self.audit,audit);out=self.stage();synthetic_local_reviews(out)
        result=source.check(out)
        self.assertFalse(result['result']['current_standard_receipt_valid'])
        self.assertTrue(result['result']['unresolved_reviews'])

    def test_new_producer_must_not_depend_on_its_consumer(self):
        patch=ir.load(self.p);producer=patch['candidates'][0]['producer']
        producer['inputs']=['N001'];producer['argument'][0]['text']='N001 gives p ∧ p; take its first conjunct p.'
        producer['argument'][0]['uses']=['N001'];ir.write(self.p,patch)
        with self.assertRaisesRegex(ValueError,'CYCLE'):self.stage()

    def test_receipt_coverage_cannot_be_changed_after_acceptance(self):
        out=self.stage();synthetic_local_reviews(out);source.check(out)
        path=out/'source-acceptance.json';value=ir.load(path);value['coverage']['inherited_inferences']=[];ir.write(path,value)
        with self.assertRaisesRegex(ir.Invalid,'coverage/bindings changed'):
            source.read_source(out/'case/nl0.json',out/'case/spec.json',incremental=path)

    def test_substitution_review_from_another_packet_is_rejected(self):
        out=self.stage();synthetic_local_reviews(out)
        path=out/'case/cut-review.json';value=ir.load(path)
        value['cuts']['C001:R001']['packet_sha256']='0'*64;ir.write(path,value)
        with self.assertRaisesRegex(ir.Invalid,'stale substitution review packet'):source.check(out)

    def test_new_producer_replay_must_match_exact_current_packet(self):
        out=self.stage();synthetic_local_reviews(out)
        path=out/'case/producer-review.json';value=ir.load(path)
        value['reviews']['R004']['replay']['packet_sha256']='0'*64;ir.write(path,value)
        with self.assertRaisesRegex(ValueError,'STALE-PACKET'):source.check(out)

    def test_missing_substitution_condition_review_rejected(self):
        out=self.stage();synthetic_local_reviews(out)
        path=out/'case/cut-review.json';value=ir.load(path)
        value['cuts']['C001:R001']['checks']['condition_discharge']='UNVERIFIED';ir.write(path,value)
        with self.assertRaisesRegex(ir.Invalid,'substitution review'):source.check(out)

    def test_evidence_edit_revokes_accepted_revision(self):
        out=self.stage();synthetic_local_reviews(out);source.check(out)
        (out/'case/TEST_ONLY_RECEIPT_SHAPE.txt').write_text('changed')
        with self.assertRaisesRegex(ir.Invalid,'stale bound artifact'):
            source.read_source(out/'case/nl0.json',out/'case/spec.json',incremental=out/'source-acceptance.json')

    def test_baseline_edit_revokes_delta_before_acceptance(self):
        out=self.stage();synthetic_local_reviews(out)
        (self.g.parent/'problem.txt').write_text('changed')
        with self.assertRaisesRegex(ir.Invalid,'stale bound artifact'):source.check(out)

    def test_zero_extraction_inherits_without_new_mathematical_review(self):
        patch=ir.load(self.p);patch['candidates']=[];ir.write(self.p,patch)
        out=self.stage();result=source.check(out)
        self.assertTrue(result['result']['current_standard_receipt_valid'])
        self.assertEqual(result['coverage']['new_full_reviews'],[])
        self.assertEqual(ir.digest(out/'case/nl0.json'),ir.digest(self.g))

    def test_second_revision_can_validate_existing_incremental_authority(self):
        out=self.stage();synthetic_local_reviews(out);source.check(out)
        patch={'version':source.VERSION,'baseline_graph_sha256':ir.digest(out/'case/nl0.json'),
               'spec_sha256':ir.digest(out/'case/spec.json'),'candidates':[]}
        path=self.base/'second-patch.json';ir.write(path,patch)
        second=self.base/'second'
        source.stage(out/'case/nl0.json',out/'case/spec.json',path,second,incremental=out/'source-acceptance.json')
        self.assertTrue(source.check(second)['result']['current_standard_receipt_valid'])

    def test_workflow_requires_source_acceptance_and_freezes_exact_arguments(self):
        cp,pp,rp=interface(self.g,self.s,self.base/'interfaces');synthetic_interface_review(rp)
        with self.assertRaisesRegex(ir.Invalid,'source is not accepted'):
            workflow.freeze(self.g,self.s,cp,pp,rp,self.base/'bad-run')
        manifest=workflow.freeze(self.g,self.s,cp,pp,rp,self.base/'good-run',audit_a=self.audit)
        self.assertEqual(manifest['concurrency']['requested'],'auto')
        self.assertEqual(manifest['concurrency']['effective'],len(ir.load(pp)['steps']))
        self.assertEqual(manifest['concurrency']['effective'],3)
        self.assertEqual(workflow.bound(self.base/'good-run')['status'],'SOURCE_AND_IR_FROZEN')
        value=ir.load(cp);value['conclusion']['type']='True';ir.write(cp,value)
        with self.assertRaisesRegex(ir.Invalid,'stale bound artifact'):workflow.bound(self.base/'good-run')

    def test_frozen_configuration_and_mapping_cannot_be_edited(self):
        cp,pp,rp=interface(self.g,self.s,self.base/'interfaces');synthetic_interface_review(rp)
        directory=self.base/'frozen-run';workflow.freeze(self.g,self.s,cp,pp,rp,directory,audit_a=self.audit)
        path=directory/'manifest.json';value=ir.load(path);value['concurrency']['effective']=10;ir.write(path,value)
        with self.assertRaisesRegex(ir.Invalid,'stale bound artifact'):workflow.bound(directory)

    def test_workflow_rejects_cross_source_dependency(self):
        out=self.stage();synthetic_local_reviews(out);source.check(out)
        g,s=out/'case/nl0.json',out/'case/spec.json'
        cp,pp,rp=interface(g,s,self.base/'interfaces')
        plan=ir.load(pp);plan['steps'][0]['inputs']=['H001'];ir.write(pp,plan)
        review=ir.load(rp);review['plan_sha256']=ir.digest(pp);ir.write(rp,review);synthetic_interface_review(rp)
        with self.assertRaisesRegex(ir.Invalid,'source input boundary'):
            workflow.freeze(g,s,cp,pp,rp,self.base/'bad-run',incremental=out/'source-acceptance.json')

    def test_audit_b_accepts_json_string_authority_paths_from_workflow(self):
        cp,pp,_=interface(self.g,self.s,self.base/'interfaces')
        bp=self.base/'proofs.json'
        ir.write(bp,{'contract_sha256':ir.digest(cp),'plan_sha256':ir.digest(pp),
                     'proofs':{'T001':'exact ⟨h_H001.1, h_H001.1⟩','T002':'exact Or.inl h_H001.1','T003':'exact ⟨h_T001, h_T002⟩'}})
        result=audit_b.prepare(cp,pp,bp,self.base/'audit-b',graph=str(self.g),spec=str(self.s),audit_a=str(self.audit))
        self.assertEqual(result['status'],'AUDIT-B-PREPARED')
        self.assertTrue(ir.load(self.base/'audit-b/source-inventory.json')['audit_a_current_passed'])


if __name__=='__main__':unittest.main()
