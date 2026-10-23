"""Security and binding controls for structural NL0 authoring; not mathematical certification."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import os

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from artifact_validation import NL0Contract, signature_probe


class ArtifactValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

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
