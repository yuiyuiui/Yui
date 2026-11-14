"""Security and binding controls for structural NL0 authoring; not mathematical certification."""
import harness_support
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import os

from artifact_validation import NL0Contract, signature_probe, expand_submission, preflight, own_text_lines, resolve_own


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

    def neutral(self):
        fixture=Path(__file__).parent/'fixtures/closed-addition'
        return {'spec':json.loads((fixture/'spec.json').read_text()),
                'graph':json.loads((fixture/'nl0.json').read_text())}

    def invalid_scope(self,value):
        # Preflight succeeds; the full declaration/fact scope check rejects it.
        value['graph']['inferences'][1]['locals'][0]['end']='S001'
        return value

    def test_external_source_errors_identify_the_actual_row_and_recover_in_place(self):
        from copy import deepcopy
        from basis_fixtures import add_external_applications, artifact, dependency
        value=self.neutral()
        material={'input':'original.txt'}
        add_external_applications(value['graph'],artifact(dependency('B001',2),dependency('B002',2)),[material])
        value['spec'].pop('case_id')
        value['graph'].pop('case_id')
        owner=NL0Contract(self.root/'receiver',{'original.txt':'Reviewed source.'},'owned-case',global_only=True)
        for step in value['graph']['inferences']:
            for k in ('rules','locals','argument','applications'): step.pop(k)
        owner(deepcopy(value))
        pair=[owner.directory/k for k in ('spec.json','nl0.json')]
        accepted=[p.read_bytes() for p in pair]
        for position in (0,1):
            pid=value['graph']['propositions'][position]['id']
            for field,invalid in [('source',None),('source','absent'),('verification',True),
                                  ('verification',{'status':'UNVERIFIED_PRIMARY'}),('primary_evidence',[{'input':'missing'}]),
                                  ('evidence',[{'path':'/another/case/doc.txt','sha256':'a'*64}])]:
                attempt=deepcopy(value)
                row=attempt['graph']['propositions'][position]
                if field=='source' and invalid is None: row.pop(field)
                elif field=='source': row[field]=invalid
                else:row['source'][field]=invalid
                with self.subTest(pid=pid,field=field,invalid=invalid),self.assertRaisesRegex(ValueError,pid+r'\.source'):
                    owner(attempt)
                self.assertEqual([p.read_bytes() for p in pair],accepted)
        modified=deepcopy(value)
        modified['graph']['propositions'][0]['source']['evidence']=[{'path':'inputs/original.txt','sha256':'a'*64}]
        with self.assertRaisesRegex(ValueError,'EVIDENCE-HASH'):
            owner(modified)
        owner(deepcopy(value))
        self.assertEqual([p.read_bytes() for p in pair],accepted)
        self.assertEqual(json.loads(pair[0].read_text())['case_id'],'owned-case')

    def test_prepared_and_external_theorems_bind_only_their_reviewed_primary_material(self):
        from basis_fixtures import dependency
        owner=NL0Contract(self.root/'materials',{'text.txt':'citation','basis-registry.json':'checked derivation'})
        context={'evidence':[]}
        for category in (2,4):
            row=dependency(category=category)
            row['origin']['evidence']=[{'input':'text.txt'}]
            source={}
            owner.bind_external_source('E001',source,row,context,working=True)
            self.assertEqual(source['primary_evidence'],[owner.expected_inputs[0]])
            with self.assertRaisesRegex(ValueError,'reviewed original evidence'):
                owner.bind_external_source('E001',{'primary_evidence':[{'input':'basis-registry.json'}]},row,context,working=True)
        source={}
        owner.bind_external_source('E001',source,dependency(category=3),context,working=True)
        self.assertEqual(source['primary_evidence'],[owner.expected_inputs[1]])

    def test_staged_view_of_a_retained_source_is_bound_to_its_own_text_bytes(self):
        import hashlib
        from basis_fixtures import dependency
        name='basis-evidence-000.txt'
        owner=NL0Contract(self.root/'view',{name:'retained excerpt'})
        digest=hashlib.sha256(b'retained excerpt').hexdigest()
        original='b'*64
        context={'evidence':[{'path':'/earlier/primary.pdf','sha256':original}],
                 'staged_evidence':[{'input':name,'source_sha256':original,'text_sha256':digest}]}
        row=dependency(category=4)
        row['origin']['evidence']=[{'path':'download/primary.pdf','sha256':original}]
        source={}
        owner.bind_external_source('E001',source,row,context,working=True)
        self.assertEqual(source['primary_evidence'],owner.expected_inputs)
        context['staged_evidence'][0]['text_sha256']='c'*64
        with self.assertRaisesRegex(ValueError,'staged original evidence changed'):
            owner.bind_external_source('E001',{},row,context,working=True)

    def test_rejected_initial_draft_publishes_no_canonical_pair(self):
        contract=NL0Contract(self.root/'first-invalid',{'problem.txt':'Neutral controller fixture.'})
        with self.assertRaises(ValueError):contract(self.invalid_scope(self.neutral()))
        self.assertFalse((contract.directory/'spec.json').exists())
        self.assertFalse((contract.directory/'nl0.json').exists())
        self.assertTrue((contract.directory/'candidate-0001.json').exists())
        self.assertFalse(list(contract.directory.glob('.validation-*.json')))

    def test_rejected_later_draft_preserves_the_previous_valid_pair_byte_for_byte(self):
        contract=NL0Contract(self.root/'later-invalid',{'problem.txt':'Neutral controller fixture.'})
        contract(self.neutral())
        paths=[contract.directory/name for name in ['spec.json','nl0.json']]
        before=[p.read_bytes() for p in paths]
        changed=self.invalid_scope(self.neutral());changed['spec']['full_target']+=' Extra draft text.'
        with self.assertRaises(ValueError):contract(changed)
        self.assertEqual([p.read_bytes() for p in paths],before)
        self.assertEqual(contract.last_valid_candidate,1)
        self.assertNotIn(2,contract.valid_drafts)
        self.assertFalse(list(contract.directory.glob('.validation-*.json')))

    def test_valid_pair_publication_failure_restores_prior_bytes_without_acceptance(self):
        import artifact_validation as av
        contract=NL0Contract(self.root/'io-failure',{'problem.txt':'Neutral controller fixture.'})
        contract(self.neutral());paths=[contract.directory/name for name in ['spec.json','nl0.json']]
        before=[p.read_bytes() for p in paths];real_write=av.write
        def interrupted(path,value):
            if Path(path)==paths[1]:raise OSError('Injected canonical second-write failure')
            return real_write(path,value)
        changed=self.neutral();changed['spec']['full_target']+=' Equivalent restatement for an I/O control.'
        with patch.object(av,'write',side_effect=interrupted):
            with self.assertRaisesRegex(OSError,'Injected canonical'):contract(changed)
        self.assertEqual([p.read_bytes() for p in paths],before)
        self.assertEqual(contract.last_valid_candidate,1)
        self.assertNotIn(2,contract.valid_drafts)
        self.assertFalse(list(contract.directory.glob('.validation-*.json')))

    def test_valid_edit_publishes_exact_validated_hashes(self):
        import artifact_validation as av
        contract=NL0Contract(self.root/'valid-update',{'problem.txt':'Neutral controller fixture.'})
        contract(self.neutral())
        value={'base_candidate':1,'patches':[{'op':'replace','path':'/spec/full_target',
            'value':'For real a=b prove the same equality a+0=b; neutral publication control.'}]}
        result=contract(value)
        self.assertEqual(result['summary']['spec_sha256'],av.nl0.sha(contract.directory/'spec.json'))
        self.assertEqual(result['summary']['graph_sha256'],av.nl0.sha(contract.directory/'nl0.json'))
        self.assertEqual(json.loads((contract.directory/'spec.json').read_text()),value['spec'])
        self.assertEqual(json.loads((contract.directory/'nl0.json').read_text()),value['graph'])
        self.assertEqual(contract.last_valid_candidate,2)

    def test_guarded_definition_template_separates_guard_producer_from_object_use(self):
        import re
        text=(Path(__file__).parents[1]/'nl0/templates/guarded-definition-example.md').read_text()
        value=json.loads(re.search(r'```json\n(.*?)\n```',text,re.S).group(1))
        contract=NL0Contract(self.root/'guarded',{'neutral.txt':'Unique Q witness and its equality to a.'})
        self.assertFalse(contract(value)['mathematical_acceptance'])
        self.assertEqual(value['graph']['inferences'][1]['inputs'],['N001'])
        value['graph']['inferences'][0]['definitions'].append('D002')
        with self.assertRaisesRegex(ValueError,'DEFINITION-PREREQUISITE'):contract(value)

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

    def test_failed_record_guard_reports_the_actual_pointer_and_record_identity(self):
        base={'spec':{},'graph':{'propositions':[{'id':'M004'},{'id':'M017'}]}}
        with self.assertRaises(ValueError) as failure:
            expand_submission({'base_input':'prior','patches':[
                {'op':'test','path':'/graph/propositions/0/id','value':'M017'}]},
                {'prior':json.dumps(base)})
        message=str(failure.exception)
        self.assertIn('/graph/propositions/0/id',message)
        self.assertIn('actual="M004"',message)
        self.assertIn('"index": 1',message)
        self.assertIn('"id": "M017"',message)
        self.assertEqual(base['graph']['propositions'][0]['id'],'M004')

    def test_literal_text_edit_preserves_unselected_text_and_rejects_ambiguous_matches(self):
        base={'spec':{},'graph':{'text':'First line.\nChoose ε > 0.\nLast line.'}}
        documents={'prior':json.dumps(base)}
        result,receipt=expand_submission({'base_input':'prior','patches':[
            {'op':'replace_text','path':'/graph/text','old':'Choose ε > 0.','new':'Fix ε > 0.'}]},documents)
        self.assertEqual(result['graph']['text'],'First line.\nFix ε > 0.\nLast line.')
        self.assertEqual(json.loads(documents['prior']),base)
        self.assertEqual(receipt['patches'][0]['op'],'replace_text')
        for text,old in [('duplicate duplicate','duplicate'),('aaa','aa'),('abc','missing'),('abc','')]:
            with self.assertRaises(ValueError):
                expand_submission({'base_input':'prior','patches':[
                    {'op':'replace_text','path':'/graph/text','old':old,'new':'new'}]},
                    {'prior':json.dumps({'spec':{},'graph':{'text':text}})})

    def test_stable_record_selectors_follow_IDs_not_shifted_numeric_positions(self):
        value={'spec':{'parameters':[{'symbol':'x','type':'real number'}]},
               'graph':{'inferences':[{'id':'R009','argument':[{'id':'S001','text':'Unchanged.'}]},
                                      {'id':'R002','argument':[{'id':'S007','text':'Old text.'}]}]}}
        docs={'base':json.dumps(value)}
        out,_=expand_submission({'base_input':'base','patches':[
            {'op':'replace_text','path':'/graph/inferences/@R002/argument/@S007/text','old':'Old','new':'New'},
            {'op':'test','path':'/spec/parameters/@x/type','value':'real number'}]},docs)
        self.assertEqual(out['graph']['inferences'][0],value['graph']['inferences'][0])
        self.assertEqual(out['graph']['inferences'][1]['argument'][0]['text'],'New text.')
        self.assertEqual(json.loads(docs['base']),value)
        for pointer in ['/graph/inferences/@R404','/spec/parameters/@missing']:
            with self.assertRaisesRegex(ValueError,'exactly one'):
                expand_submission({'base_input':'base','patches':[{'op':'remove','path':pointer}]},docs)
        duplicate={'spec':{},'graph':{'rows':[{'id':'N001'},{'id':'N001'}]}}
        with self.assertRaisesRegex(ValueError,'matches='):
            expand_submission({'base_input':'base','patches':[{'op':'remove','path':'/graph/rows/@N001'}]},
                              {'base':json.dumps(duplicate)})

    def test_hash_guarded_line_edit_preserves_latex_unicode_endings_and_duplicate_lines(self):
        text='\\(a\\)\r\nSame\r\nSame\r\n尾行'
        base={'spec':{},'graph':{'rows':[{'id':'S002','text':text}]}}
        view=own_text_lines(text,2,2)
        self.assertEqual(view['lines'],[{'line':2,'text':'Same\r\n'}])
        edit={'op':'replace_lines','path':'/graph/rows/@S002/text',
              'start_line':2,'end_line':2,'text':'Changed\r\n','text_sha256':view['text_sha256']}
        out,_=expand_submission({'base_input':'base','patches':[edit]},{'base':json.dumps(base)})
        self.assertEqual(out['graph']['rows'][0]['text'],'\\(a\\)\r\nChanged\r\nSame\r\n尾行')
        self.assertEqual(base['graph']['rows'][0]['text'],text)

    def test_line_edit_rejects_stale_hash_bad_bounds_and_accidental_merge_atomically(self):
        value={'spec':{'label':'unchanged'},'graph':{'text':'one\ntwo\nlast'}}
        edit={'op':'replace_lines','path':'/graph/text','start_line':2,'end_line':2,
              'text':'new\n','text_sha256':own_text_lines(value['graph']['text'],1,1)['text_sha256']}
        for changed in [{'text_sha256':'0'*64},{'start_line':0},{'end_line':9},
                        {'start_line':True},{'text':'no newline'},{'text':4},{'old':'extra'}]:
            with self.assertRaises(ValueError):
                expand_submission({'base_input':'base','patches':[
                    {'op':'replace','path':'/spec/label','value':'not committed'},
                    {**edit,**changed}]},{'base':json.dumps(value)})
        self.assertEqual(value['spec']['label'],'unchanged')
        out,_=expand_submission({'base_input':'base','patches':[{**edit,'text':''}]},{'base':json.dumps(value)})
        self.assertEqual(out['graph']['text'],'one\nlast')

    def test_bounded_line_view_reads_large_own_strings_and_rejects_nonstring_values(self):
        text=('a'*500+'\n')*100
        self.assertEqual(len(own_text_lines(text,60,63)['lines']),4)
        for value,start,end in [([],1,1),('abc',2,2),('abc',True,1)]:
            with self.assertRaises(ValueError):own_text_lines(value,start,end)

    def test_missing_path_reports_actual_ancestor_and_record_identities_without_redirecting(self):
        value={'graph':{'inferences':[{'id':'R009','argument':[]}]},'spec':{}}
        for pointer in ['/graph/inferences/7/argument','/graph/inferences/@absent/argument']:
            with self.assertRaises(ValueError) as result:resolve_own(value,pointer)
            self.assertIn('deepest_existing_prefix',str(result.exception))
            self.assertIn('R009',str(result.exception))
        with self.assertRaises(ValueError) as result:
            expand_submission({'base_input':'base','patches':[{'op':'replace','path':'/graph/nope','value':1}]},
                              {'base':json.dumps(value)})
        self.assertIn('inferences',str(result.exception))

    def test_failed_literal_edit_returns_current_text_without_applying_any_patch(self):
        value={'spec':{'label':'unchanged'},'graph':{'text':'Actual current text.'}}
        with self.assertRaisesRegex(ValueError,'Actual current text='):
            expand_submission({'base_input':'base','patches':[
                {'op':'replace','path':'/spec/label','value':'not committed'},
                {'op':'replace_text','path':'/graph/text','old':'stale','new':'other'}]},
                {'base':json.dumps(value)})
        self.assertEqual(value['spec']['label'],'unchanged')

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

    def test_independent_missing_objects_are_aggregated_without_relaxing_scope(self):
        fixture=Path(__file__).parent/'fixtures/closed-addition'
        value={'spec':json.loads((fixture/'spec.json').read_text()),'graph':json.loads((fixture/'nl0.json').read_text())}
        value['graph']['inferences'][0]['argument'][0]['objects'].append('undeclared_alpha')
        value['graph']['inferences'][1]['argument'][1]['objects'].append('undeclared_beta')
        contract=NL0Contract(self.root/'object-errors',{'problem.txt':'Synthetic fixture only.'})
        with self.assertRaises(ValueError) as failure:contract(value)
        self.assertIn('undeclared_alpha',str(failure.exception))
        self.assertIn('undeclared_beta',str(failure.exception))
        value['graph']['inferences'][0]['argument'][0]['objects'].remove('undeclared_alpha')
        value['graph']['inferences'][1]['argument'][1]['objects'].remove('undeclared_beta')
        value['graph']['inferences'][1]['locals'][0]['end']='S001'
        with self.assertRaisesRegex(ValueError,'UNDECLARED-OBJECT'):contract(value)

    def test_parameter_type_words_do_not_trigger_field_specific_guesses(self):
        fixture=Path(__file__).parent/'fixtures/closed-addition'
        value={'spec':json.loads((fixture/'spec.json').read_text()),'graph':json.loads((fixture/'nl0.json').read_text())}
        for label in ['irreducible representation', 'compact space', 'prime ideal',
                      'admissible object', 'sheaf of modules on a scheme']:
            value['spec']['parameters'][0]['type']=label
            self.assertEqual(preflight(value['spec'],value['graph']),[])

    def test_prose_theorem_names_are_semantic_review_not_structural_acceptance(self):
        fixture=Path(__file__).parent/'fixtures/closed-addition'
        spec=json.loads((fixture/'spec.json').read_text());graph=json.loads((fixture/'nl0.json').read_text())
        s=graph['inferences'][0]['argument'][0]
        for name in ['mean value theorem', 'Tonelli theorem', 'Nakayama lemma']:
            s['text']=f'By the {name}, the conclusion follows.'
            self.assertEqual(preflight(spec,graph),[])
        contract=NL0Contract(self.root/'semantic-boundary',{'problem.txt':'Synthetic fixture only.'})
        result=contract({'spec':spec,'graph':graph})
        self.assertFalse(result['mathematical_acceptance'])

    def test_domain_notation_uses_the_same_declarations_as_any_other_object(self):
        fixture=Path(__file__).parent/'fixtures/closed-addition'
        spec=json.loads((fixture/'spec.json').read_text());graph=json.loads((fixture/'nl0.json').read_text())
        graph['inferences'][0]['argument'][0]['objects'].append('norm')
        contract=NL0Contract(self.root/'domain-notation',{'problem.txt':'Synthetic fixture only.'})
        with self.assertRaisesRegex(ValueError,'undeclared.*norm'):contract({'spec':spec,'graph':graph})
        spec['definitions'].append(dict(id='D001',symbol='norm',type='function on the stated module',
            definition='norm is the specified size function.',depends_on=[],requires=[],binders=[],objects=[]))
        graph['inferences'][0]['definitions'].append('D001')
        self.assertFalse(contract({'spec':spec,'graph':graph})['mathematical_acceptance'])

    def test_unknown_library_name_is_not_misreported_as_an_available_definition(self):
        with patch('artifact_validation.run_lean',return_value={
            'exit_code':1,'stdout':'error: Unknown source declaration','stderr':'','wall_seconds':0}):
            with self.assertRaisesRegex(ValueError,'SOURCE_NOT_FOUND'):
                signature_probe(self.root/'missing','M001','nonexistent_neutral_name',
                                'Mathlib.Topology.MetricSpace.HausdorffDimension',1)

    def test_real_native_resolver_accepts_alias_and_records_actual_canonical_name(self):
        row=signature_probe(self.root/'alias','M001','isCompact_Icc',None,1)
        self.assertEqual(row['declaration'],'CompactIccSpace.isCompact_Icc')
        self.assertEqual(row['module'],'Mathlib.Topology.Order.Compact')
        self.assertTrue(row['signature'].startswith('@CompactIccSpace.isCompact_Icc :'))
        self.assertEqual(row['declaration_kind'],'theorem')

    def test_actual_predicate_definition_is_not_accepted_as_proved_theorem(self):
        with self.assertRaisesRegex(ValueError,'SOURCE_KIND_MISMATCH'):
            signature_probe(self.root/'predicate','M001','Nat.Prime',None,1)

    def test_exact_task_proof_copy_is_canonical_text_and_never_a_mathematical_pass(self):
        fixture=Path(__file__).parent/'fixtures/closed-addition'
        value={'spec':json.loads((fixture/'spec.json').read_text()),'graph':json.loads((fixture/'nl0.json').read_text())}
        text='Header.\nH001 states a=b. Equality symmetry gives b=a.\n'
        value['graph']['inferences'][0]['argument'][0]['text']={'from_task':'problem.txt','start_line':2,'end_line':2}
        contract=NL0Contract(self.root/'copied-proof',{'problem.txt':text})
        self.assertFalse(contract(value)['mathematical_acceptance'])
        self.assertEqual(value['graph']['inferences'][0]['argument'][0]['text'],text.splitlines(keepends=True)[1])
        bindings=json.loads((contract.directory/'task-text-bindings-0001.json').read_text())
        self.assertEqual(bindings['bindings'][0]['from_task'],'problem.txt')
        self.assertEqual(bindings['bindings'][0]['start_line'],2)
        self.assertNotIn('verdict',bindings)

    def test_literal_definition_copy_preserves_bytes_and_full_canonical_checks(self):
        import re
        text=(Path(__file__).parents[1]/'nl0/templates/guarded-definition-example.md').read_text()
        value=json.loads(re.search(r'```json\n(.*?)\n```',text,re.S).group(1))
        definition=value['spec']['definitions'][0]['definition']+'\r\n'
        value['spec']['definitions'][0]['definition']={'from_task':'input.txt','start_line':2,'end_line':2}
        contract=NL0Contract(self.root/'copied-definition',{'input.txt':'Header.\r\n'+definition})
        self.assertFalse(contract(value)['mathematical_acceptance'])
        self.assertEqual(value['spec']['definitions'][0]['definition'],definition)
        record=json.loads((contract.directory/'task-text-bindings-0001.json').read_text())
        self.assertEqual(record['bindings'][0]['path'],'/spec/definitions/0/definition')

    def test_literal_given_is_canonical_and_missing_graph_alias_is_bound(self):
        value=self.neutral();text=value['spec']['hypotheses'][0]['statement']+'\r\n'
        value['spec']['hypotheses'][0]['statement']={'from_task':'problem.md','start_line':1,'end_line':1}
        value['graph']['propositions'][0].pop('statement')
        contract=NL0Contract(self.root/'given-copy',{'problem.md':text})
        self.assertFalse(contract(value)['mathematical_acceptance'])
        self.assertEqual(value['spec']['hypotheses'][0]['statement'],text)
        self.assertEqual(value['graph']['propositions'][0]['statement'],text)

    def test_missing_edit_hash_is_located_and_cannot_apply_an_earlier_edit(self):
        base=self.neutral();text=json.dumps(base)
        patch={'base_input':'base.json','patches':[
            {'op':'replace','path':'/spec/full_target','value':'Changed.'},
            {'op':'replace_lines','path':'/graph/inferences/0/argument/0/text',
             'start_line':1,'end_line':1,'text':'Changed.\n'}]}
        with self.assertRaisesRegex(ValueError,'/patches/1') as failure:
            expand_submission(patch,{'base.json':text})
        self.assertIn("missing=['text_sha256']",str(failure.exception))
        self.assertEqual(json.loads(text),base)

    def test_invalid_module_locator_gives_exact_safe_omission_advice(self):
        for module in ['Mathlib/Topology/Basic','Mathlib.Topology.Basic; bad','']:
            with self.assertRaisesRegex(ValueError,'dotted Mathlib module name') as failure:
                signature_probe(self.root/'never-probed','M001','isCompact_singleton',module,1)
            self.assertIn('Omit this optional locator',str(failure.exception))
            self.assertFalse((self.root/'never-probed').exists())

    def test_definition_and_argument_copy_fail_atomically_on_foreign_or_bad_ranges(self):
        from copy import deepcopy
        import task_proof_text
        request={'from_task':'input.txt','start_line':1,'end_line':1}
        spec={'definitions':[{'definition':deepcopy(request)}]}
        for invalid in [dict(request,from_task='foreign'),dict(request,end_line=2),dict(request,start_line=True)]:
            graph={'inferences':[{'argument':[{'text':invalid}]}]}
            before=deepcopy((spec,graph))
            with self.assertRaisesRegex(ValueError,'TASK_TEXT'):
                task_proof_text.materialize(graph,{'input.txt':'Exact definition.\r\n'},spec=spec)
            self.assertEqual((spec,graph),before)

    def test_read_range_clamps_only_end_and_keeps_complete_hash(self):
        import hashlib
        text='First\r\nSecond\n'
        view=own_text_lines(text,1,200)
        self.assertEqual(view['actual_range'],{'start_line':1,'end_line':2})
        self.assertEqual(view['requested_range'],{'start_line':1,'end_line':200})
        self.assertEqual(''.join(row['text'] for row in view['lines']),text)
        self.assertEqual(view['text_sha256'],hashlib.sha256(text.encode()).hexdigest())
        for start,end in [(3,4),(1,251),(True,2),(1,True)]:
            with self.assertRaises(ValueError):own_text_lines(text,start,end)

    def test_preflight_reports_multiple_located_application_and_scope_errors(self):
        value=self.neutral();r=value['graph']['inferences'][1]
        r['applications']=[{'at':'S999','input':'M999'},{'at':r['argument'][0]['id'],'input':'H001'}]
        r['locals'][0]['end']='S998'
        messages=preflight(value['spec'],value['graph']);text='\n'.join(messages)
        for part in ['/applications/0','/applications/1','/locals/0','S999','M999','S998','actual argument IDs']:
            self.assertIn(part,text)
        self.assertEqual(preflight(self.neutral()['spec'],self.neutral()['graph']),[])

    def test_stale_inference_scope_owner_is_located_without_changing_it(self):
        value=self.neutral();local=value['graph']['inferences'][1]['locals'][0]
        local['scope']='R001/S001 through S002'
        text='\n'.join(preflight(value['spec'],value['graph']))
        self.assertIn('/graph/inferences/1/locals/0/scope',text)
        self.assertIn('actual owner=R002',text)
        self.assertEqual(local['scope'],'R001/S001 through S002')
        for label in ['R002/S001 through S002','Within this inference']:
            local['scope']=label;self.assertEqual(preflight(value['spec'],value['graph']),[])

    def test_one_explicit_source_use_synchronizes_views_without_rewriting_proof(self):
        template=Path(__file__).parents[1]/'nl0/templates/source-application-example.md'
        value=json.loads(template.read_text().split('```json\n',1)[1].split('\n```',1)[0])
        r=value['graph']['inferences'][0];app=r['applications'].pop()
        r['inputs']=[];r['argument'][0]['uses']=[]
        original_text=r['argument'][0]['text'];other=json.loads(json.dumps(value['graph']['inferences'][1]))
        contract=NL0Contract(self.root/'source-use',{'neutral-problem.txt':'Neutral source-use control.'})
        signature_probe(contract.directory,'M001','isCompact_singleton','Mathlib.Topology.Compactness.Compact',1)
        with self.assertRaises(ValueError):contract(value)
        call={'inference':'R001',**app};revision={'base_candidate':1,'source_uses':[call]}
        self.assertFalse(contract(revision)['mathematical_acceptance'])
        bound=revision['graph']['inferences'][0]
        self.assertEqual(bound['inputs'],['M001'])
        self.assertEqual(bound['argument'][0]['uses'],['M001'])
        self.assertEqual(bound['applications'],[app])
        self.assertEqual(bound['argument'][0]['text'],original_text)
        self.assertEqual(revision['graph']['inferences'][1],other)
        repeated={'base_candidate':2,'source_uses':[call]};contract(repeated)
        self.assertEqual(repeated['graph']['inferences'][0]['applications'],[app])
        frozen=contract.drafts[3]
        for bad in [{**call,'input':'H001'},{**call,'input':'M999'},{**call,'bindings':'Conflicting replacement.'}]:
            with self.assertRaises(ValueError):contract({'base_candidate':3,'source_uses':[bad]})
            self.assertEqual(contract.drafts[3],frozen)

    def test_library_probe_rejects_code_injection_before_execution(self):
        for name in ['Nat.add_zero\n#eval IO.println "bad"','Nat.add_zero;','Nat.add_zero`']:
            with self.assertRaises(ValueError):
                signature_probe(self.root,'M001',name,'Mathlib.Algebra.Group.Nat.Defs',1)
        with self.assertRaises(ValueError):
            signature_probe(self.root,'M001','Nat.add_zero','../Other',1)

    def test_model_visible_example_matches_the_authoring_contract(self):
        template=Path(__file__).parents[1]/'nl0/templates/submission-example.md'
        value=json.loads(template.read_text().split('```json\n',1)[1].split('\n```',1)[0])
        contract=NL0Contract(self.root/'example',{'problem.txt':'Neutral format example.'},
                             case_id=value['spec']['case_id'])
        self.assertFalse(contract(value)['mathematical_acceptance'])
        value['graph']['propositions'][0]['statement']='Different from the submitted specification.'
        with self.assertRaisesRegex(ValueError,'not an undisclosed controller H list'):
            contract(value)

    def test_model_visible_source_example_registers_actual_evidence_and_explicit_H(self):
        template=Path(__file__).parents[1]/'nl0/templates/source-application-example.md'
        value=json.loads(template.read_text().split('```json\n',1)[1].split('\n```',1)[0])
        contract=NL0Contract(self.root/'source-example',{'neutral-problem.txt':'If a=b, compactness transfers from {a} to {b}.'},
                             case_id=value['spec']['case_id'])
        signature_probe(contract.directory,'M001','isCompact_singleton',
                        'Mathlib.Topology.Compactness.Compact',1)
        self.assertFalse(contract(value)['mathematical_acceptance'])
        self.assertEqual(value['graph']['inferences'][1]['inputs'],['H001','N001'])
        self.assertIn('signature',value['graph']['propositions'][1]['source'])
        self.assertTrue(value['graph']['propositions'][1]['source']['evidence'])

    def test_source_renumbering_reuses_only_actual_metadata_and_remains_stable(self):
        template=Path(__file__).parents[1]/'nl0/templates/source-application-example.md'
        value=json.loads(template.read_text().split('```json\n',1)[1].split('\n```',1)[0])
        contract=NL0Contract(self.root/'renumbered',{'neutral-problem.txt':'If a=b, compactness transfers from {a} to {b}.'})
        signature_probe(contract.directory,'M017','isCompact_singleton','Mathlib.Topology.Compactness.Compact',1)
        original=json.loads(json.dumps(value['graph']['inferences']))
        self.assertFalse(contract(value)['mathematical_acceptance'])
        source=next(p['source'] for p in value['graph']['propositions'] if p['id']=='M001')
        report=json.loads((contract.directory/source['evidence'][0]['path']).read_text())
        self.assertEqual(set(report['sources']),{'M001'})
        self.assertEqual(report['metadata_reuse']['previous_bound_source_id'],'M017')
        self.assertEqual(value['graph']['inferences'],original)
        key=contract.author_check.status(1)['content_sha256']
        self.assertFalse(contract({'accept_candidate':1})['mathematical_acceptance'])
        self.assertEqual(contract.author_check.status(2)['content_sha256'],key)

    def test_report_level_alias_cannot_bind_an_absent_native_source_row(self):
        from runtime_config import load_lock
        template=Path(__file__).parents[1]/'nl0/templates/source-application-example.md'
        value=json.loads(template.read_text().split('```json\n',1)[1].split('\n```',1)[0])
        contract=NL0Contract(self.root/'empty-report',{'neutral-problem.txt':'Neutral source control.'})
        path=contract.directory/'library/empty/library-sources.json';path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'probe_version':1,'exit_code':0,'mathlib_commit':load_lock()['mathlib']['rev'],
            'sources':{},'requested_selector':{'declaration':'isCompact_singleton','module_hint':None}}))
        with self.assertRaisesRegex(ValueError,'SOURCE-PROBE: no actual successful'):
            contract(value)

    def test_source_ID_cannot_escape_case_before_metadata_rebinding(self):
        template=Path(__file__).parents[1]/'nl0/templates/source-application-example.md'
        value=json.loads(template.read_text().split('```json\n',1)[1].split('\n```',1)[0])
        value['graph']['propositions'][1]['id']='M001/../../outside'
        contract=NL0Contract(self.root/'unsafe-source-ID',{'problem.txt':'Neutral data control.'})
        with self.assertRaisesRegex(ValueError,'safe Mddd'):
            # Limit the check to the intended source-ID binding boundary.
            with patch('artifact_validation.preflight',return_value=[]):contract(value)
        self.assertFalse((self.root/'outside').exists())

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

    def test_importing_module_hint_is_corrected_only_from_actual_native_evidence(self):
        row=signature_probe(self.root/'wrong-module','M001',
            'hasFDerivAt_integral_of_dominated_of_fderiv_le',
            'Mathlib.MeasureTheory.Integral.IntegralEqImproper',1)
        self.assertEqual(row['module'],'Mathlib.Analysis.Calculus.ParametricIntegral')

    def test_library_metadata_is_bound_without_rewriting_mathematics(self):
        contract=NL0Contract(self.root/'bound',{'problem.txt':'Dimension of the empty set.'},case_id='empty')
        source_statement='For every metric space Y, the Hausdorff dimension of the empty subset of Y is zero.'
        conclusion='The Hausdorff dimension of the empty subset of X is zero.'
        source={'hypotheses':[],
                'declaration':'dimH_empty','module':'Mathlib.Topology.MetricSpace.HausdorffDimension'}
        value={'spec':{'format_version':2,'case_id':'empty','full_target':conclusion,'conclusion':conclusion,
            'parameters':[{'symbol':'X','type':'metric space'}],'hypotheses':[],'definitions':[],
            'logic':{'classical':False,'rules':['direct']}},
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
