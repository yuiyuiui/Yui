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
        stage.model_history['own-item']={'id':'own-item'}
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
        self.assertIn('own-item',active.model_history)
        self.assertIn('own authorized history',active.allowed_user_messages)
        self.assertEqual(active.rpc_id,41)
        self.assertGreaterEqual(len(active.role_session['prior_submissions']),2)
        self.assertFalse(second.work.exists())
        self.assertEqual(self.budget.report()['active_model_stages'],0)

    def test_second_submission_uses_the_same_live_relay_with_fresh_stage_evidence(self):
        from relay_fixtures import RelayFixture
        responses=[]
        with RelayFixture(self.root/'wire') as wire:
            first=wire.stage;first.budget=self.budget
            first_thread=first.thread_id='same-native-role'
            port=wire.port
            def complete(stage):
                stage.initial_user_message='Synthetic transport only.'
                stage.allowed_user_messages.add(stage.initial_user_message)
                responses.append(wire.exchange())
                return self.complete(stage)
            with patch.object(ArtifactStage,'_execute',complete):
                with self.sessions.use('author'):first.execute()
                second=self.stage('next-assignment')
                with self.sessions.use('author'):second.execute()
            self.assertEqual([r.split(b'\r\n',1)[0] for r in responses],[b'HTTP/1.1 200 OK']*2)
            self.assertEqual(wire.port,port);self.assertEqual(first.thread_id,first_thread)
            self.assertEqual(first.logs,second.logs)
            self.assertTrue((first.logs/'response-0001.sse').is_file())
            self.assertEqual(len(wire.calls),2)

    def test_author_and_reviewer_are_different_role_conversations(self):
        author=self.stage('author');reviewer=self.stage('reviewer')
        with patch.object(ArtifactStage,'_execute',self.complete):
            with self.sessions.use('author'):author.execute()
            with self.sessions.use('reviewer'):reviewer.execute()
        self.assertIsNot(self.sessions.roles['author']['stage'],self.sessions.roles['reviewer']['stage'])
        self.assertEqual(self.budget.report()['observed_peak_model_stages'],1)

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


if __name__=='__main__':unittest.main()
