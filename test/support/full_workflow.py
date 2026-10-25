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
from execution_health import StageFailure, qualification, review_outcome, record_qualification


def accepted(directory):
    directory=Path(directory);row=ir.load(directory/'stage/result.json')
    if row['status']=='CANCELLED':raise execution_state.Cancelled('Stage cancelled externally')
    checked=qualification(row)
    if not checked['identity_and_input_boundary_verified']:
        raise StageFailure('EXECUTION_UNQUALIFIED','Model identity or input boundary is unverified',evidence=directory/'stage/result.json',details=checked)
    if row['status']!='ACCEPTED' or checked['execution_health']!='NO_RECORDED_FAULT':
        raise StageFailure(row.get('task_outcome') or 'EXECUTION_UNQUALIFIED',
            'Stage did not deliver a healthy submitted artifact; preserve actual candidates for explicit qualified recovery',
            evidence=directory/'stage/result.json',details=checked)
    return row


def nl0_artifact_for_audit(directory):
    """Complete isolated source eligibility is distinct from timing qualification."""
    from author_check import digest
    directory=Path(directory);stage=directory/'stage'
    row=ir.load(stage/'result.json');checked=record_qualification(row)
    if row.get('status')=='CANCELLED':raise execution_state.Cancelled('NL0 author cancelled externally')
    def reject(message):
        raise StageFailure(row.get('task_outcome') or 'AUTHOR_ARTIFACT_INELIGIBLE',message,
            evidence=stage/'result.json',details=checked)
    if row.get('status')!='ACCEPTED' or not checked['identity_and_input_boundary_verified']:
        reject('No complete identity/input-bound definitive NL0 submission')
    if (row.get('isolation_violation') or row.get('execution_fault')
            or row.get('temporary_workspace_removed') is not True):
        reject('Isolation, controller or cleanup evidence is not eligible for automatic mathematical review')
    if not checked['submitted_record_qualified']:
        reject('Only a disclosed recovered transport interruption may qualify a complete NL0 for first A')
    source=stage/'case'
    try:
        submitted=ir.load(stage/'accepted.json')
        canonical={'spec':ir.load(source/'spec.json'),'graph':ir.load(source/'nl0.json')}
        progress=ir.load(source/'author-check-progress.json')
        authority=row['exposure'].get('acceptance_contract')
        if (submitted!=canonical or progress.get('content_sha256')!=digest(canonical)
                or progress.get('author_release_ready') is not True
                or progress.get('reported_readiness')!='no_known_issue' or progress.get('open_issues')
                or not authority or progress.get('acceptance_contract')!=authority):
            reject('Canonical NL0 differs from the actual submitted/release-ready author artifact')
        a.nl0.validate(source/'nl0.json',source/'spec.json')
        tools=[__import__('json').loads(line) for line in (stage/'tools.jsonl').read_text().splitlines() if line.strip()]
        if not any(t.get('tool') in {'submit_artifact','submit_draft'}
            and t.get('result',{}).get('stage_complete') is True
            and t['result'].get('author_closing_check',{}).get('author_release_ready') is True
            and t['result']['author_closing_check'].get('content_sha256')==digest(canonical) for t in tools):
            reject('No actual matching complete author submit-tool result')
    except (OSError,KeyError,ValueError) as error:
        if isinstance(error,StageFailure):raise
        reject('NL0 submission/release binding failed: '+str(error))
    return {'author_artifact_ready_for_audit':True,'content_sha256':digest(canonical),
        'author_stage_result':str(stage/'result.json'),'execution':checked,
        'author_timing_qualified':checked['measurement_valid'],
        'transport_recovery_disclosure':row.get('transport_health') if checked['execution_health']!='NO_RECORDED_FAULT' else None,
        'scope':'Eligibility for first independent mathematical review only; not Audit A acceptance or benchmark qualification.'}


def audit_source(case,source,name,budget,progress,*,reuse_from=(),controls=None):
    source=Path(source).resolve();directory=a.ROOT/'test/results'/name
    if (source/'audit-a.json').is_file():
        prior=a.nl0.validate(source/'nl0.json',source/'spec.json',source/'audit-a.json',allow_unresolved=True)[0]
        if prior['current_standard_receipt_valid']:
            result={'full_acceptance':True,'source_audit_status':prior['audit_status'],
                    'authority':a.bind(source/'audit-a.json'),'reused_unchanged_acceptance':True,
                    'execution_policy':'Prior receipt retains its original execution disclosure; not a new-policy run.'}
            progress(case,'SOURCE_AUDIT_A_PASSED',**result)
            return result
    if not directory.exists():a.prepare(source,a.ROOT/'test'/case,directory,reuse_from=reuse_from)
    else:
        campaign=ir.load(directory/'campaign.json')
        if campaign['graph']!=a.bind(source/'nl0.json') or campaign['spec']!=a.bind(source/'spec.json'):
            raise ValueError('The prepared audit is for a different exact source')
    progress(case,'ACTUAL_AUDIT_A',directory=str(directory))
    a.run(directory,1200,budget=budget)
    if budget.execution:budget.execution.check()
    result=a.collect(directory,controls or a.ROOT/'test/results/audit-a-behavior-v1/behavioral-summary.json')
    if not result['full_acceptance']:
        status=review_outcome(row['verdict'] for row in result.get('unresolved_reviews',[]))
        if status=='REVIEW_PASSED':status='REVIEW_INCOMPLETE'
        raise StageFailure(status,'Actual Audit A did not pass',phase='audit-a',evidence=directory/'inspection.json')
    progress(case,'SOURCE_AUDIT_A_PASSED',inspection=str(directory/'inspection.json'))
    return result


