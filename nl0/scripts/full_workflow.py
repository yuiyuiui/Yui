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
    if not a.global_acceptance(directory)['accepted']:
        result={'full_acceptance':False,'review_coverage':'GLOBAL_COMPLETE_LOCAL_NOT_STARTED',
            'global_review':str(directory/'global-acceptance.json')}
        a.write(directory/'inspection.json',result)
        return result
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
              authority=None,prior_interface=None,diagnostics=None,prior_run=None,sessions=None):
    source,interface=Path(source).resolve(),Path(interface).resolve()
    author.prepare(source,problem or source/'inputs',interface,authority=authority,
                   prior_interface=prior_interface,diagnostics=diagnostics)
    progress(case,'INTERFACE_AUTHORING',directory=str(interface))
    if sessions:
        with sessions.use('lean-global-author'):author.run(interface,stage_seconds(budget),budget=budget)
    else:author.run(interface,stage_seconds(budget),budget=budget)
    accepted(interface)
    if prior_run is None and prior_interface:
        previous=Path(prior_interface).parents[2]/'workflow'
        selected=workflow.proof_run(previous)
        if (selected/'report.json').is_file():prior_run=selected
    return from_interface(case,source,interface,destination,budget,progress,
                          proof_budget=proof_budget,authority=authority,
                          prior_run=prior_run,sessions=sessions)


def prove_with_repair(case,frozen,destination,interface,budget,proof_budget,progress,*,prior_run=None,reviewed_interface=None,sessions=None):
    """Preserve local work; diagnose explicit obstructions after their handoffs."""
    import proof_diagnosis
    import time
    from controller_common import bind
    destination=Path(destination);guidance={};round_number=0;rounds=[];diagnostic_reports=[];started=time.monotonic();initial_prior_run=prior_run
    while True:
        round_number+=1
        current=destination/'proof-run' if round_number==1 else destination/'proof-repairs'/f'{round_number:04d}'
        progress(case,'FROZEN_LEAN_PROOF_WORK',directory=str(current),repair_round=round_number)
        proof=run_graph.run(Path(frozen['contract']),Path(frozen['plan']),current,
            timeout_seconds=stage_seconds(proof_budget),budget=proof_budget,prior_run=prior_run,
            repair_guidance=guidance,reviewed_interface=reviewed_interface,sessions=sessions,diagnostic_interface=interface,
            shared_store=destination/'shared-proofs' if ir.load(frozen['contract']).get('shared_obligations') else None)
        rounds.append(bind(current/'report.json'))
        workflow.bound(destination)
        if budget.execution:budget.execution.check()
        local_failures={j['step']:j['verification'] for j in proof.get('jobs',[]) if j.get('verification',{}).get('exit_code',0)!=0}
        if local_failures:
            guidance.update({step:{'route':'LOCAL_PROOF_REPAIR','actual_compiler_feedback':row} for step,row in local_failures.items()})
            prior_run=current
            continue
        if proof['status']!='GRAPH_REPAIR_REQUIRED':
            if workflow.proof_rounds.locally_complete(proof.get('status')):
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
        progress(case,'PROOF_CONNECTION_DIAGNOSIS_AFTER_HANDOFF',directory=str(current))
        diagnoses={}
        for step,request in sorted(proof['repair_requests'].items()):
            if request.get('diagnosis'):
                diagnoses[step]=ir.load(request['diagnosis']['diagnosis_report'])
                ir.need(diagnoses[step]==request['diagnosis'],'Changed qualified live diagnosis')
            elif sessions:
                with sessions.use('proof-connection'):
                    diagnoses[step]=proof_diagnosis.run(current,step,interface,destination/'diagnoses'/f'{round_number:04d}'/step,
                        budget=budget,timeout=stage_seconds(budget))
            else:diagnoses[step]=proof_diagnosis.run(current,step,interface,destination/'diagnoses'/f'{round_number:04d}'/step,
                budget=budget,timeout=stage_seconds(budget))
        summary={'proof_run':str(current),'diagnoses':diagnoses,'source_unchanged':True,
                 'scope':'No theorem accepted; active local assignments reached handoffs before serial connection diagnosis.'}
        summary_path=destination/'diagnoses'/f'{round_number:04d}'/'report.json';ir.write(summary_path,summary)
        diagnostic_reports.append(bind(summary_path))
        for step,diagnosis in diagnoses.items():
            if diagnosis['route']=='BASIS_REVISION_REQUIRED':
                import basis_defect
                report=current/'workers'/step/'diagnosis-requests'/diagnosis['evidence_key']/'review/stage/accepted.json'
                ir.need(diagnosis['basis_defect']==bind(report),'Changed proof-worker basis defect handoff')
                basis_defect.stop(report.parent)
        unresolved=[x for x in diagnoses.values() if x['route']=='SOURCE_REVIEW_REQUIRED']
        if unresolved:
            notices=[]
            for diagnosis in unresolved:
                path=Path(diagnosis.get('diagnosis_report','')).parent
                if path.is_dir() and (path/'report.json').is_file():
                    notices.append(proof_diagnosis.notice_source(current/'inputs/contract.json',diagnosis['step'],path,diagnosis))
            raise StageFailure('PROOF_REVIEW_REQUIRED','Qualified diagnosis identifies a source error or important missing mathematical justification; no frozen premise or target was changed',
                phase='proof-diagnosis',evidence=summary_path,details={'checkpoint':{'proof_run':str(current),
                    'source_issue_notices':notices,'preserve_completed_work':True,'restart_whole_workflow':False}})
        if any(x['route']=='INTERFACE_REPAIR_REQUIRED' for x in diagnoses.values()):
            raise StageFailure('FROZEN_INTERFACE_REQUIRES_USER','Located protected public-contract defect; user decision required',
                phase='frozen-interface',evidence=summary_path,details={'prior_proof_run':str(current),'user_decision_required':True})
        if any(x['route']=='INTERNAL_INTERFACE_REPAIR' for x in diagnoses.values()):
            import internal_interface_repair
            raise StageFailure('INTERNAL_INTERFACE_REPAIR_REQUIRED','Located internal T-plan defect; return to preprocessing under the unchanged public contract',
                phase='internal-interface-repair',evidence=summary_path,
                details={'prior_proof_run':str(current), 'internal_repair':internal_interface_repair.context(destination)})
        guidance.update(diagnoses);prior_run=current
        progress(case,'LOCATED_PROOF_BODY_REPAIR',diagnosis=str(summary_path),preserve_own_drafts=True)


