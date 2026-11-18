"""File manifests for local Lean work inside translate."""
import hashlib
import json
from pathlib import Path
import re

REQUEST = 'yui-private-proof-request-1'
RESULT = 'yui-private-proof-result-1'
LOCAL_TASK = 'yui-lean-local-task-1'
LOCAL_OWNER = ('run_id', 'sender', 'node', 'contract_sha256', 'plan_sha256')
LOCAL_FILES = ('goal', 'inputs', 'source', 'review')
OUTCOMES = {'checked': ('proof', 'check'), 'needs_parent_repair': ('diagnosis',),
            'unfinished': ('progress',), 'execution_error': ('error',)}
SHA256 = re.compile(r'[a-f0-9]{64}')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(row, names, at):
    require(isinstance(row, dict), f'{at}: expected an object')
    difference = sorted(set(row) ^ set(names))
    require(not difference, f'{at}: missing or unexpected fields {difference}')


def read(path):
    def unique(pairs):
        row = {}
        for key, value in pairs:
            require(key not in row, 'Duplicate JSON field '+key)
            row[key] = value
        return row
    require(path.is_file() and not path.is_symlink(), 'Missing or linked manifest '+str(path))
    return json.loads(path.read_text(), object_pairs_hook=unique)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(base, path):
    return {'path':Path(path).relative_to(base).as_posix(), 'sha256':sha(path)}


def resolve(base, ref, at):
    fields(ref, ('path','sha256'), at)
    name = ref['path']
    require(isinstance(name,str) and name and not Path(name).is_absolute() and '\\' not in name
            and '\0' not in name and all(part not in ('','.','..') for part in name.split('/')), at+'/path: expected a local relative path')
    require(isinstance(ref['sha256'],str) and SHA256.fullmatch(ref['sha256']), at+'/sha256: invalid digest')
    path = base.resolve()/name
    require(path.resolve()==path and path.is_file(), at+'/path: missing or linked file '+name)
    require(sha(path)==ref['sha256'], at+'/sha256: changed file '+name)
    return path


def artifacts(base, row, names):
    fields(row, names, '/files')
    return {name:resolve(base,row[name],'/files/'+name) for name in names}


def read_local_task(path, expected):
    path = Path(path)
    row = read(path)
    fields(expected, LOCAL_OWNER, '/expected')
    fields(row, ('schema', *LOCAL_OWNER, 'files'), '/')
    require(row['schema'] == LOCAL_TASK, '/schema: unknown local Lean task')
    for key, value in expected.items():
        require(row[key] == value, f'/{key}: different local Lean task')
    return artifacts(path.parent, row['files'], LOCAL_FILES)


def read_request(path):
    path = Path(path)
    return validate_request(read(path),path)


def validate_request(row, path):
    fields(row, ('schema','run_id','parent_node','task_id','parent_context_sha256','files'), '/')
    require(row['schema']==REQUEST, '/schema: unknown private proof request')
    for key in ('run_id','parent_node','task_id'):
        require(isinstance(row[key],str) and row[key].strip(), '/'+key+': expected an identifier')
    require(isinstance(row['parent_context_sha256'],str) and SHA256.fullmatch(row['parent_context_sha256']),
            '/parent_context_sha256: invalid digest')
    return row, artifacts(path.parent,row['files'],('source','contract','plan'))


def read_result(path, expected_request):
    path, expected_request = Path(path), Path(expected_request)
    return validate_result(read(path),path,expected_request)


def validate_result(row, path, expected_request):
    fields(row, ('schema','request','attempt','status','files'), '/')
    require(row['schema']==RESULT, '/schema: unknown private proof result')
    number = row['attempt']
    require(type(number) is int and number>0 and path.name==f'result-{number:03d}.json','/attempt: wrong result version')
    require(isinstance(row['status'],str) and row['status'] in OUTCOMES,'/status: unknown private proof outcome')
    issued = resolve(path.parent,row['request'],'/request')
    require(issued==expected_request.parent.resolve()/expected_request.name, '/request: result belongs to another request')
    files = artifacts(path.parent,row['files'],OUTCOMES[row['status']])
    for name, file in files.items():
        require(file.is_relative_to(path.parent.resolve()/f'attempt-{number:03d}'), '/files/'+name+': different attempt')
    return row, files
