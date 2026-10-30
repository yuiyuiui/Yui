"""Faults at a native test provider endpoint, never a production relay."""
import json
from pathlib import Path
import socket
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

from native_fixture import NativeFixture
import run_pilot


class NativeFaultFixture(NativeFixture):
    def __init__(self, root, failure='disconnect', *, failures=1, real_wait=False):
        self.failure=failure;self.failure_count=failures;self.real_wait=real_wait;self.waits=[];self.checkpoint_writes=0
        super().__init__(root,responder=self.respond,validator=self.validate)
        self.checkpoint=self.stage.logs/'saved-checkpoint.json'
        self.original_wait=self.stage.wait_remote_retry
        if not real_wait:self.stage.wait_remote_retry=self.fast_wait

    def validate(self,value):
        if value=={'checkpoint':True}:
            self.checkpoint_writes+=1;self.checkpoint.write_text('{"saved":true}')
        elif value!={'complete':True} or not self.checkpoint.exists():raise ValueError('Missing checked checkpoint')
        return {'synthetic':True}

    def respond(self,fixture,handler,number,payload):
        if number==1:return self.tool(handler,number,'check_draft',{'checkpoint':True})
        if number>1+self.failure_count:return self.tool(handler,number,'submit_draft',{'complete':True})
        if isinstance(self.failure,int):
            code={401:'authentication_error',403:'authentication_error',402:'credit_balance_exhausted',
                429:'rate_limit_exceeded',503:'server_is_overloaded'}.get(self.failure,'invalid_request_error')
            body=json.dumps({'error':{'code':code,'type':code,'message':'Synthetic provider error'}}).encode()
            handler.send_response(self.failure);handler.send_header('Content-Length',str(len(body)))
            handler.send_header('Content-Type','application/json');handler.send_header('Connection','close')
            handler.end_headers();handler.wfile.write(body);handler.wfile.flush();handler.close_connection=True;return
        handler.send_response(200);handler.send_header('Content-Type','text/event-stream')
        handler.send_header('Transfer-Encoding','chunked');handler.send_header('Connection','close');handler.end_headers()
        event={'type':'response.created','response':{'id':f'partial-{number}','model':self.stage.model,'status':'in_progress','output':[]}}
        block=('data: '+json.dumps(event)+'\n\n').encode()
        handler.wfile.write(f'{len(block):X}\r\n'.encode()+block+b'\r\n');handler.wfile.flush()
        if self.failure=='timeout':time.sleep(.5)
        try:handler.connection.shutdown(socket.SHUT_RDWR)
        except OSError:pass
        handler.connection.close();handler.close_connection=True

    def fast_wait(self,seconds,reason,turn,deadline):
        original_time=time;original_threading=threading;clock=[time.monotonic()]
        fixture=self
        class Sleeper:
            def wait(self,duration):clock[0]+=duration
        class Threads:
            def __getattr__(self,name):return getattr(original_threading,name)
            def Event(self):return Sleeper() if original_threading.get_ident()==fixture.worker.ident else original_threading.Event()
        with patch.object(run_pilot,'time',SimpleNamespace(monotonic=lambda:clock[0],sleep=original_time.sleep)),patch.object(run_pilot,'threading',Threads()):
            self.original_wait(seconds,reason,turn,deadline)
        self.waits.append(seconds)

    def paused(self):
        path=self.stage.logs/'error-state.json'
        return json.loads(path.read_text()) if path.is_file() else None
