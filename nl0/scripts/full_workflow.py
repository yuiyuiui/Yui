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
            or not (row.get('temporary_workspace_removed') is True
                    or (row.get('temporary_workspace_removed') is False
                        and __import__('run_resources').safe_stage_workspace(row)))):
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
            progress(case,'SOURCE_AUDIT_A_PASSED' if result['full_acceptance'] else 'SOURCE_AUDIT_A_CONDITIONAL',**result)
            if getattr(budget,'execution',None):budget.execution.release_retained('nl0','AUDIT_A_FINALIZED')
            return result
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
    if (result['full_acceptance'] or result.get('conditional_acceptance')) and getattr(budget,'execution',None):
        budget.execution.release_retained('nl0','AUDIT_A_FINALIZED')
    return result


def stage_seconds(budget):
    limit=__import__('runtime_config').configured_timeout('stage')
    return budget.execution.remaining(limit) if budget.execution else limit


def translate(case,source,interface,destination,budget,progress,*,proof_budget=None,problem=None,
              authority=None,prior_interface=None,diagnostics=None,prior_run=None):
    source,interface=Path(source).resolve(),Path(interface).resolve()
    author.prepare(source,problem or source/'inputs',interface,authority=authority,
                   prior_interface=prior_interface,diagnostics=diagnostics)
    progress(case,'INTERFACE_AUTHORING',directory=str(interface))
    author.run(interface,stage_seconds(budget),budget=budget);accepted(interface)
    if prior_interface and ir.load(prior_interface)==ir.load(interface/'stage/accepted.json'):
        raise StageFailure('REPAIR_UNCHANGED','The rejected interface was resubmitted unchanged; no repeated audit is started')
    if prior_run is None and prior_interface:
        previous=Path(prior_interface).parents[2]/'workflow'
        selected=workflow.proof_run(previous)
        if (selected/'report.json').is_file():prior_run=selected
    return from_interface(case,source,interface,destination,budget,progress,
                          proof_budget=proof_budget,authority=authority,
                          prior_run=prior_run)


def prove_with_repair(case,frozen,destination,interface,budget,proof_budget,progress,*,prior_run=None,reviewed_interface=None):
    """Retire one shared proof round before serial diagnosis or interface repair."""
    import proof_diagnosis
    import time
    from controller_common import bind
    destination=Path(destination);guidance={};seen=set();round_number=0;rounds=[];diagnostic_reports=[];started=time.monotonic();initial_prior_run=prior_run
    while True:
        round_number+=1
        current=destination/'proof-run' if round_number==1 else destination/'proof-repairs'/f'{round_number:04d}'
        progress(case,'FROZEN_LEAN_PROOF_WORK',directory=str(current),repair_round=round_number)
        proof=run_graph.run(Path(frozen['contract']),Path(frozen['plan']),current,
            timeout_seconds=stage_seconds(proof_budget),bank=False,budget=proof_budget,prior_run=prior_run,
            repair_guidance=guidance,reviewed_interface=reviewed_interface,
            shared_store=destination/'shared-proofs' if ir.load(frozen['contract']).get('shared_obligations') else None)
        rounds.append(bind(current/'report.json'))
        workflow.bound(destination)
        if budget.execution:budget.execution.check()
        if proof['status']!='GRAPH_REPAIR_REQUIRED':
            if proof['status']=='FRAGMENT_ASSEMBLED':
                ir.write(destination/'proof-repair-history.json',{'rounds':rounds,'diagnoses':diagnostic_reports,
                    'wall_seconds':time.monotonic()-started,'prior_run':str(initial_prior_run) if initial_prior_run else None,
                    'scope':'All rounds and serial diagnoses in this workflow; inherited earlier attempts remain separate in their original ledgers.'})
                workflow.select_proof_run(destination,current)
            return proof,current
        faults=[job['step'] for job in proof.get('jobs',[]) if
            job.get('worker',{}).get('stage',{}).get('execution_fault') or
            not __import__('run_resources').safe_stage_workspace(job.get('worker',{}).get('stage',{}))]
        if faults:
            raise StageFailure('EXECUTION_FAULT','A retired proof worker has an unconfirmed runtime/cleanup fault; do not start interface repair',
                phase='proof',evidence=current/'report.json',details={'affected_steps':faults,
                    'recoverability':'VERIFIED_SOFTWARE_REPAIR_REQUIRED',
                    'checkpoint':{'proof_run':str(current),'preserve_completed_work':True,'restart_whole_workflow':False}})
        progress(case,'PROOF_ROUND_RETIRED_FOR_DIAGNOSIS',directory=str(current))
        diagnoses={}
        for step,request in sorted(proof['repair_requests'].items()):
            key=(step,request['evidence_key'])
            if key in seen:
                raise StageFailure('PROOF_REPAIR_STALLED','The same obligation/evidence recurred after located repair; preserve the checkpoint instead of resampling',
                    phase='proof-diagnosis',evidence=current/'report.json',details={'checkpoint':{'proof_run':str(current),
                        'preserve_completed_work':True,'restart_whole_workflow':False},'step':step})
            seen.add(key)
            diagnoses[step]=proof_diagnosis.run(current,step,interface,destination/'diagnoses'/f'{round_number:04d}'/step,
                budget=budget,timeout=stage_seconds(budget))
        summary={'proof_run':str(current),'diagnoses':diagnoses,'source_unchanged':True,
                 'scope':'No theorem accepted; all running nodes in this own round have retired before serial repair.'}
        summary_path=destination/'diagnoses'/f'{round_number:04d}'/'report.json';ir.write(summary_path,summary)
        diagnostic_reports.append(bind(summary_path))
        unresolved=[x for x in diagnoses.values() if x['route'] in {'SOURCE_REVIEW_REQUIRED','UNRESOLVED'}]
        if unresolved:
            raise StageFailure('PROOF_REVIEW_REQUIRED','Located diagnosis needs source review or remains unresolved; no frozen premise or target was changed',
                phase='proof-diagnosis',evidence=summary_path,details={'checkpoint':{'proof_run':str(current),
                    'preserve_completed_work':True,'restart_whole_workflow':False}})
        if any(x['route']=='INTERFACE_REPAIR_REQUIRED' for x in diagnoses.values()):
            raise StageFailure('INTERFACE_REPAIR_REQUIRED','New proof evidence locates a source/interface mismatch; return to its author and fresh independent semantic review',
                phase='interface-repair',evidence=summary_path,details={'prior_proof_run':str(current)})
        guidance.update(diagnoses);prior_run=current
        progress(case,'LOCATED_PROOF_BODY_REPAIR',diagnosis=str(summary_path),preserve_own_drafts=True)


