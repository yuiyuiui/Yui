"""Actual local JSON-RPC cancellation with a fake carrier; no provider calls."""
import harness_support
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from clean_stage import ArtifactStage
import execution_state as e
import concurrency


class CarrierCancellationTests(unittest.TestCase):
    def test_active_turn_receives_exact_interrupt_and_owned_process_is_reaped(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);script=root/'fake_carrier.py'
            script.write_text('''import json,sys
for line in sys.stdin:
 m=json.loads(line);method=m.get('method');r={}
 if method=='thread/start':r={'thread':{'id':'neutral-thread'}}
 if method=='turn/start':r={'turn':{'id':'neutral-turn'}}
 if 'id' in m:print(json.dumps({'id':m['id'],'result':r}),flush=True)
 if method=='turn/interrupt':print(json.dumps({'method':'turn/completed','params':{'turn':{'id':'neutral-turn','status':'interrupted'}}}),flush=True)
''')
            recorder=e.Recorder(root/'run','neutral',concurrency.resolve(1))
            budget=concurrency.Budget(concurrency.resolve(1),execution=recorder)
            class FakeStage(ArtifactStage):
                def start_process(self):
                    self.proc=subprocess.Popen([sys.executable,str(script)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                        text=True,bufsize=1,start_new_session=True)
                    self.execution.register_process(self.proc,'neutral-fake-carrier',self.execution_task)
                    def read():
                        for line in self.proc.stdout:
                            item=json.loads(line);self.inbox.put(item)
                    self.reader_thread=threading.Thread(target=read,daemon=True);self.reader_thread.start()
            stage=FakeStage(root/'stage','Neutral cancellation software control.',phase='control',library=False,budget=budget)
            results=[];thread=threading.Thread(target=lambda:results.append(stage.execute()));thread.start()
            try:
                deadline=time.monotonic()+5
                while not any(t.get('model_started_at_utc') for t in recorder.state['tasks'].values()) and time.monotonic()<deadline:time.sleep(.02)
                self.assertTrue(stage.proc)
                e.request_cancel(recorder.root);thread.join(5)
                self.assertFalse(thread.is_alive())
                result,_=results[0]
                self.assertEqual(result['status'],'CANCELLED')
                self.assertEqual(result['task_outcome'],'EXTERNAL_CANCELLED')
                self.assertEqual(result['api_calls'],0)
                self.assertIsNotNone(stage.proc.poll())
                calls=[json.loads(s) for s in (root/'stage/client.jsonl').read_text().splitlines()]
                interrupt=[c for c in calls if c.get('method')=='turn/interrupt']
                self.assertEqual(interrupt[0]['params'],{'threadId':'neutral-thread','turnId':'neutral-turn'})
            finally:
                e.request_cancel(recorder.root);thread.join(5);recorder.close('CONTROL_FINISHED')


if __name__=='__main__':unittest.main()
