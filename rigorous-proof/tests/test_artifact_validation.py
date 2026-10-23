"""Security and binding controls for structural NL0 authoring; not mathematical certification."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import os

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from artifact_validation import NL0Contract, signature_probe, expand_submission


class ArtifactValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_explicit_local_edits_preserve_unselected_proof_and_do_not_mutate_base(self):
        fixture=Path(__file__).parent/'fixtures/closed-addition'
        base={'spec':json.loads((fixture/'spec.json').read_text()),
              'graph':json.loads((fixture/'nl0.json').read_text())}
        text=json.dumps(base)
        edits={'base_input':'base.json','patches':[
            {'op':'test','path':'/spec/case_id','value':base['spec']['case_id']},
            {'op':'replace','path':'/spec/full_target','value':base['spec']['full_target']+' Explicit local revision.'}]}
        contract=NL0Contract(self.root/'edited',{'base.json':text},case_id=base['spec']['case_id'])
        self.assertFalse(contract(edits)['mathematical_acceptance'])
        self.assertEqual(set(edits),{'spec','graph'})
        self.assertEqual(edits['graph']['inferences'],base['graph']['inferences'])
        self.assertEqual(json.loads(text),base)
        self.assertTrue((contract.directory/'submission-edits-0001.json').exists())

    def test_edit_preconditions_and_paths_cannot_silently_replace_other_content(self):
        docs={'base.json':json.dumps({'spec':{'a/b':[1,2]},'graph':{}})}
        for edit in [
            {'op':'test','path':'/spec/a~1b/0','value':9},
            {'op':'remove','path':'/spec/a~1b/2'},
            {'op':'replace','path':'/spec/missing','value':1},
            {'op':'remove','path':'/spec/a~1b/-1'},
            {'op':'replace','path':'/spec/a~2b','value':1},
            {'op':'replace','path':'/graph','value':{}},
            {'op':'replace','path':'/other/x','value':1}]:
            with self.assertRaises(ValueError):
                expand_submission({'base_input':'base.json','patches':[edit]},docs)
        result,_=expand_submission({'base_input':'base.json','patches':[
            {'op':'add','path':'/spec/a~1b/-','value':3},
            {'op':'remove','path':'/spec/a~1b/0'}]},docs)
        self.assertEqual(result['spec']['a/b'],[2,3])

    def test_local_edits_cannot_skip_the_full_producer_gate_or_read_undeclared_files(self):
        fixture=Path(__file__).parent/'fixtures/closed-addition'
        base={'spec':json.loads((fixture/'spec.json').read_text()),
              'graph':json.loads((fixture/'nl0.json').read_text())}
        contract=NL0Contract(self.root/'invalid-edit',{'base.json':json.dumps(base)},
                             case_id=base['spec']['case_id'])
        with self.assertRaises(ValueError):
            contract({'base_input':'base.json','patches':[
                {'op':'replace','path':'/graph/inferences','value':[]}]})
        with self.assertRaises(ValueError):
            expand_submission({'base_input':'/etc/passwd','patches':[{'op':'remove','path':'/spec/a'}]}, {})
        with self.assertRaisesRegex(ValueError,'Duplicate JSON key'):
            expand_submission({'base_input':'duplicate','patches':[{'op':'remove','path':'/spec/a'}]},
                              {'duplicate':'{"spec":{},"spec":{},"graph":{}}'})

    def test_same_stage_draft_edits_resume_rejected_structure_without_cross_stage_access(self):
        fixture=Path(__file__).parent/'fixtures/closed-addition'
        base={'spec':json.loads((fixture/'spec.json').read_text()),
              'graph':json.loads((fixture/'nl0.json').read_text())}
        contract=NL0Contract(self.root/'draft',{'problem.txt':'Neutral fixture.'},case_id=base['spec']['case_id'])
        original=base['graph']['inferences']
        base['graph']['inferences']=[]
        with self.assertRaises(ValueError):contract(base)
        repaired={'base_candidate':1,'patches':[{'op':'replace','path':'/graph/inferences','value':original}]}
        self.assertFalse(contract(repaired)['mathematical_acceptance'])
        self.assertEqual(repaired['graph']['inferences'],original)
        other=NL0Contract(self.root/'other-stage',{'problem.txt':'Separate fixture.'},case_id=base['spec']['case_id'])
        with self.assertRaisesRegex(ValueError,'same stage'):
            other({'base_candidate':1,'patches':[{'op':'replace','path':'/graph/inferences','value':original}]})

    def test_later_bookkeeping_edit_cannot_silently_discard_a_previous_proof_edit(self):
        original={'spec':{'conclusion':'old'},'graph':{'proof':'old proof','objects':[]}}
        revised={'spec':{'conclusion':'old'},'graph':{'proof':'completed mathematical proof','objects':[]}}
        docs={'base.json':json.dumps(original)};drafts={1:json.dumps(revised)}
        changes=[{'op':'replace','path':'/graph/objects','value':['x']}]
        with self.assertRaisesRegex(ValueError,'preserve your accumulated proof edits'):
            expand_submission({'base_input':'base.json','patches':changes},docs,drafts)
        final,_=expand_submission({'base_candidate':1,'patches':changes},docs,drafts)
        self.assertEqual(final['graph']['proof'],'completed mathematical proof')
        exact,_=expand_submission({'accept_candidate':1},docs,drafts)
        self.assertEqual(exact,revised)
        reset,receipt=expand_submission({'base_input':'base.json','patches':changes,'reset_base':True},docs,drafts)
        self.assertEqual(reset['graph']['proof'],'old proof');self.assertTrue(receipt['reset_base'])

    def test_only_metadata_and_omitted_aliases_are_bound_and_missing_proof_is_rejected(self):
        fixture=Path(__file__).parent/'fixtures/closed-addition'
        value={'spec':json.loads((fixture/'spec.json').read_text()),
               'graph':json.loads((fixture/'nl0.json').read_text())}
        original=value['graph']['inferences'][0]['argument'][0]['text']
        value['graph']['propositions'][0].pop('statement')
        value['graph']['propositions'][-1].pop('statement')
        contract=NL0Contract(self.root/'case',{'problem.txt':'Explicit target input.'},
                             case_id=value['spec']['case_id'])
        checked=contract(value)
        self.assertFalse(checked['mathematical_acceptance'])
        self.assertEqual(value['graph']['inferences'][0]['argument'][0]['text'],original)
        self.assertEqual(value['spec']['inputs'][0]['path'],'inputs/problem.txt')
        self.assertEqual(value['graph']['propositions'][0]['statement'],value['spec']['hypotheses'][0]['statement'])
        self.assertEqual(value['graph']['propositions'][-1]['statement'],value['spec']['conclusion'])
        value['graph']['inferences']=[]
        with self.assertRaises(ValueError):contract(value)

    def test_known_case_identity_is_filled_but_explicit_conflicts_are_preserved(self):
        fixture=Path(__file__).parent/'fixtures/closed-addition'
        value={'spec':json.loads((fixture/'spec.json').read_text()),'graph':json.loads((fixture/'nl0.json').read_text())}
        expected=value['spec'].pop('case_id');value['graph'].pop('case_id')
        contract=NL0Contract(self.root/'ids',{'problem.txt':'Synthetic fixture only.'},case_id=expected)
        self.assertFalse(contract(value)['mathematical_acceptance'])
        self.assertEqual(value['graph']['case_id'],expected)
        value['graph']['case_id']='conflicting-case'
        with self.assertRaisesRegex(ValueError,'graph.case_id'):contract(value)
        self.assertIn(2,contract.drafts)

    def test_multiple_decidable_reference_errors_are_reported_together(self):
        fixture=Path(__file__).parent/'fixtures/closed-addition'
        value={'spec':json.loads((fixture/'spec.json').read_text()),'graph':json.loads((fixture/'nl0.json').read_text())}
        value['graph']['inferences'][0]['inputs']=['N999'];value['graph']['inferences'][1]['output']='N998'
        contract=NL0Contract(self.root/'errors',{'problem.txt':'Synthetic fixture only.'})
        with self.assertRaises(ValueError) as failure:contract(value)
        self.assertIn('N999',str(failure.exception));self.assertIn('N998',str(failure.exception))
        self.assertEqual(json.loads(contract.drafts[1])['graph']['inferences'][0]['inputs'],['N999'])

    def test_library_probe_rejects_code_injection_before_execution(self):
        for name in ['Nat.add_zero\n#eval IO.println "bad"','Nat.add_zero;','Nat.add_zero`']:
            with self.assertRaises(ValueError):
                signature_probe(self.root,'M001',name,'Mathlib.Algebra.Group.Nat.Defs',1)
        with self.assertRaises(ValueError):
            signature_probe(self.root,'M001','Nat.add_zero','../Other',1)

    def test_model_visible_example_matches_the_authoring_contract(self):
        template=Path(__file__).parents[1]/'templates/submission-example.md'
        value=json.loads(template.read_text().split('```json\n',1)[1].split('\n```',1)[0])
        contract=NL0Contract(self.root/'example',{'problem.txt':'Neutral format example.'},
                             case_id=value['spec']['case_id'])
        self.assertFalse(contract(value)['mathematical_acceptance'])
        value['graph']['propositions'][0]['statement']='Different from the submitted specification.'
        with self.assertRaisesRegex(ValueError,'not an undisclosed controller H list'):
            contract(value)

    def test_relative_probe_directory_runs_in_the_native_sandbox(self):
        previous=Path.cwd()
        try:
            os.chdir(self.root)
            row=signature_probe(Path('relative-case'),'M001','dimH_empty',
                'Mathlib.Topology.MetricSpace.HausdorffDimension',1)
            report=json.loads((self.root/'relative-case'/row['evidence'][0]['path']).read_text())
            self.assertEqual(report['exit_code'],0)
            self.assertIn('dimH_empty',row['signature'])
        finally:
            os.chdir(previous)

    def test_native_probe_launch_failure_is_not_a_candidate_rejection(self):
        with patch('artifact_validation.run_lean',return_value={
            'exit_code':1,'stdout':'','stderr':'sandbox-exec: missing sandbox profile','wall_seconds':0}):
            with self.assertRaises(OSError):
                signature_probe(self.root/'failed','M001','dimH_empty',
                    'Mathlib.Topology.MetricSpace.HausdorffDimension',1)

    def test_generic_analytic_signature_preserves_conditions_without_recursive_structure_expansion(self):
        row=signature_probe(self.root/'analytic-signature','M001',
            'integral_bilinear_hasFDerivAt_right_eq_neg_left_of_integrable',
            'Mathlib.Analysis.Calculus.LineDeriv.IntegrationByParts',1)
        self.assertLess(len(row['signature']),20000)
        for condition in ['FiniteDimensional','IsAddHaarMeasure','Integrable','HasFDerivAt','tsupport']:
            self.assertIn(condition,row['signature'])
        self.assertIn('sources',json.loads((self.root/'analytic-signature'/row['evidence'][0]['path']).read_text()))

    def test_importing_module_cannot_be_mislabeled_as_the_declaration_source(self):
        with self.assertRaisesRegex(ValueError,'Declaration source module differs'):
            signature_probe(self.root/'wrong-module','M001',
                'hasFDerivAt_integral_of_dominated_of_fderiv_le',
                'Mathlib.MeasureTheory.Integral.IntegralEqImproper',1)

    def test_library_metadata_is_bound_without_rewriting_mathematics(self):
        contract=NL0Contract(self.root/'bound',{'problem.txt':'Dimension of the empty set.'},case_id='empty')
        source_statement='For every metric space Y, the Hausdorff dimension of the empty subset of Y is zero.'
        conclusion='The Hausdorff dimension of the empty subset of X is zero.'
        source={'hypotheses':[],
                'declaration':'dimH_empty','module':'Mathlib.Topology.MetricSpace.HausdorffDimension'}
        value={'spec':{'format_version':2,'case_id':'empty','full_target':conclusion,'conclusion':conclusion,
            'parameters':[{'symbol':'X','type':'metric space'}],'hypotheses':[],'definitions':[],
            'logic':{'classical':False,'rules':['direct'],'calculations':['Instantiation of a universally quantified theorem.'],
                     'primitives':[]}},
            'graph':{'format_version':2,'case_id':'empty','propositions':[
                {'id':'M001','kind':'mathlib','statement':source_statement,'definitions':[],
                 'binders':[{'symbol':'Y','type':'metric space'}],'objects':['Y'],'source':source},
                {'id':'P','kind':'target','statement':conclusion,'definitions':[],'binders':[],'objects':['X']}],
                'inferences':[{'id':'R001','inputs':['M001'],'output':'P','definitions':[],'rules':['direct'],
                    'locals':[],'argument':[{'id':'S001','text':'Instantiate M001 at X to obtain the stated equality.',
                    'uses':['M001'],'uses_local':[],'objects':['X'],'produces':[],'introduces':[],'discharges':[]}],
                    'applications':[{'input':'M001','at':'S001','bindings':'Instantiate Y with X and its metric structure.','hypothesis_checks':[]}]}]}}
        with self.assertRaisesRegex(ValueError,'no actual successful stage probe'):
            contract(value)
        probe=signature_probe(contract.directory,'M001','dimH_empty',source['module'],1)
        checked=contract(value)
        bound=value['graph']['propositions'][0]
        self.assertFalse(checked['mathematical_acceptance'])
        self.assertEqual(bound['statement'],source_statement)
        self.assertEqual(bound['source']['statement'],source_statement)
        self.assertEqual(bound['source']['signature'],probe['signature'])
        self.assertEqual(value['graph']['inferences'][0]['argument'][0]['text'],
                         'Instantiate M001 at X to obtain the stated equality.')
        # Transcription mistakes are corrected from the real probe, while the
        # author's declaration choice and all NL mathematical content persist.
        bound['source']['signature']='incorrect transcription'
        contract(value)
        self.assertEqual(value['graph']['propositions'][0]['source']['signature'],probe['signature'])
        value['graph']['propositions'][0]['source']['statement']='Conflicting authored duplicate.'
        with self.assertRaisesRegex(ValueError,'Both texts are authored in this artifact'):
            contract(value)


if __name__=='__main__':unittest.main()
