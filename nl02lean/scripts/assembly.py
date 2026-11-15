"""Close a generated conditional proof against actual pinned library proofs.

Native elaboration supplies universe metadata. Assembly does not change the
frozen mathematical interfaces, author a new proof route or issue Audit B.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import time

import ir
import lean_timeout_policy
import helper_modules


LEVEL_PROBE = '''
open Lean Meta Elab Command in
run_cmd do
  let result ← liftTermElabM do
    let info ← getConstInfo `Translation.P
    forallTelescope info.type fun xs body => do
      let mut retained := #[]
      let omitted : Array String := __M_BINDERS__
      for x in xs do
        let decl ← getFVarLocalDecl x
        if !omitted.contains decl.userName.toString then
          retained := retained.push x
      let exported ← mkForallFVars retained body
      let used := (collectLevelParams {} exported).params.toList
      return Json.mkObj [("parameters", toJson (info.levelParams.map Name.toString)),
        ("export_used_parameters", toJson (used.map Name.toString))]
  logInfo m!"YUI_ASSEMBLY_LEVELS_JSON:{result.compress}"
'''


def library_source(c, mapping):
    retained = [p for p in c['premises'] if p['kind'] != 'mathlib']
    context = ir.binder_text(c)
    ins = ' '.join(f"(h_{p['id']} : {p['type']})" for p in retained)
    text = '\nnamespace AuditBExport\nset_option autoImplicit false\n'
    for p in c['premises']:
        if p['kind'] == 'mathlib':
            text += f"theorem resolved_{p['id']} {context} {ins} : {p['type']} := by\n{ir.proof_text(mapping['library_terms'][p['id']])}\n\n"
    return text


def export_source(c, mapping):
    """Resolve actual universe levels inside the same native elaboration."""
    retained = [p for p in c['premises'] if p['kind'] != 'mathlib']
    context = ir.binder_text(c)
    ins = ' '.join(f"(h_{p['id']} : {p['type']})" for p in retained)
    arguments = ' '.join([p['name'] for p in c['parameters']] + ['h_'+p['id'] for p in retained])
    actual = [f"(@resolved_{p['id']} {arguments})" if p['kind']=='mathlib' else 'h_'+p['id']
              for p in c['premises']]
    args = [p['name'] for p in c['parameters']] + actual
    omitted = '#['+', '.join(json.dumps('h_'+p['id']) for p in c['premises'] if p['kind']=='mathlib')+']'
    helper = Path(__file__).with_name('basis_export.lean').read_text()
    helper = helper.replace('AuditBExport.P', 'Translation.P').replace('yui_basis_', 'yui_assembly_')
    helper = helper.replace('yuiBasisDeclaredLevels', 'yuiAssemblyDeclaredLevels').replace('__DISCHARGED_BINDERS__', omitted)
    source = library_source(c, mapping) + helper + '\n'
    source += f"set_option Elab.async false in\ntheorem P {context} {ins} : {c['conclusion']['type']} := by\n"
    source += '  exact yui_assembly_export%('+', '.join(args)+')\n\nend AuditBExport\n'
    return source + LEVEL_PROBE.replace('__M_BINDERS__', omitted)


def build(c, mapping, formal, out, work, *, checks=()):
    """Compile the stable source once, including actual universe/export checks."""
    start = time.monotonic()
    out, work = Path(out), Path(work)
    source = formal + export_source(c, mapping)
    (out/'Proof.lean').write_text(source)
    with lean_timeout_policy.whole_file_scope(out/'lean-timeouts', key='assembly-export'):
        native, module = helper_modules.compile_proof_module(source, checks, out, work)
    found = re.findall(r'YUI_ASSEMBLY_LEVELS_JSON:(\{[^\n]*\})', native['stdout'])
    levels = json.loads(found[-1]) if found else None
    report = {'status': 'ASSEMBLY-FAILED', 'failed_layer': 'MATHLIB_DISCHARGE_OR_LEVEL_INSPECTION',
              'universe_parameters': levels, 'standalone_proof': 'FAILED', 'compiled_module':module}
    if (ir.native_succeeded(native) and isinstance(levels, dict)
            and all(isinstance(levels.get(k), list) and all(isinstance(x, str) for x in levels[k])
                    for k in ('parameters', 'export_used_parameters'))):
        report.update(status='ASSEMBLY-PASSED', failed_layer=None,
                      standalone_proof='KERNEL_CHECKED',
                      proof_sha256=ir.digest(out / 'Proof.lean'))
    ir.write(out / 'assembly-compiler.json', native)
    report.update(compiler_exit_code=native['exit_code'], wall_seconds=time.monotonic() - start,
                  scope='Standalone source-facing proof closure only; independent Audit B remains required.')
    ir.write(out / 'assembly.json', report)
    return report
