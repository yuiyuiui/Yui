"""Real setup qualification through the ordinary carrier and native consumers."""
from pathlib import Path
import hashlib
import http.client
from datetime import datetime, timezone
from urllib.parse import urlencode
import json
import re
import shutil
import tempfile
import uuid

from controller_common import CORE, bind, write
from runtime_config import use_environment, auth_home, host_tools


def record(directory, name, data):
    path=Path(directory)/(name+'.json')
    write(path,data)
    return {'passed':True,'execution':'actual','evidence':[bind(path)]}


def source_readers(directory):
    """Extract a tiny owned PDF through the same reader used for proof inputs."""
    from target_selection import text
    sentence='Yui setup source reader'
    stream=('BT /F1 12 Tf 50 100 Td ('+sentence+') Tj ET').encode()
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] '
        b'/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    content=bytearray(b'%PDF-1.4\n');offsets=[0]
    for number,obj in enumerate(objects,1):
        offsets.append(len(content));content.extend(str(number).encode()+b' 0 obj\n'+obj+b'\nendobj\n')
    xref=len(content)
    content.extend(b'xref\n0 6\n0000000000 65535 f \n')
    for offset in offsets[1:]:content.extend(f'{offset:010d} 00000 n \n'.encode())
    content.extend(b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(xref).encode()+b'\n%%EOF\n')
    file=Path(directory)/'source-reader.pdf';file.write_bytes(content)
    extracted=text(file)
    if sentence not in extracted:
        raise ValueError('The ordinary PDF proof reader did not return the expected source text')
    return {'source':bind(file),'expected_text_found':True}


PROVIDER_HOST='chatgpt.com'
METADATA_MAX_BYTES=8 * 1024 * 1024


def provider_metadata(profiles):
    """One authenticated GET, using the same verified-TLS/system-proxy route."""
    from run_pilot import system_https_proxy
    auth = json.loads((auth_home()/'auth.json').read_text())
    tokens = auth.get('tokens') or {}
    token, account = tokens.get('access_token'), tokens.get('account_id')
    if not isinstance(token, str) or not token or not isinstance(account, str) or not account:
        raise ValueError('Provider metadata check requires existing subscription authentication')
    if any(c in token+account for c in '\r\n'):
        raise ValueError('Malformed subscription credential header; value withheld')
    lock = host_tools()
    match = re.search(r'\b(\d+\.\d+\.\d+[A-Za-z0-9.+_-]*)\b', lock['codex']['version'])
    if not match:
        raise ValueError('Cannot establish the actual native client version')
    path = '/backend-api/codex/models?' + urlencode({'client_version': match[1]})
    proxy = system_https_proxy()
    connection = None
    try:
        if proxy:
            connection = http.client.HTTPSConnection(*proxy, timeout=25)
            connection.set_tunnel(PROVIDER_HOST, 443)
        else:
            connection = http.client.HTTPSConnection(PROVIDER_HOST, timeout=25)
        connection.request('GET', path, headers={'Authorization': 'Bearer '+token,
            'ChatGPT-Account-Id': account, 'Accept': 'application/json',
            'Accept-Encoding': 'identity', 'User-Agent': 'codex_cli_rs/'+match[1],
            'originator': 'codex_cli_rs'})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError('Provider metadata unavailable: metadata HTTP '+str(response.status))
        if 'application/json' not in (response.getheader('Content-Type') or '').lower():
            raise ValueError('Provider access check did not return model JSON')
        body = response.read(METADATA_MAX_BYTES+1)
        if len(body) > METADATA_MAX_BYTES:
            raise ValueError('Provider metadata exceeds the bounded access check')
        try:
            catalog = json.loads(body)
        except (ValueError, UnicodeError) as error:
            raise ValueError('Malformed provider model metadata') from error
        models = catalog.get('models') if isinstance(catalog, dict) else None
        if not isinstance(models, list) or any(not isinstance(row, dict) for row in models):
            raise ValueError('Provider metadata has no model catalog')
        for profile in profiles.values():
            matched = [row for row in models if row.get('slug') == profile['id']]
            if len(matched) != 1 or profile['reasoning_effort'] not in {
                    r.get('effort') for r in matched[0].get('supported_reasoning_levels', []) if isinstance(r, dict)}:
                raise ValueError('Provider does not advertise the selected model/effort')
        return {'at_utc': datetime.now(timezone.utc).isoformat(), 'method': 'GET',
                'host': PROVIDER_HOST, 'path': path, 'http_status': 200,
                'request_id': (response.getheader('x-request-id') or '')[:256] or None,
                'catalog_sha256': hashlib.sha256(body).hexdigest(),
                'verified_profiles': profiles, 'system_https_proxy': proxy,
                'inference_calls': 0, 'credential_values_logged': False,
                'scope': 'Authenticated metadata access, not a guarantee of future inference health'}
    except (OSError, http.client.HTTPException) as error:
        raise ValueError('Provider access check failed: '+type(error).__name__) from None
    finally:
        if connection:
            connection.close()


