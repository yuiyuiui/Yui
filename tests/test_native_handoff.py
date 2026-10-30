"""Actual native client, deterministic loopback responses; no model or credentials."""
import harness_support
import http.server
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from clean_stage import ArtifactStage
from translation_author import InterfaceStage
from role_sessions import Sessions
import run_pilot


@unittest.skipUnless(shutil.which('codex'),'A compatible local Codex CLI is required')
class NativeHandoffTests(unittest.TestCase):
    def test_two_submissions_reuse_actual_thread_without_post_submit_provider_calls(self):
        with tempfile.TemporaryDirectory(prefix='yui-native-control-') as raw:
            root=Path(raw);sessions=Sessions();servers=[];stages=[];calls=[];faults=[]

            def start(stage):
                class Handler(http.server.BaseHTTPRequestHandler):
                    def log_message(self,*args):pass
                    def do_POST(self):
                        try:
                            payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                            number=stage.reserve_request_number();stage.normalize_request(payload,request_number=number)
                            calls.append(stage.logs.name)
                            item={'id':'fc-'+str(len(calls)),'type':'function_call','call_id':'call-'+str(len(calls)),
                                  'name':'submit_draft','arguments':json.dumps({'artifact':{'round':len(calls)}}),'status':'completed'}
                            response={'id':'resp-'+str(len(calls)),'object':'response','model':stage.model,'status':'completed',
                                'output':[item],'service_tier':'default',
                                'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}}
                            events=[{'type':'response.created','response':{**response,'status':'in_progress','output':[]}},
                                {'type':'response.output_item.added','output_index':0,'item':{**item,'arguments':'','status':'in_progress'}},
                                {'type':'response.function_call_arguments.delta','item_id':item['id'],'output_index':0,'delta':item['arguments']},
                                {'type':'response.function_call_arguments.done','item_id':item['id'],'output_index':0,'arguments':item['arguments']},
                                {'type':'response.output_item.done','output_index':0,'item':item},
                                {'type':'response.completed','response':response}]
                            text=''.join('data: '+json.dumps(e)+'\n\n' for e in events)
                            for event in events:stage.observe_model_event(event,number)
                            (stage.logs/f'response-{number:04d}.sse').write_text(text)
                            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
                            self.wfile.write(text.encode());self.wfile.flush();self.close_connection=True
                        except Exception as error:
                            unknown=[{k:v for k,v in item.items() if k!='encrypted_content'} for item in payload.get('input',[])
                                if item.get('role') not in {'user','developer','system'} and item.get('type')!='function_call_output'
                                and item.get('id') not in stage.model_history]
                            outputs=[item for item in payload.get('input',[]) if item.get('type')=='function_call_output']
                            faults.append(repr(error)+' outputs='+repr(outputs)[:600]+' unknown='+repr(unknown)[:400]);self.send_error(500)
                server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
                servers.append(server);stage.relay=server
                threading.Thread(target=server.serve_forever,daemon=True).start()
                state=stage.work/'state';port=server.server_port
                (state/'config.toml').write_text(f'''model = "{stage.model}"
model_provider = "pilot-relay"
model_reasoning_effort = "high"
project_doc_max_bytes = 0
[model_providers.pilot-relay]
name = "Loopback software test, never an actual model"
base_url = "http://127.0.0.1:{port}"
wire_api = "responses"
requires_openai_auth = false
request_max_retries = 0
stream_max_retries = 0
[features]
apps = false
plugins = false
memories = false
hooks = false
multi_agent = false
shell_tool = false
shell_snapshot = false
''')
                env={'PATH':os.environ['PATH'],'HOME':str(stage.work/'home'),'CODEX_HOME':str(state),'LANG':'en_US.UTF-8'}
                stage.proc=subprocess.Popen([shutil.which('codex'),'app-server','--stdio'],env=env,cwd=stage.work/'input',
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,bufsize=1,start_new_session=True)
                stage.network_proxy=None
                def read():
                    for line in stage.proc.stdout:
                        try:stage.inbox.put(json.loads(line))
                        except ValueError:pass
                stage.reader_thread=threading.Thread(target=read,daemon=True);stage.reader_thread.start()
                stage.rpc('initialize',{'clientInfo':{'name':'yui-local-test','version':'1'},'capabilities':{'experimentalApi':True}})
                stage.proc.stdin.write(json.dumps({'method':'initialized'})+'\n');stage.proc.stdin.flush()

            def fail(stage,error,**kwargs):
                raise RuntimeError('Local native protocol test failed; requests='+str(calls)+'; loopback errors='+repr(faults)+'; error='+str(error.get('message') if isinstance(error,dict) else error))
            try:
                with patch.object(ArtifactStage,'start_process',start),patch.object(ArtifactStage,'pause_error',fail):
                    for n in (1,2):
                        stage=InterfaceStage(root/('round-'+str(n)),'Submit the fixture object through submit_draft. This is a software protocol test.',
                            phase='translation-source-preparation' if n==1 else 'interface-authoring',library=False)
                        stages.append(stage)
                        with sessions.use('fixture-author'):result,artifact=stage.execute()
                        self.assertEqual(result['status'],'ACCEPTED',result)
                        self.assertEqual(artifact,{'round':n})
                    self.assertEqual(len(calls),2,'A submitted tool must not trigger an extra provider request')
                    self.assertFalse(faults,faults)
                    first=json.loads((stages[0].logs.parent/'round-1/result.json').read_text())
                    second=json.loads((root/'round-2/result.json').read_text())
                    self.assertEqual(first['native_thread_id'],second['native_thread_id'])
                    self.assertEqual(second['exposure']['status'],'TRANSMITTED-EXPOSURE-CHECK-PASSED',second['exposure'])
                    self.assertFalse(list(root.rglob('local-cancellations.jsonl')))
                    sessions.close_all('INTERFACE_FROZEN',[root/'round-2/accepted.json'])
            finally:
                for entry in sessions.roles.values():
                    stage=entry['stage']
                    if stage.proc and stage.proc.poll() is None:
                        stage.proc.terminate();stage.proc.wait(timeout=10)
                    shutil.rmtree(stage.work,ignore_errors=True)
                for stage in stages:shutil.rmtree(stage.work,ignore_errors=True)
                for server in servers:server.shutdown();server.server_close()


if __name__=='__main__':unittest.main()
