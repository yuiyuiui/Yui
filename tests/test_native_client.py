"""Native completion and handoff regressions with the real Codex executable."""
import harness_support
from pathlib import Path
import tempfile
import unittest
import json
import shutil
from native_fixture import NativeFixture

@unittest.skipUnless(shutil.which('codex'),'Codex executable required')
class NativeClientTests(unittest.TestCase):
    def test_submission_and_late_provider_tail_are_normal_handoff(self):
        for delay in (0,.03,.2):
            with self.subTest(delay=delay),tempfile.TemporaryDirectory() as root,NativeFixture(root,tail_delay=delay) as f:
                f.start();f.wait()
                result=f.outcomes[0][0]
                self.assertEqual(result['status'],'ACCEPTED')
                self.assertEqual(result['execution_health'],'NO_RECORDED_FAULT',result.get('execution_fault'))
                self.assertEqual(len(f.calls),1)
                self.assertTrue(f.stage.proc.poll() is None)
                self.assertFalse((f.stage.logs/'error-state.json').exists())
                self.assertFalse((f.stage.logs/'relay-errors.jsonl').exists())
                self.assertTrue((f.stage.logs/'accepted.json').exists())
                self.assertEqual(result['exposure']['status'],'NATIVE-CODEX-CONTEXT-CHECK-PASSED')
                self.assertFalse(result['measurement_complete'])

    def test_same_role_submits_again_in_the_same_process_and_thread(self):
        from clean_stage import ArtifactStage
        from role_sessions import Sessions
        import execution_state
        import threading
        def respond(f,handler,number,payload):
            f.code(handler,number,'text(await tools.submit_draft({artifact:{synthetic:true}}));')
        with tempfile.TemporaryDirectory() as root,NativeFixture(root,tail_delay=.05,responder=respond) as f:
            sessions=Sessions();f.start(sessions,'audit-a-global');f.wait()
            original=sessions.roles['audit-a-global']['stage'];pid=original.proc.pid;thread=original.thread_id
            self.assertEqual(f.outcomes[0][0]['status'],'ACCEPTED')
            second=ArtifactStage(Path(root)/'revision','Review the revised synthetic object.',phase='control',library=False)
            def revise():
                try:
                    with execution_state.activate(f.recorder),sessions.use('audit-a-global'):
                        f.outcomes.append(second.execute())
                except BaseException as error:f.exceptions.append(error)
            f.worker=threading.Thread(target=revise,daemon=True);f.worker.start()
            f.wait(lambda:len(f.outcomes)==2)
            self.assertEqual(f.outcomes[-1][0]['status'],'ACCEPTED')
            self.assertEqual((original.proc.pid,original.thread_id),(pid,thread))
            self.assertEqual(len(f.calls),2)
            self.assertFalse((original.logs/'error-state.json').exists())
            evidence=Path(root)/'global-acceptance.json';evidence.write_text('{"synthetic":true}')
            sessions.close(['audit-a-global'],'GLOBAL_REVIEW_PASSED',[evidence])
            self.assertIsNotNone(original.proc.poll())
            self.assertFalse(original.work.exists())

    def test_native_A_review_receipt_binds_the_shared_acceptance_authority(self):
        from clean_stage import ArtifactStage
        import native_client
        with tempfile.TemporaryDirectory() as root,NativeFixture(root) as f:
            unused=f.stage;f.stage=ArtifactStage(Path(root)/'review','Synthetic global review submission.',phase='audit-a-global',library=False)
            unused.release_resources('USER_CANCELLED')
            f.start();f.wait();result=f.outcomes[0][0]
            manifest=json.loads((f.stage.logs/'execution-manifest.json').read_text())
            self.assertEqual(result['exposure']['acceptance_contract'],manifest['acceptance_contract'])
            self.assertIsNotNone(result['exposure']['acceptance_contract'])
            source=f.stage.logs/'harness-snapshot'/manifest['acceptance_contract']['source']
            source.write_text(source.read_text()+'\nChanged authority\n')
            self.assertEqual(native_client.audit(f.stage.logs)['status'],'VALIDATION_FAILED')

    def test_native_context_readback_detects_changed_config_prompt_tool_and_input(self):
        import native_client
        from clean_stage import ArtifactStage
        with tempfile.TemporaryDirectory() as root,NativeFixture(root) as f:
            inputs=Path(root)/'inputs';inputs.mkdir()
            doc=inputs/'text.txt';doc.write_text('Only this synthetic input is permitted.')
            import hashlib
            manifest=inputs/'inputs.json';manifest.write_text(json.dumps({'inputs':[{'id':'text','path':'text.txt','sha256':hashlib.sha256(doc.read_bytes()).hexdigest()}]}))
            original=f.stage
            f.stage=ArtifactStage(Path(root)/'bound','Read only the declared synthetic material.',phase='control',library=False,inputs=manifest)
            original.release_resources('USER_CANCELLED')
            f.start();f.wait()
            self.assertEqual(f.outcomes[0][0]['exposure']['status'],'NATIVE-CODEX-CONTEXT-CHECK-PASSED')
            root=f.stage.logs
            recorded=json.loads((root/'execution-manifest.json').read_text())
            files=[root/'effective-config.toml',root/'prompt.txt',root/'system.txt',
                   root/recorded['frozen_task_files'][0]['path'],root/'harness-snapshot/SKILL.md.snapshot.txt']
            for path in files:
                with self.subTest(path=path.name):
                    prior=path.read_bytes()
                    changed=prior.replace(b'model_reasoning_effort = "high"',b'model_reasoning_effort = "low"') if path.name=='effective-config.toml' else prior+b'\nChanged\n'
                    path.write_bytes(changed)
                    self.assertEqual(native_client.audit(root)['status'],'VALIDATION_FAILED')
                    path.write_bytes(prior)
            tool=root/'tools.json';before=tool.read_text();data=json.loads(before);data[0]['description']='changed catalog';tool.write_text(json.dumps(data))
            self.assertEqual(native_client.audit(root)['status'],'VALIDATION_FAILED');tool.write_text(before)
            self.assertEqual(native_client.audit(root)['status'],'NATIVE-CODEX-CONTEXT-CHECK-PASSED')
            receipt=root/'native-client.json';before=receipt.read_text();value=json.loads(before)
            value['native_components']['code_mode_host']['sha256']='changed';receipt.write_text(json.dumps(value))
            self.assertIn('native_components_changed',native_client.audit(root)['errors'])
            receipt.write_text(before)

    def test_legacy_native_receipt_without_helper_binding_remains_readable(self):
        import native_client
        with tempfile.TemporaryDirectory() as root,NativeFixture(root) as f:
            f.start();f.wait()
            manifest=f.stage.logs/'execution-manifest.json';data=json.loads(manifest.read_text())
            data['resolved_environment']['codex'].pop('code_mode_host')
            data['resolved_environment']['codex'].pop('package_manifest')
            manifest.write_text(json.dumps(data))
            receipt=f.stage.logs/'native-client.json';data=json.loads(receipt.read_text())
            data.pop('native_components');receipt.write_text(json.dumps(data))
            self.assertEqual(native_client.audit(f.stage.logs)['status'],'NATIVE-CODEX-CONTEXT-CHECK-PASSED')
