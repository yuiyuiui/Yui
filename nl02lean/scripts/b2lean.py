"""Discharge prepared basis ports after the shared conditional Audit B.

This stage composes existing checked proofs; it never resamples a semantic audit
or fabricates a new theorem interface. Final native inspection is mandatory.
"""
from __future__ import annotations

from pathlib import Path
import json
import time

import audit_b
import basis
import basis_native
import final_acceptance
import ir
import workflow
from controller_common import bind, write, verify_bindings
from execution_health import StageFailure


def render(contract, context, conditional_source, levels, *, legacy=False, graph=None):
    artifact=basis.verify_context(context);basis.check_interface(context,contract,graph)
    by_port=basis.basis_graph.handoff().by_port(artifact,graph)
    retained=[p for p in contract['premises'] if p['kind']!='mathlib'
        and (p['kind']=='hypothesis' or by_port[p['id']]['category']==4)]
    expected=audit_b.full_type(contract,contract['conclusion']['type'],retained)
    parameters=ir.binder_text(contract)
    hypotheses=' '.join(f"(h_{p['id']} : {p['type']})" for p in retained)
    arguments=[p['name'] for p in contract['parameters']]
    for premise in contract['premises']:
        if premise['kind']=='mathlib':continue  # Already discharged by ordinary assembly.
        row=by_port.get(premise['id'])
        arguments.append('(@YuiBasis.'+row['id']+')' if row and basis.prepared(row) else 'h_'+premise['id'])
    # The connected proof already contains exactly these checked declarations.
    declarations,_,_=basis.declarations(artifact, omit=contract.get('prepared_instances',{}).get('included',()))
    source=conditional_source+'\n'+declarations
    source+='\nnamespace YuiClosed\nset_option autoImplicit false\n'
    if legacy:
        # Historical receipts bind the original renderer, including its inferred
        # levels. Never reinterpret their checked source using the new helper.
        used=set(levels['export_used_parameters'])
        universe=['_' for name in levels['parameters'] if name in used]
        suffix='.{'+', '.join(universe)+'}' if universe else ''
        application='@AuditBExport.P'+suffix+' '+' '.join(arguments)
    else:
        omitted=['h_'+p['id'] for p in contract['premises'] if p['kind']=='external'
            and basis.prepared(by_port[p['id']])]
        helper=Path(__file__).with_name('basis_export.lean').read_text()
        source+=helper.replace('__DISCHARGED_BINDERS__', '#['+', '.join(map(json.dumps,omitted))+']')+'\n'
        application='yui_basis_export%('+', '.join(arguments)+')'
    source+=f"set_option Elab.async false in\ntheorem P {parameters} {hypotheses} : {contract['conclusion']['type']} := by\n"
    source+='  exact '+application+'\n\nend YuiClosed\n'
    return source, expected, [p['id'] for p in retained]


def actual_residual(context,retained,graph=None):
    registry=ir.load(context['basis']['path'])
    ports=basis.basis_graph.handoff().by_port(registry,graph)
    return sorted(r['id'] for p,r in ports.items() if r['category']==4 and p in retained)


