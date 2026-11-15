"""Small same-owner reconnect reminders from actual calls and direct task states."""
import hashlib
import json
from pathlib import Path
import re

VERSION = 'yui-native-reconnect-1'
TOOL = 'read_recovery_state'
INDEX_LIMIT = 16
PAGE_LIMIT = 12000
GUIDANCE = ('Read relevant completed returns with read_recovery_state before deciding '
    'whether to wait, continue or repair locally. Read kind=index for older calls. '
    'For kind=arguments/result, supply call_id and the matching arguments_sha256/result_sha256 as sha256. '
    'If you already have these exact results, continue without rereading them. '
    'Preserve running work; a local tool return does not establish that you received '
    'it before disconnection. These facts do not accept a proof or change your task.')


def text(value):return json.dumps(value, ensure_ascii=False)
def digest(value):return hashlib.sha256(value.encode()).hexdigest()


def records(path):
    if path.is_file():
        with path.open() as stream:
            for line in stream:yield json.loads(line)


def tools():
    return [{'type':'function','name':TOOL,
        'description':'Read only this owner\'s actual call index or saved arguments/result after interruption. Index pages contain at most 16 entries; data pages at most 12000 characters. No foreign files or task results are accessible.',
        'inputSchema':{'type':'object','properties':{
            'kind':{'type':'string','enum':['index','arguments','result']},
            'call_id':{'type':'string','minLength':1},'sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
            'offset':{'type':'integer','minimum':0},
            'limit':{'type':'integer','minimum':1,'maximum':PAGE_LIMIT}},
            'required':['kind'],'additionalProperties':False}}]


def begin_call(owner, params):
    if params['tool']==TOOL:return
    calls=owner.recovery_calls
    if params['callId'] not in calls:
        arguments=text(params['arguments'])
        calls[params['callId']]={'call_id':params['callId'],'tool':params['tool'],
            'turn_id':params['turnId'],'arguments_sha256':digest(arguments),
            'arguments_characters':len(arguments),'state':'RUNNING'}


def complete_call(owner, call_id, delivered):
    row=owner.recovery_calls.get(call_id)
    if row is not None:
        row.update(state='RETURNED',result_sha256=digest(delivered),result_characters=len(delivered))


def progress(owner):
    """No directory walk, proof text, heartbeat, token counter or external query."""
    own={}
    validator=getattr(owner,'validator',None)
    for name in ('attempt','last_checked','last_valid_candidate'):
        value=getattr(validator,name,None)
        if type(value) is int and value>0:own[name]=value
    drafts=getattr(owner,'own_lean_drafts',{})
    for kind,rows in drafts.items():
        if rows:own[kind+'_attempts']=len(rows)
    children=[];recorder=getattr(owner,'execution',None)
    task=getattr(owner,'execution_task',None)
    if recorder is not None and task is not None:
        with recorder.lock:
            children=[{k:row[k] for k in ('id','state','role','stage') if k in row}
                      for row in recorder.state['tasks'].values() if row.get('parent_task')==task]
    return own,children


def snapshot(owner, *, offset=None):
    own,children=progress(owner)
    calls=list(owner.recovery_calls.values())
    start=max(0,len(calls)-INDEX_LIMIT) if offset is None else offset
    child_start=max(0,len(children)-INDEX_LIMIT) if offset is None else offset
    return {'version':VERSION,'thread_id':owner.thread_id,'own_progress':own,
        'calls':calls[start:start+INDEX_LIMIT],'call_total':len(calls),'call_offset':start,
        'children':children[child_start:child_start+INDEX_LIMIT],
        'child_total':len(children),'child_offset':child_start,'mathematical_acceptance':False}


def message(continuation, state):
    return continuation+'\n\nReconnect progress (execution facts only):\n'+text(state)+'\n'+GUIDANCE