def from_interface(case,source,interface,destination,budget,progress,*,proof_budget=None,authority=None,prior_run=None):
    source,interface,destination=[Path(p).resolve() for p in (source,interface,destination)]
    budget=a.concurrency.serial_budget(budget)
    proof_budget=proof_budget or a.concurrency.Budget(a.concurrency.resolve(),execution=budget.execution,role='proof')
    authority=authority or {'graph':str(source/'nl0.json'),'spec':str(source/'spec.json'),'audit_a':str(source/'audit-a.json')}
    bindings=ir.load(interface/'accepted-interface-paths.json')
    review_directory=destination.parent/'interface-review'
    interface_review.prepare(interface,review_directory)
    progress(case,'INTERFACE_FRESH_SEMANTIC_REVIEW',directory=str(review_directory))
    interface_review.run(review_directory,stage_seconds(budget),budget=budget)
    if budget.execution:budget.execution.check()
    try:
        reviewed=interface_review.collect(review_directory)
    except StageFailure as error:
        if error.result.get('status')!='MATHEMATICAL_REVIEW_FAILED' or not error.result.get('record_context_qualified'):raise
        reviewed={'all_checks_passed':False,'review_status':'MATHEMATICAL_REVIEW_FAILED',
            'review_coverage':'INCOMPLETE','located_blocker':error.result,
            'actual_record':ir.load(review_directory/'stage/accepted.json')}
        ir.write(review_directory/'report.json',reviewed)
    if not reviewed['all_checks_passed']:
        raise StageFailure('INTERFACE_REVIEW_FAILED','The proposed types do not have a passing independent source-correspondence review',
            phase='interface-review',evidence=review_directory/'report.json',details={'review_status':reviewed['review_status']})
    progress(case,'INTERFACE_SEMANTIC_REVIEW_PASSED',directory=str(review_directory))
    interface_review.verify_receipt(review_directory/'review.json',bindings['contract'],bindings['plan'],ir.digest(authority['graph']))
    workflow.freeze(**authority,contract=bindings['contract'],plan=bindings['plan'],interface_review=review_directory/'review.json',out=destination,
        max_concurrency=proof_budget.configuration['requested'],interface_binding=interface/'accepted-interface-paths.json')
    frozen=workflow.bound(destination)
    # Free-form strategy queries remain optional; native timeout advice is automatic.
    proof,proof_directory=prove_with_repair(case,frozen,destination,interface,budget,proof_budget,progress,
        prior_run=prior_run,reviewed_interface=review_directory/'review.json')
    if proof['status']!='FRAGMENT_ASSEMBLED':
        raise StageFailure('PROOF_UNFINISHED','Actual Lean proof queue unfinished; preserve each node outcome',phase='proof',evidence=proof_directory/'report.json')
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
