"""Logged public-source search/read tools; no credentials, paywall or CAPTCHA bypass."""
from __future__ import annotations
from datetime import datetime,timezone
from html.parser import HTMLParser
import ipaddress
import http.client
import json
from pathlib import Path
import socket
import urllib.error
import urllib.parse
import urllib.request
import uuid

from controller_common import bind,write

VERSION='yui-source-access-1'
LIMIT=32*1024*1024


class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.links=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style'}:self.hidden+=1
        if tag=='a':
            href=dict(attrs).get('href')
            if href:self.links.append(href)
    def handle_endtag(self,tag):
        if tag in {'script','style'}:self.hidden=max(0,self.hidden-1)
        if tag in {'p','div','br','li','h1','h2','h3'}:self.parts.append('\n')
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)


def public_url(url):
    parts=urllib.parse.urlsplit(url)
    if parts.scheme!='https' or not parts.hostname or parts.username or parts.password:
        raise ValueError('Only public HTTPS source URLs without embedded credentials are allowed')
    if parts.port not in {None,443}:raise ValueError('Nonstandard source ports are not supported')
    addresses=socket.getaddrinfo(parts.hostname,443,type=socket.SOCK_STREAM)
    if not addresses or not any(ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError('Private/local source addresses are not allowed')
    return url


def public_connection(address,timeout=30,source_address=None):
    host,port=address
    candidates=list(dict.fromkeys(row[4][0] for row in socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
                                  if ipaddress.ip_address(row[4][0]).is_global))
    if not candidates:raise ValueError('No public source address')
    last=None
    for ip in candidates:
        try:return socket.create_connection((ip,port),timeout,source_address)
        except OSError as error:last=error
    raise last


class PublicHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        # A configured proxy is user infrastructure, not a URL supplied by the
        # model. Direct source connections use only validated public addresses;
        # the standard HTTPS layer still verifies the original host's TLS name.
        if not self._tunnel_host:self._create_connection=public_connection
        super().connect()


class PublicHTTPS(urllib.request.HTTPSHandler):
    def https_open(self,req):return self.do_open(PublicHTTPSConnection,req,context=self._context)


class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        public_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def fetch(directory,url):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    record={'version':VERSION,'origin':'controller_https','url':url,
            'retrieved_at':datetime.now(timezone.utc).isoformat(),'status':'UNAVAILABLE'}
    path=directory/('access-'+uuid.uuid4().hex+'.json')
    try:
        public_url(url)
        request=urllib.request.Request(url,headers={'User-Agent':'Yui-Source-Reader/1.0'})
        with urllib.request.build_opener(Redirect(),PublicHTTPS()).open(request,timeout=30) as response:
            raw=response.read(LIMIT+1)
            if len(raw)>LIMIT:raise ValueError('Source exceeds the 32 MiB retrieval limit')
            record.update(final_url=response.geturl(),http_status=response.status)
            pdf=raw.startswith(b'%PDF-')
            document=path.with_suffix('.pdf' if pdf else '.html');document.write_bytes(raw)
            record['document']=bind(document)
            if pdf:
                from target_selection import text as document_text
                text=document_text(document)
            else:
                parser=Text();parser.feed(raw.decode('utf-8',errors='replace'))
                text=''.join(parser.parts)
            lower=text.lower()
            blocked=any(marker in lower for marker in ['verify you are human','complete the captcha','checking your browser','access denied'])
            browser=not pdf and b'/httpservice/retry/enablejs' in raw
            record.update(status='HUMAN_ACCESS_REQUIRED' if blocked else 'BROWSER_REQUIRED' if browser else 'READABLE' if text.strip() else 'NO_EXTRACTABLE_TEXT',
                          document=bind(document))
            extracted=path.with_suffix('.txt');extracted.write_text(text)
            record['text']=bind(extracted)
    except urllib.error.HTTPError as error:
        record.update(status='HTTP_ERROR',http_status=error.code,reason=str(error))
    except (OSError,ValueError,ImportError,urllib.error.URLError) as error:
        record.update(reason=type(error).__name__+': '+str(error))
    write(path,record)
    return {**record,'record':bind(path)}


def read(directory,url,*,offset=0,limit=24000):
    result=None
    for path in sorted(Path(directory).glob('access-*.json')):
        previous=json.loads(path.read_text())
        if previous.get('url')==url and previous.get('status')=='READABLE':
            if any(bind(previous[key]['path'])!=previous[key] for key in ('document','text')):
                raise ValueError('Cached source bytes changed')
            result={**previous,'record':bind(path)};break
    if result is None:result=fetch(directory,url)
    if result['status']=='READABLE':
        value=Path(result['text']['path']).read_text();offset=max(0,int(offset));limit=max(1,min(int(limit),24000))
        result.update(content=value[offset:offset+limit],next_offset=offset+limit,
                      has_more=offset+limit<len(value))
    return result


def evidence_references(result,base):
    """Expose own downloaded files as case-relative NL0 evidence bindings."""
    base=Path(base).resolve();references={}
    for key in ('record','document','text'):
        if key not in result:continue
        row=result[key];path=Path(row['path']).resolve()
        if not path.is_relative_to(base) or bind(path)!=row:raise ValueError('Source evidence escaped or changed')
        references[key]={'path':str(path.relative_to(base)),'sha256':row['sha256']}
    return {'evidence':list(references.values()),'access_record':references.get('record'),
            'primary_evidence_candidates':[references[k] for k in ('document','text') if k in references]
                if result.get('status')=='READABLE' else [],
            'evidence_scope':'Readability and transport only. Identify the original complete source before designating primary evidence; search/abstract pages are not theorem verification.'}


def search(directory,query):
    if not isinstance(query,str) or not query.strip():raise ValueError('Supply a source title, author, DOI or search phrase')
    endpoints=[('google','https://www.google.com/search?q='+urllib.parse.quote(query)),
               ('arxiv','https://arxiv.org/search/?searchtype=all&query='+urllib.parse.quote(query))]
    attempts=[];candidates=[]
    for engine,url in endpoints:
        result=fetch(directory,url);attempts.append({'engine':engine,**result})
        if result['status']!='READABLE':continue
        parser=Text();parser.feed(Path(result['document']['path']).read_text(errors='replace'))
        for href in parser.links:
            if href.startswith('/url?'):
                params=urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
                href=(params.get('q') or params.get('url') or [''])[0]
            host=urllib.parse.urlsplit(href).hostname
            if href.startswith('https://') and host and href not in candidates and not (host=='google.com' or host.endswith('.google.com')):
                candidates.append(href)
    return {'query':query,'candidates':candidates[:30],
            'attempts':[{k:r[k] for k in ('engine','status','record')} for r in attempts],
            'scope':'Search results are locators, not verified theorem statements; read the actual source.'}


def defer(directory,*,source_id,statement,input_id,quote,inputs,attempts):
    """Bind an explicit secondary statement to actual failed primary access."""
    import hashlib,re
    if not re.fullmatch(r'E\d{3,}',source_id):raise ValueError('Use an external E source ID')
    if not statement.strip() or input_id not in inputs or not quote.strip() or quote not in inputs[input_id]:
        raise ValueError('A complete stated assumption and exact quotation from a supplied input are required')
    if ' '.join(statement.split())!=' '.join(quote.split()):
        raise ValueError('An unverified external statement must preserve its complete secondary quotation')
    root=Path(directory).resolve();rows=[]
    for relative in attempts:
        path=(root/relative).resolve()
        if not path.is_relative_to(root/'external-sources') or not path.name.startswith('access-') or not path.is_file():
            raise ValueError('Unknown own source-access record')
        row=json.loads(path.read_text())
        if row.get('version')!=VERSION or row.get('origin')!='controller_https' or row.get('status') not in {
                'HTTP_ERROR','HUMAN_ACCESS_REQUIRED','BROWSER_REQUIRED','UNAVAILABLE','NO_EXTRACTABLE_TEXT'}:
            raise ValueError('Deferral needs actual failed primary-text access; readable sources must be checked')
        rows.append({'path':str(path.relative_to(root)),'sha256':bind(path)['sha256']})
    if not rows:raise ValueError('Try retrieving the primary source before deferring its verification')
    folder=root/'external-sources';folder.mkdir(exist_ok=True)
    basis=folder/('secondary-'+hashlib.sha256(inputs[input_id].encode()).hexdigest()+'.txt')
    basis.write_text(inputs[input_id])
    record={'version':'yui-deferred-source-1','source_id':source_id,'statement':statement,
            'basis':{'path':str(basis.relative_to(root)),'sha256':bind(basis)['sha256']},
            'input_id':input_id,'quote':quote,'attempts':rows,
            'qualification':'UNVERIFIED_PRIMARY: conditional on this explicit secondary statement; no original-source fidelity claim.'}
    path=folder/('deferred-'+source_id+'.json')
    if path.exists() and json.loads(path.read_text())!=record:raise ValueError('Preserve the previous deferred statement; use a revised source ID')
    write(path,record)
    return {'path':str(path.relative_to(root)),'sha256':bind(path)['sha256'],'qualification':record['qualification']}
