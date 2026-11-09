"""Independent receiving-side examples for already reviewed mathematical inputs."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'blocks'))
import foundation_handoff as handoff


class Handoff(unittest.TestCase):
    def setUp(self):
        self.inventory = {
            'dependencies': [
                {'id':'B001','category':1,'compatibility':'native','port':None,'statement':'The first fact.'},
                {'id':'B002','category':3,'compatibility':'internal','port':'E009','statement':'A derived fact.'},
                {'id':'B003','category':1,'compatibility':'native','port':None,'statement':'An internal prerequisite.'}],
            'global_graph': {'propositions':[{'id':'E009','statement':'A derived fact.'}],
                             'inferences':[{'id':'R001','inputs':['E009'],'output':'N001','basis':['B001','B002']},
                                           {'id':'R002','inputs':['H001'],'output':'P','basis':['B001']}]}}

    def test_two_consumers_share_one_label_and_private_premise_stays_private(self):
        seed, labels = handoff.numbered_seed(self.inventory)
        self.assertEqual(labels, {'B001':'M001','B002':'E009'})
        self.assertEqual([r['inputs'] for r in seed['inferences']], [['E009','M001'],['H001','M001']])
        self.assertIsNone(self.inventory['dependencies'][0]['port'])
        self.assertEqual(len([r for r in seed['propositions'] if r['id']=='M001']),1)

    def test_rename_all_consumers_without_touching_frozen_content(self):
        graph, labels = handoff.numbered_seed(self.inventory)
        for row in graph['propositions']:
            row['kind'] = 'mathlib' if row['id'].startswith('M') else 'external'
        handoff.attach(self.inventory, graph, labels)
        handoff.rename(self.inventory, graph, {'B001':'M014','B002':'E001'})
        owners = handoff.by_port(self.inventory,graph)
        self.assertEqual({key:row['id'] for key,row in owners.items()}, {'M014':'B001','E001':'B002'})
        self.assertEqual([r['inputs'] for r in graph['inferences']], [['E001','M014'],['H001','M014']])
        self.assertEqual(self.inventory['dependencies'][1]['port'],'E009')
        next_seed,next_labels=handoff.numbered_seed(self.inventory,graph)
        self.assertEqual(next_labels,{'B001':'M014','B002':'E001'})
        self.assertEqual(next_seed['inferences'][0]['basis'],['B002','B001'])
        self.assertEqual(next_seed['inferences'][1]['inputs'],['H001','M014'])
        with self.assertRaises(ValueError):
            handoff.rename(self.inventory,graph,{'B001':'E005'})
        graph['propositions'][0]['statement']='A weaker fact.'
        with self.assertRaises(ValueError):
            handoff.by_port(self.inventory,graph)

    def test_repair_rejects_collisions_wrong_identity_and_partial_rewrites(self):
        from copy import deepcopy
        graph,labels=handoff.numbered_seed(self.inventory)
        for row in graph['propositions']:
            row['kind']='mathlib' if row['id'].startswith('M') else 'external'
        graph['propositions'].append({'id':'H001','statement':'Original.','kind':'hypothesis'})
        handoff.attach(self.inventory,graph,labels)
        before=deepcopy(graph)
        for changes in ({'B001':'H001'},{'B001':'E009'},{'B999':'M002'},{'B001':'E020'},{'B001':'M1000'},{'B001':None}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                handoff.rename(self.inventory,graph,changes)
            self.assertEqual(graph,before)
        for invalid in ({'version':handoff.VERSION,'labels':{'B001':'M001','B003':'M001'}},
                        {'version':'unknown','labels':{}},{'version':handoff.VERSION,'labels':{'B002':'E044'}}):
            with self.assertRaises(ValueError):
                handoff.by_port(self.inventory,{**graph,handoff.FIELD:invalid})
        graph['inferences'][0]['applications']=[]
        with self.assertRaises(ValueError):
            handoff.rename(self.inventory,graph,{'B001':'M019'})

    def test_all_allocated_names_fit_the_lean_premise_interface(self):
        row={**self.inventory['dependencies'][0],'id':'B999'}
        self.assertEqual(handoff.allocate(row,{'M999','M000'}),'M001')
        with self.assertRaisesRegex(ValueError,'occupied'):
            handoff.allocate(row,{f'M{i:03}' for i in range(1000)})

    def test_previous_unversioned_working_graph_gets_the_missing_direct_native_label(self):
        previous={'propositions':self.inventory['global_graph']['propositions'],
                  'inferences':[{'id':'R002','inputs':['H001'],'output':'P'}]}
        seed,labels=handoff.numbered_seed(self.inventory,previous)
        self.assertEqual(labels,{'B001':'M001'})
        self.assertEqual(seed['inferences'][0]['inputs'],['H001','M001'])

    def test_without_context_neither_unbound_selector_nor_bad_hash_is_material(self):
        refs = {'source.txt':{'path':'inputs/source.txt','sha256':'a'*64}}
        self.assertEqual(handoff.material_ref({'input':'source.txt'},refs,'E001.source'),refs['source.txt'])
        for invalid in ({'input':'other'}, {'input':'source.txt','path':'extra'}, None,
                        {'path':'/outside','sha256':'a'*64}, {'path':'inputs/source.txt','sha256':'wrong'}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                handoff.material_ref(invalid,refs,'E001.source')


if __name__ == '__main__':
    unittest.main()
