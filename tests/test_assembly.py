"""Native assembly controls only; no model call or exercise result."""
import harness_support
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

HERE = harness_support.LEAN
import assembly
import audit_b
import ir
import lean_names
import lean_timeout_policy
import pilot_common
from audit_b_fixtures import fixture


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix='yui-assembly-control-'))

    def tearDown(self):
        shutil.rmtree(self.base)

    def test_real_local_and_whole_file_calls_start_with_their_separate_limits(self):
        cp,pp,bp,ip=fixture(self.base/'case','mathlib')
        out=self.base/'audit';audit_b.prepare(cp,pp,bp,out,fragment=ip)
        mapping=ir.load(out/'mapping.json');mapping['library_terms']['M001']='exact Nat.add_comm a b'
        ir.write(out/'mapping.json',mapping)
        actual=pilot_common._run_lean;calls=[]
        def controlled(file,work,**kwargs):
            native=actual(file,work,**kwargs)
            calls.append((Path(file).name,native['native_limits']['timeout_seconds']))
            return native
        with patch.object(pilot_common,'_run_lean',side_effect=controlled):
            result=audit_b.build(out)
        self.assertEqual(result['status'],'AUDIT-B-MECHANICAL-PASSED')
        self.assertIn(('Check.lean',360),calls)
        for name in ('AssemblyInputs.lean','Proof.lean','Audit.lean'):
            self.assertIn((name,1800),calls)

    def test_valid_partial_inspector_output_cannot_pass_after_timeout(self):
        cp,pp,bp,ip=fixture(self.base/'case','mathlib')
        def prepare(name):
            out=self.base/name;audit_b.prepare(cp,pp,bp,out,fragment=ip)
            mapping=ir.load(out/'mapping.json');mapping['library_terms']['M001']='exact Nat.add_comm a b'
            ir.write(out/'mapping.json',mapping)
            return out
        good=prepare('good');audit_b.build(good)
        partial=ir.load(good/'compiler.json')
        out=prepare('timed-out');actual=pilot_common._run_lean
        def controlled(file,work,**kwargs):
            if Path(file).name=='Audit.lean':
                return {**partial,'exit_code':124,'timed_out':True,'error_kind':'LEAN_TIMEOUT','timeout_scope':'native_call'}
            return actual(file,work,**kwargs)
        def located(directory,source,native,budget,remaining,**kwargs):
            line,quote=next((i,s) for i,s in enumerate(source.splitlines(),1) if s.strip())
            return {'category':'code_issue','line':line,'quote':quote,
                    'reason':'Synthetic located timeout in the retained source.',
                    'next_action':'Return to the connection author at the same allowance.'}
        with patch.object(pilot_common,'_run_lean',side_effect=controlled), \
                patch.object(lean_timeout_policy,'inspect_source',side_effect=located):
            result=audit_b.build(out)
        self.assertEqual(result['assembly'],'ASSEMBLY-PASSED')
        self.assertEqual(result['inspection'],'KERNEL_INSPECTION_FAILED')
        self.assertEqual(result['status'],'AUDIT-B-MECHANICAL-FAILED')
        self.assertFalse(ir.load(out/'mechanical.json')['passed'])
        self.assertTrue(ir.load(out/'compiler.json')['timed_out'])
        self.assertEqual(ir.load(out/'compiler.json')['timeout_reviews'][-1]['next_seconds'],1800)
        import final_acceptance
        with self.assertRaisesRegex(ValueError,'Proof integrity failed'):
            final_acceptance.proof_integrity(out)

    def test_unfinished_assembly_cannot_pass_using_early_universe_output(self):
        cp,pp,bp,_=fixture(self.base/'case')
        c=ir.load(cp);mapping={'library_terms':{}}
        for code in (0,124):
            out=self.base/str(code);out.mkdir()
            work=out/'native';(work/'output').mkdir(parents=True)
            native={'exit_code':code,'stdout':'YUI_ASSEMBLY_LEVELS_JSON:{"parameters":[],"export_used_parameters":[]}\n',
                    'stderr':'','timed_out':True,'wall_seconds':0}
            with patch.object(ir,'run_lean',return_value=native) as run:
                result=assembly.build(c,mapping,'-- synthetic incomplete source\n',out,work)
            self.assertEqual(run.call_count,1)
            self.assertEqual(result['status'],'ASSEMBLY-FAILED')
            self.assertFalse((out/'Proof.lean').exists())

    def run_assembly(self, *, generic=False, invalid_library=False):
        cp, pp, bp, _ = fixture(self.base / 'case')
        c, plan, bundle = [ir.load(p) for p in (cp, pp, bp)]
        c['parameters'] = [{'name': 'A', 'type': 'Type*'}, {'name': 'x', 'type': 'A'}] if generic else []
        c['premises'] = [{'id': 'M001', 'kind': 'mathlib',
                          'type': '∀ {β : Type*} (xs ys : List β), (xs ++ ys).length = xs.length + ys.length',
                          'statement': 'List concatenation length, general signature.'}]
        c['conclusion']['type'] = 'x = x' if generic else 'True'
        plan['steps'][0].update(inputs=['M001'], statement=c['conclusion']['type'])
        bundle['proofs'] = {'T001': 'rfl' if generic else 'exact True.intro'}
        ir.write(cp, c)
        plan['contract_sha256'] = ir.digest(cp)
        ir.write(pp, plan)
        mapping = {'library_terms': {'M001': 'exact DoesNotExist' if invalid_library else 'exact @List.length_append'}}
        out, work = self.base / 'audit', self.base / 'native'
        out.mkdir(); (work / 'input').mkdir(parents=True); (work / 'output').mkdir()
        report = assembly.build(c, mapping, ir.render(cp, plan, bundle['proofs']), out, work)
        return out, report

    def test_private_polymorphic_library_levels_are_closed(self):
        out, report = self.run_assembly()
        self.assertEqual(report['status'], 'ASSEMBLY-PASSED', ir.load(out / 'assembly-compiler.json'))
        self.assertTrue(report['universe_parameters']['parameters'])
        self.assertFalse(report['universe_parameters']['export_used_parameters'])
        self.assertIn('Translation.P.{0}', (out / 'Proof.lean').read_text())
        self.assertNotIn('(h_M001', (out / 'Proof.lean').read_text().split('namespace AuditBExport')[1].split('theorem P ')[1])

    def test_retained_generic_parameter_is_not_specialized_to_zero(self):
        out, report = self.run_assembly(generic=True)
        self.assertEqual(report['status'], 'ASSEMBLY-PASSED', ir.load(out / 'assembly-compiler.json'))
        self.assertTrue(report['universe_parameters']['export_used_parameters'])
        source = (out / 'Proof.lean').read_text()
        self.assertIn('theorem P (A : Type*) (x : A)', source)
        self.assertIn('Translation.P.{_', source)

    def test_failed_library_discharge_cannot_reach_standalone_pass(self):
        out, report = self.run_assembly(invalid_library=True)
        self.assertEqual(report['status'], 'ASSEMBLY-FAILED')
        self.assertEqual(report['standalone_proof'], 'NOT_STARTED')
        self.assertFalse((out / 'Proof.lean').exists())
        self.assertIn('DoesNotExist', ir.load(out / 'assembly-compiler.json')['stdout'])

    def test_unicode_and_quoted_names_are_data_not_commands(self):
        self.assertEqual(lean_names.parts('MeasureTheory.lintegral_indicator_const₀'),
                         ['MeasureTheory', 'lintegral_indicator_const₀'])
        self.assertEqual(lean_names.parts('A.«a.b»'), ['A', 'a.b'])
        self.assertEqual(lean_names.parts("A.lemma'"), ['A', "lemma'"])
        self.assertEqual(lean_names.canonical('Nat.«add_comm»'),'Nat.add_comm')
        for bad in ['', 'A..b', 'A.b\n#eval 1', 'A.b; axiom bad : False', 'A.«unfinished']:
            with self.subTest(name=bad):
                self.assertFalse(lean_names.valid(bad))

    def test_discharge_cannot_contain_commands_or_placeholders(self):
        cp, pp, bp, ip = fixture(self.base / 'case', 'mathlib')
        c, inventory = ir.contract(cp), ir.load(ip)
        out = self.base / 'audit'
        audit_b.prepare(cp, pp, bp, out, fragment=ip)
        mapping = ir.load(out / 'mapping.json')
        mapping['library_terms']['M001'] = 'sorry'
        with self.assertRaisesRegex(ir.Invalid, 'forbidden proof'):
            audit_b.validate_mapping(c, inventory, mapping)

    def test_assembly_helpers_are_bound_by_the_audit_manifest(self):
        cp,pp,bp,ip=fixture(self.base/'case','mathlib')
        out=self.base/'audit';audit_b.prepare(cp,pp,bp,out,fragment=ip)
        tools=ir.load(out/'manifest.json')['tool_sha256']
        import dependency_instances
        for module in (assembly,lean_names,dependency_instances):
            path=Path(module.__file__).resolve()
            self.assertEqual(tools[str(path)],ir.digest(path))

    def test_unicode_mathlib_declaration_reaches_actual_kernel_inspection(self):
        cp, pp, bp, ip = fixture(self.base / 'case', 'mathlib')
        c, plan, bundle, inventory = [ir.load(p) for p in (cp, pp, bp, ip)]
        c['header'] += 'open MeasureTheory\nopen scoped ENNReal\n'
        c['parameters'] = [{'name':'mu','type':'Measure ℝ'}, {'name':'s','type':'Set ℝ'},
                           {'name':'c','type':'ℝ≥0∞'}]
        target = '(∫⁻ x, s.indicator (fun _ => c) x ∂mu) = c * mu s'
        c['premises'] = [{'id':'H001','kind':'hypothesis','type':'NullMeasurableSet s mu','statement':'s is null-measurable.'},
                         {'id':'M001','kind':'mathlib','type':target,'statement':'Integral of this constant indicator.'}]
        c['conclusion']['type'] = target
        ir.write(cp,c)
        plan['steps'][0].update(statement=target,inputs=['H001','M001'])
        plan['contract_sha256'] = ir.digest(cp);ir.write(pp,plan)
        bundle.update(contract_sha256=ir.digest(cp),plan_sha256=ir.digest(pp),proofs={'T001':'exact h_M001'})
        ir.write(bp,bundle)
        declaration = 'MeasureTheory.lintegral_indicator_const₀'
        inventory['parameters'] = c['parameters']
        inventory['propositions'] = [{'id':'H001','kind':'hypothesis','statement':'s is null-measurable.'},
            {'id':'M001','kind':'mathlib','statement':'Integral of a constant indicator.','source':{'declaration':declaration}},
            {'id':'P','kind':'target','statement':'The stated indicator integral equality.'}]
        inventory['inferences'][0]['inputs']=['H001','M001'];ir.write(ip,inventory)
        out=self.base/'audit';audit_b.prepare(cp,pp,bp,out,fragment=ip)
        mapping=ir.load(out/'mapping.json');mapping['library_terms']['M001']='exact MeasureTheory.lintegral_indicator_const₀ h_H001 c'
        ir.write(out/'mapping.json',mapping)
        result=audit_b.build(out)
        self.assertEqual(result['status'],'AUDIT-B-MECHANICAL-PASSED',
                         (result,ir.load(out/'compiler.json')['stdout'][-3000:]))
        self.assertEqual(ir.load(out/'assembly.json')['standalone_proof'],'KERNEL_CHECKED')
        self.assertTrue(all(x['definitionally_equal'] for x in ir.load(out/'elaborated.json')['comparisons']))

    def test_quoted_library_name_resolves_to_the_same_pinned_declaration(self):
        cp,pp,bp,ip=fixture(self.base/'case','mathlib')
        out=self.base/'audit';audit_b.prepare(cp,pp,bp,out,fragment=ip)
        mapping=ir.load(out/'mapping.json');mapping['library_terms']['M001']='exact Nat.«add_comm» a b'
        ir.write(out/'mapping.json',mapping)
        result=audit_b.build(out)
        self.assertEqual(result['status'],'AUDIT-B-MECHANICAL-PASSED',result)

    def test_inspector_budget_failure_does_not_relabel_checked_assembly(self):
        cp,pp,bp,ip=fixture(self.base/'case','mathlib')
        out=self.base/'audit';audit_b.prepare(cp,pp,bp,out,fragment=ip)
        mapping=ir.load(out/'mapping.json');mapping['library_terms']['M001']='exact Nat.add_comm a b'
        ir.write(out/'mapping.json',mapping)
        actual=ir.run_lean
        def controlled(file,work,**kwargs):
            if Path(file).name=='Audit.lean':
                return {'exit_code':1,'stdout':str(file)+':1:0: error: maximum number of heartbeats (2000000) has been reached',
                        'stderr':'','wall_seconds':0,'synthetic_control':True}
            return actual(file,work,**kwargs)
        with patch.object(ir,'run_lean',side_effect=controlled):result=audit_b.build(out)
        self.assertEqual(result['assembly'],'ASSEMBLY-PASSED')
        self.assertEqual(result['inspection'],'INSPECTION_HEARTBEAT_EXHAUSTED')
        self.assertEqual(result['status'],'AUDIT-B-MECHANICAL-FAILED')
        self.assertEqual(ir.load(out/'assembly-compiler.json')['exit_code'],0)
        self.assertFalse(ir.load(out/'mechanical.json')['passed'])


if __name__ == '__main__':
    unittest.main()
