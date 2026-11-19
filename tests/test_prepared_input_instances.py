"""A checked foundation used at fresh universes, with real Lean at both sides."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import harness_support
import assembly
import basis
import basis_native
import b2lean
import ir
from basis_fixtures import artifact, dependency, checked_context, active_artifact


class PreparedInstances(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scratch = tempfile.TemporaryDirectory()
        cls.addClassCleanup(scratch.cleanup)
        cls.root = Path(scratch.name)
        cls.typ = '∀ (A B : Type*) (x : A) (y : B), x = x ∧ y = y'
        cls.row = dependency(category=2, typ=cls.typ, proof='intro A B x y; exact ⟨rfl, rfl⟩')
        cls.row['statement'] = 'Each of two elements, of possibly different types, equals itself.'
        cls.registry = artifact(cls.row)
        cls.context = checked_context(cls.root/'basis', cls.registry)

    def setUp(self):
        self.work = self.root / self._testMethodName
        self.work.mkdir()
        self.path = self.work/'contract.json'
        source = self.work/'source.json'
        ir.write(source, {'text':'Apply the two reflexivity statements at their actual types.'})
        self.c = {'id':'genericPort','version':2,'source':{'path':source.name,'sha256':ir.digest(source)},
            'source_steps':[{'id':'S001','text':'Apply pair reflexivity.'}],
            'pins':{'lean_version':ir.load_lock()['lean']['version_number'],'mathlib_commit':ir.load_lock()['mathlib']['rev']},
            'header':'import Mathlib\n','parameters':[],
            'premises':[{'id':'E001','kind':'external','type':self.typ,'statement':self.row['statement']}],
            'conclusion':{'type':'(0 : Nat) = 0','statement':'Zero equals zero.'},
            'review':{'mode':'development_owner_review'},'representation':'Equality of elements.'}
        self.generic = {'id':'T001','inputs':['E001'],'source_steps':['S001'],'universe_params':['v'],
            'statement':'∀ (A : Type v) (x : A), x = x','explanation':'Use pair reflexivity with a small type.',
            'input_instances':{'E001':[{'levels':['v','0'],'uses':[{'parameters':[
                {'name':'A','type':'Type v'},{'name':'x','type':'A'}],
                'args':['A','Nat','x','0'],'expected':'x = x ∧ (0 : Nat) = 0'}]},
                {'levels':['0','v'],'uses':[{'parameters':[{'name':'A','type':'Type v'},
                    {'name':'x','type':'A'}],'args':['Nat','A','0','x']}]}]}}
        self.terminal = {'id':'T002','inputs':['T001'],'source_steps':['S001'],
            'statement':self.c['conclusion']['type'],'explanation':'Use the generic node at Nat.',
            'input_instances':{'T001':[{'levels':['0'],'uses':[{'args':['Nat','0']}]}]}}
        self.v = {'version':2,'representation_notes':self.c['representation'],
                  'steps':[self.generic,self.terminal],'terminal':'T002'}

    def bind(self):
        selected = {key for step in self.v['steps'] for key in step.get('input_instances',{})}
        basis.check_interface(self.context,self.c,step_instances=selected)
        ir.write(self.path,self.c)
        self.v['contract_sha256'] = ir.digest(self.path)

    def test_native_use_private_helpers_connection_and_actual_closed_signature(self):
        self.bind()
        basis.check_interface(self.context,self.c)
        self.assertEqual(self.c['prepared_instances']['included'],['B001'])
        r = ir.check(self.path,self.v,types_only=True)
        self.assertEqual(r['exit_code'],0,ir.compiler_feedback(r))
        packet = ir.local_packet(self.path,self.v,'T001')
        self.assertEqual([p['binder'] for p in packet['inputs']],['h_E001','h_E001_2'])
        self.assertNotIn('theorem B001',packet['header'])
        helper = 'intro A x; exact (h_E001_2 Nat A 0 x).2'
        r = ir.check_auxiliary(self.path,self.v,'T001',self.generic['statement'],helper,out=self.work/'aux')
        self.assertEqual(r['exit_code'],0,ir.compiler_feedback(r))
        proofs = {'T001':'intro A x; exact (h_E001 A Nat x 0).1','T002':'exact h_T001 Nat 0'}
        r = ir.check(self.path,self.v,proofs,only='T001')
        self.assertEqual(r['exit_code'],0,ir.compiler_feedback(r))
        formal = ir.render(self.path,self.v,proofs)
        self.assertEqual(formal.count('theorem B001 :'),1)
        self.assertNotIn('__yui_preflight',formal)
        stage = self.work/'audit-b'
        stage.mkdir()
        sandbox = self.work/'native'
        for sub in ('input','output'):(sandbox/sub).mkdir(parents=True)
        report = assembly.build(self.c,{'library_terms':{}},formal,stage,sandbox)
        self.assertEqual(report['status'],'ASSEMBLY-PASSED',report)
        closed, expected, retained = b2lean.render(self.c,self.context,(stage/'Proof.lean').read_text(),
                                                   report['universe_parameters'])
        self.assertEqual(retained,[])
        self.assertEqual(closed.count('theorem B001 :'),1)
        native = basis_native.check(closed,[('target','YuiClosed.P',expected)],['YuiClosed.P'],self.work/'closed')
        self.assertTrue(native['passed'],native['errors'])
        inspected=ir.load(self.work/'closed/elaborated.json')['dependencies']['declarations']
        final=next(d for d in inspected if d['name']=='YuiClosed.P')
        self.assertEqual(final['levels'],[])
        self.assertTrue(any(d['name']=='YuiBasis.B001' for d in inspected))

    def test_swapped_levels_fail_at_the_named_use_before_dispatch(self):
        self.generic['input_instances']['E001'][0]['levels']=['0','v']
        self.bind()
        r=ir.check(self.path,self.v,types_only=True)
        self.assertNotEqual(r['exit_code'],0)
        self.assertIn('T001 <- E001 (h_E001, use 1)',r['failed_input_uses'])

    def test_forged_or_unavailable_authority_cannot_specialize_a_premise(self):
        self.bind()
        with self.assertRaisesRegex(ValueError,'2basis'):
            basis.check_interface(None,self.c)
        for field in ('source','included','ports'):
            c=deepcopy(self.c)
            if field=='ports': c['prepared_instances'][field]['E001']['basis']='B999'
            elif field=='included': c['prepared_instances'][field]=[]
            else: c['prepared_instances'][field]+='\n-- replaced\n'
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'differ'):
                basis.check_interface(self.context,c)
        c=deepcopy(self.c)
        del c['prepared_instances']
        ir.write(self.path,c)
        self.v['contract_sha256']=ir.digest(self.path)
        with self.assertRaisesRegex(ValueError,'T001 <- E001'):
            ir.validate(self.path,self.v)

    def test_ordinary_inputs_keep_their_original_contract(self):
        del self.generic['input_instances']
        self.bind()
        self.assertNotIn('prepared_instances',self.c)
        packet=ir.local_packet(self.path,self.v,'T001')
        self.assertEqual(packet['inputs'],[{'id':'E001','binder':'h_E001','type':self.typ}])
        self.assertNotIn('YuiBasis',packet['header'])

    def test_fixed_foundation_use_can_be_repaired_without_changing_the_premise(self):
        typ = '∀ (A : Type) (x : A), x = x'
        row = dependency('B005', category=2, typ=typ, proof='intro A x; rfl')
        row['statement'] = 'Every element of a fixed-level type equals itself.'
        self.context = checked_context(self.work/'fixed-basis', artifact(row))
        self.c['header'] += 'abbrev IndexOf (n : Nat) := Fin (n + 1)\n'
        self.c['parameters'] = [{'name':'n','type':'Nat'},{'name':'i','type':'IndexOf n'}]
        self.c['premises'][0].update(id='E005', type=typ, statement=row['statement'])
        self.c['conclusion']['type'] = 'i = i'
        self.c['conclusion']['statement'] = 'The chosen index equals itself.'
        self.generic.pop('universe_params')
        use = {'args':['IndexOf n','true'],'expected':'i = i'}
        instance = {'levels':[],'uses':[use]}
        self.generic.update(statement='i = i', inputs=['E005'],
            input_instances={'E005':[instance]})
        self.terminal.update(statement='i = i',
            input_instances={'T001':[{'levels':[],'uses':[{'args':[],'expected':'i = i'}]}]})
        self.bind()
        self.assertNotIn('prepared_instances',self.c)
        before = self.path.read_bytes()
        instance['levels'] = ['0']
        with self.assertRaisesRegex(ir.Invalid,r'T001 <- E005: explicit levels'):
            ir.validate(self.path,self.v)
        instance['levels'] = []
        rejected = ir.check(self.path,self.v,types_only=True)
        self.assertNotEqual(rejected['exit_code'],0)
        self.assertIn('T001 <- E005 (h_E005, use 1)',rejected['failed_input_uses'])

        use['args'][-1] = 'i'
        accepted = ir.check(self.path,self.v,types_only=True)
        self.assertEqual(accepted['exit_code'],0,ir.compiler_feedback(accepted))
        self.assertEqual(self.path.read_bytes(),before)
        packet = ir.local_packet(self.path,self.v,'T001')
        self.assertEqual(packet['inputs'],[{'id':'E005','binder':'h_E005','type':typ,'uses':[use]}])
        proofs = {'T001':'exact h_E005 (IndexOf n) i','T002':'exact h_T001'}
        assembled = ir.check(self.path,self.v,proofs)
        self.assertEqual(assembled['exit_code'],0,ir.compiler_feedback(assembled))
        formal = ir.render(self.path,self.v,proofs)
        endpoint = next(line for line in formal.splitlines() if line.startswith('theorem P '))
        self.assertIn(f'(h_E005 : {typ})',endpoint)
        self.assertNotIn('YuiBasis',formal)

    def test_checked_mathlib_port_can_be_specialized_and_normally_discharged(self):
        product='Set.image Prod.swap (Set.prod s t) = Set.prod t s'
        typ='∀ (A B : Type*) (s : Set A) (t : Set B), '+product
        row=dependency(compatibility='native',port='M017',typ=typ,proof='exact @Set.image_swap_prod')
        row['origin']['declaration']='Set.image_swap_prod'
        row['statement']='Swapping the factors of a product set interchanges the two sets.'
        registry=artifact(row)
        registry['global_graph']['propositions'].append({'id':'M017','statement':row['statement']})
        registry['global_graph']['inferences'][-1]['inputs'].append('M017')
        registry['global_graph']['inferences'][-1]['basis'].append('B001')
        self.context=checked_context(self.work/'basis',registry)
        self.c['premises'][0].update(id='M017',kind='mathlib',type=typ,statement=row['statement'])
        at_nat='Set.image Prod.swap (Set.prod s (Set.univ : Set Nat)) = Set.prod (Set.univ : Set Nat) s'
        self.generic['statement']='∀ (A : Type v) (s : Set A), '+at_nat
        self.generic['inputs']=['M017']
        self.generic['input_instances']={'M017':[{'levels':['v','0'],'uses':[{
            'parameters':[{'name':'A','type':'Type v'},{'name':'s','type':'Set A'}],
            'args':['A','Nat','s','(Set.univ : Set Nat)'],'expected':at_nat}]}]}
        self.terminal['inputs'].append('M017')
        self.terminal['statement']=self.c['conclusion']['type']='∀ (s : Set Nat), '+at_nat
        self.c['conclusion']['statement']='Swap a product with the universal set of natural numbers.'
        self.terminal['input_instances']['T001'][0]['uses']=[{
            'parameters':[{'name':'s','type':'Set Nat'}],'args':['Nat','s'],'expected':at_nat}]
        self.bind()
        self.assertEqual(self.c['prepared_instances']['ports']['M017']['basis'],'B001')
        proofs={'T001':'intro A s; exact h_M017 A Nat s Set.univ','T002':'exact h_T001 Nat'}
        formal=ir.render(self.path,self.v,proofs)
        stage=self.work/'audit-b'
        stage.mkdir()
        sandbox=self.work/'native'
        for sub in ('input','output'):(sandbox/sub).mkdir(parents=True)
        report=assembly.build(self.c,{'library_terms':{'M017':row['lean']['proof']}},formal,stage,sandbox)
        self.assertEqual(report['status'],'ASSEMBLY-PASSED',report)
        closed,expected,retained=b2lean.render(self.c,self.context,(stage/'Proof.lean').read_text(),
                                               report['universe_parameters'])
        self.assertEqual(retained,[])
        result=basis_native.check(closed,[('target','YuiClosed.P',expected)],['YuiClosed.P'],self.work/'closed')
        self.assertTrue(result['passed'],result['errors'])

    def test_native_inventory_distinguishes_derived_proof_residual_and_unused_fact(self):
        root = dependency(compatibility='adapted',typ=self.typ,proof=self.row['lean']['proof'])
        derived = dependency('B002',3)
        residual = dependency('B003',4,typ=self.typ)
        other = dependency('B004',2,typ=self.typ,proof=self.row['lean']['proof'])
        registry = active_artifact(artifact(root,derived,residual,other))
        registry['dependencies'][1]['lean'] = {'type':self.typ,'proof':'exact YuiBasis.B001'}
        body,checks,roots=basis.declarations(registry)
        out=self.work/'proofs'
        self.assertTrue(basis_native.check(registry['lean_header']+body,checks,roots,out)['passed'])
        native=ir.load(out/'elaborated.json')
        ports=basis.basis_graph.handoff().by_port(registry)
        self.assertEqual(set(basis.universe_ports(ports,native)),{'E001','E002','E004'})
        support=basis.instance_evidence(registry,ports,native,{'E002'})
        self.assertEqual(support['included'],['B001','B002'])
        self.assertEqual(set(support['ports']),{'E002'})
        self.assertNotIn('B003',support['source'])
        self.assertNotIn('B004',support['source'])
        self.assertIsNone(basis.instance_evidence(registry,ports,native,{'E003'}))
