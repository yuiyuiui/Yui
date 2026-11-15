"""Observed failed-turn ordering and real native recovery/result retrieval."""
import harness_support
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

from clean_stage import ArtifactStage
import native_carrier
import native_client
from native_fault_fixtures import NativeFaultFixture


class InterruptedDispatch(unittest.TestCase):
    def run_incident(self, *, recovery=True, failures=1):
        with tempfile.TemporaryDirectory() as raw:
            stage=ArtifactStage(Path(raw)/'stage','Synthetic parent of three workers.',phase='control',library=False)
            try:
                stage.proc=Mock(stdin=io.StringIO());stage.proc.poll.return_value=None
                stage.thread_id='parent';stage.stop_on_submission=False
                stage.tools.append(native_carrier.tool('dispatch_batch','Synthetic private work.',{},[]))
                stage.tool_names.add('dispatch_batch')
                starts=[];dispatches=[];recovered=[]
                original_dispatch=stage.dispatch
                result={'proposals':[{'id':i,'route':'Existing completed work.'} for i in ('B001','B002','B003')]}
                def event(turn,status):
                    row={'id':turn,'status':status}
                    if status=='failed':row['error']={'code':'network_error','message':'Synthetic stream loss'}
                    return {'method':'turn/completed','params':{'threadId':'parent','turn':row}}
                def call(turn,key,tool,args):
                    return {'id':100+len(starts),'method':'item/tool/call','params':{
                        'threadId':'parent','turnId':turn,'callId':key,'tool':tool,'arguments':args}}
                def dispatch(name,args):
                    if name!='dispatch_batch':return original_dispatch(name,args)
                    dispatches.append(name)
                    # The native reader enqueues failure while this synchronous
                    # tool is still serving its children, as in the real runs.
                    stage.inbox.put(event('turn-1','failed'))
                    self.assertNotIn('batch',stage.tool_history)
                    return result  # Children finish before the parent handles failure.
                def rpc(method,params,**kwargs):
                    self.assertEqual(method,'turn/start');starts.append(params)
                    turn='turn-'+str(len(starts))
                    if len(starts)==1:
                        stage.inbox.put(call(turn,'batch','dispatch_batch',{}))
                    elif len(starts)<=failures:
                        stage.inbox.put(event(turn,'failed'))
                    else:
                        message=params['input'][0]['text']
                        self.assertIn('read_recovery_state',message)
                        self.assertIn('"call_id": "batch"',message)
                        self.assertNotIn('Existing completed work.',message)
                        summary=stage.recovery_calls['batch']
                        stage.inbox.put(call(turn,'retrieve',native_carrier.native_recovery.TOOL,
                            {'kind':'result','call_id':'batch','sha256':summary['result_sha256']}))
                        stage.inbox.put(call(turn,'finish','submit_draft',{'artifact':{'synthetic':True}}))
                        stage.inbox.put(event(turn,'completed'))
                        recovered.append(message)
                    return {'turn':{'id':turn}}
                with patch.object(stage,'rpc',side_effect=rpc),patch.object(stage,'dispatch',side_effect=dispatch), \
                        patch.object(stage,'wait_remote_retry') as retry:
                    if recovery:stage.solve_turns(stage.prompt())
                    else:
                        with patch.object(native_carrier.native_recovery,'recover',side_effect=lambda owner,prompt:prompt):
                            stage.solve_turns(stage.prompt())
                rows=[json.loads(s) for s in (stage.logs/'tools.jsonl').read_text().splitlines()]
                read=next(r for r in rows if r['tool']==native_carrier.native_recovery.TOOL)
                self.assertEqual(json.loads(read['result']['text']),result)
                self.assertEqual(dispatches,['dispatch_batch'])
                self.assertEqual(retry.call_count,failures)
                self.assertTrue(stage.accepted);self.assertTrue(recovered)
                self.assertEqual(len(list((stage.logs/'recovery').glob('*.json'))),1)
            finally:shutil.rmtree(stage.work,ignore_errors=True)

    def test_stream_fails_during_children_and_recovery_reads_the_finished_batch_once(self):
        self.run_incident()

    def test_repeated_disconnects_do_not_drop_or_redispatch_the_completed_batch(self):
        self.run_incident(failures=3)

    def test_acceptance_detects_the_original_generic_continuation_bug(self):
        with self.assertRaisesRegex(AssertionError,'read_recovery_state'):
            self.run_incident(recovery=False)


