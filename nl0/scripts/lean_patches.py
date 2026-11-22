"""Explicit patch recipes and portable evidence for fixed public Lean libraries."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import shutil
import time

from controller_common import bind, write
from execution_state import current
import native_workspace
from staging_storage import copy_input, write_bytes

RECIPE = 'yui-lean-patch-recipe-1'
RECEIPT = 'yui-lean-patches-1'
SHA = re.compile(r'[0-9a-f]{64}')


def relative(path, suffix=''):
    if (not isinstance(path,str) or not re.fullmatch(r'[A-Za-z0-9_.\-/]+',path)
            or not path.endswith(suffix) or any(part.lower() in {'','.','..','.git'} for part in path.split('/'))):
        raise ValueError('Invalid relative '+suffix+' path in Lean patch recipe')
    return Path(path)


def recipe_value(raw, origin):
    recipe=json.loads(raw)
    if (not isinstance(recipe,dict) or set(recipe)!={'version','repository','revision','patches'}
            or recipe['version']!=RECIPE or any(recipe[k]!=origin[k] for k in ('repository','revision'))
            or not isinstance(recipe['patches'],list) or not recipe['patches']):
        raise ValueError('An explicit patch recipe must name this fixed repository and commit')
    names=set()
    for row in recipe['patches']:
        if (not isinstance(row,dict) or set(row)!={'path','sha256'} or not isinstance(row['sha256'],str)
                or not SHA.fullmatch(row['sha256'])):
            raise ValueError('Invalid ordered patch digest in the recipe')
        relative(row['path'],'.patch')
        if row['path'] in names:raise ValueError('Duplicate patch in the recipe')
        names.add(row['path'])
    return recipe


def frozen_recipe(run, locator, origin):
    if run is None:
        raise ValueError('A user-frozen patch recipe requires a prepared run')
    run=Path(run)
    marker=json.loads((run/'.yui-run.json').read_bytes())
    job=json.loads((run/'job.json').read_bytes())
    if marker.get('job')!=bind(run/'job.json') or marker.get('run_id')!=job.get('run_id'):
        raise ValueError('Invalid frozen patch input authority')
    inputs=run/'inputs'
    def read(row):
        path=inputs/row['path']
        if path.resolve()!=path or not path.is_relative_to(inputs) or bind(path)['sha256']!=row['sha256']:
            raise ValueError('Changed frozen patch input')
        return path.read_bytes()
    recipe=next((row for row in job['documents'] if row['id']==locator and locator.endswith('.json')),None)
    if recipe is None:
        raise ValueError('Use an explicitly frozen patch recipe input')
    raw=read(recipe)
    files=[]
    for row in recipe_value(raw,origin)['patches']:
        doc=next((item for item in job['documents'] if item['path'].endswith('.patch')
                  and item['sha256']==row['sha256']),None)
        if doc is None:
            raise ValueError('Patch digest is absent from the frozen inputs: '+row['path'])
        files.append(read(doc))
    return raw,files,{'kind':'USER_FROZEN','input':locator,'run_id':job['run_id']}


def locked_patch(config, lock, origin):
    """Recognize Lake's pinned dependency and the static post_update patch list."""
    packages=json.loads(lock)['packages']
    matches=[item['name'].removeprefix('«').removesuffix('»') for item in packages
             if item.get('type')=='git' and not item.get('subDir') and not item.get('inherited')
             and item.get('rev')==origin['revision'] and item['url'].removesuffix('.git')==origin['repository'].removesuffix('.git')]
    if len(matches)!=1:raise ValueError('The upstream Lake lock must name the exact unvendored dependency')
    package=matches[0]
    if not re.fullmatch(r'[A-Za-z0-9_-]+',package):raise ValueError('Unsupported upstream package name')
    post=('\n'+config.decode()).partition('\npost_update ')[2]
    for names,body in re.findall(r'\bfor\s+name\s+in\s+#\[([^\]]+)\]\s+do\s*\n((?:    [^\n]*\n)+)',post):
        if not any(package in choice for choice in re.findall(r'`(?:«([\w-]+)»|([\w-]+))',names)):
            continue
        template=re.search(r'let patchNames := #\[s!"\{label\}(-[\w.-]+\.patch)"\]',body)
        if template and 'for patchName in patchNames do' in body and re.search(r'/ "patches" /',body):
            return Path('patches')/(package+template[1])
    raise ValueError('Upstream Lake configuration does not declare a supported patch for '+package)


