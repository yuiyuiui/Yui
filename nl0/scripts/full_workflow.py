"""Compose real clean mathematical workflow stages; no mathematical verdict is synthesized."""
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
    checked=record_qualification(row)
    if not checked['identity_and_input_boundary_verified']:
        raise StageFailure('EXECUTION_UNQUALIFIED','Model identity or input boundary is unverified',evidence=directory/'stage/result.json',details=checked)
    if row['status']!='ACCEPTED' or not checked['submitted_record_qualified']:
        raise StageFailure(row.get('task_outcome') or 'EXECUTION_UNQUALIFIED',
            'Stage did not deliver a qualified submitted artifact; preserve actual faults and candidates',
            evidence=directory/'stage/result.json',details=checked)
    return row


def nl0_artifact_for_audit(directory):
    """Complete isolated source eligibility is distinct from timing qualification."""
    from author_check import digest
    directory=Path(directory);stage=directory/'stage'
    row=ir.load(stage/'result.json');checked=record_qualification(row)
    if row.get('status')=='CANCELLED':raise execution_state.Cancelled('NL0 author cancelled externally')
    if row.get('execution_fault'):
        raise StageFailure('EXECUTION_FAULT',row['execution_fault'],phase='nl0-authoring',
            evidence=stage/'result.json',details={**checked,
                'tool_execution_fault':row.get('tool_execution_fault'),
                'recoverability':'VERIFIED_SOFTWARE_REPAIR_REQUIRED',
                'checkpoint':{'stage_directory':str(directory),'preserve_completed_work':True,
                              'restart_whole_workflow':False}})
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


def audit_source(case,source,directory,budget,progress,*,reuse_from=(),controls=None,problem=None,audit_budget=None):
    source,directory=Path(source).resolve(),Path(directory).resolve()
    if (source/'audit-a.json').is_file():
        prior=a.nl0.validate(source/'nl0.json',source/'spec.json',source/'audit-a.json',allow_unresolved=True)[0]
        if prior['current_standard_receipt_valid'] or prior.get('current_conditional_receipt_valid'):
            result={'source_audit_status':prior['audit_status'],
                    'authority':a.bind(source/'audit-a.json'),'reused_unchanged_acceptance':True,
                    'full_acceptance':prior['current_standard_receipt_valid'],
                    'conditional_acceptance':prior.get('current_conditional_receipt_valid',False)}
            progress(case,'SOURCE_AUDIT_A_PASSED' if result['full_acceptance'] else 'SOURCE_AUDIT_A_CONDITIONAL',**result);return result
    a.prepare(source,problem or source/'inputs',directory,reuse_from=reuse_from)
    progress(case,'ACTUAL_AUDIT_A',directory=str(directory))
    a.run(directory,stage_seconds(budget),budget=budget,audit_budget=audit_budget)
    if budget.execution:budget.execution.check()
    try:
        result=a.collect(directory,controls)
    except StageFailure as error:
        if error.result.get('status')!='MATHEMATICAL_REVIEW_FAILED' or not error.result.get('record_context_qualified'):
            raise
        result={'full_acceptance':False,'review_coverage':'INCOMPLETE','located_blocker':error.result}
        a.write(directory/'inspection.json',result)
    progress(case,'SOURCE_AUDIT_A_PASSED' if result['full_acceptance'] else
             'SOURCE_AUDIT_A_CONDITIONAL' if result.get('conditional_acceptance') else 'AUDIT_A_FINDINGS',
             inspection=str(directory/'inspection.json'),warnings=result.get('source_warnings',[]))
    return result


def stage_seconds(budget):
    limit=__import__('runtime_config').configured_timeout('stage')
    return budget.execution.remaining(limit) if budget.execution else limit


