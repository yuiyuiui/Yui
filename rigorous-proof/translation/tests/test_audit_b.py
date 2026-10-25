import copy
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE/'scripts'))
import ir
import audit_b as audit


def fixture(directory,variant='identity'):
    directory.mkdir(parents=True,exist_ok=True)
    mathlib=ir.load_lock()['mathlib']['rev']
    source={'mathematical_input':'Let p be a proposition. Given H001: p, prove P: p.',
            'source_steps':[{'id':'S001','text':'Apply H001 directly.'}]}
    params=[{'name':'p','type':'Prop'}]
    premises=[{'id':'H001','kind':'hypothesis','type':'p','statement':'p holds.'}]
    target='p';body='exact h_H001'
    props=[{'id':'H001','kind':'hypothesis','statement':'p holds.'},{'id':'P','kind':'target','statement':'p holds.'}]
    if variant in {'mathlib','unmapped_mathlib'}:
        source={'mathematical_input':'For natural numbers a,b, prove a+b=b+a by the declared commutativity result.',
                'source_steps':[{'id':'S001','text':'Instantiate the declared addition commutativity theorem at a,b.'}]}
        params=[{'name':'a','type':'ℕ'},{'name':'b','type':'ℕ'}]
        premises=[{'id':'M001','kind':'mathlib','type':'a+b=b+a','statement':'For these a,b, addition commutes.'}] if variant=='mathlib' else []
        target='a+b=b+a';body='exact h_M001' if premises else 'exact Nat.add_comm a b'
        props=([{'id':'M001','kind':'mathlib','statement':'For all natural a,b, a+b=b+a.',
                 'source':{'declaration':'Nat.add_comm'}}] if premises else []) + [
                 {'id':'P','kind':'target','statement':'For these a,b, a+b=b+a.'}]
    if variant=='weakened_external':
        source={'mathematical_input':'Let p,q be propositions. The supplied external input E001 states p. Prove p.',
                'source_steps':[{'id':'S001','text':'Apply exactly the supplied external statement E001: p.'}]}
        params=[{'name':'p','type':'Prop'},{'name':'q','type':'Prop'}]
        premises=[{'id':'E001','kind':'external','type':'p ∧ q','statement':'Intentionally strengthened external input.'}]
        target='p';body='exact h_E001.1'
        props=[{'id':'E001','kind':'external','statement':'p holds.'},{'id':'P','kind':'target','statement':'p holds.'}]
    if variant=='unmapped_instance':
        source={'mathematical_input':'An unregistered mathematical property of the reals.',
                'source_steps':[{'id':'S001','text':'Attempt to use a library instance as the entire proof.'}]}
        params=[];premises=[];target='IsTopologicalRing ℝ';body='exact instIsTopologicalRingReal'
        props=[{'id':'P','kind':'target','statement':'The real numbers form a topological ring.'}]
    (directory/'source.json').write_text(__import__('json').dumps(source,indent=2)+'\n')
    header='import Mathlib\n'
    if variant=='hidden_field':
        header+='\nstructure Box (q : Prop) where\n  hidden : q\n'
        params.append({'name':'box','type':'Box p'})
    if variant=='equivalent_target': target='p ∧ True';body='exact ⟨h_H001, True.intro⟩'
    if variant=='wrong_target': target='True';body='exact True.intro'
    if variant=='extra_axiom':
        header+='axiom hiddenProof : False\n'
        body='exact False.elim hiddenProof'
    c={'version':1,'id':'audit_control','source':{'path':'source.json','sha256':ir.digest(directory/'source.json')},
       'source_steps':source['source_steps'],'pins':{'lean_version':'4.32.2','mathlib_commit':mathlib},
       'header':header,'parameters':params,'premises':premises,
       'endpoint_correspondence':{p['id']:{'mode':'direct','explanation':'The displayed binders and assertion encode the source '+p['id']+'.'} for p in props if p['kind'] in {'external','target'}},
       'conclusion':{'statement':props[-1]['statement'],'type':target},'representation':{'scope':'propositional/Nat controls'},
       'review':{'mode':'development_owner_review','scope':'Synthetic Audit B controls; no whole-case certification.'}}
    if variant=='equivalent_target':
        c['endpoint_correspondence']['P']={'mode':'equivalent','explanation':'The encoding pairs the original assertion with True; take the first projection to recover the original, and pair it with True.intro in the other direction.'}
    cpath=directory/'contract.json';ir.write(cpath,c)
    plan={'version':1,'contract_sha256':ir.digest(cpath),'representation_notes':'Preserve the fixed proposition or natural-number statement.',
          'steps':[{'id':'T001','statement':target,'inputs':[p['id'] for p in premises],
                    'source_steps':['S001'],'explanation':source['source_steps'][0]['text']}],'terminal':'T001'}
    ppath=directory/'plan.json';ir.write(ppath,plan)
    bpath=directory/'proofs.json';ir.write(bpath,{'contract_sha256':ir.digest(cpath),'plan_sha256':ir.digest(ppath),'proofs':{'T001':body}})
    inventory={'scope':'development_fragment','source_sha256':c['source']['sha256'],
               'full_target':source['mathematical_input'],'parameters':[p for p in params if p['name']!='box'],
               'definitions':[],'logic':{'classical':False,'calculations':[]},'propositions':props,
               'inferences':[{'id':'R001','inputs':[p['id'] for p in premises],'output':'P','argument':source['source_steps']}]}
    ipath=directory/'inventory.json';ir.write(ipath,inventory)
    return cpath,ppath,bpath,ipath