def upstream_recipe(work, cache, locator, origin, deadline):
    import public_lean
    authority=public_lean.raw_pin(locator,'.json') or public_lean.raw_pin(locator,'.lean')
    if authority is None or not (locator.endswith('.json') or Path(authority['source_path']).name=='lakefile.lean'):
        raise ValueError('Use a fixed upstream build recipe URL or a frozen recipe input')
    with public_lean.cached_checkout(work,authority,cache,deadline) as root:
        path=root/authority['source_path']
        def read(paths):
            public_lean.materialize(work,root,paths,deadline)
            if any(p.resolve()!=p or not p.is_file() for p in paths):
                raise ValueError('The fixed upstream build recipe or an input is missing')
            return [p.read_bytes() for p in paths]
        if path.name=='lakefile.lean':
            config,lock=read([path,path.with_name('lake-manifest.json')])
            patch=locked_patch(config,lock,origin)
            files=read([path.parent/patch])
            raw=json.dumps({'version':RECIPE,'repository':origin['repository'],'revision':origin['revision'],
                            'patches':[{'path':str(patch),'sha256':hashlib.sha256(files[0]).hexdigest()}]}).encode()
            return raw,files,{'kind':'UPSTREAM_BUILD',**authority},{'lakefile.lean':config,'lake-manifest.json':lock}
        raw,=read([path])
        paths=[path.parent/relative(row['path'],'.patch') for row in recipe_value(raw,origin)['patches']]
        return raw,read(paths),{'kind':'UPSTREAM_BUILD',**authority},{}


def retain(directory, raw, files, authority, origin, config):
    rows=recipe_value(raw,origin)['patches']
    materials={'recipe.json':raw,**config}
    if len(rows)!=len(files):
        raise ValueError('Incomplete ordered patch recipe')
    for index,(row,patch) in enumerate(zip(rows,files),1):
        sha=hashlib.sha256(patch).hexdigest()
        if sha!=row['sha256']:
            raise ValueError('Patch digest mismatch: '+row['path'])
        materials[f'{index:03d}.patch']=patch
    directory.mkdir(parents=True,exist_ok=True)
    for filename,data in materials.items():
        write_bytes(directory/filename,data)
    receipt=directory/'receipt.json'
    write(receipt,{'version':RECEIPT,'repository':origin['repository'],'revision':origin['revision'],
                   'authority':authority,'files':{name:hashlib.sha256(data).hexdigest() for name,data in materials.items()},
                   'order':[row['sha256'] for row in rows]})
    return {**bind(receipt),'kind':authority['kind']}


def inventory(root, metadata, *, full=False):
    """Verify the portable recipe and every ordered patch against the manifest."""
    if not metadata.get('patches'):
        return {},None
    from lean_libraries import _input, _verify_file
    prefix=Path('patches');path=prefix/'receipt.json'
    _verify_file(_input(root,path),metadata['patches'],full)
    receipt=json.loads((root/path).read_bytes())
    kind=receipt['authority']['kind']
    if receipt['version']!=RECEIPT or kind not in {'USER_FROZEN','UPSTREAM_BUILD'}:
        raise ValueError('Missing patch source authorization')
    members={path:metadata['patches']}
    files=receipt['files']
    recipe_path=prefix/'recipe.json'
    _verify_file(_input(root,recipe_path),files['recipe.json'],full)
    members[recipe_path]=files['recipe.json']
    rows=recipe_value((root/recipe_path).read_bytes(),receipt)['patches']
    if receipt['order']!=[row['sha256'] for row in rows]:
        raise ValueError('Patch order differs from the authorized recipe')
    if kind=='UPSTREAM_BUILD' and Path(receipt['authority']['source_path']).name=='lakefile.lean':
        for name in ('lakefile.lean','lake-manifest.json'):
            member=prefix/name
            _verify_file(_input(root,member),files[name],full)
            members[member]=files[name]
        patch=locked_patch((root/prefix/'lakefile.lean').read_bytes(),(root/prefix/'lake-manifest.json').read_bytes(),receipt)
        if [row['path'] for row in rows]!=[str(patch)]:raise ValueError('The retained Lake configuration declares a different patch')
    for index,row in enumerate(rows,1):
        file=prefix/f'{index:03d}.patch'
        if files.get(file.name)!=row['sha256']:
            raise ValueError('Patch digest differs from the authorized recipe')
        _verify_file(_input(root,file),row['sha256'],full)
        members[file]=row['sha256']
    if set(files)!={p.name for p in members if p!=path}:
        raise ValueError('Unrecognized additional patch evidence')
    return members,receipt


def verify_origin(origin, *, full=False):
    ref=origin['patch_authority']
    path=Path(ref['path'])
    if path.name!='receipt.json' or path.parent.name!='patches':
        raise ValueError('Invalid retained patch authority path')
    members,receipt=inventory(path.parent.parent,{'patches':ref['sha256']},full=full)
    if (receipt['authority']['kind']!=ref['kind'] or receipt['order']!=origin['patch_order']
            or any(receipt[k]!=origin[k] for k in ('repository','revision'))):
        raise ValueError('Patched Lean origin differs from its authorized recipe')
    return path.parent.parent,members


