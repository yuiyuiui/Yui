"""Independent boundaries for working NL0 revisions and protected mathematical inputs."""
from copy import deepcopy
from pathlib import Path
import json
import shutil
import tempfile
import unittest

import harness_support as support
from basis_fixtures import active_artifact,artifact,checked_context,dependency
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

    def test_pre_usage_basis_review_only_applies_to_the_original_format(self):
        import basis_review
        packet = {'items':{'B001':{}}, 'global_graph':{'propositions':[{'id':'P'}]}}
        rule = basis_review.PRE_USAGE_RULE
        self.assertEqual(basis_review.rule_for(packet, rule), rule)
        for row in (packet['items']['B001'], packet['global_graph']['propositions'][0]):
            row['usage'] = {'references':[]}
            with self.assertRaisesRegex(ValueError, 'Unknown basis review rules'):
                basis_review.rule_for(packet, rule)
            del row['usage']
        with self.assertRaisesRegex(ValueError, 'Unknown basis review rules'):
            basis_review.rule_for(packet, 'unknown')

    def test_direct_global_and_local_authors_share_usage_and_revision_rebuilds_consumers(self):
        spec = nl0.load(self.source/'spec.json')
        complete = nl0.load(self.source/'nl0.json')
        docs = {'paper.md':'First manuscript.', 'appendix.md':'Separate appendix.'}
        refs = [{'document':'inputs/'+name, 'locator':'Lemma 2.1'} for name in docs]
        draft = {'spec':deepcopy(spec), **fg.shape(deepcopy(complete))}
        draft['proof_outline'] = support.elementary_outline(draft['inferences'])
        claim = next(p for p in draft['propositions'] if p['id']=='N001')
        claim['statement'] += ' Used in Lemma 2.1 (see H001).'
        claim['usage'] = {'references':refs}
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            directory = root/'global-graphs/0001/stage/case'
            author = fg.AuthorContract(directory,docs,spec['case_id'],fg.DIRECT)
            malformed = deepcopy(draft)
            next(p for p in malformed['propositions'] if p['id']=='N001')['usage']['references'] = ['Lemma 2.1']
            with self.assertRaisesRegex(ValueError, 'usage/references/0'):
                fg.protocol.validate(malformed, author.schema)
            author(draft)
            chosen = fg.select({'root':str(root)},fg.checked_receipt(directory,fg.DIRECT))
            assigned = fg.read_working(chosen)
            prop = next(p for p in assigned['graph']['propositions'] if p['id']=='N001')
            self.assertEqual(prop['usage'], {'inferences':['R002'], 'references':refs})
            local = fg.AuthorContract(root/'local',{**docs,fg.ASSIGNED:json.dumps(assigned)},spec['case_id'],fg.LOCAL)
            proofs = [{k:r[k] for k in ('id',*fg.BODY_FIELDS)} for r in complete['inferences']]
            local({'local_proofs':proofs})
            self.assertEqual(nl0.load(local.directory/'nl0.json')['propositions'],assigned['graph']['propositions'])
            next_author = fg.AuthorContract(root/'revised',{**docs,'prior-global.json':json.dumps(assigned)},
                                           spec['case_id'],fg.DIRECT)
            revision = {'spec':deepcopy(assigned['spec']), **fg.shape(deepcopy(assigned['graph']))}
            revision['inferences'][-1]['inputs'].append('H001')
            revision['proof_outline'] = support.elementary_outline(revision['inferences'])
            next_author(revision)
            changed = nl0.load(next_author.directory/'nl0.json')['propositions']
            self.assertEqual(next(p for p in changed if p['id']=='H001')['usage']['inferences'],['R001','R002'])
            self.assertEqual(next(p for p in changed if p['id']=='N001')['usage'],prop['usage'])

    def test_both_entries_split_a_long_derivation_before_selection(self):
        spec = nl0.load(self.source/'spec.json')
        complete = fg.shape(nl0.load(self.source/'nl0.json'))
        proof = 'First derivation. ' + 'x' * 8200 + '\nSecond derivation. ' + 'y' * 8200 + '\n'
        with tempfile.TemporaryDirectory() as raw:
            for owner in (fg.DIRECT,fg.BASIS):
                with self.subTest(owner=owner):
                    root = Path(raw)/owner
                    directory = root/'global-graphs/0001/stage/case'
                    docs = {'problem.md':proof}
                    if owner==fg.BASIS:
                        registry = artifact()
                        context = checked_context(root/'foundations',registry)
                        docs['basis-registry.json'] = Path(context['basis']['path']).read_text()
                        docs['proof-context.json'] = json.dumps(context)
                    author = fg.AuthorContract(directory,docs,spec['case_id'],owner)
                    bundled = {'spec':deepcopy(spec),**deepcopy(complete)}
                    bundled['propositions'] = [p for p in bundled['propositions'] if p['id']!='N001']
                    bundled['inferences'] = [{'id':'R002','inputs':['H001'],'output':'P','definitions':[]}]
                    bundled['proof_outline'] = support.elementary_outline(bundled['inferences'])
                    bundled['proof_outline']['R002']['steps'][0]['source_spans'] = [
                        {'from_task':'problem.md','start_line':1,'end_line':2}]
                    with self.assertRaisesRegex(ValueError,'OUTLINE_REVIEW:.*R002'):
                        author(bundled)
                    self.assertFalse((directory/fg.graph_outline.FILENAME).exists())
                    split = {'spec':deepcopy(spec),**deepcopy(complete)}
                    split['proof_outline'] = support.elementary_outline(split['inferences'])
                    for line, rid in enumerate(('R001','R002'),1):
                        split['proof_outline'][rid]['steps'][0]['source_spans'] = [
                            {'from_task':'problem.md','start_line':line,'end_line':line}]
                    checked = author(split)
                    submitted = {'accept_candidate':checked['candidate_number']}
                    author(submitted)
                    selected = fg.select({'root':str(root)},fg.checked_receipt(directory,owner))
                    record = nl0.load(selected['path'])
                    self.assertEqual(record['version'],'yui-working-graph-5')
                    readback = fg.read_outline(record)
                    self.assertEqual(readback['inferences'],submitted['graph']['proof_outline'])
                    self.assertEqual(readback['workload']['R001']['consumers'],['R002'])
                    self.assertEqual(sum(row['source_characters'] for row in readback['workload'].values()),len(proof))
                    self.assertLess(max(row['source_characters'] for row in readback['workload'].values()),len(proof))
                    (directory/fg.graph_outline.FILENAME).write_text('{}')
                    with self.assertRaisesRegex(ValueError,'Frozen input/runtime changed'):
                        fg.read_working(selected)

    def test_outline_rechecks_local_scope_and_actual_source_ranges(self):
        graph = {'inferences':[{'id':'R001','inputs':['H001'],'output':'P'}]}
        first = {'conclusion':'Choose a witness under H001.','uses':['H001'],
                 'source_spans':[{'from_task':'proof.md','start_line':1,'end_line':1}]}
        last = {'conclusion':'Prove both properties for that witness.','uses':['S001'],
                'source_spans':[{'from_task':'proof.md','start_line':1,'end_line':2}]}
        entry = {'steps':[first,last]}
        documents = {'proof.md':'Choose w.\nVerify its two properties.\n'}
        with self.assertRaisesRegex(ValueError,'OUTLINE_REVIEW:.*R001'):
            fg.graph_outline.check(graph,{'R001':entry},documents)
        entry['keep_together'] = {'kind':'shared_witness','reason':'Both properties concern the same chosen w.'}
        report = fg.graph_outline.check(graph,{'R001':entry},documents)
        self.assertEqual(report['workload']['R001']['source_characters'],len(documents['proof.md']))
        last['uses'] = []
        with self.assertRaisesRegex(ValueError,'OUTLINE_INPUT:.*S001'):
            fg.graph_outline.check(graph,{'R001':entry},documents)
        last['uses'] = ['S001']
        last['source_spans'][0]['end_line'] = 3
        with self.assertRaisesRegex(ValueError,'OUTLINE_SOURCE:.*proof.md:1-3'):
            fg.graph_outline.check(graph,{'R001':entry},documents)

    def test_explicit_foundation_uses_move_to_a_split_producer(self):
        docs = {'basis-registry.json':json.dumps(self.registry), 'problem.md':'A synthetic proof.'}
        with tempfile.TemporaryDirectory() as raw:
            author = fg.AuthorContract(Path(raw)/'draft',docs,None,fg.BASIS)
            graph = deepcopy(self.seed)
            next(p for p in graph['propositions'] if p['id']=='E001')['kind'] = 'external'
            first,final = graph['inferences']
            first['basis'] = ['B001']
            final['basis'] = []
            final['inputs'].remove('E001')
            author.bind_graph(graph,{})
            self.assertIn('E001',first['inputs'])
            self.assertNotIn('E001',final['inputs'])

    def test_a_matching_graph_label_cannot_substitute_an_unrelated_native_theorem(self):
        import basis
        import basis_sources
        from controller_common import manifest
        from test_basis_sources import direct
        row=direct()
        row['usage']={'references':[{'document':'inputs/problem.md','locator':'Lemma 2.1'}]}
        registry=artifact(row)
        rules=basis_graph.handoff()
        graph,labels=rules.numbered_seed(registry)
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            (root/'inputs').mkdir()
            (root/'inputs/problem.md').write_text(registry['full_target'])
            manifest(root/'inputs')
            author=basis.BasisContract(root,registry['full_target'])
            author(registry)
            context=nl0.load(author.last_receipt['path'])
            native=next(p for p in graph['propositions'] if p['id']=='M001')
            native.update(kind='mathlib',source=basis_sources.material(registry,context['native'])['B001']['source'])
            rules.attach(registry,graph,labels)
            basis.check_graph_sources(context,registry,graph)
            native['source']['declaration']='Nat.mul_zero'
            with self.assertRaisesRegex(ValueError,'M001.*B001'):
                basis.check_graph_sources(context,registry,graph)

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
                nl0.usage.bind(graph, set())
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

    def test_repair_boundary_uses_effective_scope_and_retains_unaffected_drafts(self):
        from clean_stage import ArtifactStage
        from controller_common import manifest

        spec=nl0.load(self.source/'spec.json')
        complete=nl0.load(self.source/'nl0.json')
        spec['definitions']=[{'id':key,'symbol':symbol,'type':'natural number','definition':symbol+'=0.',
            'binders':[],'objects':[],'depends_on':dependencies,'requires':[]}
            for key,symbol,dependencies in [('D001','u',['D002']),('D002','v',[]),('D003','w',[])]]
        shape=fg.shape(deepcopy(complete))
        next(p for p in shape['propositions'] if p['id']=='N001')['definitions']=['D001']
        docs={'problem.txt':(self.source/'problem.txt').read_text()}

        def draft(spec, graph):
            return {'spec':deepcopy(spec), **deepcopy(graph),
                    'proof_outline':support.elementary_outline(graph['inferences'])}

        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw).resolve()
            initial=fg.AuthorContract(root/'global-graphs/0001/stage/case',docs,spec['case_id'],fg.DIRECT)
            guarded=deepcopy(spec)
            guarded['definitions'][1]['requires']=['H001']
            with self.assertRaisesRegex(ValueError,'DIRECT-GUARD: R002/D002'):
                initial(draft(guarded,shape))
            initial(draft(spec,shape))
            job={'root':str(root)}
            previous=fg.select(job,fg.checked_receipt(initial.directory,fg.DIRECT))
            assigned=fg.read_working(previous)

            local=root/'local'
            (local/'inputs').mkdir(parents=True)
            (local/'inputs/problem.txt').write_text(docs['problem.txt'])
            write(local/'inputs'/fg.ASSIGNED,assigned)
            manifest(local/'inputs')
            stage=ArtifactStage(local/'stage','Synthetic local graph repair.',phase=fg.LOCAL,kind='nl0',
                                inputs=local/'inputs/inputs.json',library=False)
            def report(kind,subject):
                return {'inference':'R002','kind':kind,'subject':subject,
                        'explanation':'Synthetic located requirement for the assigned proof.'}
            try:
                # D001 is delivered through R002's premise and R001's output.
                # D002 is delivered transitively, while the ancestor H001 is not.
                for rid,premise in [('R001','H001'),('R002','N001')]:
                    packet=stage.dispatch('read_author_packet',{'inference':rid})
                    self.assertEqual([d['id'] for d in packet['definitions']],['D001','D002'])
                    self.assertEqual([p['id'] for p in packet['inputs']],[premise])
                self.assertEqual(stage.validator.author_check.reads,{})
                for kind,subject in [('missing_definition','D001'),('missing_definition','D002'),
                                     ('missing_input','N001'),('output','N001')]:
                    with self.subTest(kind=kind,subject=subject):
                        reply=stage.dispatch(graph_repair.TOOL,{'findings':[report(kind,subject)]})
                        self.assertFalse(reply['accepted'])
                        self.assertIsNone(stage.accepted)
                        if kind!='output':self.assertIn('already supplied in the conditional packet',reply['error'])

                blockers=[report('missing_input','H001'),report('missing_definition','D003')]
                for kind,subject in [('wrong_input','N001'),('wrong_definition','D001'),('wrong_statement','N001')]:
                    self.assertEqual(graph_repair.assess(assigned,{'findings':[report(kind,subject)]})
                                     ['blockers'][0]['subject'],subject)
                bodies=[{k:r[k] for k in ('id',*fg.BODY_FIELDS)} for r in complete['inferences']]
                batch={'findings':blockers,'local_proofs':bodies}
                reply=stage.dispatch(graph_repair.TOOL,batch)
                self.assertTrue(reply['stage_complete'])
                self.assertFalse(reply['mathematical_acceptance'])
                evidence=local/'stage/accepted.json'
                write(evidence,stage.accepted)
                obligations=graph_repair.assess(assigned,batch)
            finally:
                stage.release_resources('USER_CANCELLED')

            global_docs={**docs,'prior-global.json':json.dumps(assigned),
                         graph_repair.FEEDBACK:json.dumps(obligations)}
            revise=fg.AuthorContract(root/'global-graphs/0002/stage/case',global_docs,spec['case_id'],fg.DIRECT)
            revised=fg.shape(deepcopy(assigned['graph']))
            revised['inferences'][-1]['definitions'].append('D001')  # Already inherited at R002.
            with self.assertRaisesRegex(ValueError,'GRAPH_REPAIR_SCOPE:.*R002'):
                revise(draft(assigned['spec'],revised))
            revised['inferences'][-1]['inputs'].append('H001')
            revised['inferences'][-1]['definitions'].append('D003')
            revise(draft(assigned['spec'],revised))
            checked=fg.checked_receipt(revise.directory,fg.DIRECT,previous=previous)
            selected=fg.select(job,checked,previous=previous)
            current=fg.read_working(selected)
            feedback=graph_repair.revision_feedback(
                {'global':previous,'obligations':obligations,'evidence':[bind(evidence)]},selected,current)
            self.assertEqual(feedback['blockers'],blockers)
            self.assertEqual(feedback['changed_inferences'],['R002'])
            self.assertEqual(feedback['local_proofs'],bodies[:1])

            author=fg.AuthorContract(root/'next',{**docs,fg.ASSIGNED:json.dumps(current),
                graph_repair.FEEDBACK:json.dumps(feedback)},spec['case_id'],fg.LOCAL)
            last=deepcopy(bodies[-1])
            last['argument'][-1]['uses'].append('H001')
            last['argument'][-1]['text']+=' Compose with the original equality a=b.'
            checked=author({'local_proofs':[last]})
            self.assertFalse(checked['mathematical_acceptance'])
            self.assertFalse(author.author_check.status(1)['author_release_ready'])
            final=nl0.load(author.directory/'nl0.json')['inferences']
            self.assertEqual(final[0]['argument'],bodies[0]['argument'])
