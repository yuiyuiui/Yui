"""Own-stage coverage controls; synthetic verdicts are not mathematical audits."""
import harness_support
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from review_contract import ReviewContract, ReviewProgressGuard
from clean_stage import ArtifactStage
from execution_health import qualification, require_review_execution, StageFailure


class ReviewCompletionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.c=ReviewContract(self.root/'review',{'checks':{}},['/checks/a','/checks/b'],lambda v:{'actual':v})

    def tearDown(self):self.tmp.cleanup()

    def row(self,verdict='PASS'):
        return {'verdict':verdict,'notes':'Synthetic coverage fixture only.','locations':['/explicit']}

    def test_same_input_subjudgments_survive_reconstruction_without_completing_parent(self):
        self.c.bind_context({'source':'fixed source'})
        self.c.record('/checks/a','assessed',self.row(),part='definition D001')
        self.assertEqual(self.c.progress()['remaining'],['/checks/a','/checks/b'])
        restored=ReviewContract(self.root/'review',{'checks':{}},['/checks/a','/checks/b'],lambda v:{'actual':v})
        restored.bind_context({'source':'fixed source'})
        self.assertEqual(restored.progress(pointer='/checks/a',part='definition D001')['item']['judgment'],self.row())
        self.assertEqual(restored.progress()['part_count'],1)
        before=(self.root/'review/progress.json').read_bytes()
        stale=ReviewContract(self.root/'review',{'checks':{}},['/checks/a','/checks/b'],lambda v:v)
        with self.assertRaisesRegex(ValueError,'review inputs'):stale.bind_context({'source':'changed'})
        self.assertEqual((self.root/'review/progress.json').read_bytes(),before)
        with self.assertRaisesRegex(ValueError,'REVIEW_INCOMPLETE'):
            restored({'from_saved_review':True,'summary':{'findings':[]}})

    def test_unread_submission_continues_and_preserves_assessed_work(self):
        value={'checks':{'a':self.row()},'findings':[],
               'coverage':{'/checks/a':'assessed','/checks/b':'unread'}}
        with self.assertRaisesRegex(ValueError,'REVIEW_INCOMPLETE'):self.c(value)
        self.assertEqual(self.c.progress()['remaining'],['/checks/b'])
        self.assertEqual(self.c.items['/checks/a']['judgment'],self.row())
        self.c.record('/checks/b','assessed',self.row('UNVERIFIED'))
        complete={'from_saved_review':True,'summary':{'findings':[]}}
        self.c(complete)
        self.assertEqual(complete['checks']['b']['verdict'],'UNVERIFIED')
        self.assertNotIn('coverage',complete)

    def test_revised_packet_delivers_current_material_without_a_page_read_gate(self):
        from controller_common import write, manifest

        def stage(name, conclusion):
            directory=self.root/name
            inputs=directory/'inputs'; inputs.mkdir(parents=True)
            write(inputs/'packet.json',{'inference':{'text':conclusion}}); manifest(inputs)
            contract=ReviewContract(directory/'review',{'checks':{}},['/checks/a'],lambda value:{})
            return ArtifactStage(directory/'stage','Review the assigned packet.',phase='audit-a-packet-replay',
                inputs=inputs/'inputs.json',validator=contract,library=False)

        previous=stage('previous','The claim omits its domain.')
        revised=stage('revised','The claim is restricted to the nonzero domain.')
        try:
            revision=revised.prepare_role_revision(previous)
            self.assertNotEqual(revision['version_id'],revision['previous_version_id'])
            self.assertEqual(revision['changed_documents'],['packet.json'])
            self.assertIn(revision['version_id'],revised.input_prompt)
            self.assertIn('restricted to the nonzero domain',revised.task_inputs['packet.json'])
            artifact={'checks':{'a':self.row()},'coverage':{'/checks/a':'assessed'},'findings':[]}
            passed=revised.dispatch('submit_draft',{'artifact':artifact})
            self.assertTrue(passed['stage_complete'],passed)
        finally:
            previous.release_resources('USER_CANCELLED')
            revised.release_resources('USER_CANCELLED')

    def test_identical_partial_checkpoint_cannot_invent_progress_or_duplicate_history(self):
        self.c.bind_context({'source':'fixed source'})
        guard=ReviewProgressGuard(self.c)
        args={'pointer':'/checks/a','part':'definition D001','coverage':'assessed','judgment':self.row()}
        guard.observe('record_review_item',args,self.c.record(**args))
        for _ in range(3):
            guard.observe('submit_draft',{'artifact':{'from_saved_review':True,'summary':{}}},
                          {'accepted':False,'error':'Synthetic missing parent judgment'})
        self.assertIsNotNone(guard.blocked)
        guard.observe('record_review_item',args,self.c.record(**deepcopy(args)))
        self.assertIsNotNone(guard.blocked)
        self.assertEqual(len(list((self.c.directory/'parts').glob('*/*.json'))),1)

    def test_missing_judgment_cannot_be_synthesized_from_summary(self):
        self.c.record('/checks/a','assessed',self.row())
        with self.assertRaisesRegex(ValueError,'may not replace'):
            self.c({'from_saved_review':True,'summary':{'checks':{'b':self.row()},'findings':[]}})
        self.assertEqual(self.c.items['/checks/b']['coverage'],'unread')

    def test_malformed_full_update_preserves_previous_judgments(self):
        self.c.record('/checks/a','assessed',self.row())
        checkpoint=self.c.progress()
        invalid={'checks':{'a':self.row('FAIL'),'b':{}},
                 'coverage':{'/checks/a':'assessed','/checks/b':'assessed'}}
        with self.assertRaises(ValueError):
            self.c(invalid)
        self.assertEqual(self.c.progress(),checkpoint)

    def test_record_acknowledgment_does_not_repeat_prior_long_judgments(self):
        long_note=self.row();long_note['notes']='Preserved reviewer evidence. '*1000
        first=self.c.record('/checks/a','assessed',long_note)
        second=self.c.record('/checks/b','assessed',self.row())
        self.assertEqual(first['remaining'],['/checks/b'])
        self.assertEqual(second['assessed_count'],2)
        self.assertNotIn('items',second)
        self.assertNotIn('required',second)
        self.assertEqual(self.c.progress()['items']['/checks/a']['judgment'],long_note)

    def test_early_real_blocker_keeps_untouched_work_incomplete(self):
        finding={'verdict':'FAIL','explanation':'Synthetic located defect.','locations':['/explicit']}
        with self.assertRaises(ValueError):self.c.blocker(finding)
        self.c.record('/checks/a','assessed',self.row('FAIL'))
        result=self.c.blocker(finding)
        self.assertEqual(result['status'],'REVIEW_BLOCKED_INCOMPLETE')
        self.assertEqual(result['coverage']['remaining'],['/checks/b'])

    def test_global_complete_assessment_collects_all_findings_before_return(self):
        self.c.complete_assessment=True
        self.c.record('/checks/a','assessed',self.row('FAIL'))
        finding={'verdict':'FAIL','explanation':'Synthetic first global defect.','locations':['/explicit']}
        with self.assertRaisesRegex(ValueError,'Complete all assigned global checks'):
            self.c.blocker(finding)
        stage=ArtifactStage(self.root/'global-stage','Synthetic global review.',phase='audit-a-global',library=False,validator=self.c)
        import shutil
        try:
            self.assertNotIn('submit_review_blocker',stage.tool_names)
            self.c.record('/checks/b','assessed',self.row('FAIL'))
            value={'from_saved_review':True,'summary':{'findings':[finding,dict(finding,explanation='Synthetic second defect.')]}}
            self.c(value)
            self.assertEqual(len(value['findings']),2)
            self.assertEqual([row['verdict'] for row in value['checks'].values()],['FAIL','FAIL'])
        finally:shutil.rmtree(stage.work)

    def test_stage_tools_keep_partial_review_inside_current_stage(self):
        stage=ArtifactStage(self.root/'stage','Synthetic review tool control.',phase='review',library=False,validator=self.c)
        import shutil
        try:
            self.assertIn('record_review_item',stage.tool_names)
            self.assertNotIn('report_obstacle',stage.tool_names)
            recorded=stage.dispatch('record_review_item',{'pointer':'/checks/a','coverage':'assessed','judgment':self.row()})
            self.assertFalse(recorded['stage_complete'])
            draft={'from_saved_review':True,'summary':{'findings':[]}}
            result=stage.dispatch('submit_draft',{'artifact':draft})
            self.assertFalse(result['accepted']);self.assertIsNone(stage.accepted)
            stage.dispatch('record_review_item',{'pointer':'/checks/b','coverage':'assessed','judgment':self.row('UNVERIFIED')})
            result=stage.dispatch('submit_draft',{'artifact':draft})
            self.assertTrue(result['stage_complete'])
            self.assertEqual(stage.accepted['checks']['b']['verdict'],'UNVERIFIED')
        finally:shutil.rmtree(stage.work)


class QualificationTests(unittest.TestCase):
    def test_missing_usage_does_not_erase_qualified_actual_judgment(self):
        row={'status':'ACCEPTED','execution_health':'NO_RECORDED_FAULT','usage':{'complete':False},
             'exposure':{'status':'NATIVE-CODEX-CONTEXT-CHECK-PASSED','configured_model':__import__('native_carrier').MODEL,'errors':[]}}
        self.assertTrue(require_review_execution(row,'synthetic-result')['execution_qualified'])
        self.assertFalse(qualification(row)['measurement_valid'])
        bad=deepcopy(row);bad['exposure']['configured_model']=''
        with self.assertRaises(StageFailure):require_review_execution(bad,'synthetic-result')
        bad=deepcopy(row);bad['execution_health']='UNVERIFIED'
        with self.assertRaises(StageFailure):require_review_execution(bad,'synthetic-result')


if __name__=='__main__':unittest.main()
