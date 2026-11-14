"""Explicit portable job preparation; formal jobs verify their selected Lean pair."""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import ExitStack,contextmanager
from functools import wraps
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from staging_storage import copy_input
import re
import shutil
import subprocess
import uuid

from controller_common import CORE, bind, write, runtime_bindings, verify_bindings
from runtime_config import validate_profile
from variant import OUTPUT_DIRECTORY

VERSION = 'yui-case-job-5'
ATTACHMENT_VERSION = 'yui-case-job-4'
ENVIRONMENT_VERSION = 'yui-case-job-3'
LEGACY_VERSION = 'yui-case-job-2'
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
    copy_input(source,destination)
    return 'exact_utf8_bytes'


def prepare(problem, *, track, profiles, max_concurrency='auto', policy='normal',
            materials=(), source=None, audit=None, output=None, time_budget_seconds=None,
            resume=None, resume_bindings=(), target=None, formalization='conditional', stop_after=None,
            lean_environment=None, lean_libraries=()):
    import concurrency
    from runtime_config import time_limit
    if track not in TRACKS or policy not in {'normal','first-pass'}:
        raise ValueError('Unknown track or execution policy')
    from basis import validate_mode
    validate_mode(formalization, track,resume=resume)
    from workflow_checkpoint import allowed
    if stop_after is not None and (resume or stop_after not in allowed(track,formalization)):
        raise ValueError('Cannot stop after a stage outside the requested public route')
    if set(profiles) != {'nl0','lean'}:
        raise ValueError('Freeze both profile slots; unused slots are not dispatched')
    profiles = {key:validate_profile(row) for key,row in profiles.items()}
    concurrency.resolve(max_concurrency)
    time_limit(time_budget_seconds)
    import lean_environment as environments
    if resume and lean_libraries:raise ValueError('Recovery inherits frozen Lean libraries; do not attach a replacement')
    if resume:
        prior = json.loads((Path(resume['prior_run'])/'job.json').read_text())
        selected = (prior.get('lean_environment') if 'lean_environment' in prior else
                    environments.legacy() if prior['track'] != 'nl0' else None)
        if lean_environment is not None and lean_environment != selected:
            raise ValueError('Recovery cannot change the frozen Lean environment')
    else:
        selected = lean_environment if lean_environment is not None else (
            environments.resolve() if track != 'nl0' or lean_libraries else None)
    if selected is not None:
        selected = environments.verify(selected)
    from runtime_config import use_environment
    import lean_libraries as attached_lean
    with use_environment(selected),attached_lean.generated(None),ExitStack() as selections:
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
        root = Path(output).expanduser().absolute() if output else problem.parent/OUTPUT_DIRECTORY/run_id
        if root.exists() or root.is_symlink() or root.resolve().is_relative_to(CORE):
            raise ValueError('Use a new run directory outside the installed skill')
        if any(p == root.resolve() or p.is_relative_to(root.resolve()) for p in [problem,*extra]):
            raise ValueError('A run may not contain/overwrite its original input documents')
        root.mkdir(parents=True,exist_ok=False)
        root=root.resolve();inputs=root/'inputs';inputs.mkdir()
        from fault_control import capture_owner
        capture_owner(root)
        documents=[]
        try:
            import lean_libraries as attached_lean
            inherited=([*prior.get('lean_libraries',[]),*attached_lean.read_generated(
                Path(prior['root'])/'imported-lean',base=prior.get('lean_libraries',[]))] if resume else [])
            attachments=(attached_lean.inherit(inherited,root) if resume else
                         [attached_lean.capture(path,root) for path in lean_libraries])
            selections.enter_context(attached_lean.use(attachments))
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
            if formalization=='unconditional' and not target:
                raise ValueError('Unconditional formalization needs an explicit frozen target selection')
            prior_summaries=({json.loads((Path(prior['root'])/'inputs'/row['path']).read_text())['name']:row
                for row in prior['documents'] if row.get('extraction')=='explicit_lean_library_summary'} if resume else {})
            for index,descriptor in enumerate(attachments,1):
                if resume and descriptor['name'] not in prior_summaries:continue
                old_summary=prior_summaries.get(descriptor['name'])
                name=old_summary['id'] if old_summary else f'lean-library-{index:03d}.json'
                with attached_lean.use([descriptor]):write(inputs/name,attached_lean.summary()[0])
                original=Path(inherited[index-1]['manifest']['path']) if resume else Path(lean_libraries[index-1]).resolve()
                documents.append({'id':name,'path':name,'sha256':bind(inputs/name)['sha256'],
                    'original':bind(original),'extraction':'explicit_lean_library_summary'})
            if authority and documents[0]['sha256'] not in {row['sha256'] for row in data[2]['inputs']}:
                raise ValueError('Primary proof differs from the accepted NL0 inputs; do not translate a different problem under its receipt')
            write(inputs/'inputs.json',{'inputs':[{k:row[k] for k in ('id','path','sha256')} for row in documents]})
            import runtime_snapshot
            snapshot,runtime=runtime_snapshot.capture(root,runtime_bindings(),core=CORE)
            job={'version':VERSION,'id':case_id+'-'+run_id,'case':case_id,'run_id':run_id,
                 'track':track,'policy':policy,'problem':str(problem),'root':str(root),
                 'profiles':profiles,'max_concurrency':max_concurrency,'documents':documents,
                 'lean_environment':selected,'lean_libraries':attachments,
                 'source':str(Path(source).resolve()) if source else None,
                 'audit':str(Path(audit).resolve()) if audit else None,
                 'source_authority':authority,'authority_bindings':[bind(p) for p in [*source_files,*audit_files]],
                 'time_budget_seconds':time_budget_seconds,'runtime':runtime,
                 'runtime_snapshot':snapshot}
            job['formalization']=formalization
            if stop_after:job['stop_after']=stop_after
            if (any(r['path']==str(root/'runtime/workflow/workflow.json') for r in runtime)
                    and track in {'nl0','full'} and (not resume or resume.get('mode')=='basis-revision')):
                job['workflow_protocol']='yui-workflow-1'
            from runtime_config import host_tools
            job['native_components']=deepcopy(host_tools()['codex'])
            if target:job['target_selection']=target
            if resume:
                job['resume']=resume
                job['authority_bindings'].extend(resume_bindings)
                import basis
                prior=json.loads((Path(resume['prior_run'])/'job.json').read_text())
                if basis.mode(prior)!=formalization:raise ValueError('Recovery cannot change the formalization goal')
                job['authority_bindings'].extend(basis.recovery_bindings(prior))
            write(root/'job.json',job)
            write(root/MARKER,{'version':VERSION,'run_id':run_id,'root':str(root),
                              'job':bind(root/'job.json'),'original_inputs':[row['original'] for row in documents]})
            return job
        except Exception:
            # A failed preparation has no model processes or scientific outputs.
            shutil.rmtree(root)
            raise


