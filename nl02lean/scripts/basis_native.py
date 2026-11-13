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
    return source + '\nend YuiBasis\n', checks


def inspector(checks, roots):
    rows = [(key, ('value:' if name.startswith(TYPE_PREFIX) else 'decl:')+name,
             typ, lean_names.parts(name)) for key, name, typ in checks]
    array = '#['+', '.join('('+', '.join(
        '#['+', '.join(json.dumps(p) for p in value)+']' if isinstance(value, list)
        else json.dumps(value, ensure_ascii=False) for value in row)+')' for row in rows)+']'
    template = (audit_b.HERE/'scripts/audit_probe.lean').read_text()
    root_array = '#['+', '.join('`'+name for name in roots)+']'
    return template.replace('__AUDIT_CHECKS__', array).replace('#[`AuditBExport.P]', root_array)


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
        if not row.get('imported') and row.get('kind') in {'axiom', 'opaque'}:
            problems.append('UNPROVED_PROJECT_DECLARATION:'+row['name'])
    return sorted(set(problems))


def check(source, checks, roots, out):
    """Retain source/compiler/inspection evidence; always release native scratch."""
    out = Path(out);out.mkdir(parents=True, exist_ok=False)
    environment = audit_b.environment()
    (out/'Proof.lean').write_text(source)
    inspected = source+'\n'+inspector(checks, roots)
    (out/'Inspection.lean').write_text(inspected)
    work = Path(tempfile.mkdtemp(prefix='yui-basis-native-')).resolve()
    from run_resources import register_workspace
    try:register_workspace(work,out)
    except BaseException:
        shutil.rmtree(work)  # No native process has been started at this point.
        raise
    try:
        (work/'input').mkdir();(work/'output').mkdir()
        file = work/'output/Inspection.lean';file.write_text(inspected)
        native = ir.run_lean(file, work)
    except BaseException as error:
        # Do not delete ownership evidence when a native call cannot confirm its
        # process shutdown. The case/test cleanup boundary can reclaim it later.
        write(out/'workspace-retained.json',{'workspace':str(work),
            'reason':type(error).__name__+': '+str(error),'cleanup_confirmed':False})
        raise
    else:shutil.rmtree(work)
    write(out/'compiler.json', native)
    found = re.findall(r'NL2LEAN_AUDIT_JSON:(\{[^\n]*\})', native['stdout'])
    evidence = json.loads(found[-1]) if found else None
    write(out/'elaborated.json', evidence)
    problems = errors(native, evidence, checks, roots)
    result = {'version':'yui-basis-native-1', 'passed':not problems, 'errors':problems,
        'timeout_diagnostic_model_called':bool(native.get('timeout_reviews')),
        'checks':checks, 'roots':roots, 'environment':environment,
        'bindings':[bind(out/name) for name in ('Proof.lean','Inspection.lean','compiler.json','elaborated.json')],
        'scope':'Native types, signatures and proof trust only; no mathematical source review.'}
    write(out/'check.json', result)
    return result


def verify(path):
    path = Path(path);value = ir.load(path)
    ir.need(value['version']=='yui-basis-native-1', 'Unknown basis native receipt')
    from controller_common import verify_bindings
    verify_bindings(value['bindings'])
    ir.need(value['environment']==audit_b.environment(), 'Basis pinned environment changed')
    native = ir.load(path.parent/'compiler.json');evidence = ir.load(path.parent/'elaborated.json')
    found = re.findall(r'NL2LEAN_AUDIT_JSON:(\{[^\n]*\})', native['stdout'])
    ir.need(found and json.loads(found[-1])==evidence, 'Basis native output/evidence mismatch')
    expected = errors(native, evidence, value['checks'], value['roots'])
    ir.need(value['passed'] is True and not expected and value['errors']==expected, 'Basis native acceptance failed')
    return value