def copy_evidence(source,destination,metadata):
    for path in inventory(source,metadata)[0]:
        target=destination/path
        target.parent.mkdir(parents=True,exist_ok=True)
        copy_input(source/path,target)


@contextmanager
def worktree(work,origin,cache,deadline):
    """Apply authorized patches to an isolated copy of the fixed checkout."""
    import public_lean
    with public_lean.cached_checkout(work,origin,cache,deadline) as pristine:
        if 'patch_authority' not in origin:
            yield pristine
            return
        source,members=verify_origin(origin)
        root=work/'patched-checkout'
        shutil.copytree(pristine,root,symlinks=True)
        for patch in sorted(path for path in members if path.suffix=='.patch'):
            file=source/patch
            raw=file.read_bytes().decode()
            if re.search(r'(?m)^(?:GIT binary patch|(?:old mode|new mode|new file mode|deleted file mode) (?!100(?:644|755)$))',raw):
                raise ValueError('Lean patches may only touch ordinary text files')
            files=[]
            for line in public_lean.git(work,root,['apply','--numstat','--',str(file)],deadline).splitlines():
                added,removed,name=line.split('\t',2)
                if not added.isdigit() or not removed.isdigit():
                    raise ValueError('Lean patch must be a textual source diff')
                files.append(root/relative(name))
            if not files:
                raise ValueError('Lean patch has no source changes')
            public_lean.materialize(work,root,files,deadline)
            if any(path.resolve()!=path for path in files):
                raise ValueError('Lean patch touches a redirected path')
            public_lean.git(work,root,['apply','--index','--check','--',str(file)],deadline)
            public_lean.git(work,root,['apply','--index','--',str(file)],deadline)
        yield root


def read_source(base,url,recipe,*,offset=0,limit=24000,browser=False):
    import lean_libraries
    import public_lean
    import source_access
    pin=public_lean.raw_pin(url,'.lean')
    if pin is None:
        raise ValueError('A patched source needs the exact .lean URL at a fixed Git commit')
    if browser:raise ValueError('Patched source is read from a fixed Git checkout')
    locator=recipe
    external=Path(base)/'external-sources'
    key=hashlib.sha256((url+'\n'+locator).encode()).hexdigest()
    access=external/f'access-patched-{key}.json'
    if not access.is_file():
        run=lean_libraries.generated_root()
        cache=Path(run)/'public-sources' if run else external/'public-sources'
        recorder,_=current()
        deadline=time.monotonic()+(recorder.remaining(1800) if recorder else 1800)
        if locator.startswith('https://'):
            with native_workspace.temporary('yui-patch-recipe-') as work:
                native_workspace.record(work,confirmed=True,phase='patch-recipe')
                raw,files,authority,config=upstream_recipe(work,cache,locator,pin,deadline)
        else:
            raw,files,authority=frozen_recipe(Path(run).parent if run else None,locator,pin)
            config={}
        pin['patch_authority']=retain(external/f'patch-recipe-{key}'/'patches',raw,files,authority,pin,config)
        pin['patch_order']=[row['sha256'] for row in recipe_value(raw,pin)['patches']]
        with native_workspace.temporary('yui-patched-lean-source-') as work:
            native_workspace.record(work,confirmed=True,phase='patched-source')
            with worktree(work,pin,cache,deadline) as root:
                source=root/pin['source_path']
                public_lean.materialize(work,root,[source],deadline)
                if source.resolve()!=source or not source.is_file():
                    raise ValueError('Requested Lean file is absent after applying the authorized patches')
                content=external/f'patched-{key}.lean'
                copy_input(source,content)
        document=bind(content)
        pin['source_sha256']=document['sha256']
        write(access,{'status':'READABLE','document_kind':'TEXT','url':url,'final_url':url,
                      'recipe':locator,'document':document,'text':document,'patched_origin':pin})
    return source_access.read(external,url,offset=offset,limit=limit,recipe=locator)


def review_inputs():
    import lean_libraries
    evidence={};documents={}
    for descriptor,metadata in lean_libraries.validate(lean_libraries.current()):
        root=Path(descriptor['root'])
        members,receipt=inventory(root,metadata)
        if not members:
            continue
        name=metadata['name']
        files={}
        for path,sha in members.items():
            filename=f'basis-patch-{name}-{path.name}'
            documents[filename]=root/path
            files[path.name]={'input':filename,'sha256':sha}
        modules={}
        for row in metadata['modules']:
            module=row['module'];filename=f'basis-patched-source-{module}.lean'
            documents[filename]=root/'source'/Path(*module.split('.')).with_suffix('.lean')
            modules[module]={'input':filename,'sha256':row['source_sha256']}
        evidence[name]={'authority':receipt['authority'],'repository':receipt['repository'],
                        'revision':receipt['revision'],'order':receipt['order'],'files':files,
                        'modules':modules}
    return evidence,documents
