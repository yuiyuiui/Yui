"""Real Codex process with a deterministic test endpoint; no forwarding or login."""
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from unittest.mock import patch

import harness_support
from clean_stage import ArtifactStage
import native_client
import fault_control
import execution_state


class NativeFixture:
    def __init__(self, root, *, tail_delay=0, responder=None, validator=None, inputs=None):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.auth=self.root/'empty-auth';self.auth.mkdir()
        self.calls=[];self.call_times=[];self.failures=[];self.outcomes=[];self.exceptions=[];self.notifications=[]
        self.stack=ExitStack();self.tail_delay=tail_delay;self.responder=responder
        self.stage=ArtifactStage(self.root/'stage','Submit the synthetic fixture object using submit_draft.',
            phase='control',library=False,validator=validator,inputs=inputs)
        (self.stage.logs/'owner-context.json').write_text('{"thread_id":"synthetic-native-owner"}')
        self.recorder=execution_state.Recorder(self.root/'case','synthetic-native',{})
        fixture=self
        class Endpoint(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*args):pass
            def do_POST(self):
                try:
                    payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    fixture.calls.append(payload);fixture.call_times.append(time.monotonic())
                    if fixture.responder:fixture.responder(fixture,self,len(fixture.calls),payload)
                    else:fixture.tool(self,len(fixture.calls),'submit_draft',{'synthetic':True})
                except (BrokenPipeError,ConnectionResetError):pass
                except Exception as error:fixture.failures.append(repr(error));self.close_connection=True
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Endpoint)
        self.server.daemon_threads=True
        self.server_thread=threading.Thread(target=self.server.serve_forever,daemon=True)

    def tool(self, handler, number, name, artifact):
        item={'id':f'item-{number}','call_id':f'call-{number}','type':'function_call','name':name,
              'arguments':json.dumps({'artifact':artifact}),'status':'completed'}
        self.respond_item(handler,number,item)

    def code(self, handler, number, code):
        item={'id':f'item-{number}','call_id':f'call-{number}','type':'custom_tool_call',
              'name':'exec','input':code,'status':'completed'}
        self.respond_item(handler,number,item)

    def respond_item(self, handler, number, item):
        custom=item['type']=='custom_tool_call';field='input' if custom else 'arguments'
        delta_type='response.custom_tool_call_input' if custom else 'response.function_call_arguments'
        response={'id':f'resp-{number}','object':'response','model':self.stage.model,'status':'completed',
            'output':[item],'service_tier':'default','usage':{'input_tokens':2,'output_tokens':1,'total_tokens':3}}
        events=[{'type':'response.created','response':{**response,'status':'in_progress','output':[]}},
            {'type':'response.output_item.added','output_index':0,'item':{**item,field:'','status':'in_progress'}},
            {'type':delta_type+'.delta','item_id':item['id'],'output_index':0,'delta':item[field]},
            {'type':delta_type+'.done','item_id':item['id'],'output_index':0,field:item[field]},
            {'type':'response.output_item.done','output_index':0,'item':item},
            {'type':'response.completed','response':response}]
        handler.send_response(200);handler.send_header('Content-Type','text/event-stream')
        handler.send_header('Connection','close');handler.end_headers()
        for index,event in enumerate(events):
            if index==len(events)-1 and self.tail_delay:time.sleep(self.tail_delay)
            handler.wfile.write(('data: '+json.dumps(event)+'\n\n').encode());handler.wfile.flush()
        handler.close_connection=True

    def __enter__(self):
        self.server_thread.start();original_config=native_client.configuration
        def config(stage):
            text=original_config(stage)
            return text.replace('requires_openai_auth = true','requires_openai_auth = false').replace('[model_providers.yui-native]',f'[model_providers.yui-native]\nbase_url = "http://127.0.0.1:{self.server.server_port}"\nstream_idle_timeout_ms = 300')
        self.stack.enter_context(patch.object(native_client,'configuration',config))
        self.stack.enter_context(patch('runtime_config.auth_home',return_value=self.auth))
        self.stack.enter_context(patch.object(fault_control,'queue_notification',lambda thread,message:self.notifications.append(message) or {'status':'QUEUED','exit_code':0}))
        original_popen=subprocess.Popen
        def popen(command,*args,**kwargs):
            if 'app-server' in command:
                # Validate the actual launched client, including linked tests
                # with multiple stages sharing this deterministic endpoint.
                state=Path(kwargs['env']['CODEX_HOME'])
                text=(state/'config.toml').read_text()
                assert f'http://127.0.0.1:{self.server.server_port}' in text
                assert not (state/'auth.json').exists()
                kwargs['env']['NO_PROXY']='127.0.0.1,localhost';kwargs['env']['no_proxy']='127.0.0.1,localhost'
            return original_popen(command,*args,**kwargs)
        self.stack.enter_context(patch.object(subprocess,'Popen',popen))
        return self

    def start(self, sessions=None, role=None):
        def run():
            try:
                with execution_state.activate(self.recorder):
                    if sessions:
                        with sessions.use(role):self.outcomes.append(self.stage.execute())
                    else:self.outcomes.append(self.stage.execute())
            except BaseException as error:self.exceptions.append(error)
        self.worker=threading.Thread(target=run,daemon=True);self.worker.start();return self

    def wait(self, predicate=None, seconds=12):
        deadline=time.monotonic()+seconds;predicate=predicate or (lambda:bool(self.outcomes))
        while time.monotonic()<deadline:
            if self.exceptions:raise AssertionError(repr(self.exceptions))
            if predicate():return
            time.sleep(.01)
        path=self.stage.logs/'error-state.json'
        events=self.stage.logs/'events.jsonl'
        tail=events.read_text().splitlines()[-3:] if events.exists() else []
        raise AssertionError('Native fixture timeout; calls='+str(len(self.calls))+'; pause='+(path.read_text()[:1200] if path.exists() else 'none')+'; tail='+repr(tail))

    def __exit__(self,*args):
        try:
            pgid=self.stage.proc.pid if self.stage.proc else None
            worker=getattr(self,'worker',None)
            if worker and worker.is_alive():
                path=self.stage.logs/'error-state.json'
                if path.exists():fault_control.cancel_paused(self.stage.logs)
                else:execution_state.request_cancel(self.recorder.root)
                worker.join(5)
            if self.stage.work.exists():self.stage.release_resources('USER_CANCELLED')
            if worker and worker.is_alive():raise AssertionError('Test controller survived cancellation')
            if self.stage.proc and self.stage.proc.poll() is None:raise AssertionError('Test native process survived cleanup')
            if pgid:
                # Code Mode creates a child process not visible in Popen. Check
                # the entire owned group after releasing its native parent.
                def members():
                    rows=subprocess.check_output(['ps','-axo','pid=,pgid='],text=True).splitlines()
                    return [int(row.split()[0]) for row in rows if len(row.split())==2 and int(row.split()[1])==pgid]
                end=time.monotonic()+2
                while members() and time.monotonic()<end:time.sleep(.02)
                if members():raise AssertionError('Test native/helper process group survived cleanup')
        finally:
            self.recorder.close('CANCELLED');self.server.shutdown();self.server.server_close()
            self.server_thread.join(2);self.stack.close()
