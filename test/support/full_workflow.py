"""Compose real clean exercise stages; no mathematical verdict is synthesized."""
from pathlib import Path

import audit_a_campaign as a
import translation_author as author
import interface_review
import audit_b_mapping
import audit_b_review
import ir
import workflow
import run_graph
import execution_state


def accepted(directory):
    directory=Path(directory);row=ir.load(directory/'stage/result.json')
    if row['status']=='CANCELLED':raise execution_state.Cancelled('Stage cancelled externally')
    if row['status']!='ACCEPTED' or row.get('exposure',{}).get('status')!='TRANSMITTED-EXPOSURE-CHECK-PASSED':
        raise ValueError('No actual exposure-qualified submitted artifact: '+str(directory))
    return row


def audit_source(case,source,name,budget,progress):
    source=Path(source).resolve();directory=a.ROOT/'test/results'/name
    if not directory.exists():a.prepare(source,a.ROOT/'test'/case,directory)
    else:
        campaign=ir.load(directory/'campaign.json')
        if campaign['graph']!=a.bind(source/'nl0.json') or campaign['spec']!=a.bind(source/'spec.json'):
            raise ValueError('The prepared audit is for a different exact source')
    progress(case,'ACTUAL_AUDIT_A',directory=str(directory))
    a.run(directory,1200,budget=budget)
    if budget.execution:budget.execution.check()
    result=a.collect(directory,a.ROOT/'test/results/audit-a-behavior-v1/behavioral-summary.json')
    if not result['full_acceptance']:raise ValueError('Actual Audit A did not pass: '+str(directory))
    return result


def translate(case,source,interface_name,workflow_name,budget,progress):
    source=Path(source).resolve();results=a.ROOT/'test/results'
    interface=results/interface_name
    if not interface.exists():author.prepare(source,a.ROOT/'test'/case,interface)
    progress(case,'INTERFACE_AUTHORING',directory=str(interface))
    author.run(interface,1800,budget=budget);accepted(interface)
    return from_interface(case,source,interface_name,workflow_name,budget,progress)


def from_interface(case,source,interface_name,workflow_name,budget,progress,candidate=None):
    """Review an actual submitted or explicitly recovered typed model artifact."""
    source=Path(source).resolve();results=a.ROOT/'test/results';interface=results/interface_name
    review=results/(interface_name+'-review');interface_review.prepare(interface,review,candidate=candidate)
    progress(case,'INTERFACE_SEMANTIC_REVIEW',directory=str(review))
    interface_review.run(review,1200,budget=budget)
    checked=interface_review.collect(review)
    if not checked['all_checks_passed']:raise ValueError('Actual interface review did not pass: '+str(review))
    bindings=ir.load(review/'bindings.json');destination=budget.execution.root/'workflow' if budget.execution else results/workflow_name
    if bindings['source_graph']!=a.bind(source/'nl0.json') or bindings['spec']!=a.bind(source/'spec.json'):
        raise ValueError('The recovered interface is not bound to this exact source')
    workflow.freeze(source/'nl0.json',source/'spec.json',bindings['contract']['path'],bindings['plan']['path'],review/'review.json',destination,
        audit_a=source/'audit-a.json',max_concurrency=budget.configuration['requested'])
    frozen=workflow.bound(destination)
    progress(case,'FROZEN_LEAN_PROOF_WORK',directory=str(destination))
    proof=run_graph.run(Path(frozen['contract']),Path(frozen['plan']),destination/'proof-run',
        timeout_seconds=1800,bank=False,budget=budget)
    workflow.bound(destination)
    if proof['status']!='FRAGMENT_ASSEMBLED':raise ValueError('Actual Lean assembly unfinished: '+str(destination))
    mapping=results/(workflow_name+'-mapping');audit_b_mapping.prepare(destination,mapping)
    progress(case,'AUDIT_B_MAPPING_AND_REAL_BUILD',directory=str(mapping))
    audit_b_mapping.run(mapping,1800,budget=budget);audit_b_mapping.adopt(mapping)
    audit_review=results/(workflow_name+'-audit-b-review');audit_b_review.prepare(destination/'audit-b',audit_review)
    progress(case,'AUDIT_B_FRESH_SEMANTIC_REVIEW',directory=str(audit_review))
    audit_b_review.run(audit_review,1800,budget=budget)
    verdict=audit_b_review.collect(audit_review)
    if not verdict['all_checks_passed']:raise ValueError('Actual Audit B semantic review did not pass: '+str(audit_review))
    result=workflow.finish(destination,audit_review/'review.json')
    progress(case,result['status'],directory=str(destination));return result
