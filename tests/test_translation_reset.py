"""Explicit destructive reset boundaries, with accepted synthetic source receipts."""
import harness_support
from pathlib import Path
import shutil
import tempfile
import unittest

from audit_a_fixtures import synthetic_stage
import audit_a_campaign as campaign
from clean_stage import ArtifactStage
from controller_common import bind,write
import concurrency
import execution_state
import source_preparation
import translation_reset


class TranslationResetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.source=self.root/'nl0/accepted';shutil.copytree(harness_support.CORE/'tests/fixtures/closed-addition',self.source)
        (self.source/'audit-a.json').unlink()
        audit=self.root/'audit-a/current';campaign.prepare(self.source,self.source,audit)
        for job in campaign.nl0.load(audit/'campaign.json')['jobs']:synthetic_stage(audit/job['id'])
        campaign.collect(audit,None)
        self.authority={k:str(self.source/name) for k,name in [('graph','nl0.json'),('spec','spec.json'),('audit_a','audit-a.json')]}
        self.record=self.root/'nl0-to-lean/current/final-decision.json'
        write(self.record,{'state':'USER_DECIDED','root':str(self.root),'owner_process':execution_state.identity(__import__('os').getpid()),
            'control':{'action':'reset-translation'}})

    def tearDown(self):self.tmp.cleanup()

    def test_reset_preserves_a_source_inputs_prior_native_files_and_all_reported_usage(self):
        recorder=execution_state.Recorder(self.root,'neutral',concurrency.resolve(1))
        stage=ArtifactStage(self.root/'nl0-to-lean/current/stage','Synthetic held carrier.',phase='interface-authoring',library=False)
        stage.workspace_retention=__import__('run_resources').retention(stage.work,stage.logs)
        write(stage.logs/'result.json',{'temporary_workspace_removed':False,'workspace_retention':stage.workspace_retention})
        write(stage.logs/'usage.json',{'synthetic':'summary'});(stage.logs/'usage-ledger.jsonl').write_text('')
        recorder.task('old-translation',state='WAITING_REVIEW',usage_ledger=str(stage.logs/'usage.json'))
        recorder.retain_stage(stage,'lean')
        (self.root/'native-checks').mkdir();(self.root/'native-checks/old-a.json').write_text('NL0')
        native_name='a'*32+'.json';(self.root/'native-checks'/native_name).write_text('translation')
        (self.root/'native-checks/user-notes.json').write_text('preserve unrelated file')
        (self.root/'inputs').mkdir();(self.root/'inputs/problem.md').write_text('preserve original input')
        write(self.root/'audit-b/old-result.json',{'synthetic':'remove'})
        try:
            receipt=translation_reset.apply(self.root,self.authority,recorder,bind(self.record),{'old-a.json'})
            self.assertTrue(receipt.is_file());self.assertFalse(stage.work.exists())
            self.assertFalse((self.root/'nl0-to-lean').exists());self.assertFalse((self.root/'audit-b').exists())
            self.assertEqual((self.root/'inputs/problem.md').read_text(),'preserve original input')
            self.assertTrue((self.root/'native-checks/old-a.json').is_file())
            self.assertFalse((self.root/'native-checks'/native_name).exists())
            self.assertTrue((self.root/'native-checks/user-notes.json').is_file())
            self.assertTrue(source_preparation.read_source(**self.authority)[0][0]['current_standard_receipt_valid'])
            self.assertTrue(Path(recorder.state['archived_usage_ledgers'][0]).is_file())
        finally:
            recorder.close('CANCELLED');shutil.rmtree(stage.work,ignore_errors=True)

    def test_stale_or_different_user_choice_never_deletes_translation(self):
        record=bind(self.record);write(self.record,{'state':'USER_DECIDED','control':{'action':'deliver-actual'}})
        with self.assertRaisesRegex(ValueError,'evidence changed'):
            translation_reset.apply(self.root,self.authority,None,record,set())
        with self.assertRaisesRegex(ValueError,'matching final user decision'):
            translation_reset.apply(self.root,self.authority,None,bind(self.record),set())
        self.assertTrue(self.record.is_file())


if __name__=='__main__':unittest.main()
