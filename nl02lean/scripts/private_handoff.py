"""Issue and verify the frozen files exchanged with a single private proof worker."""
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
from pathlib import Path
import re

import ir
import lean_environment
import lean_libraries
import local_helpers
from controller_common import write, verify_bindings

from workflow_execution import block_module

wire = block_module(Path(__file__).resolve().parents[2]/'workflow','private_proof_handoff')


@contextmanager
def locked(directory, name):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory/name).open('a+b') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def publish(path, value):
    ir.need(not path.is_symlink(), 'Linked private proof artifact: '+str(path))
    if path.exists():
        ir.need(ir.load(path)==value, 'Published private proof artifact changed: '+str(path))
    else:
        write(path,value)


def environment():
    value=lean_environment.identity(ir.load_lock())
    libraries=lean_libraries.identity()
    if libraries:
        value['lean_libraries']=libraries
    return value


def run_id(parent):
    parent=Path(parent).resolve()
    for directory in (parent,*parent.parents):
        marker=directory/'.yui-run.json'
        if marker.is_file():
            row=ir.load(marker)
            ir.need(row['root']==str(directory),'Wrong private proof case root')
            return row['run_id']
    return 'standalone-'+local_helpers.digest(str(parent))


@dataclass
class Request:
    path: Path
    record: dict
    source: dict
    contract: Path
    plan: dict
    documents: dict

    @property
    def root(self):
        return self.path.parent


def read_request(path):
    path=Path(path)
    record, files=wire.read_request(path)
    source=ir.load(files['source'])
    declared=ir.load(files['contract']).get('source')
    ir.need(wire.resolve(files['contract'].parent,declared,'/files/contract/source')==files['source'],
            '/files/contract/source: not the issued source')
    contract=ir.contract(files['contract'])
    plan=ir.load(files['plan'])
    ir.validate(files['contract'],plan)
    ir.need(source['identity']==record['task_id'] and source['environment']==environment(),
            '/files/source: different task or Lean environment')
    ir.need(contract['header']==source['header'] and contract['parameters']==source['parameters']
            and contract['premises']==source['premises'] and contract['conclusion']=={'statement':source['statement'],'type':source['type']}
            and plan['terminal']=='T001' and len(plan['steps'])==1 and plan['steps'][0]['explanation']==source['route'],
            '/files/contract or /files/plan: task differs from issued source')
    task={key:source[key] for key in ('identity','header','parameters','premises','type','statement','route')}
    owner={key:record[key] for key in ('run_id','parent_node','parent_context_sha256','task_id')}
    origin=[{k:row[k] for k in ('name','sha256')} for row in source['documents']]
    ir.need(path.parent.name==local_helpers.digest([owner,task,source['environment'],origin]),
            '/files/source: task differs from the originally issued request')
    docs={}
    for index,row in enumerate(source['documents'],1):
        view=wire.resolve(files['source'].parent,row['file'],f'/files/source/documents/{index}/file')
        name=f'S{index:03d} '+row['name']
        docs[name]={'path':str(view),'sha256':row['file']['sha256']}
    return Request(path,record,source,files['contract'],plan,docs)


def issue(base, *, identity, header, parameters, premises, target, statement, route, evidence=(),
          parent_node=None, parent_context=None):
    from jobs import stage_document
    base=Path(base).resolve()
    ir.need(isinstance(identity,str) and re.fullmatch(r'[A-Za-z0-9_]+',identity),'Invalid private proof task ID')
    ir.type_text(target)
    verify_bindings(evidence)
    task={'identity':identity,'header':header,'parameters':parameters,'premises':premises,
          'type':target,'statement':statement,'route':route}
    pins=environment()
    origin=[{'name':Path(ref['path']).name,'sha256':ref['sha256']} for ref in evidence]
    owner={'run_id':run_id(base.parent),'parent_node':parent_node or base.parent.name,
           'parent_context_sha256':parent_context or local_helpers.digest(task),'task_id':identity}
    root=base/local_helpers.digest([owner,task,pins,origin])
    request=root/'request.json'
    with locked(root,'.issue.lock'):
        if not request.exists():
            inputs=root/'input'; inputs.mkdir(exist_ok=True)
            docs=[]
            for i,(ref,original) in enumerate(zip(evidence,origin),1):
                view=inputs/f'source-{i:03d}.txt'
                stage_document(Path(ref['path']),view)
                docs.append({**original,'file':wire.reference(inputs,view)})
            verify_bindings(evidence)
            source=inputs/'source.json'
            write(source,{**task,'documents':docs,'environment':pins})
            cpath=inputs/'contract.json'
            write(cpath,{'version':2,'id':'PrivateProof','source':wire.reference(inputs,source),
                'source_steps':[{'id':'S001','text':route}],
                'pins':{'lean_version':pins['lean_version'],'mathlib_commit':pins['mathlib_commit']},
                'header':header,'parameters':parameters,'premises':premises,'conclusion':{'statement':statement,'type':target},
                'representation':{'scope':'Private conditional proof under the listed ports'},
                'review':{'mode':'development_owner_review','scope':'Local implementation; full parent acceptance required'}})
            plan=inputs/'plan.json'
            write(plan,{'version':2,'contract_sha256':ir.digest(cpath),'representation_notes':'Use the exact enclosing types and binders.',
                'steps':[{'id':'T001','statement':target,'inputs':[p['id'] for p in premises],
                          'source_steps':['S001'],'explanation':route}],'terminal':'T001'})
            ir.validate(cpath,ir.load(plan))
            value={'schema':wire.REQUEST,**owner,'files':{k.stem:wire.reference(root,k) for k in (source,cpath,plan)}}
            wire.validate_request(value,request)
            publish(request,value)
        req=read_request(request)
        ir.need(all(req.record[k]==v for k,v in owner.items()) and all(req.source[k]==v for k,v in task.items())
                and [{k:row[k] for k in ('name','sha256')} for row in req.source['documents']]==origin,
                'Private proof request differs from its issuer')
        if not (root/'legacy-candidate.json').exists() and not any(root.glob('attempt-*')):
            prior=legacy_candidate(req,base,task,evidence)
            if prior is not None:
                publish(root/'legacy-candidate.json',{'request_sha256':ir.digest(request),'proof':prior})
    return request


