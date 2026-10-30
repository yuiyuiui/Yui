"""Final native acceptance inheriting a bound pre-proof semantic review."""
from pathlib import Path

import audit_b
import ir
import source_preparation

SCHEMA='yui-frozen-interface-acceptance-1'
INTERFACE_ERRORS={'ELABORATED_SIGNATURE_MISMATCH','FROZEN_INTERFACE_MISMATCH'}


def proof_integrity(directory):
    out=Path(directory);manifest=audit_b.bound_inputs(out);m=ir.load(out/'mechanical.json')
    ir.need(m['manifest_sha256']==ir.digest(out/'manifest.json') and
        m['mapping_sha256']==ir.digest(out/'mapping.json'),'Changed native audit bindings')
    for name,sha in m['artifacts'].items():ir.need(ir.digest(out/name)==sha,'Changed native audit artifact: '+name)
    ir.need(m['passed']==(not m['errors']),'Inconsistent native audit summary')
    ir.need(not set(m['errors'])-INTERFACE_ERRORS,'Proof integrity failed; semantic review cannot override it')
    ir.need(m['compiler_exit_code']==0 and m['assembly']['status']=='ASSEMBLY-PASSED' and
        m['inspection']['status']=='KERNEL_INSPECTION_PASSED','Actual standalone compilation/inspection required')
    ir.need(all(row['exit_code']==0 for row in m['local_checks'].values()),'Internal proof closure failed')
    compiler=ir.load(out/'compiler.json');evidence=ir.load(out/'elaborated.json')
    import json,re
    emitted=re.findall(r'NL2LEAN_AUDIT_JSON:(\{[^\n]*\})',compiler['stdout'])
    ir.need(compiler['exit_code']==0 and emitted and json.loads(emitted[-1])==evidence,'Native inspection output differs from saved evidence')
    deps=evidence['dependencies'];ir.need(not deps['truncated'],'Incomplete dependency inspection')
    for row in deps['declarations']:
        ir.need(not set(row['axioms'])-audit_b.AXIOMS,'Unpermitted axiom in actual proof')
        ir.need(row['imported'] or row['kind'] not in {'axiom','opaque'},'Unproved internal declaration')
    assembly=ir.load(out/'assembly.json')
    ir.need(assembly['proof_sha256']==ir.digest(out/'Proof.lean'),'Actual compiled proof changed')
    return manifest,m,evidence


def check(directory):
    import workflow,interface_review
    out=Path(directory).resolve();frozen=workflow.bound(out)
    ir.need(frozen['interface_review'] is not None,'Machine final acceptance requires pre-proof semantic authority')
    interface_review.verify_receipt(frozen['interface_review'],frozen['contract'],frozen['plan'],
        ir.digest(frozen['authority']['graph']))
    native,m,evidence=proof_integrity(out/'audit-b')
    ir.need(m.get('frozen_contract_sha256')==ir.digest(frozen['contract']),'Native inspection used another frozen authority')
    for key in ('graph','spec','audit_a','incremental'):
        wanted_source=frozen['authority'].get(key);actual_source=native['authority'].get(key)
        ir.need((wanted_source is None)==(actual_source is None),'Final source authority changed')
        if wanted_source:ir.need(ir.digest(wanted_source)==ir.digest(actual_source),'Final source authority changed')
    actual=ir.contract(native['contract']);wanted=ir.contract(frozen['contract'])
    expected={'__frozen__'+sid for sid in audit_b.frozen_endpoints(wanted,ir.load(out/'audit-b/source-inventory.json'))}
    rows=evidence.get('frozen_comparisons',[])
    ir.need(len(rows)==len(expected) and {r['id'] for r in rows}==expected,'Missing complete frozen endpoint inspection')
    consistent=(actual['header']==wanted['header'] and actual['pins']==wanted['pins'] and
        all(r['definitionally_equal'] for r in rows))
    return {'interface_consistent':consistent,'proof_integrity_passed':True,
        'status':'FROZEN_INTERFACE_CONSISTENT' if consistent else 'INTERFACE_DEVIATION_REQUIRES_B_FINAL',
        'semantic_review':source_preparation.binding(frozen['interface_review']),
        'mechanical':source_preparation.binding(out/'audit-b/mechanical.json')}