@contextmanager
def scientific_context(job):
    """Use one job's frozen environment, attachments and generated public units."""
    if not isinstance(job,dict) or not isinstance(job.get('root'),str) or not Path(job['root']).is_absolute():
        raise ValueError('A frozen scientific context requires its absolute owned job root')
    import lean_environment as environments
    import lean_libraries
    from runtime_config import use_environment
    selected=(job.get('lean_environment') if 'lean_environment' in job else
              environments.legacy() if job.get('version')==LEGACY_VERSION and job.get('track')!='nl0' else None)
    with use_environment(selected),lean_libraries.generated(None),lean_libraries.use(job.get('lean_libraries',[])), \
            lean_libraries.generated(Path(job['root'])/'imported-lean'):
        yield


def prior_context(function):
    @wraps(function)
    def scoped(previous,*args,**kwargs):
        job=json.loads((Path(previous).resolve()/'job.json').read_text())
        with scientific_context(job):return function(previous,*args,**kwargs)
    return scoped


def resume_materials(job):
    problem=Path(job['problem']);result=[]
    for row in job['documents'][1:]:
        path=Path(row['original']['path'])
        if row['id']!='target-selection.json' and row.get('extraction')!='explicit_lean_library_summary' and path!=problem and path not in result:
            result.append(path)
    return result


def validate(job, *, verify_runtime=True):
    """All consumers validate a job under its own frozen scientific scope."""
    with scientific_context(job):return _validate(job,verify_runtime=verify_runtime)