def prepare_control(base,variant='identity'):
    c,p,b,i=fixture(base/'case',variant)
    directory=base/'audit'
    audit.prepare(c,p,b,directory,fragment=i)
    mapping=ir.load(directory/'mapping.json')
    if variant in {'wrong_target','hidden_field'}:
        # Independent expected type follows the original NL statement, rather
        # than the formalizer's weakened goal or added Box parameter.
        mapping['entries']['P']['expected_type']='∀ (p : Prop) (h_H001 : p), p'
    if variant=='weakened_external':
        mapping['entries']['P']['expected_type']='∀ (p q : Prop) (h_E001 : p), p'
        mapping['entries']['E001']['expected_type']='∀ (p q : Prop), p'
    if variant=='mathlib':
        mapping['library_terms']['M001']='exact Nat.add_comm a b'
    ir.write(directory/'mapping.json',mapping)
    return directory


def synthetic_receipt(directory):
    """Receipt-format control, not an automated semantic audit."""
    record=ir.load(directory/'review-template.json')
    note=directory/'test-only-evidence.txt';note.write_text('TEST RECEIPT SHAPE ONLY. No independent certification or new mathematical review.\n')
    evidence=[{'path':note.name,'sha256':ir.digest(note)}]
    mechanical=ir.load(directory/'mechanical.json')
    record['reviewer']={'identity':'TEST_RECEIPT_SHAPE_ONLY','mode':'same_context_self_audit',
                        'independent':False,'disclosure':'Synthetic validator regression, not a substantive audit.'}
    for key,row in record['nodes'].items():
        row.update(verdict='PASS',notes='Synthetic located receipt for validator regression only.',
                   locations=mechanical['required_review_locations'][key],evidence=evidence)
    for row in record['checks'].values():
        row.update(verdict='PASS',notes='Synthetic complete receipt; semantic quality is not being certified.',
                   locations=['/inventory','/actual_elaborated_evidence'],evidence=evidence)
    path=directory/'test-only-review.json';ir.write(path,record)
    return path


class AuditBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=Path(tempfile.mkdtemp(prefix='audit-b-controls-'))
        cls.directories={}
        cls.outcomes={}
        for variant in ('identity','wrong_target','hidden_field','mathlib','unmapped_mathlib','weakened_external','unmapped_instance','extra_axiom','equivalent_target'):
            directory=prepare_control(cls.base/variant,variant)
            cls.outcomes[variant]=audit.build(directory)
            cls.directories[variant]=directory

    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.base)

    def setUp(self):
        self.copy=Path(tempfile.mkdtemp(prefix='audit-b-receipt-'))/'audit'
        shutil.copytree(self.directories['identity'],self.copy)

    def tearDown(self): shutil.rmtree(self.copy.parent)

    def test_actual_positive_kernel_inspection(self):
        self.assertEqual(self.outcomes['identity']['status'],'AUDIT-B-MECHANICAL-PASSED',self.outcomes)
        data=ir.load(self.directories['identity']/'elaborated.json')
        self.assertTrue(all(x['definitionally_equal'] for x in data['comparisons']))

    def test_lean_valid_weakened_target_rejected(self):
        report=ir.load(self.directories['wrong_target']/'mechanical.json')
        self.assertEqual(report['compiler_exit_code'],0)
        self.assertIn('ELABORATED_SIGNATURE_MISMATCH',report['errors'])

    def test_hidden_proof_field_is_exposed_and_extra_parameter_rejected(self):
        directory=self.directories['hidden_field'];report=ir.load(directory/'mechanical.json')
        self.assertEqual(report['compiler_exit_code'],0)
        self.assertIn('ELABORATED_SIGNATURE_MISMATCH',report['errors'])
        declarations=ir.load(directory/'elaborated.json')['dependencies']['declarations']
        constructor=next(d for d in declarations if d['name']=='Box.mk')
        self.assertTrue(any(b['proof_valued'] for b in constructor['signature']['binders']))

    def test_mathlib_premise_is_discharged_by_an_actual_library_proof(self):
        self.assertEqual(self.outcomes['mathlib']['status'],'AUDIT-B-MECHANICAL-PASSED',self.outcomes['mathlib'])
        data=ir.load(self.directories['mathlib']/'elaborated.json')
        exported=next(r for r in data['comparisons'] if r['id']=='P')
        self.assertNotIn('h_M001',exported['actual_type'])

    def test_equivalent_encoding_is_passed_to_review_not_automatically_certified(self):
        directory=self.directories['equivalent_target']
        report=ir.load(directory/'mechanical.json')
        self.assertTrue(report['passed'])
        note=ir.load(directory/'review-packet.json')['mapping']['entries']['P']['correspondence']
        self.assertEqual(note['mode'],'equivalent')
        with self.assertRaises(ir.Invalid):
            audit.check(directory,directory/'review-template.json')

    def test_unlisted_mathlib_result_is_freely_available(self):
        report=ir.load(self.directories['unmapped_mathlib']/'mechanical.json')
        self.assertEqual(report['compiler_exit_code'],0)
        self.assertTrue(report['passed'])
        self.assertNotIn('unmapped_imported_proofs',report)

    def test_library_instance_can_be_used_as_an_ordinary_proof(self):
        report=ir.load(self.directories['unmapped_instance']/'mechanical.json')
        self.assertEqual(report['compiler_exit_code'],0)
        self.assertTrue(report['passed'])

    def test_unproved_project_axiom_is_still_rejected(self):
        report=ir.load(self.directories['extra_axiom']/'mechanical.json')
        self.assertFalse(report['passed'])
        self.assertIn('UNPROVED_OR_EXECUTABLE_HEADER_DECLARATION',report['errors'])
        self.assertTrue(any(e.startswith('UNPERMITTED_AXIOM:') for e in report['errors']))

    def test_external_input_with_same_count_but_changed_content_rejected(self):
        directory=self.directories['weakened_external'];report=ir.load(directory/'mechanical.json')
        self.assertEqual(report['compiler_exit_code'],0)
        self.assertIn('ELABORATED_SIGNATURE_MISMATCH',report['errors'])
        comparison=next(r for r in ir.load(directory/'elaborated.json')['comparisons'] if r['id']=='E001')
        self.assertFalse(comparison['definitionally_equal'])

    def test_only_external_and_complete_target_have_semantic_rows(self):
        for variant in ('identity','mathlib','unmapped_mathlib'):
            report=ir.load(self.directories[variant]/'mechanical.json')
            self.assertEqual(set(report['required_review_locations']),{'P'})
        report=ir.load(self.directories['weakened_external']/'mechanical.json')
        self.assertEqual(set(report['required_review_locations']),{'E001','P'})

    def test_explanation_is_required_and_bound_to_review(self):
        c=ir.contract(self.base/'identity/case/contract.json')
        inventory=ir.load(self.copy/'source-inventory.json')
        mapping=ir.load(self.copy/'mapping.json')
        mapping['entries']['P']['correspondence']['explanation']=''
        with self.assertRaisesRegex(ir.Invalid,'explanation is missing'):
            audit.validate_mapping(c,inventory,mapping)
        path=synthetic_receipt(self.copy);record=ir.load(path)
        record['nodes']['P']['locations'].remove('/mapping/entries/P/correspondence')
        ir.write(path,record)
        with self.assertRaisesRegex(ir.Invalid,'paired source/kernel'): audit.check(self.copy,path)

    def test_pending_template_never_passes(self):
        with self.assertRaises(ir.Invalid): audit.check(self.copy,self.copy/'review-template.json')

    def test_synthetic_complete_receipt_checks_shape_but_not_independence(self):
        result=audit.check(self.copy,synthetic_receipt(self.copy))
        self.assertEqual(result['status'],'DEVELOPMENT-AUDIT-B-PASSED')
        self.assertFalse(result['whole_nl0_and_current_audit_a'])
        self.assertFalse(result['semantic_review_automatically_verified'])

    def test_missing_source_mapping_rejected(self):
        c=ir.contract(self.base/'identity/case/contract.json');inventory=ir.load(self.copy/'source-inventory.json')
        mapping=ir.load(self.copy/'mapping.json');del mapping['entries']['P']
        with self.assertRaisesRegex(ir.Invalid,'missing/extra'): audit.validate_mapping(c,inventory,mapping)

    def test_mismatched_root_source_kind_rejected(self):
        c=ir.contract(self.base/'identity/case/contract.json');inventory=ir.load(self.copy/'source-inventory.json')
        inventory['propositions'][0]['kind']='external'
        with self.assertRaisesRegex(ir.Invalid,'missing/extra|root assumption'):
            audit.validate_mapping(c,inventory,ir.load(self.copy/'mapping.json'))

    def test_different_or_decoy_root_rejected(self):
        c=ir.contract(self.base/'identity/case/contract.json');inventory=ir.load(self.copy/'source-inventory.json')
        mapping=ir.load(self.copy/'mapping.json');mapping['entries']['P']['selector']='decl:True.intro'
        with self.assertRaisesRegex(ir.Invalid,'actual assembled root'): audit.validate_mapping(c,inventory,mapping)

    def test_missing_paired_semantic_locations_rejected(self):
        path=synthetic_receipt(self.copy);record=ir.load(path);record['nodes']['P']['locations']=['/inventory']
        ir.write(path,record)
        with self.assertRaisesRegex(ir.Invalid,'paired source/kernel'): audit.check(self.copy,path)

    def test_self_review_cannot_claim_independence(self):
        path=synthetic_receipt(self.copy);record=ir.load(path);record['reviewer']['independent']=True;ir.write(path,record)
        with self.assertRaisesRegex(ir.Invalid,'independence'): audit.check(self.copy,path)

    def test_changed_review_packet_rejected(self):
        path=synthetic_receipt(self.copy);ir.write(self.copy/'review-packet.json',{'changed':True})
        with self.assertRaisesRegex(ir.Invalid,'kernel audit artifact'): audit.check(self.copy,path)

    def test_modified_mapping_revokes_review(self):
        path=synthetic_receipt(self.copy);m=ir.load(self.copy/'mapping.json');m['entries']['P']['expected_type']='True';ir.write(self.copy/'mapping.json',m)
        with self.assertRaisesRegex(ir.Invalid,'semantic mapping'): audit.check(self.copy,path)

    def test_changed_evidence_revokes_review(self):
        path=synthetic_receipt(self.copy);(self.copy/'test-only-evidence.txt').write_text('changed')
        with self.assertRaisesRegex(ir.Invalid,'semantic evidence'): audit.check(self.copy,path)

    def test_old_policy_or_permission_ledger_is_not_silently_reused(self):
        c=ir.contract(self.base/'identity/case/contract.json')
        inventory=ir.load(self.copy/'source-inventory.json')
        mapping=ir.load(self.copy/'mapping.json');mapping['version']=1
        with self.assertRaisesRegex(ir.Invalid,'unsupported Audit B policy'):
            audit.validate_mapping(c,inventory,mapping)
        mapping['version']=audit.VERSION;mapping['calculation_links']={}
        with self.assertRaisesRegex(ir.Invalid,'obsolete or unexpected'):
            audit.validate_mapping(c,inventory,mapping)

    def test_equivalence_explanation_does_not_override_independent_rejection(self):
        path=synthetic_receipt(self.copy);record=ir.load(path)
        record['nodes']['P']['verdict']='FAIL'
        record['nodes']['P']['notes']='Synthetic negative: the stated identification omits a hypothesis.'
        ir.write(path,record)
        with self.assertRaisesRegex(ir.Invalid,'unperformed/failed semantic review: P'):
            audit.check(self.copy,path)


if __name__=='__main__':unittest.main()