def from_interface(case,source,interface,destination,budget,progress,*,proof_budget=None,authority=None,prior_run=None,sessions=None):
    source,interface,destination=[Path(p).resolve() for p in (source,interface,destination)]
    budget=a.concurrency.serial_budget(budget)
    proof_budget=proof_budget or a.concurrency.Budget(a.concurrency.resolve(),execution=budget.execution,role='proof')
    authority=authority or {'graph':str(source/'nl0.json'),'spec':str(source/'spec.json'),'audit_a':str(source/'audit-a.json')}
    bindings=ir.load(interface/'accepted-interface-paths.json')
    review_directory=destination.parent/'interface-review'
    interface_review.prepare(interface,review_directory)
    progress(case,'INTERFACE_FRESH_SEMANTIC_REVIEW',directory=str(review_directory))
    if sessions:
        with sessions.use('lean-global-reviewer'):interface_review.run(review_directory,stage_seconds(budget),budget=budget)
    else:interface_review.run(review_directory,stage_seconds(budget),budget=budget)
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
    if sessions:sessions.close(['lean-global-author','lean-global-reviewer'],'INTERFACE_FROZEN',[destination/'freeze-seal.json',review_directory/'review.json'])
    # Free-form strategy queries remain optional; native timeout advice is automatic.
    proof,proof_directory=prove_with_repair(case,frozen,destination,interface,budget,proof_budget,progress,
        prior_run=prior_run,reviewed_interface=review_directory/'review.json',sessions=sessions)
    if not workflow.proof_rounds.locally_complete(proof.get('status')):
        raise StageFailure('PROOF_UNFINISHED','Actual Lean proof queue unfinished; preserve each node outcome',phase='proof',evidence=proof_directory/'report.json')
    import audit_b,final_acceptance
    workflow.prepare_audit(destination)
    try:
        built=audit_b.build(destination/'audit-b',frozen_contract=frozen['contract'])
        ready=built['status']=='AUDIT-B-MECHANICAL-PASSED'
        if not ready:
            final_acceptance.proof_integrity(destination/'audit-b');ready=True
    except (ValueError,KeyError,TypeError):ready=False
    if not ready:
        mapping=destination.parent/'assembly'
        audit_b_mapping.prepare(destination,mapping)
        progress(case,'PROOF_CONNECTION_REPAIR',directory=str(mapping))
        if sessions:
            with sessions.use('proof-connection'):audit_b_mapping.run(mapping,stage_seconds(budget),budget=budget)
        else:audit_b_mapping.run(mapping,stage_seconds(budget),budget=budget)
        accepted(mapping);audit_b_mapping.adopt(mapping)
    result=finish_translation(case,destination,budget,progress)
    if sessions:
        if result['status']=='DIFFERENT_RESULT_DELIVERED':sessions.cancel_all()
        else:
            current_steps={step['id'] for step in ir.load(frozen['plan'])['steps']}
            superseded={role for role in sessions.roles if role.startswith('lean:') and role[5:] not in current_steps}
            sessions.close_all('WORKFLOW_FINALIZED',[destination/'report.json'],superseded=superseded)
    progress(case,result['status'],directory=str(destination));return result