def finish(directory, *, exceptional_review=None):
    import workflow,audit_b_review
    out=Path(directory).resolve();gate=check(out);frozen=workflow.bound(out)
    deviation=not gate['interface_consistent']
    if deviation:
        ir.need(exceptional_review is not None,'Interface deviation needs actual B-final semantic review')
        reviewed=audit_b_review.collect(Path(exceptional_review).parent) if not (Path(exceptional_review).parent/'report.json').exists() else ir.load(Path(exceptional_review).parent/'report.json')
        audit_b_review.verify_actual_review(Path(exceptional_review).parent)
        ir.need(reviewed['all_checks_passed'],'Unfaithful final artifact requires user decision')
        ir.need(ir.load(Path(exceptional_review).parent/'bindings.json')['audit']==str(out/'audit-b'),'B-final reviewed another artifact')
    else:
        ir.need(exceptional_review is None,'Normal final acceptance needs no final semantic model')
    data=source_preparation.read_source(**frozen['authority'])[0]
    conditional=deviation or not data[0].get('current_standard_receipt_valid')
    receipt={'schema':SCHEMA,'workflow':str(out),'status':'AUDIT-B-CONDITIONAL' if conditional else 'AUDIT-B-PASSED',
        'acceptance_basis':'EXCEPTIONAL_FINAL_SEMANTIC_REVIEW' if deviation else 'FROZEN_INTERFACE_SEMANTICS_INHERITED',
        'source_conditional':not data[0].get('current_standard_receipt_valid'),
        'final_semantic_model_called':deviation,'freeze_deviation':deviation,
        'gate':gate,'bindings':[source_preparation.binding(out/'manifest.json'),
            source_preparation.binding(out/'audit-b/Proof.lean'),source_preparation.binding(out/'audit-b/mechanical.json')],
        'exceptional_review':source_preparation.binding(exceptional_review) if exceptional_review else None,
        'warning':'Final source-faithful contract differs from the frozen interface; report this freeze-integrity harness defect.' if deviation else None}
    destination=out/'audit-b/machine-acceptance.json'
    ir.need(not destination.exists(),'Preserve the prior final acceptance')
    ir.write(destination,receipt)
    if deviation:
        ir.write(out/'freeze-warning.json',receipt)
        (out/'freeze-warning.md').write_text('# Frozen interface deviation\n\n'+receipt['warning']+'\n')
    return {**receipt,'receipt_sha256':ir.digest(destination),'receipt_path':str(destination),
        'scope':'Final native proof integrity and bound pre-proof semantics; not a newly performed independent final review.'}


def validate_receipt(path):
    """Read-only validation; never calls a model or Lean."""
    path=Path(path);receipt=ir.load(path);ir.need(receipt['schema']==SCHEMA,'Unknown machine final acceptance')
    for binding in receipt['bindings']:source_preparation.unchanged(binding)
    gate=check(receipt['workflow']);ir.need(gate==receipt['gate'],'Final acceptance gate changed')
    if receipt['exceptional_review']:
        import audit_b_review
        source_preparation.unchanged(receipt['exceptional_review'])
        audit_b_review.verify_actual_review(Path(receipt['exceptional_review']['path']).parent)
        ir.need(not gate['interface_consistent'] and receipt['final_semantic_model_called'] and receipt['freeze_deviation'],'Invalid exceptional review scope')
    else:ir.need(gate['interface_consistent'] and not receipt['final_semantic_model_called'] and not receipt['freeze_deviation'],'Invalid inherited semantic scope')
    import workflow
    frozen=workflow.bound(receipt['workflow'])
    data=source_preparation.read_source(**frozen['authority'])[0]
    conditional=receipt['freeze_deviation'] or not data[0].get('current_standard_receipt_valid')
    ir.need(receipt['source_conditional']==(not data[0].get('current_standard_receipt_valid')),'Source qualification changed')
    ir.need(receipt['status']==('AUDIT-B-CONDITIONAL' if conditional else 'AUDIT-B-PASSED'),'Final acceptance scope was promoted')
    ir.need(receipt['acceptance_basis']==('EXCEPTIONAL_FINAL_SEMANTIC_REVIEW' if receipt['freeze_deviation'] else 'FROZEN_INTERFACE_SEMANTICS_INHERITED'),'Final review origin changed')
    return receipt
