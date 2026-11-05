"""Basis correspondence coverage, frozen evidence, independent execution and invalidation."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

import harness_support
from basis_fixtures import artifact, checked_context, dependency, synthetic_review
import basis
import basis_review
from clean_stage import ArtifactStage
from controller_common import bind, write
from execution_health import StageFailure
import ir
from role_sessions import Sessions


class BasisFidelityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch=tempfile.TemporaryDirectory()
        cls.revision=Path(cls.scratch.name).resolve()/'2basis/0001'
        cls.value=artifact(dependency(),dependency('B002',2),dependency('B003',3))
        cls.context=checked_context(cls.revision,cls.value)
        cls.packet=ir.load(cls.revision/'review/inputs'/basis_review.PACKET)
        cls.batch=cls.revision/'review/assessment.json'

    @classmethod
    def tearDownClass(cls):cls.scratch.cleanup()

    def test_one_review_for_all_formal_items_reports_the_real_proposition(self):
        self.assertEqual(self.packet['required'],['B001','B002'])
        self.assertEqual({ref['path'] for ref in ir.load(self.context['semantic_review']['path'])['assessments'].values()},
                         {str(self.batch)})
        item=self.packet['items']['B002']
        self.assertIn('∀',item['actual_type'])
        self.assertIn('Nat',item['actual_type'])
        self.assertTrue(item['signature'])
        self.assertNotIn('actual_type',self.packet['items']['B003'])
        self.assertEqual(basis.verify_context(self.context),self.value)

    def test_affected_dependency_component_and_common_target_force_fresh_assessment(self):
        original=basis_review.item_keys(self.packet)
        def changed(transform):
            candidate=deepcopy(self.packet);transform(candidate)
            keys=basis_review.item_keys(candidate)
            return {k for k in original if original[k]!=keys[k]}
        self.assertEqual(changed(lambda p:p['items']['B003'].update(statement='Modified internal use.')),{'B001'})
        self.assertEqual(changed(lambda p:p['items']['B002'].update(actual_type='True')),{'B002'})
        self.assertEqual(changed(lambda p:p.update(proof='Changed common route.')),{'B001','B002'})
        self.assertEqual(changed(lambda p:p['documents'].update({'problem.md':'different bytes'})),{'B001','B002'})

    def test_exact_rows_and_coverage_reject_missing_foreign_unassessed_and_empty_judgments(self):
        raw=ir.load(self.batch.parent/'stage/accepted.json')
        required=self.packet['required']
        for transform in [lambda v:v['items'].pop('B002'),
                          lambda v:v['items'].update(B099=deepcopy(v['items']['B001'])),
                          lambda v:v['items']['B001'].update(locations=['/items/B002/statement']),
                          lambda v:v['items']['B001'].update(source=' '),
                          lambda v:v['items']['B001'].update(verdict='assessed')]:
            candidate=deepcopy(raw);transform(candidate)
            with self.assertRaises(ValueError):basis_review.validate_rows(candidate,required)
        extra=deepcopy(raw);extra['items']['B001']['locations'].reverse();extra['items']['B001']['locations'].append('/proof')
        basis_review.validate_rows(extra,required,packet=self.packet)
        extra['items']['B001']['locations'].append('/typo')
        with self.assertRaises(ValueError):basis_review.validate_rows(extra,required,packet=self.packet)
        with self.assertRaises(ValueError):basis_review.validate_rows(raw,required,{'basis_id':'B001'})
        historic=deepcopy(self.context);historic['version']=basis.VERSION;historic.pop('semantic_review')
        with self.assertRaises(ValueError):basis.verify_context(historic)

    def test_rebinding_a_fabricated_result_or_an_edited_transcript_still_fails(self):
        original=self.batch.read_bytes()
        stage=self.batch.parent/'stage'
        cases=[('tools.jsonl',''),
               ('result.json',json.dumps({**ir.load(stage/'result.json'),'role_session':{'role':'basis-author'}})),
               ('accepted.json',json.dumps({'items':{'B001':{'verdict':'PASS'}}}))]
        for name,fake in cases:
            path=stage/name;before=path.read_bytes()
            try:
                path.write_text(fake)
                record=json.loads(original)
                record['execution']=[bind(stage/n) for n in basis_review.STAGE_FILES]
                write(self.batch,record)
                with self.assertRaises(ValueError):basis_review.read_batch(bind(self.batch))
            finally:
                path.write_bytes(before);self.batch.write_bytes(original)
        self.assertEqual(basis.verify_context(self.context),self.value)

    def test_reused_pass_and_nonpass_keep_exact_original_evidence(self):
        base=self.revision.parent;history={}
        def assess(number,value,fail=False):
            out=base/number;path=out/'stage/accepted.json';write(path,value)
            context={**self.context,'basis':bind(path)}
            sessions=Sessions()
            calls=[]
            def review(stage):
                packet=ir.load(stage.logs.parent/'inputs'/basis_review.PACKET)
                calls.append(packet['required'])
                return synthetic_review(stage,{'B002':'UNVERIFIED'} if fail else {})
            with patch.object(ArtifactStage,'_execute',review):
                try:
                    ref,issues=basis_review.assess(out,context,value,sessions,None,history)
                finally:
                    if (out/'review/report.json').exists():
                        sessions.close_all('BASIS_PREPARED',[out/'review/report.json'])
            return calls,ref,issues
        calls,first,issues=assess('0002',self.value,True)
        self.assertEqual(calls,[['B001','B002']]);self.assertEqual(set(issues),{'B002'})
        with self.assertRaises(StageFailure) as exc:assess('0003',self.value)
        self.assertEqual(exc.exception.result['status'],'REPAIR_CYCLE')
        second=deepcopy(self.value);second['dependencies'][1]['statement']+=' Revised natural-number scope.'
        calls,ref,issues=assess('0004',second)
        self.assertEqual(calls,[['B002']]);self.assertFalse(issues)
        reports=[ir.load(x['path'])['assessments'] for x in (first,ref)]
        self.assertEqual(reports[0]['B001'],reports[1]['B001'])
        self.assertNotEqual(reports[0]['B002'],reports[1]['B002'])

    def test_complete_saved_submissions_from_checks_or_individual_judgments_verify(self):
        for mode in ('check','record'):
            with self.subTest(mode=mode):
                out=self.revision.parent/('saved-'+mode)
                path=out/'stage/accepted.json';write(path,self.value)
                context={**self.context,'basis':bind(path)}
                sessions=Sessions()
                with patch.object(ArtifactStage,'_execute',lambda stage:synthetic_review(stage,saved_via=mode)):
                    ref,issues=basis_review.assess(out,context,self.value,sessions,None,{})
                self.assertFalse(issues)
                sessions.close_all('BASIS_PREPARED',[out/'review/report.json'])
                self.assertFalse(basis_review.verify(ref,context,self.value))

    def test_empty_scope_records_an_empty_report_without_a_reviewer(self):
        with tempfile.TemporaryDirectory() as raw,patch.object(ArtifactStage,'execute',side_effect=AssertionError('Unexpected model call')):
            context=checked_context(Path(raw),artifact())
            self.assertEqual(ir.load(context['semantic_review']['path'])['assessments'],{})
            self.assertFalse((Path(raw)/'review/stage').exists())
            self.assertEqual(basis.verify_context(context),artifact())
