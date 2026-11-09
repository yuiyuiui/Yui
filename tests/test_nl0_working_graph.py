"""Independent boundaries for working NL0 revisions and protected mathematical inputs."""
from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import unittest

import harness_support as support
from basis_fixtures import active_artifact,artifact,dependency
from controller_common import bind,write
from execution_health import StageFailure
import basis_graph
import frozen_graph as fg
import graph_repair
import nl0


class WorkingGraphTests(unittest.TestCase):
    def setUp(self):
        self.registry=active_artifact(artifact(dependency(category=4)))
        self.seed=self.registry['global_graph']
        self.source=support.TESTS/'fixtures/closed-addition'

    def test_frozen_foundations_allow_splitting_merging_and_reusing_intermediates(self):
        draft=deepcopy(self.seed)
        middle=next(p for p in draft['propositions'] if p['id']=='N001')
        middle['statement']='Equality holds in the reverse order.'
        draft['propositions'].append({'id':'N002','statement':'The two numbers are equal.'})
        draft['inferences'].insert(1,{'id':'R003','inputs':['N001'],'output':'N002','basis':[]})
        draft['inferences'][-1]['inputs'].append('N002')
        basis_graph.verify_handoff(self.registry,draft)
        basis_graph.active({**self.registry,'global_graph':draft})
        merged=deepcopy(draft)
        merged['propositions']=[p for p in merged['propositions'] if not p['id'].startswith('N')]
        last=merged['inferences'][-1]
        last['inputs']=['H001','E001']
        merged['inferences']=[last]
        basis_graph.verify_handoff(self.registry,merged)
        basis_graph.active({**self.registry,'global_graph':merged})

    def test_a_graph_edit_cannot_replace_a_hypothesis_target_or_external_statement(self):
        for key in ('P','H001','E001'):
            draft=deepcopy(self.seed)
            next(p for p in draft['propositions'] if p['id']==key)['statement']='A weaker statement.'
            with self.subTest(key=key),self.assertRaises(ValueError):
                basis_graph.verify_handoff(self.registry,draft)
        for prefix in ('H','M','E'):
            draft=deepcopy(self.seed)
            draft['propositions'].append({'id':prefix+'999','statement':'New assumption.'})
            with self.subTest(prefix=prefix),self.assertRaises(ValueError):
                basis_graph.verify_handoff(self.registry,draft)

    def test_consent_names_exact_residual_but_allows_another_intermediate(self):
        scope=basis_graph.residual_scope(self.registry)
        other=deepcopy(self.registry)
        other['proof']='Another route through the same premises.'
        next(p for p in other['global_graph']['propositions'] if p['id']=='N001')['statement']='Intermediate.'
        self.assertEqual(basis_graph.residual_scope(other),scope)
        for mutate in (lambda r:r.update(full_target='True'),lambda r:r.update(lean_header='import Lean'),
                       lambda r:r['dependencies'][0]['lean'].update(type='False'),
                       lambda r:r['dependencies'][0].update(statement='False.'),
                       lambda r:r['dependencies'][0]['origin'].update(revision='Other edition')):
            other=deepcopy(self.registry);mutate(other)
            self.assertNotEqual(basis_graph.residual_scope(other),scope)

    def test_stale_and_cyclic_revisions_never_replace_the_current_assignment(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw).resolve()
            def candidate(index,statement,previous=None):
                source=root/'global-graphs'/str(index).zfill(4)/'stage/case'
                shutil.copytree(self.source,source)
                graph=nl0.load(source/'nl0.json')
                graph.update(fg.shape(graph))
                next(p for p in graph['propositions'] if p['id']=='N001')['statement']=statement
                write(source/'nl0.json',graph)
                return fg.checked_receipt(source,fg.DIRECT,previous=previous)
            job={'root':str(root)}
            first=fg.select(job,candidate(1,'b=a.'))
            second=fg.select(job,candidate(2,'The second number equals the first.',first),previous=first)
            stale=candidate(3,'The two numbers coincide.',first)
            with self.assertRaisesRegex(ValueError,'Stale'):fg.select(job,stale,previous=first)
            repeated=candidate(4,'b=a.',second)
            with self.assertRaises(StageFailure) as err:fg.select(job,repeated,previous=second)
            self.assertEqual(err.exception.result['status'],'NL0_GRAPH_REVISION_UNRESOLVED')
            self.assertEqual(nl0.load(root/'global-selection.json'),second)
            self.assertFalse(Path(repeated['path']).with_name('working.json').exists())
            self.assertEqual(bind(first['path']),first)

    def test_located_repair_has_valid_coordinates_and_no_mathematical_verdict(self):
        assigned={'graph':self.seed}
        finding={'inference':'R002','related_propositions':['H001'],'explanation':'The chosen equality uses H001 directly.'}
        issue=graph_repair.locate(assigned,finding)
        self.assertEqual(issue['location'],'/graph/inferences/1/inputs')
        self.assertNotIn('verdict',issue)
        for field in ('inputs','output','definitions'):
            with self.subTest(field=field):
                self.assertEqual(graph_repair.locate(assigned,{**finding,'field':field})['location'],
                                 '/graph/inferences/1/'+field)
        middle_index=next(i for i,p in enumerate(self.seed['propositions']) if p['id']=='N001')
        for index in ('R001','R002'):
            located=graph_repair.locate(assigned,{**finding,'inference':index,'field':'statement','related_propositions':['N001']})
            self.assertEqual(located['location'],f'/graph/propositions/{middle_index}/statement')
        assigned['graph']['propositions'].append({'id':'N999','statement':'Unrelated intermediate.'})
        for edit in ({'inference':'R999'},{'related_propositions':['E999']},{'related_propositions':['H001','H001']},
                     {'explanation':''},{'verdict':'PASS'},{'field':'body'},{'field':'statement'},
                     {'field':'statement','related_propositions':['N999']},{'field':'statement','related_propositions':['P']},
                     {'field':'statement','related_propositions':[]},{'field':'statement','related_propositions':['N001','H001']}):
            with self.subTest(edit=edit),self.assertRaises(ValueError):graph_repair.locate(assigned,{**finding,**edit})
