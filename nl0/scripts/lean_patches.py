"""Apply text diffs in a disposable Git checkout and read legacy delivery files."""
from contextlib import contextmanager
import json
from pathlib import Path
import re
import shutil

from staging_storage import copy_input


def inventory(root, metadata, *, full=False):
    """Read the bytes declared by a historical delivery's optional patch receipt."""
    if not metadata.get('patches'):
        return {}, None
    from lean_libraries import _input, _verify_file
    prefix=Path('patches')
    path=prefix/'receipt.json'
    _verify_file(_input(root,path),metadata['patches'],full)
    receipt=json.loads((root/path).read_bytes())
    members={path:metadata['patches']}
    for name,sha in receipt['files'].items():
        if not re.fullmatch(r'(?:recipe\.json|lakefile\.lean|lake-manifest\.json|[0-9]{3,}\.patch)',name):
            raise ValueError('Invalid legacy patch evidence path')
        member=prefix/name
        _verify_file(_input(root,member),sha,full)
        members[member]=sha
    return members,receipt


def copy_evidence(source,destination,metadata):
    for member in inventory(source,metadata)[0]:
        target=destination/member
        target.parent.mkdir(parents=True,exist_ok=True)
        copy_input(source/member,target)


@contextmanager
def worktree(work,origin,cache,deadline):
    from controller_common import verify_bindings
    import public_lean
    with public_lean.cached_checkout(work,origin,cache,deadline) as pristine:
        patches=origin.get('local_patches',())
        if not patches:
            yield pristine,set()
            return
        root=work/'patched-checkout'
        shutil.copytree(pristine,root,symlinks=True)
        touched=set()
        verify_bindings(patches)
        for ref in patches:
            file=Path(ref['path'])
            raw=file.read_text()
            if re.search(r'(?m)^(?:GIT binary patch|(?:old mode|new mode|new file mode|deleted file mode) (?!100(?:644|755)$))',raw):
                raise ValueError('Lean patches may only touch ordinary text files')
            paths=[]
            stats=public_lean.git(work,root,['apply','--numstat','-z','--',str(file)],deadline)
            for line in stats.rstrip('\0').split('\0'):
                parts=line.split('\t',2)
                if len(parts)!=3 or not all(value.isdigit() for value in parts[:2]):
                    raise ValueError('Use a textual diff with existing or new relative file paths')
                paths.append(root/public_lean.relative_source(parts[2]))
            public_lean.materialize(work,root,paths,deadline)
            if any(path.resolve()!=path for path in paths):
                raise ValueError('Lean patch touches a redirected path')
            public_lean.git(work,root,['apply','--index','--',str(file)],deadline)
            touched.update(paths)
        yield root,touched


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