def translate(case,source,interface,destination,budget,progress,*,proof_budget=None,problem=None,
              authority=None,prior_interface=None,diagnostics=None):
    source,interface=Path(source).resolve(),Path(interface).resolve()
    author.prepare(source,problem or source/'inputs',interface,authority=authority,
                   prior_interface=prior_interface,diagnostics=diagnostics)
    progress(case,'INTERFACE_AUTHORING',directory=str(interface))
    author.run(interface,stage_seconds(budget),budget=budget);accepted(interface)
    if prior_interface and ir.load(prior_interface)==ir.load(interface/'stage/accepted.json'):
        raise StageFailure('REPAIR_UNCHANGED','The rejected interface was resubmitted unchanged; no repeated audit is started')
    return from_interface(case,source,interface,destination,budget,progress,
                          proof_budget=proof_budget,authority=authority,
                          prior_run=Path(prior_interface).parents[2]/'workflow/proof-run' if prior_interface else None)


def from_interface(case,source,interface,destination,budget,progress,*,proof_budget=None,authority=None,prior_run=None):
    source,interface,destination=[Path(p).resolve() for p in (source,interface,destination)]
    budget=a.concurrency.serial_budget(budget)
    proof_budget=proof_budget or a.concurrency.Budget(a.concurrency.resolve(),execution=budget.execution,role='proof')
    authority=authority or {'graph':str(source/'nl0.json'),'spec':str(source/'spec.json'),'audit_a':str(source/'audit-a.json')}
    bindings=ir.load(interface/'accepted-interface-paths.json')
    progress(case,'INTERFACE_TYPES_CHECKED_SEMANTIC_REVIEW_DEFERRED',directory=str(interface))
    workflow.freeze(**authority,contract=bindings['contract'],plan=bindings['plan'],interface_review=None,out=destination,
        max_concurrency=proof_budget.configuration['requested'],interface_binding=interface/'accepted-interface-paths.json')
    frozen=workflow.bound(destination)
    progress(case,'FROZEN_LEAN_PROOF_WORK',directory=str(destination))
    proof=run_graph.run(Path(frozen['contract']),Path(frozen['plan']),destination/'proof-run',
        timeout_seconds=stage_seconds(proof_budget),bank=False,budget=proof_budget,prior_run=prior_run,
        shared_store=destination/'shared-proofs' if ir.load(frozen['contract']).get('shared_obligations') else None)
    workflow.bound(destination)
    if budget.execution:budget.execution.check()
    if proof['status']!='FRAGMENT_ASSEMBLED':
        raise StageFailure('PROOF_UNFINISHED','Actual Lean proof queue unfinished; preserve each node outcome',phase='proof',evidence=destination/'proof-run/report.json')
    mapping=destination.parent/'assembly'
    audit_b_mapping.prepare(destination,mapping)
    progress(case,'POSTPROCESSING_ASSEMBLY_AND_SOURCE_EXPORT',directory=str(mapping))
    audit_b_mapping.run(mapping,stage_seconds(budget),budget=budget);accepted(mapping);audit_b_mapping.adopt(mapping)
    audit_review=destination.parent/'audit-b-review';audit_b_review.prepare(destination/'audit-b',audit_review)
    progress(case,'AUDIT_B_FRESH_SEMANTIC_REVIEW',directory=str(audit_review))
    audit_b_review.run(audit_review,stage_seconds(budget),budget=budget)
    if budget.execution:budget.execution.check()
    try:
        verdict=audit_b_review.collect(audit_review)
    except StageFailure as error:
        if error.result.get('status')!='MATHEMATICAL_REVIEW_FAILED' or not error.result.get('record_context_qualified'):
            raise
        raw=ir.load(audit_review/'stage/accepted.json')
        verdict={'all_checks_passed':False,'review_status':'MATHEMATICAL_REVIEW_FAILED',
                 'review_coverage':'INCOMPLETE','actual_record':raw,'located_blocker':error.result}
        a.write(audit_review/'report.json',verdict)
    if not verdict['all_checks_passed']:
        raise StageFailure(verdict.get('review_status','MATHEMATICAL_REVIEW_FAILED'),'Actual Audit B semantic review did not pass',phase='audit-b',evidence=audit_review/'report.json')
    result=workflow.finish(destination,audit_review/'review.json')
    progress(case,result['status'],directory=str(destination));return result
