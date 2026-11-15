"""One complete native inspection artifact, with small bound references elsewhere."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

import ir

SCHEMA = 'yui-kernel-inspection-2'
MARKER = 'NL2LEAN_AUDIT_FILE:yui-inspection.json'


def retain_incomplete(native, source, out):
    if source.is_file() and not source.is_symlink():
        destination=Path(out)/'incomplete-inspection.json'
        shutil.copyfile(source,destination)
        native['incomplete_inspection_evidence']={'path':destination.name,
            'sha256':ir.digest(destination),'bytes':destination.stat().st_size,'diagnostic_only':True}


def project_owned(row):
    # Small synthetic dependency fixtures need not emulate a native file.
    # Real v2 evidence is validated below and always carries this field.
    return row.get('project_owned', not row['imported'])


def validate(value):
    ir.need(isinstance(value, dict) and value.get('inspection_schema') == SCHEMA,
            'Unknown native inspection schema')
    for field in ('comparisons', 'frozen_comparisons'):
        rows = value.get(field)
        ir.need(isinstance(rows, list), 'Missing native comparisons')
        for row in rows:
            ir.need(isinstance(row, dict) and all(isinstance(row.get(k), str)
                for k in ('id', 'selector', 'actual_type', 'expected_type', 'comparison_method'))
                and type(row.get('definitionally_equal')) is bool, 'Incomplete native comparison')
    deps = value.get('dependencies')
    ir.need(isinstance(deps, dict) and deps.get('truncated') is False
            and isinstance(deps.get('declarations'), list), 'Incomplete native dependency inspection')
    names = set()
    for row in deps['declarations']:
        ir.need(isinstance(row, dict) and all(isinstance(row.get(k), str)
            for k in ('name', 'kind', 'module', 'detail')), 'Incomplete native declaration')
        ir.need(row['name'] not in names, 'Duplicate native declaration')
        names.add(row['name'])
        ir.need(all(type(row.get(k)) is bool for k in
            ('imported', 'project_owned', 'proof_valued', 'instance_declaration')), 'Missing native ownership/trust fields')
        for key in ('levels', 'direct_constants', 'axioms'):
            ir.need(isinstance(row.get(key), list) and all(isinstance(x, str) for x in row[key]),
                    'Missing complete native '+key)
        ir.need(row['detail'] in {'full', 'dependency'}, 'Unknown native detail view')
        if row['detail'] == 'full':
            ir.need(isinstance(row.get('type'), str) and isinstance(row.get('signature'), dict)
                    and isinstance(row['signature'].get('binders'), list)
                    and isinstance(row['signature'].get('result'), str), 'Missing required full native signature')
    for row in deps['declarations']:
        if row['project_owned']:
            ir.need(set(row['direct_constants']) <= names, 'Missing project dependency declarations')
    return value


def capture(native, work, out):
    """Move exact emitted bytes into the durable evidence before scratch cleanup.

    Incomplete native execution never publishes an inspection, even if a file
    was written before timeout. Retain diagnostics for ordinary failed checks.
    """
    destination = Path(out)/'elaborated.json'
    source = Path(work)/'output/yui-inspection.json'
    native.pop('inspection_evidence', None)
    native.pop('incomplete_inspection_evidence', None)
    if not ir.native_succeeded(native):
        retain_incomplete(native,source,out)
        ir.write(destination, None)
        return None
    try:
        ir.need(native.get('stdout', '').count(MARKER) == 1, 'Native inspection completion marker missing')
        ir.need(source.is_file() and not source.is_symlink(), 'Native inspection file missing')
        raw = source.read_bytes()
        value = validate(json.loads(raw))
    except (OSError, ValueError, TypeError, KeyError) as error:
        native['inspection_evidence_error'] = str(error)
        retain_incomplete(native,source,out)
        ir.write(destination, None)
        return None
    destination.write_bytes(raw)
    native['inspection_evidence'] = {'schema':SCHEMA, 'path':'elaborated.json',
        'sha256':ir.digest(destination), 'bytes':len(raw)}
    return value


def verify(native, out):
    ir.need(ir.native_succeeded(native) and native.get('stdout', '').count(MARKER) == 1,
            'Actual completed native inspection required')
    ref = native.get('inspection_evidence', {})
    path = Path(out)/'elaborated.json'
    ir.need(ref.get('schema') == SCHEMA and ref.get('path') == 'elaborated.json'
            and path.is_file() and not path.is_symlink(), 'Missing bound native inspection artifact')
    ir.need(ref.get('sha256') == ir.digest(path) and ref.get('bytes') == path.stat().st_size,
            'Native inspection evidence changed')
    return validate(ir.load(path))
