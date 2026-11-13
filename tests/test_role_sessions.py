"""Conversation ownership and idle-slot controls without any model service."""
import harness_support
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from clean_stage import ArtifactStage
from controller_common import write
from role_sessions import Sessions
import concurrency


class RoleSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.sessions=Sessions();self.stages=[]
        self.budget=concurrency.Budget(concurrency.resolve(1),role='preparation_review')

    def tearDown(self):
        for stage in self.stages:shutil.rmtree(stage.work,ignore_errors=True)
        for entry in self.sessions.roles.values():shutil.rmtree(entry['stage'].work,ignore_errors=True)
        self.tmp.cleanup()

    def stage(self,name):
        stage=ArtifactStage(self.root/name,'Synthetic role protocol only.',phase='interface-authoring',
                            budget=self.budget,library=False)
        self.stages.append(stage);return stage

    @staticmethod
    def complete(stage):
        stage.submission_closed=True;stage.accepted={'own':'synthetic artifact'}
        stage.thread_id=getattr(stage,'thread_id','retained-native-thread')
        stage.rpc_id=41;stage.allowed_user_messages.add('own authorized history')
        stage.model_calls['own-call']={'id':'own-item'}
        result={'status':'ACCEPTED','temporary_workspace_removed':True}
        write(stage.logs/'result.json',result);write(stage.logs/'accepted.json',stage.accepted)
        return result,stage.accepted

    def test_revision_keeps_conversation_and_releases_idle_slot(self):
        first=self.stage('first')
        with patch.object(ArtifactStage,'_execute',self.complete):
            with self.sessions.use('author'):first.execute()
            self.assertEqual(self.budget.report()['active_model_stages'],0)
            second=self.stage('second')
            with self.sessions.use('author'):second.execute()
        active=self.sessions.roles['author']['stage']
        self.assertIs(active,first)
        self.assertEqual(active.thread_id,'retained-native-thread')
        self.assertEqual(active.model_calls['own-call'],{'id':'own-item'})
        self.assertIn('own authorized history',active.allowed_user_messages)
        self.assertEqual(active.rpc_id,41)
        self.assertGreaterEqual(len(active.role_session['prior_submissions']),2)
        self.assertFalse(second.work.exists())
        self.assertEqual(self.budget.report()['active_model_stages'],0)


    def test_author_and_reviewer_are_different_role_conversations(self):
        author=self.stage('author');reviewer=self.stage('reviewer')
        with patch.object(ArtifactStage,'_execute',self.complete):
            with self.sessions.use('author'):author.execute()
            with self.sessions.use('reviewer'):reviewer.execute()
        self.assertIsNot(self.sessions.roles['author']['stage'],self.sessions.roles['reviewer']['stage'])
        self.assertEqual(self.budget.report()['observed_peak_model_stages'],1)

    def test_private_parallel_workers_do_not_reenter_the_running_parent_role(self):
        import proof_obligations
        import role_sessions
        import runtime_config
        profiles={key:{'id':'gpt-6.1-sol','reasoning_effort':effort,
                       'speed':'standard','automatic_fallback':False}
                  for key,effort in [('nl0','max'),('lean','xhigh')]}
        with runtime_config.use_profiles(profiles):
            parent=self.stage('parent')
            def solve(item,budget):
                child=ArtifactStage(self.root/f'child-{item}','Synthetic private task.',
                    phase='basis-frontier',budget=budget,library=False)
                self.stages.append(child)
                child.execute()
                self.assertIsNone(role_sessions.current())
                self.assertEqual(child.model_selection['reasoning_effort'],'max')
                self.assertEqual(child.model_selection['selection_origin'],'explicit_run')
                self.assertFalse(hasattr(child,'role_session'))
                return item
            def execute(stage):
                if stage is parent:
                    self.assertFalse(getattr(parent,'submission_closed',False))
                    self.assertEqual(proof_obligations.parallel(parent,[1,2],solve),[1,2])
                    self.assertEqual(role_sessions.current(),(self.sessions,'parent'))
                return self.complete(stage)
            def fail_fault(stage,error,**kwargs):
                raise error
            with patch.object(ArtifactStage,'_execute',execute), \
                    patch.object(ArtifactStage,'pause_error',fail_fault):
                with self.sessions.use('parent'):parent.execute()
        self.assertEqual(set(self.sessions.roles),{'parent'})
        self.assertIs(self.sessions.roles['parent']['stage'],parent)

    def test_changed_prior_evidence_cannot_be_reused(self):
        first=self.stage('first')
        with patch.object(ArtifactStage,'_execute',self.complete):
            with self.sessions.use('author'):first.execute()
            write(first.logs/'accepted.json',{'changed':'artifact'})
            with self.sessions.use('author'):
                with self.assertRaisesRegex(ValueError,'evidence changed'):self.stage('second').execute()

    def test_only_successful_specified_boundary_releases_task_and_preserves_outputs(self):
        first=self.stage('first');gate=self.root/'gate.json';write(gate,{'synthetic':'accepted boundary'})
        with patch.object(ArtifactStage,'_execute',self.complete):
            with self.sessions.use('author'):first.execute()
        with self.assertRaises(ValueError):self.sessions.close(['author'],'FAULT',[gate])
        self.sessions.close(['author'],'GLOBAL_REVIEW_PASSED',[gate])
        self.assertFalse(first.work.exists());self.assertTrue((first.logs/'accepted.json').is_file())
        self.assertNotIn('author',self.sessions.roles)
        restored=self.stage('restored')
        with patch.object(ArtifactStage,'_execute',self.complete):
            with self.sessions.use('author'):restored.execute()
        self.assertTrue(restored.role_session['restored_role'])
        self.assertIn(str(first.logs/'accepted.json'),
                      [row['path'] for row in restored.role_session['prior_submissions']])
        self.assertIn('fresh carrier',restored.input_prompt)
        self.assertIs(self.sessions.roles['author']['stage'],restored)

    def test_closed_role_restoration_rejects_changed_saved_handoff(self):
        first=self.stage('first');gate=self.root/'gate.json';write(gate,{'synthetic':'accepted boundary'})
        with patch.object(ArtifactStage,'_execute',self.complete):
            with self.sessions.use('author'):first.execute()
        self.sessions.close(['author'],'INTERFACE_FROZEN',[gate])
        write(first.logs/'accepted.json',{'changed':'saved artifact'})
        with patch.object(ArtifactStage,'_execute',autospec=True,side_effect=self.complete) as execute:
            with self.sessions.use('author'):
                with self.assertRaisesRegex(ValueError,'Saved role handoff changed'):
                    self.stage('restored').execute()
            execute.assert_not_called()

    def test_obsolete_blocked_review_can_close_only_at_local_acceptance_without_rewriting_verdict(self):
        first=self.stage('first');gate=self.root/'gate.json';write(gate,{'synthetic':'accepted replacement'})
        with patch.object(ArtifactStage,'_execute',self.complete):
            with self.sessions.use('audit-a:R001'):first.execute()
        blocked={'status':'BLOCKED','task_outcome':'MATHEMATICAL_REVIEW_FAILED','execution_health':'NO_RECORDED_FAULT'}
        write(first.logs/'result.json',blocked)
        write(first.logs/'accepted.json',{'status':'REVIEW_BLOCKED_INCOMPLETE','mathematical_acceptance':False})
        with self.assertRaises(ValueError):self.sessions.close_all('LOCAL_REVIEWS_PASSED',[gate])
        with self.assertRaises(ValueError):self.sessions.close_all('GLOBAL_REVIEW_PASSED',[gate],superseded={'audit-a:R001'})
        for defect in ({'execution_fault':'Synthetic retained fault'},{'execution_health':'FAULT'},{'status':'UNFINISHED'}):
            write(first.logs/'result.json',{**blocked,**defect})
            with self.assertRaises(ValueError):self.sessions.close_all('LOCAL_REVIEWS_PASSED',[gate],superseded={'audit-a:R001'})
            self.assertIn('audit-a:R001',self.sessions.roles)
        write(first.logs/'result.json',blocked)
        self.sessions.close_all('LOCAL_REVIEWS_PASSED',[gate],superseded={'audit-a:R001'})
        self.assertEqual(json.loads((first.logs/'result.json').read_text()),blocked)
        self.assertFalse(first.work.exists())
        self.assertTrue(json.loads((first.logs/'role-completion.json').read_text())['superseded_by_accepted_revision'])

    def test_removed_proof_role_closes_only_at_final_acceptance_preserving_obstruction(self):
        first=self.stage('removed');gate=self.root/'gate.json';write(gate,{'synthetic':'final accepted proof'})
        def handoff(stage):
            stage.submission_closed=True
            result={'status':'REPAIR_REQUESTED','execution_health':'NO_RECORDED_FAULT'}
            write(stage.logs/'result.json',result)
            return result,None
        with patch.object(ArtifactStage,'_execute',handoff):
            with self.sessions.use('lean:T001'):first.execute()
        for boundary,superseded in [('INTERFACE_FROZEN',{'lean:T001'}),('WORKFLOW_FINALIZED',set())]:
            with self.subTest(boundary=boundary,superseded=superseded),self.assertRaises(ValueError):
                self.sessions.close_all(boundary,[gate],superseded=superseded)
            self.assertTrue(first.work.exists())
        original=json.loads((first.logs/'result.json').read_text())
        write(first.logs/'result.json',{**original,'execution_fault':'Synthetic runtime fault'})
        with self.assertRaises(ValueError):
            self.sessions.close_all('WORKFLOW_FINALIZED',[gate],superseded={'lean:T001'})
        write(first.logs/'result.json',original)
        self.sessions.close_all('WORKFLOW_FINALIZED',[gate],superseded={'lean:T001'})
        self.assertEqual(json.loads((first.logs/'result.json').read_text()),original)
        self.assertFalse(first.work.exists())
        receipt=json.loads((first.logs/'role-completion.json').read_text())
        self.assertEqual(receipt['submission']['path'],str(first.logs/'result.json'))
        self.assertTrue(receipt['superseded_by_accepted_revision'])


if __name__=='__main__':unittest.main()
