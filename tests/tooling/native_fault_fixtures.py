"""Native client + production controller, isolated synthetic service and outbox."""
from contextlib import ExitStack
import errno
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
from types import SimpleNamespace
from unittest.mock import patch

from clean_stage import ArtifactStage
import execution_state
import fault_control
import harness_support
import run_pilot


class NativeFaultFixture:
    """Only service, fake authentication, optional clock and outbox are replaced.

    start_process, stdout reader, RPCs, tools, retries, fault gate and resource
    handling execute their production implementations. No real model or owner
    task is contacted. The synthetic validator persists a genuine tool checkpoint.
    """
    def __init__(self, root, failure='disconnect', *, failures=1, real_wait=False):
        self.root=Path(root).resolve();self.failure=failure;self.failures=failures
        self.real_wait=real_wait;self.calls=[];self.errors=[];self.outcomes=[]
        self.server_errors=[];self.waits=[];self.child_identities=[]
        self.lock=threading.Lock();self.release=threading.Event()
        self.refused=socket.socket();self.refused.bind(('127.0.0.1',0))
        self.refused_port=self.refused.getsockname()[1];self.refused.close()
        self.checkpoint_writes=0;self.stack=ExitStack();self.worker=None
        self.auth=self.root/'fake-auth';self.auth.mkdir(parents=True)
        self.case=self.root/'case';self.case.mkdir()
        self.recorder=execution_state.Recorder(self.case,'synthetic-native-fault',{})
        self.stage=ArtifactStage(self.case/'stage','First check the synthetic checkpoint object, then submit the completed object.',
            phase='control',library=False,validator=self.validate)
        (self.stage.logs/'owner-context.json').write_text('{"thread_id":"synthetic-fault-owner"}')
        self.checkpoint=self.stage.logs/'saved-checkpoint.json'
        self.sink=self.root/'notification-sink'
        self.sink.write_text('#!'+sys.executable+'\nimport json,os,sys\n'
            'with open(os.environ["YUI_TEST_OUTBOX"],"a") as out:out.write(json.dumps(sys.argv[1:])+"\\n")\n'
            'print("queued to isolated test outbox")\n')
        self.sink.chmod(0o700);self.outbox=self.root/'outbox.jsonl'
        fixture=self
        class Upstream(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*args):pass
            def do_POST(self):
                try:
                    payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    with fixture.lock:
                        number=len(fixture.calls)+1
                        fixture.calls.append({'number':number,'at':time.monotonic(),'payload':payload})
                    if number==1:fixture.tool(self,number,'check_draft',{'checkpoint':True})
                    elif number<=1+fixture.failures:fixture.fail(self,number)
                    else:fixture.tool(self,number,'submit_draft',{'complete':True})
                except (BrokenPipeError,ConnectionResetError):pass
                except Exception as error:
                    fixture.server_errors.append(repr(error));self.close_connection=True
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
        self.server_thread=threading.Thread(target=self.server.serve_forever,daemon=True)

    def validate(self, value):
        if value=={'checkpoint':True}:
            self.checkpoint_writes+=1
            self.checkpoint.write_text('{"saved":true}')
        elif value!={'complete':True} or not self.checkpoint.is_file():
            raise ValueError('Synthetic completion requires the actual saved checkpoint')
        return {'synthetic_control_only':True}

    @staticmethod
    def chunks(handler, blocks, *, complete=True):
        handler.send_response(200);handler.send_header('Content-Type','text/event-stream')
        handler.send_header('Transfer-Encoding','chunked');handler.send_header('Connection','close');handler.end_headers()
        for event in blocks:
            block=('data: '+json.dumps(event)+'\n\n').encode()
            handler.wfile.write(f'{len(block):X}\r\n'.encode()+block+b'\r\n');handler.wfile.flush()
        if complete:handler.wfile.write(b'0\r\n\r\n');handler.wfile.flush();handler.close_connection=True

    def tool(self, handler, number, name, artifact):
        item={'id':f'item-{number}','call_id':f'call-{number}','type':'function_call',
            'name':name,'arguments':json.dumps({'artifact':artifact}),'status':'completed'}
        response={'id':f'synthetic-response-{number}','object':'response','model':self.stage.model,
            'status':'completed','output':[item],'service_tier':'default',
            'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}}
        self.chunks(handler,[
            {'type':'response.created','response':{**response,'status':'in_progress','output':[]}},
            {'type':'response.output_item.added','output_index':0,'item':{**item,'arguments':'','status':'in_progress'}},
            {'type':'response.function_call_arguments.delta','item_id':item['id'],'output_index':0,'delta':item['arguments']},
            {'type':'response.function_call_arguments.done','item_id':item['id'],'output_index':0,'arguments':item['arguments']},
            {'type':'response.output_item.done','output_index':0,'item':item},
            {'type':'response.completed','response':response}])

    def fail(self, handler, number):
        service_errors={'auth':(403,'authentication_error'),'capacity':(503,'server_is_overloaded'),
            'balance':(402,'credit_balance_exhausted'),'quota':(429,'insufficient_quota'),
            'request':(400,'invalid_request_error'),'capacity429':(429,'rate_limit_exceeded')}
        if self.failure in service_errors:
            status,code=service_errors[self.failure]
            body=json.dumps({'error':{'code':code,'type':code,
                'message':'Synthetic service fault after a completed checkpoint'}}).encode()
            handler.send_response(status);handler.send_header('Content-Type','application/json')
            handler.send_header('Content-Length',str(len(body)));handler.send_header('Connection','close')
            handler.end_headers();handler.wfile.write(body);handler.wfile.flush();handler.close_connection=True
            return
        self.chunks(handler,[{'type':'response.created','response':{
            'id':f'synthetic-response-{number}','model':self.stage.model,'status':'in_progress','output':[]}},
            {'type':'response.output_item.added','output_index':0,'item':{
                'id':f'partial-{number}','call_id':f'partial-call-{number}','type':'function_call',
                'name':'check_draft','arguments':'','status':'in_progress'}},
            {'type':'response.function_call_arguments.delta','item_id':f'partial-{number}',
                'output_index':0,'delta':'{"artifact":'}],complete=False)
        if self.failure=='timeout':self.release.wait(10)
        else:
            # Close an actual active connection before the final HTTP chunk/SSE
            # terminal event; this is not a mocked controller error return.
            try:handler.connection.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            handler.connection.close()
        handler.close_connection=True

    def notify(self, thread, message):
        if thread!='synthetic-fault-owner':raise AssertionError('Real owner task escaped test isolation')
        with patch.dict(os.environ,{'YUI_CODEX_BINARY':str(self.sink),'YUI_TEST_OUTBOX':str(self.outbox)}):
            # Use the production queue command, pointed only at our executable
            # test sink. Default unmocked-notification blocking remains in place.
            return harness_support._original_notification(thread,message)

    def fast_wait(self, seconds, reason, turn, deadline):
        original_time=time;original_threading=threading;clock=[time.monotonic()]
        fixture=self
        class Sleeper:
            def wait(self, duration):clock[0]+=duration
        class Threads:
            def __getattr__(self,name):return getattr(original_threading,name)
            def Event(self):
                return Sleeper() if original_threading.get_ident()==fixture.worker.ident else original_threading.Event()
        proxy=SimpleNamespace(monotonic=lambda:clock[0],sleep=original_time.sleep)
        start=clock[0]
        with patch.object(run_pilot,'time',proxy),patch.object(run_pilot,'threading',Threads()):
            self.original_wait(seconds,reason,turn,deadline)
        self.waits.append({'configured_seconds':seconds,'virtual_seconds':clock[0]-start})

    def __enter__(self):
        self.server_thread.start()
        original_connection=http.client.HTTPConnection;original_popen=subprocess.Popen
        self.stack.enter_context(patch('runtime_config.auth_home',return_value=self.auth))
        self.stack.enter_context(patch.object(run_pilot,'system_https_proxy',return_value=None))
        fixture=self;self.connection_attempts=0
        class RefusedConnection(original_connection):
            def request(connection,method,url,body=None,headers=None,**kwargs):
                with fixture.lock:
                    fixture.calls.append({'number':len(fixture.calls)+1,'at':time.monotonic(),
                        'payload':json.loads(body),'connection_refused':True})
                return super().request(method,url,body=body,headers=headers or {},**kwargs)
        def connect(*args,**kwargs):
            self.connection_attempts+=1
            if self.failure=='offline' and 1<self.connection_attempts<=1+self.failures:
                return RefusedConnection('127.0.0.1',self.refused_port,timeout=1)
            return original_connection('127.0.0.1',self.server.server_port,timeout=.3 if self.failure=='timeout' else 5)
        self.stack.enter_context(patch.object(http.client,'HTTPSConnection',side_effect=connect))
        self.stack.enter_context(patch.object(fault_control,'queue_notification',self.notify))
        def popen(command,*args,**kwargs):
            if 'app-server' in command:
                state=self.stage.work/'state'
                config=(state/'config.toml').read_text()
                if 'base_url = "http://127.0.0.1:' not in config or kwargs['env']['CODEX_HOME']!=str(state):
                    raise AssertionError('Only the isolated loopback native carrier may launch')
                # The simulated service has no real account. Disable account
                # authentication only in its temporary native configuration;
                # HTTP 403 is still injected on the actual service connection.
                actual=config.replace('requires_openai_auth = true','requires_openai_auth = false')
                (state/'config.toml').write_text(actual)
                (self.stage.logs/'effective-config.toml').write_text(actual)
                (state/'auth.json').unlink(missing_ok=True)
                kwargs['env']['NO_PROXY']='127.0.0.1,localhost'
                kwargs['env']['no_proxy']='127.0.0.1,localhost'
                (self.stage.logs/'test-boundaries.json').write_text(json.dumps({
                    'provider':'synthetic loopback only','authentication':'disabled; no real credentials',
                    'host_proxy':'bypassed for loopback','retry_wait':'real' if self.real_wait else 'virtual clock',
                    'queue_target':'isolated executable outbox; never a real owner task'}))
            return original_popen(command,*args,**kwargs)
        self.stack.enter_context(patch.object(subprocess,'Popen',popen))
        if self.failure=='disk':
            original_open=Path.open
            def open_file(path,*args,**kwargs):
                if path==self.stage.logs/'response-0002.sse':raise OSError(errno.ENOSPC,'Synthetic evidence disk full after checkpoint')
                return original_open(path,*args,**kwargs)
            self.stack.enter_context(patch.object(Path,'open',open_file))
        self.original_wait=self.stage.wait_remote_retry
        if not self.real_wait:self.stage.wait_remote_retry=self.fast_wait
        return self

    def start(self):
        def run():
            try:
                with execution_state.activate(self.recorder):self.outcomes.append(self.stage.execute())
            except BaseException as error:self.errors.append(error)
        self.worker=threading.Thread(target=run,daemon=True);self.worker.start()
        return self

    def until(self, predicate, *, seconds=15):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            if self.errors:raise AssertionError('Native fixture failed: '+repr(self.errors))
            if predicate():return
            time.sleep(.02)
        raise AssertionError('Native fault scenario timed out; errors='+repr(self.errors)+
            '; server='+repr(self.server_errors)+'; calls='+str(len(self.calls))+
            '; fault='+repr(getattr(self.stage,'last_relay_failure',None))+
            '; pause='+repr((self.paused() or {}).get('error'))+
            '; native_methods='+repr([row.get('method') for row in self.rows('events.jsonl')][-16:])+
            '; native_errors='+repr([row.get('params') for row in self.rows('events.jsonl') if row.get('method')=='error'][-2:])[:2000]+
            '; worker_stack='+(''.join(traceback.format_stack(sys._current_frames()[self.worker.ident])[-7:])
                if self.worker.ident in sys._current_frames() else 'worker exited')+
            '; stderr='+((self.stage.logs/'transport-stderr.log').read_text()[-1500:] if
                (self.stage.logs/'transport-stderr.log').exists() else 'none'))

    def rows(self, name):
        path=self.stage.logs/name
        if not path.is_file():return []
        return [json.loads(line) for line in path.read_text().split('\n')[:-1]]

    def paused(self):
        path=self.stage.logs/'error-state.json'
        if not path.exists():return None
        return json.loads(path.read_text())

    def cancel(self):
        if (self.paused() or {}).get('state')=='PAUSED_ERROR':fault_control.cancel_paused(self.stage.logs)
        else:execution_state.request_cancel(self.case)

    def __exit__(self,*args):
        process=self.stage.proc
        try:
            self.release.set()
            if self.worker and self.worker.is_alive():
                self.cancel();self.worker.join(8)
            if process and process.poll() is None:
                self.child_identities.append(execution_state.identity(process.pid))
            self.recorder.close('CANCELLED')
            if self.worker and self.worker.is_alive():self.worker.join(3)
            if self.stage.work.exists():self.stage.release_resources('USER_CANCELLED')
        finally:
            try:
                self.server.shutdown();self.server.server_close();self.server_thread.join(3)
                self.refused.close()
            finally:self.stack.close()
        if self.worker and self.worker.is_alive():raise AssertionError('Controller thread survived explicit test cancellation')
        if process and process.poll() is None:raise AssertionError('Native process survived test teardown')
