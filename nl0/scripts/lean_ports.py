"""Evidence for compiling a whole pinned module under its original name."""
import json
from pathlib import Path
import re

from controller_common import bind, verify_bindings, write
from pilot_common import native_succeeded
from staging_storage import copy_input


VERSION = 'yui-lean-port-1'
FILES = {'original':'original.lean', 'upstream':'upstream.json',
         'target_original':'target-original.json', 'target_ported':'target-ported.json'}


def failed_native(result):
    output = result.get('stdout','')+'\n'+result.get('stderr','')
    return (result.get('exit_code')==1 and not result.get('timed_out') and not result.get('cancelled')
            and not result.get('error_kind') and 'error:' in output
            and not re.search(r'unknown module prefix|object file.*\.olean.*does not exist|heartbeat',output,re.I))


def authorization(refs, origin, module, environment):
    """Read actual native results for the same fixed module in two environments."""
    verify_bindings(refs.values())
    target = json.loads(Path(refs['target_original']['path']).read_bytes())
    upstream = json.loads(Path(refs['upstream']['path']).read_bytes())
    if (target['origin']!=origin or upstream['origin']!=origin or target['module']!=module
            or upstream['module']!=module or target['environment']!=environment
            or upstream['environment']==environment or target['status']!='PUBLIC_LEAN_BUILD_FAILED'
            or upstream['status']!='PUBLIC_LEAN_READY'):
        raise ValueError('Original-name port requires the same pinned module to pass upstream and fail in the target environment')
    files = {'original':target['original_source'], 'upstream':upstream['checks'][module],
             'target_original':target['checks'][module]}
    verify_bindings(files.values())
    if (files['original']['sha256']!=origin['source_sha256']
            or not native_succeeded(json.loads(Path(files['upstream']['path']).read_bytes()))
            or not failed_native(json.loads(Path(files['target_original']['path']).read_bytes()))):
        raise ValueError('Original-name port has no completed native comparison on the full pinned source')
    return files, upstream['environment']


def create(directory, module, origin, environment, inputs, upstream, native, ported_sha256):
    directory.mkdir(parents=True)
    refs = {}
    for role, ref in {**inputs,'target_ported':native}.items():
        path=directory/FILES[role]
        copy_input(ref['path'],path)
        refs[role]={'path':path.name,'sha256':ref['sha256']}
    path=directory/'receipt.json'
    write(path,{'version':VERSION,'module':module,'origin':origin,'original_sha256':origin['source_sha256'],
                'ported_sha256':ported_sha256,'upstream_environment':upstream,'target_environment':environment,
                'files':refs})
    return bind(path)


def inventory(root, metadata, *, full=False):
    """Verify the portable evidence against the manifest's effective source bytes."""
    from lean_libraries import _verify_file
    members={};receipts={}
    modules={row['module']:row for row in metadata['modules']}
    for module,sha in metadata.get('ports',{}).items():
        prefix=Path('ports')/module
        path=prefix/'receipt.json'
        _verify_file(root/path,sha,full)
        receipt=json.loads((root/path).read_bytes())
        target=receipt['target_environment']
        if (receipt['version']!=VERSION or receipt['module']!=module
                or receipt['original_sha256']!=receipt['origin']['source_sha256']
                or receipt['ported_sha256']!=modules[module]['source_sha256']
                or target==receipt['upstream_environment']
                or any(target[k]!=metadata[k] for k in ('lean_version','mathlib_commit'))
                or set(receipt['files'])!=set(FILES)):
            raise ValueError('Changed original-name Lean port provenance: '+module)
        members[path]=sha
        for role,filename in FILES.items():
            ref=receipt['files'][role]
            if set(ref)!={'path','sha256'} or ref['path']!=filename:
                raise ValueError('Invalid portable Lean port evidence path: '+module)
            path=prefix/filename
            _verify_file(root/path,ref['sha256'],full)
            members[path]=ref['sha256']
        if receipt['files']['original']['sha256']!=receipt['original_sha256']:
            raise ValueError('Changed original Lean port source: '+module)
        statuses={key:json.loads((root/prefix/FILES[key]).read_bytes())
                  for key in ('upstream','target_original','target_ported')}
        if (not native_succeeded(statuses['upstream']) or not failed_native(statuses['target_original'])
                or not native_succeeded(statuses['target_ported'])):
            raise ValueError('Invalid native evidence for original-name Lean port: '+module)
        receipts[module]=receipt
    return members,receipts


def copy_evidence(source, destination, metadata):
    for path in inventory(source,metadata)[0]:
        target=destination/path
        target.parent.mkdir(parents=True,exist_ok=True)
        copy_input(source/path,target)


def review_inputs():
    """Expose the same manifest-bound files used for portable delivery."""
    import lean_libraries
    ports={};documents={}
    for descriptor,metadata in lean_libraries.validate(lean_libraries.current()):
        root=Path(descriptor['root'])
        _,receipts=inventory(root,metadata)
        modules={row['module']:row for row in metadata['modules']}
        for module,receipt in receipts.items():
            prefix=root/'ports'/module
            source=root/'source'/Path(*module.split('.')).with_suffix('.lean')
            files={role:(prefix/ref['path'],ref['sha256']) for role,ref in receipt['files'].items()}
            files.update(receipt=(prefix/'receipt.json',metadata['ports'][module]),
                         ported=(source,modules[module]['source_sha256']))
            disclosed={}
            for role,(path,sha) in files.items():
                name=f'basis-port-{module}-{role}{path.suffix}'
                documents[name]=path
                disclosed[role]={'input':name,'sha256':sha}
            ports[module]={'receipt_sha256':metadata['ports'][module],'files':disclosed}
    return ports,documents
