"""Pinned Lean checks shared by basis preparation and final dependency discharge.

Only generated declarations and the existing trusted inspector run here. These
checks establish kernel closure, never natural-language/source fidelity.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import tempfile

import audit_b
import ir
import lean_names
import inspection_evidence
from controller_common import bind, write


TYPE_PREFIX = 'YuiBasis.type_'


def proposition_probe(row):
    """Compare a frozen proposition with the value of its Prop-valued definition."""
    key, statement = row['id'], row['lean']['type']
    source = ir.checked_expression('type_' + key, statement, proposition=True)
    return source, (key, TYPE_PREFIX + key, statement)


def type_probes(header, rows):
    source = header + '\nnamespace YuiBasis\nset_option autoImplicit false\n'
    checks = []
    for row in rows:
        declaration, check = proposition_probe(row)
        source += declaration
        checks.append(check)
    import basis_sources
    checks.extend((key,name,'value:'+TYPE_PREFIX+key[len(basis_sources.PREFIX):])
                  for key,name,_ in basis_sources.checks(rows))
    return source + '\nend YuiBasis\n', checks


def inspector(checks, roots, *, owned_modules=()):
    rows = [(key, ('value:' if name.startswith(TYPE_PREFIX) else 'decl:')+name,
             typ, lean_names.parts(name)) for key, name, typ in checks]
    array = '#['+', '.join('('+', '.join(
        '#['+', '.join(json.dumps(p) for p in value)+']' if isinstance(value, list)
        else json.dumps(value, ensure_ascii=False) for value in row)+')' for row in rows)+']'
    template = (audit_b.HERE/'scripts/audit_probe.lean').read_text()
    root_array = '#['+', '.join('`'+name for name in roots)+']'
    return template.replace('#[`AuditBExport.P]', root_array).replace(
        '#[] -- YUI_OWNED_MODULES', '#['+', '.join(map(json.dumps,owned_modules))+'] -- YUI_OWNED_MODULES').replace(
        '__AUDIT_CHECKS__', array)


def inspection_source(source, checks, roots, prefix=None):
    """A small final wrapper only when the original scope can be replayed safely."""
    if prefix is None:return source+'\n'+inspector(checks, roots), None
    import helper_modules
    from controller_common import verify_bindings
    verify_bindings(list(prefix.values()))
    c=ir.contract(prefix['contract']['path'])
    replay=helper_modules.replay(c['header'])
    ir.need(replay is not None, 'Final module context cannot be replayed safely; use the full native source')
    conditional=Path(prefix['source']['path']).read_text()
    ir.need(source.startswith(conditional), 'Final source does not extend the exact checked conditional proof')
    directory=Path(prefix['source']['path']).parent
    ir.need(bind(directory/'compiled-module.json')==prefix['module'], 'Changed conditional module selection')
    module=helper_modules.bound_proof_module(directory)
    wrapper='import '+module['name']+'\n'+replay+'\n'+source[len(conditional):]
    return wrapper+'\n'+inspector(checks, roots, owned_modules=[module['name']]), module


def errors(native, evidence, checks, roots):
    problems = []
    if not ir.native_succeeded(native):
        problems.append('LEAN_RESOURCE_LIMIT' if native.get('exit_code') == 124 else 'LEAN_COMPILE_FAILED')
    if not isinstance(evidence, dict):return problems+['KERNEL_INSPECTION_MISSING']
    comparisons = evidence.get('comparisons', [])
    if (len(comparisons) != len(checks) or {r.get('id') for r in comparisons} != {c[0] for c in checks}
            or not all(r.get('definitionally_equal') is True for r in comparisons)):
        problems.append('ACTUAL_SIGNATURE_MISMATCH')
    deps = evidence.get('dependencies', {})
    declarations = deps.get('declarations', [])
    if deps.get('truncated') is not False or not set(roots) <= {d.get('name') for d in declarations}:
        problems.append('DEPENDENCY_INSPECTION_INCOMPLETE')
    for row in declarations:
        if set(row.get('axioms', []))-audit_b.AXIOMS:problems.append('UNPERMITTED_AXIOM:'+row['name'])
        if inspection_evidence.project_owned(row) and row.get('kind') in {'axiom', 'opaque'}:
            problems.append('UNPROVED_PROJECT_DECLARATION:'+row['name'])
    return sorted(set(problems))


def check(source, checks, roots, out, *, compiled_prefix=None):
    """Retain source/compiler/inspection evidence; always release native scratch."""
    out = Path(out);out.mkdir(parents=True, exist_ok=False)
    environment = audit_b.environment()
    (out/'Proof.lean').write_text(source)
    inspected, module = inspection_source(source, checks, roots, compiled_prefix)
    (out/'Inspection.lean').write_text(inspected)
    work = Path(tempfile.mkdtemp(prefix='yui-basis-native-')).resolve()
    from run_resources import register_workspace
    try:register_workspace(work,out)
    except BaseException:
        shutil.rmtree(work)  # No native process has been started at this point.
        raise
    try:
        (work/'input').mkdir();(work/'output').mkdir()
        if module:
            receipt=Path(module['receipt']['path'])
            for name in ir.load(receipt)['artifacts']:shutil.copyfile(receipt.parent/name,work/'output'/name)
        file = work/'output/Inspection.lean';file.write_text(inspected)
        native = ir.run_lean(file, work, **({'extra':[work/'output']} if module else {}))
        evidence = inspection_evidence.capture(native, work, out)
    except BaseException as error:
        # Do not delete ownership evidence when a native call cannot confirm its
        # process shutdown. The case/test cleanup boundary can reclaim it later.
        write(out/'workspace-retained.json',{'workspace':str(work),
            'reason':type(error).__name__+': '+str(error),'cleanup_confirmed':False})
        raise
    else:shutil.rmtree(work)
    write(out/'compiler.json', native)
    problems = errors(native, evidence, checks, roots)
    import basis_sources
    sources={}
    if not problems:
        try:sources=basis_sources.native_sources(evidence,checks,environment)
        except ValueError as error:problems.append('NATIVE_SOURCE: '+str(error))
    result = {'version':'yui-basis-native-3', 'passed':not problems, 'errors':problems,
        'timeout_diagnostic_model_called':bool(native.get('timeout_reviews')),
        'checks':checks, 'roots':roots, 'environment':environment,
        'native_sources':sources,
        'compiled_prefix':compiled_prefix,
        'bindings':[bind(out/name) for name in ('Proof.lean','Inspection.lean','compiler.json','elaborated.json',
            *(['incomplete-inspection.json'] if (out/'incomplete-inspection.json').exists() else []))]+
            [bind(Path(ir.load_lock()['mathlib']['local_path'])/s['source_path']) for s in sources.values()],
        'scope':'Native types, signatures and proof trust only; no mathematical source review.'}
    write(out/'check.json', result)
    return result


def verify(path, *, before_recheck=False):
    path = Path(path);value = ir.load(path)
    ir.need(value['version']=='yui-basis-native-3', 'Unknown basis native receipt')
    from controller_common import verify_bindings
    verify_bindings(value['bindings'])
    current=audit_b.environment()
    if value['environment']!=current:
        import lean_libraries
        ir.need(before_recheck and lean_libraries.environment_extended(value['environment'],current),
                'Basis pinned environment changed')
    native = ir.load(path.parent/'compiler.json')
    evidence = inspection_evidence.verify(native, path.parent)
    inspected,_=inspection_source((path.parent/'Proof.lean').read_text(),value['checks'],value['roots'],value['compiled_prefix'])
    ir.need((path.parent/'Inspection.lean').read_text()==inspected, 'Changed actual native inspection source')
    expected = errors(native, evidence, value['checks'], value['roots'])
    import basis_sources
    sources=basis_sources.native_sources(evidence,value['checks'],value['environment']) if not expected else {}
    ir.need(value.get('native_sources')==sources,'Changed native whole-proposition source evidence')
    ir.need(value['passed'] is True and not expected and value['errors']==expected, 'Basis native acceptance failed')
    return value