def finish(directory, out, *, context, intermediate, before_publish=None):
    started=time.monotonic()
    directory,out=Path(directory).resolve(),Path(out).resolve()
    frozen=workflow.bound(directory)
    ir.need(frozen.get('basis_context')==context,'Final closure does not match this workflow basis')
    basis.verify_context(context)
    receipt=final_acceptance.validate_receipt(intermediate['audit_b']['receipt_path'])
    ir.need(Path(receipt['workflow']).resolve()==directory,'Final closure used another Audit B receipt')
    ir.need(not receipt['freeze_deviation'],'Basis closure requires the exact frozen target/interface')
    conditional=directory/'audit-b/Proof.lean';contract=ir.contract(frozen['contract'])
    source,expected,retained=render(contract,context,conditional.read_text(),
        ir.load(directory/'audit-b/assembly.json')['universe_parameters'],graph=ir.load(frozen['authority']['graph']))
    checked=basis_native.check(source,[('P','YuiClosed.P',expected)],['YuiClosed.P'],out)
    if not checked['passed']:
        raise StageFailure('BASIS_FINAL_CLOSURE_FAILED','Prepared proofs did not close the actual frozen target',
            phase='basis-final-closure',evidence=out/'check.json',details={'errors':checked['errors']})
    # Recheck both authorities after the native call, before publishing success.
    workflow.bound(directory);basis.verify_context(context)
    final_acceptance.validate_receipt(intermediate['audit_b']['receipt_path'])
    if before_publish is not None:before_publish()
    residual=actual_residual(context,retained,ir.load(frozen['authority']['graph']))
    unconditional=not residual and not receipt['source_conditional']
    result={**intermediate,'version':'yui-b2lean-3','status':'WORKFLOW-PASSED' if unconditional else 'WORKFLOW-CONDITIONAL',
        'formalization_goal':'unconditional','achieved_scope':'UNCONDITIONAL_LEAN' if unconditional else
            'CONDITIONAL_LEAN' if residual else 'CLOSED_LEAN_SOURCE_QUALIFIED',
        'proof':str(out/'Proof.lean'),'basis_discharge_seconds':time.monotonic()-started,
        'closure':{'unconditional':unconditional,'kernel_closed':not residual,'remaining_premises':retained,
            'residual_class4':residual,'native':bind(out/'check.json'),
            'proof':bind(out/'Proof.lean'),'export':'YuiClosed.P'},
        'audit_b':intermediate['audit_b'],'conditional_workflow':str(directory),
        'bindings':[*intermediate.get('bindings',[]),bind(directory/'manifest.json'),bind(directory/'audit-b/Proof.lean'),
            bind(intermediate['audit_b']['receipt_path']),context['basis'],context['native']],
        'source_conditional':receipt['source_conditional'],
        'final_semantic_model_called':False,
        'acceptance_basis':'SHARED_AUDIT_A_AND_FROZEN_INTERFACE_WITH_FINAL_NATIVE_BASIS_DISCHARGE'}
    write(out/'report.json',result)
    if not unconditional:
        message='The unconditional goal remains incomplete: approved class-4 premises or upstream source qualifications remain.'
        write(out/'warn.json',{'status':'UNCONDITIONAL_GOAL_NOT_COMPLETED','message':message,
            'residual_class4':residual,'source_conditional':receipt['source_conditional']})
        (out/'warn.md').write_text(message+'\n')
        result['warning']=message
    return result


def validate_receipt(out):
    """Read-only revalidation of a delivered closed proof and its authority."""
    out=Path(out);report=ir.load(out/'report.json');verify_bindings(report['bindings'])
    ir.need(report.get('version') in {'yui-b2lean-1','yui-b2lean-2','yui-b2lean-3'},'Unknown final basis receipt')
    verify_bindings([report['closure']['native'],report['closure']['proof']])
    checked=basis_native.verify(report['closure']['native']['path'])
    frozen=workflow.bound(report['conditional_workflow']);context=frozen['basis_context']
    basis.verify_context(context)
    receipt=final_acceptance.validate_receipt(report['audit_b']['receipt_path'])
    source,expected,retained=render(ir.contract(frozen['contract']),context,
        (Path(report['conditional_workflow'])/'audit-b/Proof.lean').read_text(),
        ir.load(Path(report['conditional_workflow'])/'audit-b/assembly.json')['universe_parameters'],
        legacy=report['version']=='yui-b2lean-1',graph=ir.load(frozen['authority']['graph']))
    ir.need((out/'Proof.lean').read_text()==source and checked['checks']==[['P','YuiClosed.P',expected]],'Closed export changed')
    residual=actual_residual(context,retained,ir.load(frozen['authority']['graph'])) if report['version']=='yui-b2lean-3' else context['residual_class4']
    complete=not residual and not receipt['source_conditional']
    scope='UNCONDITIONAL_LEAN' if complete else 'CONDITIONAL_LEAN' if residual else 'CLOSED_LEAN_SOURCE_QUALIFIED'
    ir.need(report['formalization_goal']=='unconditional' and report['achieved_scope']==scope
        and report['final_semantic_model_called'] is False and report['proof']==str(out.resolve()/'Proof.lean'),
        'Final basis delivery scope changed')
    ir.need(report['closure']=={'unconditional':complete,'kernel_closed':not residual,'remaining_premises':retained,
        'residual_class4':residual,'native':bind(out/'check.json'),
        'proof':bind(out/'Proof.lean'),'export':'YuiClosed.P'},'Final closure scope changed')
    ir.need(report['status']==('WORKFLOW-PASSED' if complete else 'WORKFLOW-CONDITIONAL'),'Final scope promoted')
    return report
