"""Actual controller/merge/receipt paths with scripted, explicitly synthetic actors."""
import harness_support
from audit_a_fixtures import synthetic_stage
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

import audit_a_campaign as campaign
import case_runner
from clean_stage import ArtifactStage
from controller_common import write
import concurrency
import nl0_review_loop as loop
from run_resources import retention


class NL0ReviewLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'inputs').mkdir();(self.root/'inputs/problem.md').write_text('Synthetic controller fixture only.')
        self.serial=concurrency.Budget(concurrency.resolve(1),role='preparation_review')
        self.local=concurrency.Budget(concurrency.resolve(2),role='audit_r')
        self.calls=[];self.lock=threading.Lock();self.counts={};self.workspaces=[]

    def tearDown(self):
        for path in self.workspaces:shutil.rmtree(path,ignore_errors=True)
        self.tmp.cleanup()

    def exercise(self,global_failure=False,global_escalation=False,both_local_fail=False,remove_blocked_node=False):
        turns=threading.Barrier(2) if both_local_fail else None
        def author(job,directory,budget,*,baseline=None,obligations=None):
            stage=ArtifactStage(directory/'stage','Synthetic global author assignment.',phase='nl0-authoring',budget=budget,library=False)
            self.workspaces.append(stage.work)
            source=directory/'stage/case'
            loop.copy_source(baseline or harness_support.CORE/'tests/fixtures/closed-addition',source)
            if baseline:
                graph=json.loads((source/'nl0.json').read_text())
                graph['inferences'][0]['argument'][0]['text']+=' Global exposition repaired.'
                if remove_blocked_node:
                    graph['propositions']=[p for p in graph['propositions'] if p['id']!='N001']
                    graph['inferences']=[r for r in graph['inferences'] if r['id']=='R002']
                    r=graph['inferences'][0];r['inputs']=['H001']
                    r['argument'][1]['uses']=['H001']
                    r['argument'][1]['text']='H001 gives a=b. F001 gives c=a, hence c=b. Substituting c=a+0 yields a+0=b.'
                write(source/'nl0.json',graph)
            stage.execute();return source

        def execute(stage):
            role=stage.role_session['role']
            with self.lock:
                n=self.counts.get(role,0)+1;self.counts[role]=n
                self.calls.append((role,n,stage.role_session['restored_role']))
                self.workspaces.append(stage.work)
            if stage.mode=='nl0-authoring':
                artifact={'synthetic':'global draft'}
                exposure={'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED','actual_model_ids':[stage.model],'standard_tier_verified':True}
                result={'status':'ACCEPTED','execution_health':'NO_RECORDED_FAULT','exposure':exposure,'usage':{'complete':True}}
            elif stage.mode=='nl0-local-repair':
                validator=stage.validator
                if global_escalation and n==1:
                    artifact={'status':'GLOBAL_REPAIR_REQUIRED','explanation':'Synthetic shared context clarification.', 'locations':['/inference/argument']}
                else:
                    row=deepcopy(validator.original);row['argument'][0]['text']+=' Local explanation completed.'
                    artifact={'inference':row}
                validator(artifact)
                exposure={'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED','actual_model_ids':[stage.model],'standard_tier_verified':True}
                result={'status':'ACCEPTED','execution_health':'NO_RECORDED_FAULT','exposure':exposure,'usage':{'complete':True}}
            else:
                failed=(role=='audit-a-global' and global_failure and n==1)
                local_failed=(role.startswith('audit-a:') and n==1 and (both_local_fail or role=='audit-a:R001'))
                result,artifact=synthetic_stage(stage.logs.parent,global_verdict='FAIL' if failed else 'PASS',local_verdict='FAIL' if local_failed else 'PASS')
                if remove_blocked_node and role=='audit-a:R001' and n==1:
                    packet=json.loads((stage.logs.parent/'packet.json').read_text());location='/inference/argument/0/text'
                    finding={'verdict':'FAIL','explanation':'Synthetic located shared-context defect.',
                        'locations':[location],'quotation':{'location':location,'text':packet['inference']['argument'][0]['text']}}
                    stage.validator.record(sorted(stage.validator.required)[0],'assessed',
                        {'verdict':'FAIL','notes':finding['explanation'],'locations':[location]})
                    artifact=stage.validator.blocker(finding)
                    result.update(status='BLOCKED',task_outcome='MATHEMATICAL_REVIEW_FAILED')
            if turns and (role.startswith('audit-a:') or role.startswith('nl0-author:')):
                self.assertLessEqual(self.local.report()['active_model_stages'],2)
                self.assertEqual(self.serial.report()['active_model_stages'],0)
                turns.wait(timeout=8)
            stage.accepted=artifact;stage.submission_closed=True
            stage.workspace_retention=retention(stage.work,getattr(stage,'workspace_owner_logs',stage.logs))
            result.update(temporary_workspace_removed=False,workspace_retention=stage.workspace_retention,role_session=stage.role_session)
            write(stage.logs/'accepted.json',artifact);write(stage.logs/'result.json',result)
            return result,artifact

        with patch.object(ArtifactStage,'_execute',execute):
            result=loop.run({'root':str(self.root),'case':'closed-addition','policy':'normal'},self.serial,self.local,
                lambda *a,**k:None,author,case_runner.repair_obligations)
        data=campaign.nl0.validate(result['graph'],result['spec'],result['audit_a'])[0]
        self.assertTrue(data['current_standard_receipt_valid'])
        self.assertEqual(self.local.report()['active_model_stages'],0)
        return result

    def test_global_revision_then_parallel_local_repair_merge(self):
        result=self.exercise(global_failure=True)
        self.assertEqual(self.counts['nl0-author'],2)
        self.assertEqual(self.counts['audit-a-global'],2)
        self.assertEqual(self.counts['nl0-author:R001'],1)
        self.assertEqual(self.counts['audit-a:R001'],2)
        self.assertEqual(self.counts['audit-a:R002'],1)
        first_local=next(i for i,row in enumerate(self.calls) if row[0].startswith('audit-a:'))
        self.assertGreater(first_local,next(i for i,row in enumerate(self.calls) if row[:2]==('audit-a-global',2)))
        final=json.loads(Path(result['graph']).read_text())
        self.assertIn('Local explanation completed.',final['inferences'][0]['argument'][0]['text'])

    def test_local_global_escalation_restores_global_role_and_rechecks_affected_packets(self):
        self.exercise(global_escalation=True)
        self.assertTrue(any(role=='nl0-author' and restored for role,n,restored in self.calls))
        self.assertGreaterEqual(self.counts['audit-a:R001'],2)
        self.assertEqual(self.serial.report()['active_model_stages'],0)

    def test_reviewers_and_repair_authors_share_n_active_slots_while_idle_roles_remain(self):
        self.exercise(both_local_fail=True)
        self.assertEqual(self.local.report()['observed_peak_model_stages'],2)
        for rid in ('R001','R002'):
            self.assertEqual(self.counts['nl0-author:'+rid],1)
            self.assertEqual(self.counts['audit-a:'+rid],2)

    def test_global_revision_can_remove_an_obsolete_blocked_node_and_finalize_current_graph(self):
        result=self.exercise(global_escalation=True,remove_blocked_node=True)
        self.assertEqual({r['id'] for r in json.loads(Path(result['graph']).read_text())['inferences']},{'R002'})
        stage=self.root/'audit-a/local-0001-R001-0001/R001/stage'
        self.assertEqual(json.loads((stage/'result.json').read_text())['status'],'BLOCKED')
        self.assertTrue(json.loads((stage/'role-completion.json').read_text())['superseded_by_accepted_revision'])

    def test_node_patch_cannot_change_public_interface_or_another_node(self):
        source=self.root/'source';loop.copy_source(harness_support.CORE/'tests/fixtures/closed-addition',source)
        validator=loop.NodePatch(source,'R001',self.root/'author')
        row=deepcopy(validator.original);row['inputs']=[]
        with self.assertRaisesRegex(ValueError,'Public node interface changed'):validator({'inference':row})
        with self.assertRaisesRegex(ValueError,'Submit'):validator({'inference':validator.original,'other_node':{}})
        self.assertIsNone(validator.selected)


if __name__=='__main__':unittest.main()