def recover(owner, continuation):
    state=snapshot(owner)
    if not state['calls'] and not state['children'] and not state['own_progress']:
        return continuation
    # Identical flaps reuse one small immutable index. Full results already live
    # in tool_history/tools.jsonl; never duplicate them in recovery snapshots.
    content=text(state);sha=digest(content)
    relative='recovery/progress-'+sha+'.json';path=owner.logs/relative
    path.parent.mkdir(exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():raise ValueError('Reconnect progress escapes its owner')
    if path.exists():
        if path.read_text()!=content:raise ValueError('Reconnect progress record changed')
    else:path.write_text(content)
    value=message(continuation,state)
    receipt=owner.logs/'native-client.json'
    if receipt.is_file():
        bound=json.loads(receipt.read_text());key=digest(value)
        allowed=bound.setdefault('allowed_user_message_sha256',[])
        if key not in allowed:
            allowed.append(key)
            bound.setdefault('recovery_inputs',[]).append({'path':relative,'sha256':sha,
                'continuation':continuation,'message_sha256':key})
            receipt.write_text(json.dumps(bound,indent=2)+'\n')
    return value


def read(owner, args):
    """A call ID plus exact content hash, never a caller-supplied filesystem path."""
    try:
        if set(args)-{'kind','call_id','sha256','offset','limit'}:raise ValueError('Unknown recovery field')
        offset=args.get('offset',0);limit=args.get('limit',PAGE_LIMIT)
        if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=PAGE_LIMIT:
            raise ValueError('Invalid recovery page bounds')
        kind=args['kind']
        if kind=='index':return snapshot(owner,offset=offset)
        if kind not in {'arguments','result'}:raise ValueError('Unknown recovery read kind')
        call=args['call_id'];row=owner.recovery_calls[call]
        if kind=='result':value=owner.tool_history[call]
        else:value=json.loads(owner.model_calls[call]['arguments'])
        content=text(value);sha=digest(content)
        if sha!=row[kind+'_sha256'] or sha!=args['sha256']:
            raise ValueError('Recovery content differs from its exact own call')
        if offset>len(content):raise ValueError('Recovery offset exceeds saved content')
        end=min(len(content),offset+limit)
        return {'call_id':call,'kind':kind,'sha256':sha,'text':content[offset:end],
            'offset':offset,'next_offset':end if end<len(content) else None,
            'total_characters':len(content),'mathematical_acceptance':False}
    except (KeyError,ValueError,TypeError) as error:
        return {'error':str(error),'error_type':type(error).__name__,'accepted':False}


def verify_inputs(root, receipt):
    """Bind additional native input to same-thread calls and actual tool returns."""
    entries=receipt.get('recovery_inputs',[])
    if not entries:return True
    try:
        root=Path(root)
        origins={}
        for event in records(root/'events.jsonl'):
            if event.get('method')=='item/tool/call':
                row=event['params'];origins.setdefault(row['callId'],[]).append(row)
        results={}
        for row in records(root/'tools.jsonl'):
            key=(row['tool'],digest(text(row['arguments'])),digest(text(row['result'])))
            results[key]=True
        saved={(r['call_id'],r['tool'],r['arguments_sha256'],r['result_sha256'])
               for r in records(root/'request-lifecycle.jsonl') if r.get('event')=='TOOL_RESULT_SAVED'}
        for entry in entries:
            if not re.fullmatch(r'recovery/progress-[a-f0-9]{64}\.json',entry['path']):return False
            path=root/entry['path']
            if path.is_symlink() or path.parent.is_symlink():return False
            content=path.read_text();state=json.loads(content)
            if digest(content)!=entry['sha256']:return False
            if state['version']!=VERSION or state['mathematical_acceptance'] is not False:return False
            if len(state['calls'])>INDEX_LIMIT or len(state['children'])>INDEX_LIMIT:return False
            if digest(entry['continuation']) not in receipt['allowed_user_message_sha256']:return False
            if digest(message(entry['continuation'],state))!=entry['message_sha256']:return False
            if entry['message_sha256'] not in receipt['allowed_user_message_sha256']:return False
            for row in state['calls']:
                if not any(p['threadId']==state['thread_id'] and p['turnId']==row['turn_id']
                    and p['tool']==row['tool'] and digest(text(p['arguments']))==row['arguments_sha256']
                    for p in origins.get(row['call_id'],[])):return False
                if row['state']=='RETURNED':
                    if (row['tool'],row['arguments_sha256'],row['result_sha256']) not in results:return False
                    if (row['call_id'],row['tool'],row['arguments_sha256'],row['result_sha256']) not in saved:return False
                elif row['state']!='RUNNING':return False
        return True
    except (OSError,KeyError,ValueError,TypeError):return False
