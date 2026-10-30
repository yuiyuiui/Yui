"""Locate and bind the selected Codex installation's local Code Mode helper."""
from pathlib import Path
import hashlib
import json
import os


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve(binary, version):
    binary=Path(binary).resolve()
    # Packaged desktop/standalone distributions declare their layout. Never
    # select a helper from a different PATH installation.
    for root in binary.parents:
        manifest=root/'codex-package.json'
        if not manifest.is_file():continue
        data=json.loads(manifest.read_text())
        if (data.get('layoutVersion')!=1 or not isinstance(data.get('version'),str)
                or not version.endswith(' '+data['version'])):
            raise ValueError('Incompatible Codex package manifest: '+str(manifest))
        helper=(root/'bin/codex-code-mode-host').resolve()
        if not helper.is_relative_to(root):raise ValueError('Codex helper escapes selected installation')
        break
    else:
        root=binary.parent;manifest=None
        helper=(root/'codex-code-mode-host').resolve()
        if not helper.is_relative_to(root):raise ValueError('Codex helper escapes selected installation')
    if not helper.is_file() or not os.access(helper,os.X_OK):
        raise FileNotFoundError('Selected Codex installation needs an executable code-mode host: '+str(helper))
    return {'binary_path':str(binary),'sha256':digest(binary),'version':version,
        'code_mode_host':{'path':str(helper),'sha256':digest(helper)},
        'package_manifest':{'path':str(manifest),'sha256':digest(manifest)} if manifest else None}


def verify(binding):
    for row in [{'path':binding['binary_path'],'sha256':binding['sha256']},binding['code_mode_host'],
                *([binding['package_manifest']] if binding.get('package_manifest') else [])]:
        path=Path(row['path'])
        if not path.is_file() or digest(path)!=row['sha256']:
            raise ValueError('Bound Codex native component changed: '+str(path))
    if not os.access(binding['code_mode_host']['path'],os.X_OK):
        raise ValueError('Bound Codex Code Mode host is not executable')
    return binding


def for_stage(logs, configured):
    """A new worker may not silently swap a prepared run's native installation."""
    logs=Path(logs).resolve()
    for root in (logs,*logs.parents):
        if not (root/'.yui-run.json').is_file():continue
        job=json.loads((root/'job.json').read_text())
        bound=job.get('native_components')
        if bound is not None and bound!=configured:
            raise ValueError('Selected native components differ from prepared job')
        if bound is not None:verify(bound)
        break
    return verify(configured)