def provider(directory, profiles):
    """Check each distinct active profile through the actual isolated carrier."""
    from clean_stage import ArtifactStage
    from execution_state import Cancelled
    from runtime_config import use_profiles
    metadata=provider_metadata(profiles)
    completed=[];seen=set()
    for role,profile in profiles.items():
        identity=json.dumps(profile,sort_keys=True)
        if identity in seen:continue
        seen.add(identity);nonce=uuid.uuid4().hex
        def validate(value):
            if value!={'ready':True,'nonce':nonce}:
                raise ValueError('Setup carrier must return the exact requested nonce')
            return {'validated':True}
        validate.schema={'type':'object','properties':{'ready':{'const':True},'nonce':{'const':nonce}},
                         'required':['ready','nonce'],'additionalProperties':False}
        with use_profiles({'nl0':profile,'lean':profile}):
            stage=ArtifactStage(Path(directory)/('provider-'+role),
                'Connection check only. Submit exactly '+json.dumps({'ready':True,'nonce':nonce})+
                ' using submit_draft, then end your turn. Do not solve mathematics.',
                phase='setup-provider',arm='direct',kind='json',library=False,validator=validate,timeout=90)
            def stop(*args,**kwargs):
                raise Cancelled('Bounded setup probe ended; retained diagnostic requires setup repair')
            stage.pause_error=stop
            try:
                result,_=stage.execute()
                if (result.get('status')!='ACCEPTED' or result.get('execution_health')!='NO_RECORDED_FAULT'
                        or result.get('isolation_violation') or not result.get('identity_and_input_boundary_verified')):
                    raise ValueError('Actual isolated carrier probe failed; see '+str(stage.logs/'result.json'))
                completed.append({'role':role,'profile':profile,'carrier_result':bind(stage.logs/'result.json'),
                                  'nonce_returned':True,'actual_model':stage.model})
            finally:
                stage.release_resources('WORKFLOW_FINALIZED')
    return record(directory,'provider',{'metadata':metadata,'actual_carriers':completed})