def native_source(req, proof=None):
    text=ir.render(req.contract,req.plan,{'T001':proof} if proof is not None else None,
                   only='T001' if proof is not None else None, types_only=proof is None)
    return hashlib.sha256(text.encode()).hexdigest()


def validate_native(req, native, proof=None):
    ir.need(ir.native_succeeded(native) and native['selected_environment']==req.source['environment']
            and native['contract_sha256']==ir.digest(req.contract) and native['lean_sha256']==native_source(req,proof),
            '/files/check: native check does not match the issued proof or environment')
    if proof is None:
        ir.need(native['status']=='IR-TYPES-CHECKED' and native['type_check_policy']=='strict-declaration-1',
                '/files/contract: no checked private declaration')
    else:
        ir.need(native['status']=='LOCAL-PROOF-CHECKED' and native['scope']=='T001'
                and isinstance(native.get('axioms'),list) and not set(native['axioms'])-{'propext','Classical.choice','Quot.sound'},
                '/files/check: no successful complete-source and axiom check')


def read_proof(req, attempt, proof_path):
    proof=ir.load(proof_path)
    wire.fields(proof,('request_sha256','attempt','proof'),'/files/proof')
    ir.need(proof['request_sha256']==ir.digest(req.path) and type(proof['attempt']) is int and proof['attempt']==attempt,'/files/proof: different request or attempt')
    local_helpers.unpack(req.contract,req.plan,'T001',proof['proof'])
    return proof['proof']


def checked_body(req, number, files):
    proof=read_proof(req,number,files['proof'])
    check=ir.load(files['check'])
    wire.fields(check,('request_sha256','attempt','proof_sha256','native'),'/files/check')
    ir.need(check['request_sha256']==ir.digest(req.path) and type(check['attempt']) is int and check['attempt']==number and check['proof_sha256']==ir.digest(files['proof']),
            '/files/check: wrong request, attempt or proof digest')
    validate_native(req,check['native'],proof)
    body=local_helpers.as_tactic(proof,ir.local_packet(req.contract,req.plan,'T001'))
    identity=req.record['task_id']
    return local_helpers.NAME.sub(lambda match:'yui_nested_'+identity+'_'+match[0][8:],body)


DETAILS={'needs_parent_repair':('location','required_change'),'unfinished':('reason',),
         'execution_error':('step','error_type','message')}


def read_result(request, result):
    req=read_request(request)
    row,files=wire.read_result(result,request)
    if row['status']=='checked':
        return row,checked_body(req,row['attempt'],files)
    key=wire.OUTCOMES[row['status']][0]
    path=files[key];detail=ir.load(path)
    keys=DETAILS[row['status']]
    wire.fields(detail,('request_sha256','attempt','records',*keys),'/files/'+key)
    ir.need(detail['request_sha256']==ir.digest(request) and type(detail['attempt']) is int and detail['attempt']==row['attempt']
            and all(isinstance(detail[k],str) and detail[k].strip() for k in keys),'/files/'+key+': invalid outcome or identity')
    ir.need(isinstance(detail['records'],dict),'/files/'+key+'/records: expected bound records')
    for name,ref in detail['records'].items():
        wire.resolve(path.parent,ref,'/files/'+key+'/records/'+name)
    return row,detail


def legacy_candidate(req, base, task, evidence):
    """Read an older exact task's source only as a candidate for a new native check."""
    legacy={**task,'evidence':list(evidence),'pins':req.source['environment']['mathlib_commit']}
    root=base/local_helpers.digest(legacy)
    if not root.is_dir():
        return None
    ir.need(root.resolve()==root,'Linked legacy private proof directory')
    saved=root/'checked.json'
    if saved.exists():
        prior=wire.read(saved)
        for key in ('source','result'):
            old=Path(prior[key]['path'])
            ir.need(old.is_relative_to(root) and old.resolve()==old and old.is_file()
                    and prior[key]['sha256']==ir.digest(old),'Changed legacy private '+key)
        source=Path(prior['source']['path'])
        native=ir.load(prior['result']['path'])
        ir.need(ir.load(source)==legacy and ir.native_succeeded(native)
                and native['proof_sha256']==local_helpers.digest(prior['proof']),'Changed legacy private proof')
        return prior['proof']
    for complete in sorted(root.glob('attempt-*/complete.json'),reverse=True):
        folder=complete.parent
        accepted=folder/'worker/accepted.json'
        if not accepted.is_file():
            continue
        source=folder/'source.json';contract=folder/'contract.json'
        ir.need(all(p.is_file() and p.resolve()==p for p in (complete,accepted,source,contract)),
                'Missing or linked legacy native evidence')
        native=ir.load(complete)
        if ir.load(source)!=legacy or not ir.native_succeeded(native):
            continue
        plan={**req.plan,'contract_sha256':ir.digest(contract)}
        proof=ir.load(accepted)['proof']
        local_helpers.unpack(contract,plan,'T001',proof)
        body=local_helpers.as_tactic(proof,ir.local_packet(contract,plan,'T001'))
        body=local_helpers.NAME.sub(lambda match:'yui_nested_'+task['identity']+'_'+match[0][8:],body)
        ir.need(native['proof_sha256']==local_helpers.digest(body),'Changed unpublished legacy private proof')
        return body
    return None
