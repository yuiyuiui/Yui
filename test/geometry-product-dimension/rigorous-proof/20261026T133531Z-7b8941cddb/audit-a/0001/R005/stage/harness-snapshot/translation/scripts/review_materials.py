"""Deterministic endpoint review views; raw native evidence remains intact."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import ir
import correspondence

SCHEMA = 'yui-audit-b-review-view-1'
GLOBAL_LOCATIONS = ['/scope', '/endpoints', '/mechanical_summary']
DOCUMENTS = ('review-packet.json', 'source-context.json', 'source-original.txt', 'Proof.lean')


def escape(key):
    return key.replace('~', '~0').replace('/', '~1')


def locations(packet):
    if packet.get('view_schema') != SCHEMA:
        return ['/inventory', '/actual_elaborated_evidence']
    return list(GLOBAL_LOCATIONS)


def required_locations(packet):
    rows = {}
    for sid in packet['endpoints']:
        base = '/endpoints/' + escape(sid)
        rows[sid] = [base + '/source', base + '/actual', base + '/correspondence']
        if sid == 'P': rows[sid] += ['/scope/full_target', '/scope/parameters', '/scope/hypotheses']
    return rows


def native_summary(mechanical, evidence, *, foundations):
    deps = (evidence or {}).get('dependencies', {})
    declarations = deps.get('declarations', [])
    actual_axioms = sorted({a for d in declarations for a in d.get('axioms', [])})
    roots = [d for d in declarations if d['name'] == 'AuditBExport.P']
    comparisons = (evidence or {}).get('comparisons', [])
    local = mechanical.get('local_checks', {})
    return {
        'native_evidence_origin':deepcopy(mechanical.get('evidence_origin',{'kind':'current_build','native_checks_rerun':True})),
        'mechanical_passed':mechanical['passed'], 'errors':deepcopy(mechanical['errors']),
        'compiler_exit_code':mechanical['compiler_exit_code'],
        'assembly':deepcopy(mechanical.get('assembly')), 'inspection':deepcopy(mechanical.get('inspection')),
        'local_proof_checks':{'count':len(local), 'failed_ids':[k for k,v in local.items() if v['exit_code'] != 0]},
        'encoded_signature_comparisons':{'count':len(comparisons),
            'failed_ids':[r['id'] for r in comparisons if not r['definitionally_equal']],
            'scope':'Comparison to declared encoded types only; source fidelity is NOT automatically established.'},
        'closure':{'exported_root':'AuditBExport.P', 'root_found':bool(roots),
            'inspection_complete':bool(evidence and deps.get('truncated') is False),
            'inspected_declaration_count':len(declarations), 'actual_axioms':actual_axioms,
            'permitted_foundations':sorted(foundations),
            'unexpected_axioms':sorted(set(actual_axioms) - set(foundations)),
            'unproved_project_declarations':[d['name'] for d in declarations
                if not d.get('imported') and d.get('kind') in {'axiom','opaque'}]},
        'semantic_review':'NOT_PERFORMED',
        'scope':'Actual machine results only. Declared external assumptions are conditional inputs; no mathematical source-to-Lean verdict is generated.'}


def project(directory, inventory, mapping, evidence, mechanical, *, source_file, foundations):
    """Copy exact source context and inspected endpoint fields, never summarize math."""
    directory = Path(directory)
    props = {p['id']:p for p in inventory['propositions']}
    wanted = {sid for sid,p in props.items() if p['kind'] in {'external','target'}}
    ir.need(set(mapping['entries']) == wanted, 'review view requires exactly the original E/P endpoints')
    inspected = (evidence or {}).get('comparisons', [])
    comparisons = {r['id']:r for r in inspected}
    ir.need(len(comparisons)==len(inspected),'duplicate actual inspected endpoint')
    if mechanical['passed']:
        ir.need(set(comparisons) == wanted, 'missing/extra actual inspected endpoint')
    context = {k:deepcopy(inventory.get(k)) for k in ('parameters','definitions','logic','full_target')}
    context['hypotheses'] = [deepcopy(p) for p in inventory['propositions'] if p['kind']=='hypothesis']
    ir.write(directory/'source-context.json',context)
    (directory/'source-original.txt').write_bytes(Path(source_file).read_bytes())
    endpoints = {}
    for sid in sorted(wanted):
        row = comparisons.get(sid)
        endpoints[sid] = {
            'source':deepcopy(props[sid]),
            'actual':({'selector':row['selector'],'type':row['actual_type']} if row else None),
            'correspondence':deepcopy(mapping['entries'][sid]['correspondence']),
            'context_references':{'source_definitions':{'document':'source-context.json','pointer':'/definitions'},
                'original_source':'source-original.txt','actual_lean_source':'Proof.lean'},
            'scope':'Independently compare the original complete statement and actual inspected type; an author explanation is not a verdict.'}
    documents = []
    for name in DOCUMENTS[1:]:
        path = directory/name
        # A failed assembly may not have produced Proof.lean; no reviewer can
        # start until the actual mechanical gate passes.
        if path.exists(): documents.append({'id':name,'sha256':ir.digest(path),'bytes':path.stat().st_size})
    packet = {'view_schema':SCHEMA,'policy':correspondence.POLICY,
        'scope':{'source_scope':inventory['scope'], 'full_target':deepcopy(inventory.get('full_target')),
            'parameters':deepcopy(inventory.get('parameters',[])), 'hypotheses':context['hypotheses'],
            'audit_a_status':inventory.get('audit_a_status'),
            'audit_a_current_passed':inventory.get('audit_a_current_passed',False),
            'source_hashes':deepcopy(inventory.get('source_hashes',{})),
            'endpoint_ids':sorted(wanted), 'exported_root':'AuditBExport.P',
            'source_inventory_sha256':ir.digest(directory/'source-inventory.json'),
            'mapping_sha256':ir.digest(directory/'mapping.json'),
            'compiler_sha256':ir.digest(directory/'compiler.json'),
            'elaborated_sha256':ir.digest(directory/'elaborated.json')},
        'endpoints':endpoints, 'mechanical_summary':native_summary(mechanical,evidence,foundations=foundations),
        'documents':documents,
        'reading_protocol':'Read /scope and /mechanical_summary, then each /endpoints/<ID>. Follow source/actual definition references as needed. Use JSON pointers and exact continuation offsets; raw compiler/dependency dumps are machine evidence, not required review reading.'}
    ir.write(directory/'review-packet.json',packet)
    return packet


def verify_projection(directory, *, foundations):
    """Readback validation without rewriting the artifact or running Lean."""
    directory = Path(directory)
    packet = ir.load(directory/'review-packet.json')
    ir.need(packet.get('view_schema') == SCHEMA, 'unsupported compact review view')
    inventory = ir.load(directory/'source-inventory.json')
    mapping = ir.load(directory/'mapping.json');evidence = ir.load(directory/'elaborated.json')
    props = {p['id']:p for p in inventory['propositions'] if p['kind'] in {'external','target'}}
    actual = {p['id']:p for p in (evidence or {}).get('comparisons',[])}
    ir.need(set(packet['endpoints']) == set(props) == set(mapping['entries']), 'changed review endpoint inventory')
    for sid,row in packet['endpoints'].items():
        ir.need(row['source'] == props[sid] and row['correspondence'] == mapping['entries'][sid]['correspondence'], 'changed source/correspondence in review view')
        expected = {'selector':actual[sid]['selector'],'type':actual[sid]['actual_type']} if sid in actual else None
        ir.need(row['actual'] == expected, 'review view must use the actual inspected type')
    scope = packet['scope']
    for key in ['full_target','parameters']:
        ir.need(scope[key] == inventory.get(key,[]), 'changed original '+key)
    hypotheses = [p for p in inventory['propositions'] if p['kind']=='hypothesis']
    ir.need(scope['hypotheses'] == hypotheses, 'changed original hypotheses')
    for key,name in [('source_inventory_sha256','source-inventory.json'),('mapping_sha256','mapping.json'),
                     ('compiler_sha256','compiler.json'),('elaborated_sha256','elaborated.json')]:
        ir.need(scope[key] == ir.digest(directory/name), 'stale review projection: '+name)
    context=ir.load(directory/'source-context.json')
    ir.need(context == {**{k:inventory.get(k) for k in ('parameters','definitions','logic','full_target')},'hypotheses':hypotheses}, 'changed source context')
    for item in packet['documents']:
        ir.need(item['id'] in DOCUMENTS[1:] and ir.digest(directory/item['id']) == item['sha256'], 'changed review context document')
    ir.need(packet['mechanical_summary'] == native_summary(ir.load(directory/'mechanical.json'),evidence,foundations=foundations), 'changed mechanical summary')
    return packet
