"""2basis structural, authority, native and explicit-decision controls."""
import harness_support
from basis_fixtures import artifact, dependency, checked_context, TARGET
from copy import deepcopy
import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

import audit_reuse
import basis
import basis_native
import b2lean
import entrypoint
import fault_control
import ir
import jobs
import target_selection
from controller_common import bind, manifest, write
from harness_support import PROFILES


class BasisSchemaTests(unittest.TestCase):
    def test_all_four_classes_and_compatibility_are_separate(self):
        value=artifact(dependency(),dependency('B002',1,compatibility='adapted'),
            dependency('B003',2),dependency('B004',3),dependency('B005',4))
        rows,order=basis.validate(value,TARGET)
        self.assertEqual(set(order),set(rows));self.assertEqual(rows['B002']['category'],1)
        self.assertIsNone(rows['B004']['port'])

    def test_missing_extra_or_unknown_basis_fields_fail(self):
        for name in artifact():
            value=artifact();del value[name]
            with self.subTest(field=name),self.assertRaises(ValueError):basis.validate(value,TARGET)
        value=artifact();value['score']=10
        with self.assertRaises(ValueError):basis.validate(value,TARGET)

    def test_original_target_is_exact_authority(self):
        for target in ('True','If an additional condition holds, '+TARGET,''):
            with self.subTest(target=target),self.assertRaises(ValueError):basis.validate(artifact(),target)

    def test_dependency_field_and_category_rejections(self):
        variants=[{'id':'../B001'},{'id':True},{'category':True},{'category':5},
            {'statement':''},{'justification':''},{'origin':{}},{'uses':'B002'},
            {'uses':['B002','B002']},{'port':'H001'},{'lean':{'type':'True'}},
            {'compatibility':'guessed'},{'lean':{'type':'True','proof':'sorry'}}]
        for change in variants:
            value=artifact(dependency());value['dependencies'][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):basis.validate(value,TARGET)

    def test_class3_cannot_be_an_assumption_or_depend_on_unresolved4(self):
        for change in ({'port':'E003'},{'lean':{'type':'True','proof':'trivial'}},{'uses':[]},{'uses':['B004']}):
            value=artifact(dependency(),dependency('B003',3),dependency('B004',4))
            value['dependencies'][1].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):basis.validate(value,TARGET)

    def test_recursive_class3_and_topological_prepared_proofs(self):
        d=dependency('B002',3);e=dependency('B003',3);e['uses']=['B002']
        _,order=basis.validate(artifact(e,d,dependency()),TARGET)
        self.assertEqual(order,['B001','B002','B003'])

    def test_cycles_missing_duplicate_ids_ports_and_wrong_origin(self):
        values=[]
        values.append(artifact(dependency(),dependency()))
        value=artifact(dependency());value['dependencies'][0]['uses']=['B001'];values.append(value)
        value=artifact(dependency());value['dependencies'][0]['uses']=['B999'];values.append(value)
        values.append(artifact(dependency(category=2),dependency('B002',2,port='E001')))
        value=artifact(dependency());value['dependencies'][0]['origin']['kind']='textbook';values.append(value)
        for value in values:
            with self.subTest(value=value),self.assertRaises(ValueError):basis.validate(value,TARGET)

    def test_prepared_proofs_cannot_use_internal_or_unresolved_dependencies(self):
        for category in (3,4):
            first=dependency();first['uses']=['B002'];second=dependency('B002',category)
            with self.subTest(category=category),self.assertRaises(ValueError):basis.validate(artifact(first,second),TARGET)

    def test_native_adapted_and_library_ports(self):
        for category,compatibility,port in [(1,'native','E001'),(1,'adapted',None),(2,'native','M001')]:
            row=dependency(category=category,compatibility=compatibility);row['port']=port
            with self.subTest(row=row),self.assertRaises(ValueError):basis.validate(artifact(row),TARGET)

    def test_class4_requires_retained_evidence_and_no_claimed_proof(self):
        for change in ({'origin':{'kind':'textbook','reference':'X','revision':'X','evidence':[]}},
                {'lean':{'type':'True','proof':'trivial'}},{'port':None},{'compatibility':'adapted'}):
            row=dependency(category=4);row.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):basis.validate(artifact(row),TARGET)

    def test_replacement_map_requires_real_derivations_and_explanations(self):
        for row in ({'original_dependency':'E','replacement':['B999'],'explanation':'x'},
                    {'original_dependency':'E','replacement':[],'explanation':'x'},
                    {'original_dependency':'E','replacement':['B001'],'explanation':''}):
            value=artifact(dependency());value['replacements']=[row]
            with self.subTest(row=row),self.assertRaises(ValueError):basis.validate(value,TARGET)

    def test_executable_and_unproved_headers_rejected(self):
        for header in ('import Mathlib\naxiom bad : False','import Mathlib\nimport Unpinned',
                'import Mathlib\n#eval IO.println "bad"','import Mathlib\ntheorem bad : True := by trivial'):
            value=artifact();value['lean_header']=header
            with self.subTest(header=header),self.assertRaises(ValueError):basis.validate(value,TARGET)

    def test_evidence_cannot_escape_or_reference_undeclared_inputs(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);(root/'problem.md').write_text(TARGET);manifest(root)
            for evidence in ({'input':'absent'},{'input':'../problem.md'},{'path':'../x','sha256':'x'},
                    {'path':'/tmp/x','sha256':'x'},{'status':'VERIFIED'}):
                row=dependency(category=4);row['origin']['evidence']=[evidence]
                with self.subTest(evidence=evidence),self.assertRaises((ValueError,OSError)):
                    basis.evidence_bindings(artifact(row),root,root)

    def test_active_basis_versions_invalidate_every_reuse_scope(self):
        import audit_a_fixtures
        with tempfile.TemporaryDirectory() as raw:
            source=audit_a_fixtures.canonical_propositional_case(Path(raw))
            data=audit_reuse.data_from_files(source/'nl0.json',source/'spec.json')
            for scope in ('target','structure','packet:R001'):
                before=deepcopy(data);after=deepcopy(data)
                before[2]['inputs'].append({'path':'inputs/proof-context.json','sha256':'one'})
                after[2]['inputs'].append({'path':'inputs/proof-context.json','sha256':'two'})
                self.assertNotEqual(audit_reuse.context(before,scope),audit_reuse.context(after,scope))


class BasisJobTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.proof=self.root/'proof.md';self.proof.write_text('Theorem 1. '+TARGET)
    def tearDown(self):self.temp.cleanup()

    def test_legacy_jobs_and_default_are_conditional(self):
        job=jobs.prepare(self.proof,track='full',profiles=PROFILES)
        self.assertEqual(basis.mode(job),'conditional');self.assertEqual(basis.mode({}),'conditional')
        # Re-seal a historical job with no new optional field.
        del job['formalization'];write(Path(job['root'])/'job.json',job)
        marker=ir.load(Path(job['root'])/jobs.MARKER);marker['job']=bind(Path(job['root'])/'job.json')
        write(Path(job['root'])/jobs.MARKER,marker)
        jobs.validate(job)

    def test_unconditional_request_is_frozen_and_not_an_alias_for_full(self):
        selection=target_selection.resolve(self.proof,requested=TARGET)
        job=jobs.prepare(self.proof,track='full',profiles=PROFILES,formalization='unconditional',target=selection)
        jobs.validate(job);self.assertEqual(job['formalization'],'unconditional')

    def test_unknown_incompatible_and_targetless_requests_fail(self):
        for track,mode in [('nl0','unconditional'),('translate','unconditional'),('audit-b','unconditional'),('full','unknown')]:
            with self.subTest(track=track,mode=mode),self.assertRaises(ValueError):
                jobs.prepare(self.proof,track=track,profiles=PROFILES,formalization=mode)
        with self.assertRaisesRegex(ValueError,'target'):
            jobs.prepare(self.proof,track='full',profiles=PROFILES,formalization='unconditional')

    def test_cli_default_and_explicit_mode(self):
        parser=argparse.ArgumentParser();entrypoint.parsers(parser.add_subparsers(dest='command'))
        for options,expected in [([], 'conditional'),(['--formalization','unconditional'],'unconditional')]:
            args=parser.parse_args(['prepare',str(self.proof),'--track','full','--target',TARGET,'--use-config-profiles',*options])
            result=entrypoint.dispatch(args)
            self.assertEqual(result['formalization'],expected)