def _validate(job, *, verify_runtime=True):
    if job.get('version') not in {VERSION,ATTACHMENT_VERSION,ENVIRONMENT_VERSION,LEGACY_VERSION} or job.get('track') not in TRACKS:
        raise ValueError('Unsupported explicit case job')
    if job['version'] in {VERSION,ATTACHMENT_VERSION,ENVIRONMENT_VERSION} and 'lean_environment' not in job:
        raise ValueError('A v3/v4/v5 job must freeze its Lean selection or explicit NL0 null')
    if job['version'] in {VERSION,ATTACHMENT_VERSION} and 'lean_libraries' not in job:
        raise ValueError('A v4/v5 job must freeze its explicit Lean library scope')
    if job['version']==VERSION and ('runtime_snapshot' not in job
            or 'library_root' in job['runtime_snapshot']):
        raise ValueError('A v5 job requires a catalog-free runtime snapshot')
    expected={'version','id','case','run_id','track','policy','problem','root','profiles',
              'max_concurrency','documents','source','audit','source_authority','authority_bindings','time_budget_seconds','runtime'}
    if 'stop_after' in job:
        from workflow_checkpoint import allowed
        if not job.get('workflow_protocol') or job['stop_after'] not in allowed(job['track'],job.get('formalization')):
            raise ValueError('Unknown workflow stopping point')
        expected.add('stop_after')
    if 'workflow_protocol' in job:
        if job['workflow_protocol']!='yui-workflow-1' or job['track'] not in {'nl0','full'}:
            raise ValueError('Unknown public workflow protocol or track')
        expected.add('workflow_protocol')
    if 'resume' in job:expected.add('resume')
    if job['version']!=VERSION and 'library_catalog' in job:expected.add('library_catalog')
    if 'runtime_snapshot' in job:expected.add('runtime_snapshot')
    if 'target_selection' in job:expected.add('target_selection')
    if 'native_components' in job:expected.add('native_components')
    if 'formalization' in job:expected.add('formalization')
    if 'lean_environment' in job:expected.add('lean_environment')
    if job['version'] in {VERSION,ATTACHMENT_VERSION}:expected.add('lean_libraries')
    if set(job)!=expected or job.get('policy') not in {'normal','first-pass'}:
        raise ValueError('Unsupported explicit job fields/policy')
    if 'lean_environment' in job:
        selected = job['lean_environment']
        if selected is None and job['track'] != 'nl0':
            raise ValueError('Formalization requires a frozen Lean environment')
        if selected is not None:
            import lean_environment as environments
            environments.verify(selected)
    from basis import validate_mode
    validate_mode(job.get('formalization','conditional'),job['track'],resume=job.get('resume'))
    if 'native_components' in job:
        from native_runtime import verify
        verify(job['native_components'])
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
    if job.get('lean_libraries'):
        import lean_libraries
        if any(Path(row['root']).parent!=root/'lean-libraries' for row in job['lean_libraries']):
            raise ValueError('Lean library attachment belongs to another run')
        lean_libraries.validate(job['lean_libraries'],full=True)
    __import__('lean_libraries').read_generated(root/'imported-lean',base=job.get('lean_libraries',[]),full=True)
    if 'target_selection' in job:
        from target_selection import validate as validate_target
        validate_target(job['target_selection'])
        if json.loads((root/'inputs/target-selection.json').read_text())!=job['target_selection']:
            raise ValueError('Frozen target selection changed')
    if 'resume' in job:
        if job['resume'].get('mode')=='native-proof-cleanup':
            from native_cleanup_recovery import validate_descriptor
        elif job['resume'].get('mode')=='native-proof-io':
            from proof_io_recovery import validate_descriptor
        elif job['resume'].get('mode')=='basis-final-closure':
            from basis_closure_recovery import validate_descriptor
        elif job['resume'].get('mode')=='basis-revision':
            from basis_defect import validate_descriptor
        else:
            from interrupted import validate_descriptor
        validate_descriptor(job)
        import basis
        prior=json.loads((Path(job['resume']['prior_run'])/'job.json').read_text())
        if 'lean_environment' in prior and job.get('lean_environment') != prior['lean_environment']:
            raise ValueError('Recovery changed the frozen Lean environment')
        if basis.mode(prior)!=basis.mode(job):raise ValueError('Recovery changed formalization goal')
        if not all(r in job['authority_bindings'] for r in basis.recovery_bindings(prior)):
            raise ValueError('Recovery omitted prepared basis bindings')
    if verify_runtime:
        import runtime_snapshot
        if 'runtime_snapshot' in job:
            runtime_snapshot.validate(job)
        else:
            verify_bindings(job['runtime'])
        runtime_snapshot.validate_retired_catalog_binding(job)
    return job
