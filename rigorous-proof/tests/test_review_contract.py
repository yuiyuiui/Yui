"""Own-stage coverage controls; synthetic verdicts are not mathematical audits."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from review_contract import ReviewContract
from clean_stage import ArtifactStage
from execution_health import qualification, require_review_execution, StageFailure


class ReviewCompletionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.c=ReviewContract(self.root/'review',{'checks':{}},['/checks/a','/checks/b'],lambda v:{'actual':v})

    def tearDown(self):self.tmp.cleanup()

    def row(self,verdict='PASS'):
        return {'verdict':verdict,'notes':'Synthetic coverage fixture only.','locations':['/explicit']}

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

    def test_missing_judgment_cannot_be_synthesized_from_summary(self):
        self.c.record('/checks/a','assessed',self.row())
        with self.assertRaisesRegex(ValueError,'may not replace'):
            self.c({'from_saved_review':True,'summary':{'checks':{'b':self.row()},'findings':[]}})
        self.assertEqual(self.c.items['/checks/b']['coverage'],'unread')

    def test_early_real_blocker_keeps_untouched_work_incomplete(self):
        finding={'verdict':'FAIL','explanation':'Synthetic located defect.','locations':['/explicit']}
        with self.assertRaises(ValueError):self.c.blocker(finding)
        self.c.record('/checks/a','assessed',self.row('FAIL'))
        result=self.c.blocker(finding)
        self.assertEqual(result['status'],'REVIEW_BLOCKED_INCOMPLETE')
        self.assertEqual(result['coverage']['remaining'],['/checks/b'])

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
             'exposure':{'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED','actual_model_ids':['gpt-6-luna'],
                         'standard_tier_verified':True}}
        self.assertTrue(require_review_execution(row,'synthetic-result')['execution_qualified'])
        self.assertFalse(qualification(row)['measurement_valid'])
        bad=deepcopy(row);bad['exposure']['actual_model_ids']=[]
        with self.assertRaises(StageFailure):require_review_execution(bad,'synthetic-result')
        bad=deepcopy(row);bad['execution_health']='UNVERIFIED'
        with self.assertRaises(StageFailure):require_review_execution(bad,'synthetic-result')


if __name__=='__main__':unittest.main()