class BasisDecisionTests(unittest.TestCase):
    def test_all_exact_choices_and_stale_foreign_controls(self):
        for action in ('stop','continue','accept-conditional'):
            with self.subTest(action=action),tempfile.TemporaryDirectory() as raw:
                root=Path(raw);artifact_path=root/'basis.json';write(artifact_path,artifact(dependency(category=4)))
                gate=fault_control.Gate(root,stage='basis-decision',notify=Mock(return_value={'status':'QUEUED'}))
                def choose(_):
                    incident=gate.state['incident']
                    with self.assertRaises(ValueError):fault_control.final_decision(gate.root,'stale',action)
                    with self.assertRaises(ValueError):fault_control.final_decision(gate.root,incident,'deliver-actual')
                    fault_control.final_decision(gate.root,incident,action)
                    with self.assertRaises(ValueError):fault_control.final_decision(gate.root,incident,action)
                gate.wait=choose
                state=gate.pause({'status':'BASIS_USER_DECISION_REQUIRED'},resumable=False,
                    checkpoint={'basis':bind(artifact_path),'residual_class4':['B001']},
                    decisions=('stop','continue','accept-conditional'))
                self.assertEqual(state['control']['action'],action)
                self.assertIn('basis-decision',state['decisions'][action])
                self.assertFalse(state['cleanup_authorized'])

    def test_concurrent_mutually_exclusive_decisions_publish_one_complete_control(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);path=root/'basis.json';write(path,artifact(dependency(category=4)))
            gate=fault_control.Gate(root,stage='basis-decision',notify=Mock(return_value={'status':'QUEUED'}))
            start=threading.Barrier(2,timeout=5);before_replace=threading.Barrier(2,timeout=5)
            won=[]
            def choose(_):
                incident=gate.state['incident']
                control=gate.logs/'error-control'/(incident+'.json')
                original=fault_control.execution.atomic
                def overlapping_write(path,value):
                    if path==control:before_replace.wait()
                    return original(path,value)
                def attempt(action):
                    start.wait()
                    try:fault_control.final_decision(gate.root,incident,action)
                    except ValueError:return None
                    return action
                with patch.object(fault_control.execution,'atomic',overlapping_write),ThreadPoolExecutor(max_workers=2) as pool:
                    won.extend(a for a in pool.map(attempt,('stop','continue')) if a)
            gate.wait=choose
            decision=gate.pause({'status':'BASIS_USER_DECISION_REQUIRED'},resumable=False,
                checkpoint={'basis':bind(path),'residual_class4':['B001']},decisions=('stop','continue','accept-conditional'))
            self.assertEqual(won,[decision['control']['action']])

    def test_changed_artifact_and_dead_owner_cannot_be_approved(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);path=root/'basis.json';write(path,artifact(dependency(category=4)))
            gate=fault_control.Gate(root,stage='basis-decision',notify=Mock(return_value={'status':'QUEUED'}))
            def choose(_):
                incident=gate.state['incident']
                with patch.object(fault_control.execution,'same_process',return_value=False),self.assertRaises(ValueError):
                    fault_control.final_decision(gate.root,incident,'accept-conditional')
                path.write_text('{}')
                with self.assertRaises(ValueError):fault_control.final_decision(gate.root,incident,'accept-conditional')
                write(gate.root/'cancel-request.json',{'external_cancel':True})
            gate.wait=choose
            with self.assertRaises(fault_control.execution.Cancelled):
                gate.pause({'status':'BASIS_USER_DECISION_REQUIRED'},resumable=False,
                    checkpoint={'basis':bind(path),'residual_class4':['B001']},decisions=('stop','continue','accept-conditional'))


class BasisNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.value=artifact(dependency(),dependency('B002',1,compatibility='adapted'),dependency('B003',2),dependency('B004',3))
        cls.context=checked_context(cls.root/'basis',cls.value)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_real_prepared_basis_types_proofs_and_trust(self):
        self.assertEqual(basis.verify_context(self.context),self.value)
        check=basis_native.verify(self.context['native']['path'])
        self.assertEqual({row[0] for row in check['checks']},{'B001','B002','B003'})

    def test_bad_proof_and_unresolved_type_return_native_nonpass(self):
        for name,source in [('bad','import Mathlib\ntheorem Bad : False := by trivial\n'),
                ('hole','import Mathlib\ndef Bad : Prop := _\n')]:
            result=basis_native.check(source,[],[],self.root/name)
            self.assertFalse(result['passed']);self.assertIn('LEAN_COMPILE_FAILED',result['errors'])

    def test_transitive_hidden_axiom_and_sorry_are_rejected(self):
        for name,source in [('axiom','import Mathlib\naxiom hidden : False\ntheorem Bad : True := hidden.elim\n'),
                ('sorry','import Mathlib\ntheorem Bad : True := by sorry\n')]:
            result=basis_native.check(source,[('bad','Bad','True')],['Bad'],self.root/name)
            self.assertFalse(result['passed']);self.assertTrue(any('UNPERMITTED_AXIOM' in e for e in result['errors']))

    def test_actual_signature_and_extra_premises_are_checked(self):
        result=basis_native.check('import Mathlib\ntheorem Bad (h : False) : True := h.elim\n',
            [('bad','Bad','True')],['Bad'],self.root/'extra-premise')
        self.assertIn('ACTUAL_SIGNATURE_MISMATCH',result['errors'])

    def test_universe_and_instance_closed_basis_proofs(self):
        row=dependency(typ='∀ {α : Type u} [Monoid α] (a : α), a * 1 = a',proof='intro α inst a; exact mul_one a')
        value=artifact(row);value['lean_header']+='universe u\n'
        context=checked_context(self.root/'universe',value)
        basis.verify_context(context)

    def test_changed_native_evidence_pins_and_unapproved_residuals_fail(self):
        changed=deepcopy(self.context);changed['full_target']='True'
        with self.assertRaises(ValueError):basis.verify_context(changed)
        with patch.object(basis_native.audit_b,'environment',return_value={}),self.assertRaises(ValueError):basis.verify_context(self.context)
        changed=deepcopy(self.context);changed['residual_class4']=['B999']
        with self.assertRaises(ValueError):basis.verify_context(changed)

    def test_class4_only_requires_actual_type_but_exact_user_approval(self):
        value=artifact(dependency(category=4));context=checked_context(self.root/'residual',value,approved=True)
        basis.verify_context(context)
        for change in ({'approval':None},{'residual_class4':[] }):
            candidate=deepcopy(context);candidate.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):basis.verify_context(candidate)

    def test_interface_cannot_change_prepared_types_ports_or_definitions(self):
        contract={'header':'import Mathlib\n','premises':[
            {'id':r['port'],'kind':'external','type':r['lean']['type'],'statement':r['statement']}
            for r in self.value['dependencies'] if r['port']]}
        basis.check_interface(self.context,contract)
        for candidate in [dict(contract,header='import Mathlib\n-- different\n'),dict(contract,premises=[])]:
            if candidate['header']==contract['header']:expected_failure=True
            else:expected_failure=False  # Extending header is allowed; original prefix remains.
            if expected_failure:
                with self.assertRaises(ValueError):basis.check_interface(self.context,candidate)
            else:basis.check_interface(self.context,candidate)
        changed=deepcopy(contract);changed['premises'][0]['type']='True'
        with self.assertRaises(ValueError):basis.check_interface(self.context,changed)

    def test_saved_candidate_repair_rechecks_actual_proof(self):
        out=self.root/'author';inputs=out/'inputs';inputs.mkdir(parents=True)
        (inputs/'problem.md').write_text(TARGET);manifest(inputs)
        validator=basis.BasisContract(out,TARGET)
        bad=artifact(dependency(proof='exact nonexistent'))
        with self.assertRaises(ValueError):validator(bad)
        self.assertTrue((out/'candidates/0001/basis.json').exists());self.assertIsNone(validator.selected)
        result=validator({'base_candidate':1,'patches':[{'op':'replace','path':'/dependencies/0/lean/proof',
            'value':'intro n; exact Nat.add_zero n'}]})
        self.assertFalse(result['mathematical_acceptance']);self.assertEqual(result['candidate'],2)


if __name__=='__main__':unittest.main()
