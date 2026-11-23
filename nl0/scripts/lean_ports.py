"""Read old portable deliveries which declared dual-environment evidence."""
import json
from pathlib import Path
import re

from pilot_common import native_succeeded
from staging_storage import copy_input


VERSION = 'yui-lean-port-1'
FILES = {'original':'original.lean', 'upstream':'upstream.json',
         'target_original':'target-original.json', 'target_ported':'target-ported.json'}


def _failed_native(result):
    from compiler_feedback import HEADER
    output = result.get('stdout','')+'\n'+result.get('stderr','')
    return (result.get('exit_code')==1 and not result.get('timed_out') and not result.get('cancelled')
            and not result.get('error_kind') and any(m['level'].startswith('error') for m in HEADER.finditer(output))
            and not re.search(r'unknown module prefix|object file.*\.olean.*does not exist|heartbeat',output,re.I))


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
        if (not native_succeeded(statuses['upstream']) or not _failed_native(statuses['target_original'])
                or not native_succeeded(statuses['target_ported'])):
            raise ValueError('Invalid native evidence for original-name Lean port: '+module)
        receipts[module]=receipt
    return members,receipts


def copy_evidence(source, destination, metadata):
    for path in inventory(source,metadata)[0]:
        target=destination/path
        target.parent.mkdir(parents=True,exist_ok=True)
        copy_input(source/path,target)