def native(directory, selected):
    import sys
    sys.path.insert(0,str(CORE/'nl02lean/scripts'))
    import basis_native
    import lean_libraries
    from clean_stage import ArtifactStage
    from artifact_validation import signature_probe
    directory=Path(directory)
    with use_environment(selected),lean_libraries.use([]),lean_libraries.generated(None):
        result={}
        result['environment']=record(directory,'environment',selected)
        query=signature_probe(directory/'source-query','M001','isCompact_singleton',None,1)
        source=ArtifactStage(directory/'source-tools','Setup source availability check.',
                            phase='setup-query',arm='direct',library=True)
        try:
            found=source.dispatch('search_mathlib',{'query':'isCompact_singleton'})
            read=source.dispatch('read_mathlib',{'path':query['source_path'],'start_line':1,'line_count':20})
            if found.get('exit_code')!=0 or not found.get('matches') or read.get('error'):
                raise ValueError('The actual Mathlib source tools cannot read/search the selected source')
        finally:
            source.release_resources('WORKFLOW_FINALIZED')
        result['mathlib_query']=record(directory,'mathlib-query',{'probe':query,'search':found,'read':read})
        helper=(CORE/'nl02lean/scripts/basis_export.lean').read_text()
        helper=helper.replace('__DISCHARGED_BINDERS__','#["h_E001"]')
        program=('import Mathlib\nuniverse u\nnamespace AuditBExport\n'
            'theorem P (α : Type u) [Inhabited α] (h_E001 : True) : '
            '(default : α) = default := by rfl\nend AuditBExport\nnamespace YuiClosed\n'+
            helper+'\ntheorem P (α : Type u) [Inhabited α] : (default : α) = default := by\n'
            '  exact yui_basis_export%(α, inferInstance, True.intro)\nend YuiClosed\n')
        expected='∀ (α : Type u) [Inhabited α], (default : α) = default'
        checked=basis_native.check(program,[('P','YuiClosed.P',expected)],['YuiClosed.P'],directory/'core-check')
        if not checked['passed']:
            raise ValueError('Core inspector/export qualification failed: '+str(checked.get('errors')))
        evidence=record(directory,'core-inspector',checked)
        result['core_inspector']=evidence
        result['basis_export']=record(directory,'basis-export',{'check':checked,'universe_typeclass_case':True})
        bad='import Mathlib\nnamespace InvalidSetup\naxiom wrong : False\ntheorem P : False := wrong\nend InvalidSetup\n'
        rejected=basis_native.check(bad,[('P','InvalidSetup.P','False')],['InvalidSetup.P'],directory/'negative-check')
        if rejected['passed'] or not any('AXIOM' in e or 'UNPROVED' in e for e in rejected.get('errors',[])):
            raise ValueError('The core inspector did not reject a project axiom')
        result['negative_proof']=record(directory,'negative-proof',rejected)
        return result


def library_specification(source_root, build_root, name, imports, destination, *, allowed_external=()):
    """Derive an explicit public import closure; hashes are never typed by users."""
    import lean_libraries
    import lean_imports
    from runtime_config import require_environment
    selected=require_environment()
    source,build=Path(source_root).resolve(strict=True),Path(build_root).resolve(strict=True)
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',name) or not imports:
        raise ValueError('Specify the public library namespace and entry module(s)')
    pending=list(imports);rows={};seen=set()
    while pending:
        module=pending.pop()
        if module in seen:continue
        seen.add(module)
        relative=lean_libraries._module(module,name)
        file=lean_libraries._input(source,Path(str(relative)+'.lean'))
        compiled=lean_libraries._input(build,Path(str(relative)+'.olean'))
        row={'module':module,'source_sha256':bind(file)['sha256'],'olean_sha256':bind(compiled)['sha256']}
        companions={suffix:bind(lean_libraries._input(build,Path(str(relative)+suffix)))['sha256']
                    for suffix in ('.olean.private','.olean.server','.ir','.ir.sig')
                    if (build/(str(relative)+suffix)).exists()}
        if companions:row['companions']=companions
        rows[module]=row
        preamble=lean_imports.preamble(file.read_text())
        if preamble is None:raise ValueError('Cannot parse public import header: '+module)
        for line in lean_imports.code_tokens(preamble).splitlines():
            match=re.fullmatch(r'\s*(?:(?:public|private|meta)\s+)*import\s+(.+)',line)
            if match:
                for dependency in match[1].split():
                    if dependency==name or dependency.startswith(name+'.'):pending.append(dependency)
                    elif dependency.split('.')[0] not in {'Init','Lean','Std','Mathlib','Aesop','Batteries','Qq','Plausible','ProofWidgets','ImportGraph','LeanSearchClient',*allowed_external}:
                        raise ValueError('Additional external import needs explicit attachment: '+dependency)
    value={'version':'yui-lean-library-1','name':name,'source_root':str(source),'build_root':str(build),
           'lean_version':selected['lean']['version_number'],'mathlib_commit':selected['mathlib']['rev'],
           'imports':list(imports),'modules':[rows[key] for key in sorted(rows)]}
    write(destination,value)
    return Path(destination)