def stage_seconds(budget):
    limit=__import__('json').loads((a.CORE/'config.json').read_text())['timeouts']['case_seconds']
    return budget.execution.remaining(limit) if budget.execution else limit


def translate(case,source,interface_name,workflow_name,budget,progress,*,proof_budget=None):
    source=Path(source).resolve();results=a.ROOT/'test/results'
    interface=results/interface_name
    if not interface.exists():author.prepare(source,a.ROOT/'test'/case,interface)
    progress(case,'INTERFACE_AUTHORING',directory=str(interface))
    author.run(interface,stage_seconds(budget),budget=budget);accepted(interface)
    return from_interface(case,source,interface_name,workflow_name,budget,progress,proof_budget=proof_budget)


def from_interface(case,source,interface_name,workflow_name,budget,progress,candidate=None,review_name=None,*,proof_budget=None):
    """Review an actual submitted or explicitly recovered typed model artifact."""
    source=Path(source).resolve();results=a.ROOT/'test/results';interface=results/interface_name
    budget=a.concurrency.serial_budget(budget)
    proof_budget=proof_budget or a.concurrency.Budget(a.concurrency.resolve(),execution=budget.execution,role='proof')
    destination=budget.execution.root/'workflow' if budget.execution else results/workflow_name
    if candidate is not None or review_name is not None:
        # Explicit legacy recovery requests retain their separate interface review.
        review=results/(review_name or interface_name+'-review');interface_review.prepare(interface,review,candidate=candidate)
        progress(case,'INTERFACE_SEMANTIC_REVIEW',directory=str(review))
        interface_review.run(review,stage_seconds(budget),budget=budget)
        if budget.execution:budget.execution.check()
        checked=interface_review.collect(review)
        if not checked['all_checks_passed']:raise StageFailure(checked.get('review_status','MATHEMATICAL_REVIEW_FAILED'),'Actual interface review did not pass',phase='interface',evidence=review/'report.json')
        bindings=ir.load(review/'bindings.json')
        for key,name in [('source_graph','nl0.json'),('spec','spec.json')]:
            recorded=bindings[key]
            if ir.digest(recorded['path'])!=recorded['sha256'] or recorded['sha256']!=ir.digest(source/name):
                raise ValueError('The recovered interface is not bound to these exact source bytes: '+name)
        workflow.freeze(source/'nl0.json',source/'spec.json',bindings['contract']['path'],bindings['plan']['path'],review/'review.json',destination,
            audit_a=source/'audit-a.json',max_concurrency=proof_budget.configuration['requested'])
    else:
        bindings=ir.load(interface/'accepted-interface-paths.json')
        progress(case,'INTERFACE_TYPES_CHECKED_SEMANTIC_REVIEW_DEFERRED',directory=str(interface))
        workflow.freeze(source/'nl0.json',source/'spec.json',bindings['contract'],bindings['plan'],None,destination,
            audit_a=source/'audit-a.json',max_concurrency=proof_budget.configuration['requested'],
            interface_binding=interface/'accepted-interface-paths.json')
    frozen=workflow.bound(destination)
    progress(case,'FROZEN_LEAN_PROOF_WORK',directory=str(destination))
    proof=run_graph.run(Path(frozen['contract']),Path(frozen['plan']),destination/'proof-run',
        timeout_seconds=stage_seconds(proof_budget),bank=False,budget=proof_budget,
        shared_store=destination/'shared-proofs' if ir.load(frozen['contract']).get('shared_obligations') else None)
    workflow.bound(destination)
    if budget.execution:budget.execution.check()
    if proof['status']!='FRAGMENT_ASSEMBLED':raise StageFailure('PROOF_UNFINISHED','Actual Lean assembly unfinished',phase='proof',evidence=destination/'proof-run/report.json')
    mapping=results/(workflow_name+'-mapping');audit_b_mapping.prepare(destination,mapping)
    progress(case,'AUDIT_B_MAPPING_AND_REAL_BUILD',directory=str(mapping))
    audit_b_mapping.run(mapping,stage_seconds(budget),budget=budget);accepted(mapping);audit_b_mapping.adopt(mapping)
    audit_review=results/(workflow_name+'-audit-b-review');audit_b_review.prepare(destination/'audit-b',audit_review)
    progress(case,'AUDIT_B_FRESH_SEMANTIC_REVIEW',directory=str(audit_review))
    audit_b_review.run(audit_review,stage_seconds(budget),budget=budget)
    if budget.execution:budget.execution.check()
    verdict=audit_b_review.collect(audit_review)
    if not verdict['all_checks_passed']:raise StageFailure(verdict.get('review_status','MATHEMATICAL_REVIEW_FAILED'),'Actual Audit B semantic review did not pass',phase='audit-b',evidence=audit_review/'report.json')
    result=workflow.finish(destination,audit_review/'review.json')
    progress(case,result['status'],directory=str(destination));return result
