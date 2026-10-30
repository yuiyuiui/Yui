"""Real loopback relay transport; synthetic events, no credentials or models."""
from contextlib import contextmanager
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import socket
import threading
from unittest.mock import patch

from clean_stage import ArtifactStage
import run_pilot


def event(kind='response.created', **fields):
    return ('data: '+json.dumps({'type':kind, **fields},ensure_ascii=False)+'\n\n').encode()


COMPLETE=event('response.completed',response={'id':'synthetic-response','status':'completed'})


class RelayFixture:
    """Keep real HTTP framing and replace only the remote connection destination."""
    def __init__(self, root):
        self.root=Path(root)
        self.stage=ArtifactStage(self.root/'stage','Synthetic transport only.',phase='control',library=False)
        self.stage.network_proxy=None
        self.stage.initial_user_message='Synthetic transport only.'
        self.stage.allowed_user_messages.add(self.stage.initial_user_message)
        self.calls=[]
        self.respond=lambda h:self.stream(h,[event(),COMPLETE])
        fixture=self
        class Upstream(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*args):pass
            def do_POST(self):
                payload=self.rfile.read(int(self.headers['Content-Length']))
                fixture.calls.append(json.loads(payload))
                try:fixture.respond(self)
                except (BrokenPipeError,ConnectionResetError):pass
        self.upstream=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
        self.upstream_thread=threading.Thread(target=self.upstream.serve_forever,daemon=True)
        original=http.client.HTTPConnection
        self.connection_patch=patch.object(run_pilot.http.client,'HTTPSConnection',
            side_effect=lambda *a,**k:original('127.0.0.1',self.upstream.server_port,timeout=3))

    def __enter__(self):
        self.upstream_thread.start();self.connection_patch.start()
        self.port=self.stage.start_relay()
        return self

    def __exit__(self,*args):
        self.stage.relay.shutdown();self.stage.relay.server_close()
        self.upstream.shutdown();self.upstream.server_close();self.upstream_thread.join(3)
        self.connection_patch.stop()
        shutil.rmtree(self.stage.work,ignore_errors=True)

    @staticmethod
    def stream(handler, chunks, *, complete=True, status=200, content_type='text/event-stream'):
        handler.send_response(status);handler.send_header('Content-Type',content_type)
        handler.send_header('Transfer-Encoding','chunked');handler.send_header('Connection','close')
        handler.end_headers()
        for chunk in chunks:
            handler.wfile.write(f'{len(chunk):X}\r\n'.encode()+chunk+b'\r\n');handler.wfile.flush()
        if complete:handler.wfile.write(b'0\r\n\r\n');handler.wfile.flush()
        handler.close_connection=True

    def payload(self):
        return {'model':self.stage.model,'reasoning':{'effort':'high'},'input':[
            {'type':'message','role':'user','content':[{'type':'input_text','text':self.stage.initial_user_message}]}]}

    @contextmanager
    def connected(self, *, payload=None, raw_body=None, headers=None, method='POST',path='/responses'):
        body=raw_body if raw_body is not None else b'' if method=='GET' else json.dumps(payload or self.payload()).encode()
        selected={'Host':'localhost','Content-Length':str(len(body)),'Content-Type':'application/json',
            'Connection':'close',**(headers or {})}
        request=(method+' '+path+' HTTP/1.1\r\n'+''.join(k+': '+v+'\r\n' for k,v in selected.items())+'\r\n').encode()+body
        with socket.create_connection(('127.0.0.1',self.port),timeout=5) as client:
            client.sendall(request)
            yield client

    def exchange(self, **kwargs):
        with self.connected(**kwargs) as client:
            chunks=[]
            while part:=client.recv(65536):chunks.append(part)
        self.wait_closed()
        return b''.join(chunks)

    def wait_closed(self):
        for done in list(getattr(self.stage,'relay_streams',{}).values()):
            if not done.wait(3):raise AssertionError('Local relay stream did not finish')

    def records(self,name):
        path=self.stage.logs/name
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
