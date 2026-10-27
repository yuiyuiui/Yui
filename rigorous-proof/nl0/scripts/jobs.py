"""Explicit portable job preparation. Preparation calls neither a model nor Lean."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import uuid

from controller_common import CORE, bind, write, runtime_bindings, verify_bindings
from runtime_config import validate_profile
import library_catalog

VERSION = 'yui-case-job-1'
MARKER = '.yui-run.json'
TRACKS = {'nl0','full','translate','audit-b'}


def source_authority(directory):
    directory=Path(directory).resolve()
    if (directory/'source-selection.json').is_file():
        value=json.loads((directory/'source-selection.json').read_text())
        if set(value)-{'graph','spec','audit_a','incremental'}:raise ValueError('Invalid selected source authority')
        return value
    receipt=directory/'source-acceptance.json'
    if not receipt.is_file() and (directory.parent/'source-acceptance.json').is_file():receipt=directory.parent/'source-acceptance.json'
    return {'graph':str(directory/'nl0.json'),'spec':str(directory/'spec.json'),
            **({'incremental':str(receipt)} if receipt.is_file() else {'audit_a':str(directory/'audit-a.json')})}


def input_file(path):
    path = Path(path).expanduser().resolve(strict=True)
    if path.is_dir():
        path = path/'problem.md'
    if not path.is_file():
        raise ValueError('Supply an explicit proof file, or a directory containing problem.md: '+str(path))
    if path.is_relative_to(CORE):
        raise ValueError('Keep task inputs and outputs outside the installed skill')
    return path


def stage_document(source, destination):
    """Only explicitly named documents are staged; directories are never scanned."""
    if source.suffix.lower() == '.pdf':
        from target_selection import text
        destination.write_text(text(source))
        return 'pdftotext-layout' if shutil.which('pdftotext') else 'pypdf-text'
    source.read_text(encoding='utf-8')
    shutil.copyfile(source,destination)
    return 'exact_utf8_bytes'


def prepare(problem, *, track, profiles, max_concurrency='auto', policy='normal',
            materials=(), source=None, audit=None, output=None, time_budget_seconds=None,
            resume=None, resume_bindings=(), target=None):
    import concurrency
    from runtime_config import time_limit
    if track not in TRACKS or policy not in {'normal','first-pass'}:
        raise ValueError('Unknown track or execution policy')
    if set(profiles) != {'nl0','lean'}:
        raise ValueError('Freeze both profile slots; unused slots are not dispatched')
    profiles = {key:validate_profile(row) for key,row in profiles.items()}
    concurrency.resolve(max_concurrency)
    time_limit(time_budget_seconds)
    problem = input_file(problem)
    extra = [input_file(p) for p in materials]
    if len({problem,*extra}) != len(extra)+1:
        raise ValueError('Repeated explicit input')
    if track == 'translate' and source is None:
        raise ValueError('Translation requires an explicit accepted NL0 source directory')
    if track == 'audit-b' and audit is None:
        raise ValueError('Audit-only work requires an explicit existing native Audit B directory')
    case_id = re.sub('[^a-z0-9-]+','-',problem.parent.name.lower()).strip('-') or 'problem'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run_id = stamp+'-'+uuid.uuid4().hex[:10]
    root = Path(output).expanduser().absolute() if output else problem.parent/'rigorous-proof'/run_id
    if root.exists() or root.is_symlink() or root.resolve().is_relative_to(CORE):
        raise ValueError('Use a new run directory outside the installed skill')
    if any(p == root.resolve() or p.is_relative_to(root.resolve()) for p in [problem,*extra]):
        raise ValueError('A run may not contain/overwrite its original input documents')
    root.mkdir(parents=True,exist_ok=False)
    root=root.resolve();inputs=root/'inputs';inputs.mkdir()
    documents=[]
    try:
        authority=source_authority(source) if source else None
        source_files=[]
        if authority:
            import source_preparation
            data,source_files=source_preparation.read_source(**authority)
            from source_qualification import usable
            if not usable(data[0]):raise ValueError('Translation requires actual accepted Audit A authority')
        audit_files=[]
        if audit:
            for name in ('Proof.lean','compiler.json','mechanical.json','mapping.json'):
                path=Path(audit).resolve()/name
                if not path.is_file():raise ValueError('Missing actual native audit input: '+name)
                audit_files.append(path)
        for number,p in enumerate([problem,*extra]):
            name='problem.md' if number==0 else f'material-{number:03d}'+('.txt' if p.suffix.lower()=='.pdf' else p.suffix or '.txt')
            method=stage_document(p,inputs/name)
            documents.append({'id':name,'path':name,'sha256':bind(inputs/name)['sha256'],
                              'original':bind(p),'extraction':method})
        if target:
            from target_selection import validate as validate_target
            validate_target(target)
            if target['document']!=bind(problem):raise ValueError('Selected target is not from this problem')
            write(inputs/'target-selection.json',target)
            documents.append({'id':'target-selection.json','path':'target-selection.json',
                'sha256':bind(inputs/'target-selection.json')['sha256'],'original':bind(problem),'extraction':'target-selection'})
        if authority and documents[0]['sha256'] not in {row['sha256'] for row in data[2]['inputs']}:
            raise ValueError('Primary proof differs from the accepted NL0 inputs; do not translate a different problem under its receipt')
        write(inputs/'inputs.json',{'inputs':[{k:row[k] for k in ('id','path','sha256')} for row in documents]})
        job={'version':VERSION,'id':case_id+'-'+run_id,'case':case_id,'run_id':run_id,
             'track':track,'policy':policy,'problem':str(problem),'root':str(root),
             'profiles':profiles,'max_concurrency':max_concurrency,'documents':documents,
             'source':str(Path(source).resolve()) if source else None,
             'audit':str(Path(audit).resolve()) if audit else None,
             'source_authority':authority,'authority_bindings':[bind(p) for p in [*source_files,*audit_files]],
             'time_budget_seconds':time_budget_seconds,'runtime':runtime_bindings(),
             'library_catalog':library_catalog.binding()}
        if target:job['target_selection']=target
        if resume:
            job['resume']=resume
            job['authority_bindings'].extend(resume_bindings)
        write(root/'job.json',job)
        write(root/MARKER,{'version':VERSION,'run_id':run_id,'root':str(root),
                          'job':bind(root/'job.json'),'original_inputs':[row['original'] for row in documents]})
        return job
    except Exception:
        # A failed preparation has no model processes or scientific outputs.
        shutil.rmtree(root)
        raise


def validate(job, *, verify_runtime=True):
    if job.get('version')!=VERSION or job.get('track') not in TRACKS:
        raise ValueError('Unsupported explicit case job')
    expected={'version','id','case','run_id','track','policy','problem','root','profiles',
              'max_concurrency','documents','source','audit','source_authority','authority_bindings','time_budget_seconds','runtime'}
    if 'resume' in job:expected.add('resume')
    if 'library_catalog' in job:expected.add('library_catalog')
    if 'target_selection' in job:expected.add('target_selection')
    if set(job)!=expected or job.get('policy') not in {'normal','first-pass'}:
        raise ValueError('Unsupported explicit job fields/policy')
    from runtime_config import time_limit
    import concurrency
    time_limit(job['time_budget_seconds']);concurrency.resolve(job['max_concurrency'])
    root=Path(job['root']).resolve()
    if root.is_relative_to(CORE) or not (root/MARKER).is_file():
        raise ValueError('Unowned output directory or installed-skill output')
    marker=json.loads((root/MARKER).read_text())
    if (marker.get('run_id')!=job['run_id'] or marker.get('root')!=str(root)
            or marker.get('job')!=bind(root/'job.json') or json.loads((root/'job.json').read_text())!=job):
        raise ValueError('Job or ownership binding changed')
    if set(job['profiles'])!={'nl0','lean'}:
        raise ValueError('Missing phase profile')
    for profile in job['profiles'].values():validate_profile(profile)
    manifest=json.loads((root/'inputs/inputs.json').read_text())
    expected_inputs=[{key:row[key] for key in ('id','path','sha256')} for row in job['documents']]
    if manifest!={'inputs':expected_inputs}:
        raise ValueError('Frozen input manifest changed; only the declared documents may be staged')
    for row in job['documents']:
        path=(root/'inputs'/row['path']).resolve()
        if not path.is_relative_to(root/'inputs') or bind(path)['sha256']!=row['sha256']:
            raise ValueError('Frozen task input changed or escaped its directory')
        verify_bindings([row['original']])
    verify_bindings(job['authority_bindings'])
    if 'target_selection' in job:
        from target_selection import validate as validate_target
        validate_target(job['target_selection'])
        if json.loads((root/'inputs/target-selection.json').read_text())!=job['target_selection']:
            raise ValueError('Frozen target selection changed')
    if 'resume' in job:
        from interrupted import validate_descriptor
        validate_descriptor(job)
    if verify_runtime:
        verify_bindings(job['runtime'])
        if 'library_catalog' in job and job['library_catalog']!=library_catalog.binding():
            raise ValueError('Frozen user library selection or evidence changed')
    return job