def finish_translation(case,destination,budget,progress):
    """Machine normal acceptance, or the three explicitly authorized human choices."""
    import final_acceptance
    from fault_control import Gate,outcome_error
    from controller_common import bind,write
    destination=Path(destination)
    gate=final_acceptance.check(destination)
    if gate['interface_consistent']:
        return workflow.finish(destination,machine=True)
    review_number=0
    while True:
        review_number+=1
        audit_review=destination.parent/('audit-b-final' if review_number==1 else 'audit-b-final-rechecks/'+str(review_number).zfill(4))
        audit_b_review.prepare(destination/'audit-b',audit_review,interface_deviation=True)
        progress(case,'AUDIT_B_FINAL_INTERFACE_DEVIATION_REVIEW',directory=str(audit_review))
        audit_b_review.run(audit_review,stage_seconds(budget),budget=budget)
        try:verdict=audit_b_review.collect(audit_review)
        except StageFailure as error:
            if not error.result.get('record_context_qualified'):raise
            verdict={'all_checks_passed':False,'review_coverage':'INCOMPLETE',
                'actual_record':ir.load(audit_review/'stage/accepted.json'),'located_blocker':error.result}
            ir.write(audit_review/'report.json',verdict)
        if not verdict['all_checks_passed']:
            findings=bind(audit_review/'report.json')
            error=StageFailure('FINAL_FIDELITY_NOT_ACCEPTED','Final E/P fidelity was not accepted. Report the freeze defect to developers. No original-goal completion is recorded.',
                phase='audit-b-final',evidence=audit_review/'report.json',details={'user_decision_required':True,'automatic_restart':False})
            progress(case,'PAUSED_ERROR',findings=str(audit_review/'report.json'))
            decision=Gate(audit_review/'decision',recorder=budget.execution,task='case-controller',stage='audit-b-final').pause(
                outcome_error(error.result),resumable=False,checkpoint={'workflow':str(destination),'findings':findings},
                decisions=('deliver-actual','recheck','reset-translation'))
            selected=decision['control']['action'];record=bind(audit_review/'decision/error-state.json')
            try:findings_unchanged=bind(audit_review/'report.json')==findings
            except OSError:findings_unchanged=False
            if not findings_unchanged or final_acceptance.check(destination)!=gate:
                raise StageFailure('FINAL_ARTIFACT_CHANGED','Final evidence changed while waiting for the user; preserve the checkpoint',phase='audit-b-final')
            if selected=='recheck':continue
            if selected=='reset-translation':
                raise StageFailure('USER_REQUESTED_TRANSLATION_RESET','Human explicitly selected translation-only reset',
                    phase='user-decision',details={'user_decision':record})
            result={'status':'DIFFERENT_RESULT_DELIVERED','original_goal_completed':False,'user_decision':record,
                'proof':str(destination/'audit-b/Proof.lean'),
                'audit_b':{'status':'FINAL_FIDELITY_NOT_ACCEPTED','receipt_path':str(audit_review/'report.json'),
                    'receipt_kind':'USER_DELIVERY_EVIDENCE',
                    'review_coverage':verdict.get('review_coverage','COMPLETE'),
                    'findings':str(audit_review/'report.json'),'acceptance_basis':'USER_ACCEPTED_DIFFERENT_RESULT'},
                'warning':'User accepted delivery of the actual compiled result; fidelity to the original target was not accepted. See the final review and actual Lean theorem.'}
            write(destination/'report.json',result);return result
        return workflow.finish(destination,machine=True,exceptional_review=audit_review/'review.json')
