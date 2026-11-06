"""Real Lean and artifact-boundary checks for same-node helper composition."""
import harness_support
import copy
from pathlib import Path
import shutil
import tempfile
import unittest

import assembly
import ir
import local_helpers
import model_pilot
from lean_fixtures import shared_fixture, LIFT, SUP


class LocalHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='yui-helper-test-')
        cls.root=Path(cls.temp.name)
        cls.cp,cls.plan=shared_fixture(cls.root/'source')
        cls.stage=model_pilot.Stage(cls.root/'worker',cls.cp,'proof',None,cls.plan,'T001')
        packet=ir.local_packet(cls.cp,cls.plan,'T001')
        cls.args=' '.join([p['name'] for p in packet['parameters']]+[p['binder'] for p in packet['inputs']])
        first=cls.stage.dispatch('check_auxiliary',{'statement':packet['target'],'proof':LIFT})
        if not first.get('helper'):raise AssertionError(first)
        second=cls.stage.dispatch('check_auxiliary',{'statement':packet['target'],
            'proof':'exact @'+first['helper']['name']+' '+cls.args})
        if not second.get('helper'):raise AssertionError(second)
        cls.body='exact @'+second['helper']['name']+' '+cls.args
        accepted=cls.stage.dispatch('submit_transition',{'proof':cls.body})
        if not accepted.get('stage_complete'):raise AssertionError(accepted)
        cls.proof=cls.stage.accepted['proof']

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.stage.work,ignore_errors=True)
        cls.temp.cleanup()

    def test_real_helper_chain_final_node_and_standalone_export(self):
        bundle={'T001':self.proof,'T002':SUP}
        result=ir.check(self.cp,self.plan,bundle,out=self.root/'assembled')
        self.assertEqual(result['exit_code'],0,result)
        self.assertEqual(result['native_limits']['max_heartbeats'],20000000)
        self.assertEqual(result['native_limits']['timeout_seconds'],180)
        c=ir.contract(self.cp)
        with tempfile.TemporaryDirectory() as raw:
            work=Path(raw);(work/'output').mkdir();out=work/'result';out.mkdir()
            built=assembly.build(c,{'library_terms':{}},ir.render(self.cp,self.plan,bundle),out,work)
            self.assertEqual(built['status'],'ASSEMBLY-PASSED',built)
            source=(out/'Proof.lean').read_text()
            self.assertIn('theorem yui_aux_0001',source)
            self.assertIn('theorem yui_aux_0002',source)
            self.assertIn('theorem P',source)
            self.assertNotIn('sorry',source)

    def test_machine_audit_inspects_helper_dependency_bodies(self):
        import audit_b
        from audit_b_fixtures import fixture
        cp,pp,bp,ip=fixture(self.root/'machine-case')
        plan=ir.load(pp)
        checked=ir.check_auxiliary(cp,plan,'T001','p','exact h_H001',out=self.root/'machine-helper')
        rows=[local_helpers.append(cp,plan,'T001',[],'p','exact h_H001',checked)]
        body=local_helpers.package(cp,plan,'T001','exact @yui_aux_0001 p h_H001',rows)
        value=ir.load(bp);value['proofs']={'T001':body};ir.write(bp,value)
        out=self.root/'machine-audit';audit_b.prepare(cp,pp,bp,out,fragment=ip)
        result=audit_b.build(out)
        self.assertEqual(result['status'],'AUDIT-B-MECHANICAL-PASSED',result)
        deps=ir.load(out/'elaborated.json')['dependencies']['declarations']
        self.assertTrue(any(d['name']=='Translation.Local_T001.yui_aux_0001' for d in deps))
        self.assertTrue(all(not set(d['axioms'])-{'propext','Classical.choice','Quot.sound'} for d in deps))
        manifest=ir.load(out/'manifest.json')
        self.assertEqual(manifest['tool_sha256'][str(Path(local_helpers.__file__).resolve())],ir.digest(local_helpers.__file__))

    def test_explicit_shared_alias_copies_a_closed_proof_not_a_helper_assumption(self):
        import shared_lemmas
        obligation=shared_lemmas.obligation(self.cp,self.plan,'T001')
        alias=shared_lemmas.reuse_body({'obligation':obligation,'proof':self.proof},obligation)
        checked=ir.check(self.cp,self.plan,{'T001':alias},only='T001')
        self.assertEqual(checked['exit_code'],0,checked)

    def test_recheck_failure_preserves_modular_body_for_the_same_author(self):
        import proof_reuse
        stage=model_pilot.Stage(self.root/'restore-helper',self.cp,'proof',None,self.plan,'T001')
        try:
            candidate={'body':copy.deepcopy(self.proof),'previous_run':'synthetic same-context origin'}
            proof_reuse.retain_recheck_failure(stage,candidate,{'exit_code':124,'stdout':'synthetic timeout'})
            self.assertEqual(stage.local_helpers,self.proof['helpers'])
            self.assertEqual(stage.own_lean_drafts['proof'][1]['proof'],self.body)
            before=copy.deepcopy(candidate)
            stage.local_helpers.append(copy.deepcopy(stage.local_helpers[-1]))
            self.assertEqual(candidate,before,'Continuing a worker must not alter its old proof package')
            self.assertEqual(len(stage.own_lean_drafts['proof'][1]['proof_package']['helpers']),2)
            self.assertIsNone(stage.accepted)
        finally:shutil.rmtree(stage.work,ignore_errors=True)

    def test_rejected_connection_patch_does_not_mutate_original_tool_arguments(self):
        from unittest.mock import patch
        import audit_b_mapping
        root=self.root/'mapping-isolation';run=root/'proof-run';inputs=run/'inputs'
        shutil.copytree(self.cp.parent,inputs)
        ir.write(inputs/'plan.json',self.plan)
        ir.write(run/'proofs.json',{'proofs':{'T001':self.proof}})
        c=ir.contract(self.cp)
        workflow=root/'workflow';ir.write(workflow/'audit-b/source-inventory.json',{
            'scope':'whole_structured_nl0','propositions':[
                {'id':'H001','kind':'hypothesis'},{'id':'P','kind':'target'}]})
        out=root/'author';ir.write(out/'authority.json',{'workflow':str(workflow)})
        contract=audit_b_mapping.MappingContract(out)
        value={'version':audit_b_mapping.audit_b.VERSION,
               'policy':audit_b_mapping.audit_b.correspondence.POLICY,
               'source_inventory_sha256':'deliberately stale',
               'entries':{'P':{'selector':'decl:AuditBExport.P','expected_type':c['conclusion']['type'],
                   'correspondence':{'mode':'direct','explanation':'Synthetic endpoint mapping for an immutable-input test.'}}},
               'library_terms':{},
               'proof_patches':{'T001':self.body}}
        before=copy.deepcopy(value)
        with patch.object(audit_b_mapping.workflow,'bound',return_value={}), \
             patch.object(audit_b_mapping.workflow,'proof_run',return_value=run):
            with self.assertRaisesRegex(ValueError,'exact original inventory'):contract(value)
        self.assertEqual(value,before,'Rejected tool input is part of the immutable event record')

    def test_missing_foreign_stale_changed_and_cyclic_helpers_rejected(self):
        changes=[lambda p:p.update(step='T002'),lambda p:p.update(context_sha256='stale'),
            lambda p:p['helpers'][0].update(proof='trivial'),
            lambda p:p['helpers'][0].update(dependencies=['yui_aux_0002']),
            lambda p:p['helpers'].pop(0),lambda p:p.update(body='exact yui_aux_0099'),
            lambda p:p['helpers'][0]['check'].update(axioms=['sorryAx'])]
        for change in changes:
            value=copy.deepcopy(self.proof);change(value)
            with self.subTest(change=change),self.assertRaises(ValueError):
                ir.render(self.cp,self.plan,{'T001':value},only='T001')

    def test_unproved_false_helper_cannot_register_or_change_target(self):
        stage=model_pilot.Stage(self.root/'negative-helper',self.cp,'proof',None,self.plan,'T001')
        try:
            result=stage.dispatch('check_auxiliary',{'statement':'False','proof':'exact True.intro'})
            self.assertFalse(result['auxiliary_valid'])
            self.assertEqual(stage.local_helpers,[])
            self.assertIsNone(stage.accepted)
        finally:shutil.rmtree(stage.work,ignore_errors=True)
        self.assertEqual(ir.local_packet(self.cp,self.plan,'T001')['target'],self.plan['steps'][0]['statement'])

    def test_checked_helpers_remain_discoverable_without_becoming_premises(self):
        self.assertEqual(len(self.proof['helpers']),2)
        self.assertEqual(self.proof['helpers'][1]['dependencies'],['yui_aux_0001'])
        packet=ir.local_packet(self.cp,self.plan,'T001')
        self.assertEqual([r['id'] for r in packet['inputs']],['H001'])
        self.assertEqual(ir.load(self.stage.logs/'local-helpers.json'),self.proof['helpers'])


if __name__=='__main__':unittest.main()