def external_library(directory, specification, selected, profiles, *, attachments=()):
    """Use a real prepared job, public source tools and restricted native import."""
    directory=Path(directory);directory.mkdir()
    retained=directory/'consumer-evidence'
    with tempfile.TemporaryDirectory(prefix='yui-setup-library-') as raw:
        work=Path(raw).resolve()/'consumer'
        try:
            data=_external_library(work,specification,selected,profiles,attachments=attachments)
        finally:
            # Retain diagnosis/source bytes, but remove the disposable task workspace.
            # This copy is check evidence, not a resumable mathematical job.
            if work.exists():shutil.copytree(work,retained)
    data['job']=bind(retained/'run/job.json')
    data['qualification_workspace_removed']=True
    return record(directory.parent,'library-'+data.pop('name'),data)


def _external_library(directory, specification, selected, profiles, *, attachments=()):
    """Keep disposable task inputs/outputs outside the installed skill boundary."""
    import jobs
    import lean_libraries
    from clean_stage import ArtifactStage
    from pilot_common import run_lean,native_succeeded
    import delivery
    directory=Path(directory);directory.mkdir()
    problem=directory/'problem.md';problem.write_text('Check availability of the explicitly supplied public library.\n')
    job=jobs.prepare(problem,track='full',profiles=profiles,lean_environment=selected,
                     lean_libraries=[*attachments,specification],output=directory/'run')
    with jobs.scientific_context(job):
        attached=lean_libraries.current()
        wanted=json.loads(Path(specification).read_text())['name']
        data=next(data for _,data in lean_libraries.validate(attached,full=True) if data['name']==wanted)
        module=data['imports'][0]
        reader=ArtifactStage(directory/'reader','Setup external source availability.',
                             phase='setup-library',arm='direct',library=True)
        try:
            read=reader.dispatch('read_lean_library',{'module':module,'start':1,'end':20})
            search=reader.dispatch('search_lean_library',{'query':'import'})
            if not read.get('lines') or read.get('error') or search.get('error'):
                raise ValueError('Attached public library is not accessible through the actual source tools')
        finally:
            reader.release_resources('WORKFLOW_FINALIZED')
        work=directory/'native'
        for name in ('input','output','tmp','home'):(work/name).mkdir(parents=True)
        file=work/'output/Import.lean'
        modules='#['+', '.join(json.dumps(row['module']) for row in data['modules'])+']'
        file.write_text('import Mathlib\nimport Lean\n'+''.join('import '+name+'\n' for name in data['imports'])+
            'example : True := by trivial\nopen Lean Elab Command in\nrun_elab do\n'
            '  let modules : Array String := '+modules+'\n'
            '  let env ← getEnv\n  let mut found := false\n'
            '  for (name, info) in env.constants do\n'
            '    if name.toString.startsWith "_private" then continue\n'
            '    let actual ← findModuleOf? name\n'
            '    if let some actual := actual then\n'
            '      if modules.contains actual.toString then\n'
            '        match info with\n'
            '        | .thmInfo _ | .defnInfo _ =>\n'
            '          let printed ← Meta.ppExpr info.type\n'
            '          IO.println s!"YUI_LIBRARY_DECLARATION:{name}:{printed}"\n'
            '          found := true\n          break\n'
            '        | _ => pure ()\n'
            '  unless found do throwError "No public declaration is accessible from the requested library"\n')
        compiled=run_lean(file,work,timeout=120)
        if not native_succeeded(compiled):
            raise ValueError('External library failed the actual restricted native import: '+compiled['stdout'][-2000:])
        if 'YUI_LIBRARY_DECLARATION:' not in compiled['stdout']:
            raise ValueError('No actual external declaration was inspected')
        exported=directory/'export';exported.mkdir()
        exported_sources=lean_libraries.export_sources(exported)
        if not exported_sources or list(exported.rglob('*.olean')):
            raise ValueError('External public source export failed')
        jobs.validate(job)
        child=__import__('runtime_snapshot').environment(job)
        if json.loads(child['YUI_LEAN_LIBRARIES'])!=attached:
            raise ValueError('External library binding did not propagate to child context')
    return {'name':data['name'],'read':read,'search':search,'native':compiled,'export':exported_sources}
