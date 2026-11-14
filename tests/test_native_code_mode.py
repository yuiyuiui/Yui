"""Production Code Mode path with the actual helper and isolated fake model.

The fake endpoint supplies JavaScript, not direct function_call bypasses. The
real Codex/helper must execute it and deliver dynamic RPCs to the controller.
"""
import harness_support
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch
from native_fixture import NativeFixture
from native_fault_fixtures import NativeFaultFixture
import fault_control
import native_carrier


@unittest.skipUnless(harness_support.native_available(),'Native Codex executable required')
class NativeCodeModeTests(unittest.TestCase):
    def test_actual_exec_helper_reads_then_submits_through_dynamic_rpc(self):
        def respond(f,handler,number,payload):
            scripts=[
                'text(await tools.read_task_input({id:"problem",start:1,end:2}));',
                'text(await tools.read_yui({path:"SKILL.md",start:1,end:3}));',
                'text(await tools.check_draft({artifact:{synthetic:true}}));',
                'text(await tools.submit_draft({artifact:{synthetic:true}}));']
            f.code(handler,number,scripts[number-1])
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);doc=root/'problem.txt';doc.write_text('Synthetic supplied input.\n')
            inputs=root/'inputs.json';inputs.write_text(json.dumps({'inputs':[{'id':'problem','path':doc.name,
                'sha256':hashlib.sha256(doc.read_bytes()).hexdigest()}]}))
            with NativeFixture(root/'native',responder=respond,inputs=inputs) as f:
                f.start();f.wait(seconds=8)
                self.assertEqual(f.outcomes[0][0]['status'],'ACCEPTED')
                calls=[json.loads(row) for row in (f.stage.logs/'tools.jsonl').read_text().splitlines()]
                self.assertEqual([r['tool'] for r in calls],['read_task_input','read_yui','check_draft','submit_draft'])
                self.assertTrue(all('error' not in r['result'] for r in calls),calls)
                self.assertIn('Synthetic supplied input',json.dumps(calls[0]['result']))
                self.assertTrue((f.stage.logs/'accepted.json').is_file())
                self.assertFalse(f.notifications)
                self.assertEqual(f.stage.continuation_count,0)
                self.assertEqual(f.stage.completed_tool_calls,4)

    def test_spawn_denied_after_checkpoint_pauses_without_another_turn(self):
        original=native_carrier.transport_sandbox_profile
        def denied(work):
            import runtime_config
            helper=runtime_config.load_lock()['codex']['code_mode_host']['path']
            return original(work).replace('(literal '+json.dumps(helper)+')','(literal "/__test_forbidden_helper__")')
        def respond(f,handler,number,payload):
            if number==1:f.tool(handler,number,'check_draft',{'checkpoint':True})
            else:f.code(handler,number,'text(await tools.read_yui({path:"SKILL.md"}));')
        with tempfile.TemporaryDirectory() as root,NativeFaultFixture(root) as f,patch.object(native_carrier,'transport_sandbox_profile',denied):
            f.responder=respond;f.start()
            f.wait(lambda:(f.paused() or {}).get('notification',{}).get('status')=='QUEUED')
            state=f.paused()
            self.assertEqual(state['fault']['category'],'harness_bug')
            self.assertTrue(state['error']['current_generation_stop_confirmed'])
            self.assertIsNone(f.stage.proc.poll());self.assertTrue(f.stage.work.is_dir())
            self.assertTrue(f.checkpoint.is_file());self.assertEqual(f.checkpoint_writes,1)
            self.assertEqual(f.stage.continuation_count,0)
            n=len(f.calls);time.sleep(.15);self.assertEqual(len(f.calls),n)
            starts=[json.loads(s) for s in (f.stage.logs/'client.jsonl').read_text().splitlines() if json.loads(s).get('method')=='turn/start']
            self.assertEqual(len(starts),1)

    def test_code_mode_cannot_read_an_undeclared_file(self):
        def respond(f,handler,number,payload):
            code='text(await tools.read_yui({path:"/etc/passwd",start:1,end:3}));' if number==1 else 'text(await tools.submit_draft({artifact:{synthetic:true}}));'
            f.code(handler,number,code)
        with tempfile.TemporaryDirectory() as root,NativeFixture(root,responder=respond) as f:
            f.start();f.wait()
            rows=[json.loads(s) for s in (f.stage.logs/'tools.jsonl').read_text().splitlines()]
            self.assertIn('error',rows[0]['result'])
            self.assertEqual(f.outcomes[0][0]['status'],'ACCEPTED')
            self.assertFalse(f.notifications)

    def test_printed_error_text_is_not_a_native_host_failure(self):
        for message in ('failed to spawn code-mode host fake: Operation not permitted (os error 1)',
                        'gRPC code-mode session opening failed: Operation not permitted (os error 1)'):
            def respond(f,handler,number,payload):
                code='text('+json.dumps(message)+');' if number==1 else 'text(await tools.submit_draft({artifact:{synthetic:true}}));'
                f.code(handler,number,code)
            with self.subTest(message=message),tempfile.TemporaryDirectory() as root,NativeFixture(root,responder=respond) as f:
                f.start();f.wait()
                self.assertEqual(f.outcomes[0][0]['status'],'ACCEPTED');self.assertFalse(f.notifications)
