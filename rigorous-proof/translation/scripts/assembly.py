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
            text += f"theorem resolved_{p['id']} {context} {ins} : {p['type']} := by\n{ir.proof_text(mapping['entries'][p['id']]['library_term'])}\n\n"
    return text


def export_source(c, mapping, level_metadata=None):
    retained = [p for p in c['premises'] if p['kind'] != 'mathlib']
    context = ir.binder_text(c)
    ins = ' '.join(f"(h_{p['id']} : {p['type']})" for p in retained)
    arguments = ' '.join([p['name'] for p in c['parameters']] + ['h_' + p['id'] for p in retained])
    # Infer levels occurring in the retained interface from its actual terms.
    # Only levels absent from that interface are instantiated at zero. These
    # are implementation-only general M instances, not changed M signatures.
    metadata = level_metadata or {'parameters': [], 'export_used_parameters': []}
    used = set(metadata['export_used_parameters'])
    levels = ['_' if name in used else '0' for name in metadata['parameters']]
    universe = '.{' + ', '.join(levels) + '}' if levels else ''
    actual = [f"(@resolved_{p['id']} {arguments})" if p['kind'] == 'mathlib' else 'h_' + p['id']
              for p in c['premises']]
    args = ' '.join([p['name'] for p in c['parameters']] + actual)
    text = library_source(c, mapping)
    text += f"theorem P {context} {ins} : {c['conclusion']['type']} := by\n  exact @Translation.P{universe} {args}\n\n#check @P\n#print axioms P\nend AuditBExport\n"
    return text


def build(c, mapping, formal, out, work):
    """Write and really compile a complete source-facing Proof.lean first."""
    start = time.monotonic()
    out, work = Path(out), Path(work)
    omitted = '#[' + ', '.join(json.dumps('h_' + p['id']) for p in c['premises'] if p['kind'] == 'mathlib') + ']'
    prelude = formal + library_source(c, mapping) + '\nend AuditBExport\n' + LEVEL_PROBE.replace('__M_BINDERS__', omitted)
    prefile = work / 'output/AssemblyInputs.lean'
    prefile.write_text(prelude)
    (out / 'AssemblyInputs.lean').write_text(prelude)
    native = ir.run_lean(prefile, work)
    ir.write(out / 'assembly-inputs-compiler.json', native)
    found = re.findall(r'YUI_ASSEMBLY_LEVELS_JSON:(\{[^\n]*\})', native['stdout'])
    levels = json.loads(found[-1]) if found else None
    report = {'status': 'ASSEMBLY-FAILED', 'failed_layer': 'MATHLIB_DISCHARGE_OR_LEVEL_INSPECTION',
              'universe_parameters': levels, 'standalone_proof': 'NOT_STARTED'}
    if (native['exit_code'] == 0 and isinstance(levels, dict)
            and all(isinstance(levels.get(k), list) and all(isinstance(x, str) for x in levels[k])
                    for k in ('parameters', 'export_used_parameters'))):
        source = formal + export_source(c, mapping, levels)
        file = work / 'output/Proof.lean'
        file.write_text(source)
        (out / 'Proof.lean').write_text(source)
        native = ir.run_lean(file, work)
        report.update(status='ASSEMBLY-PASSED' if native['exit_code'] == 0 else 'ASSEMBLY-FAILED',
                      failed_layer=None if native['exit_code'] == 0 else 'SOURCE_FACING_EXPORT',
                      standalone_proof='KERNEL_CHECKED' if native['exit_code'] == 0 else 'FAILED',
                      proof_sha256=ir.digest(out / 'Proof.lean'))
    ir.write(out / 'assembly-compiler.json', native)
    report.update(compiler_exit_code=native['exit_code'], wall_seconds=time.monotonic() - start,
                  scope='Standalone source-facing proof closure only; independent Audit B remains required.')
    ir.write(out / 'assembly.json', report)
    return report