def strings(value):
    if isinstance(value,str):yield value
    elif isinstance(value,dict):
        for item in value.values():yield from strings(item)
    elif isinstance(value,list):
        for item in value:yield from strings(item)


@unittest.skipUnless(harness_support.native_available(),'Native Codex executable required')
class NativeRecovery(unittest.TestCase):
    def test_real_native_reconnect_reads_saved_return_via_code_mode_and_passes_input_audit(self):
        with tempfile.TemporaryDirectory() as raw,NativeFaultFixture(raw,failure='before_headers') as fixture:
            ordinary=fixture.respond
            def respond(f,handler,number,payload):
                if number!=3:return ordinary(f,handler,number,payload)
                prompt=next(s for s in strings(payload) if '\n\nReconnect progress (execution facts only):\n' in s)
                summary=json.loads(prompt.split('\nReconnect progress (execution facts only):\n')[1].split('\n')[0])
                row=next(r for r in summary['calls'] if r['tool']=='check_draft')
                args={'kind':'result','call_id':row['call_id'],'sha256':row['result_sha256']}
                f.code(handler,number,'text(await tools.read_recovery_state('+json.dumps(args)+'));')
            fixture.responder=respond;fixture.start();fixture.wait(seconds=15)
            self.assertFalse(fixture.failures);self.assertEqual(fixture.checkpoint_writes,1)
            self.assertEqual(len(fixture.calls),4);self.assertEqual(fixture.waits,[60])
            rows=[json.loads(s) for s in (fixture.stage.logs/'tools.jsonl').read_text().splitlines()]
            returned=next(r['result'] for r in rows if r['tool']=='read_recovery_state')
            self.assertEqual(json.loads(returned['text']),rows[0]['result'])
            checked=native_client.audit(fixture.stage.logs)
            self.assertEqual(checked['status'],'NATIVE-CODEX-CONTEXT-CHECK-PASSED',checked['errors'])
            receipt=fixture.stage.logs/'native-client.json';data=json.loads(receipt.read_text())
            (fixture.stage.logs/data['recovery_inputs'][0]['path']).write_text('{}')
            self.assertIn('unbound_recovery_input',native_client.audit(fixture.stage.logs)['errors'])

    def test_role_revision_uses_current_inputs_and_excludes_prior_recovery_records(self):
        from role_sessions import Sessions
        import execution_state
        import threading
        with tempfile.TemporaryDirectory() as raw,NativeFaultFixture(raw) as fixture:
            sessions=Sessions();fixture.start(sessions,'owner');fixture.wait()
            old=fixture.stage;first_calls=dict(old.recovery_calls)
            self.assertTrue(first_calls)
            revision=ArtifactStage(Path(raw)/'revision','Synthetic revised task.',phase='control',library=False)
            def revise():
                try:
                    with execution_state.activate(fixture.recorder),sessions.use('owner'):
                        fixture.outcomes.append(revision.execute())
                except BaseException as error:fixture.exceptions.append(error)
            fixture.worker=threading.Thread(target=revise,daemon=True);fixture.worker.start()
            fixture.wait(lambda:len(fixture.outcomes)==2)
            self.assertEqual(fixture.outcomes[-1][0]['status'],'ACCEPTED')
            self.assertFalse(set(first_calls)&set(old.recovery_calls))
            self.assertNotIn('recovery_inputs',json.loads((old.logs/'native-client.json').read_text()))


if __name__=='__main__':unittest.main()
