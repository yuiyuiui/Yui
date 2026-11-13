"""One owned, independent case lifecycle for an installed Yui skill."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import traceback

from controller_common import write, bind, final_write
import audit_a_campaign as a
import full_workflow as f
import jobs
import nl0_author
from clean_stage import ArtifactStage
from execution_health import StageFailure
import execution_state as execution
from runtime_config import use_profiles, use_environment
import source_preparation
import source_refactor
import basis
import case_outcomes


def source_key(source):
    from audit_reuse import hashed
    spec=json.loads((source/'spec.json').read_text());graph=json.loads((source/'nl0.json').read_text())
    spec.pop('inputs',None);graph.pop('spec_sha256',None)
    return hashed({'spec':spec,'graph':graph})


def repair_obligations(source, campaign):
    """Convert only actual assessed findings to exact baseline repair locations."""
    from author_check import digest
    from acceptance import current
    shared=current().rows
    source,campaign=Path(source),Path(campaign)
    baseline={'spec':json.loads((source/'spec.json').read_text()),'graph':json.loads((source/'nl0.json').read_text())}
    issues=[]
    for directory in sorted(campaign.iterdir()):
        if not directory.is_dir():continue
        path=directory/'stage/accepted.json'
        if not path.is_file():continue
        record=json.loads(path.read_text())
        def visit(value, criterion='review'):
            if isinstance(value,dict):
                if value.get('verdict') in {'FAIL','UNVERIFIED'}:
                    location=None
                    for candidate in value.get('locations',[]):
                        if candidate.startswith('spec.json#'):location='/spec'+candidate.split('#',1)[1]
                        elif candidate.startswith('nl0.json#'):location='/graph'+candidate.split('#',1)[1]
                        elif candidate.startswith('/inference') and directory.name in {r['id'] for r in baseline['graph']['inferences']}:
                            index=next(i for i,r in enumerate(baseline['graph']['inferences']) if r['id']==directory.name)
                            location='/graph/inferences/'+str(index)+candidate[len('/inference'):]
                        if location:
                            try:a.nl0.closure.resolve(baseline,location);break
                            except (ValueError,KeyError,TypeError,IndexError):location=None
                    if location is None:
                        if directory.name!='global':
                            location='/graph/inferences/'+str(next(i for i,r in enumerate(baseline['graph']['inferences']) if r['id']==directory.name))
                        elif '/source_reviews/' in criterion:
                            pid=criterion.split('/source_reviews/',1)[1].split('/')[0]
                            location='/graph/propositions/'+str(next(i for i,p in enumerate(baseline['graph']['propositions']) if p['id']==pid))
                        elif '/definition_reviews/' in criterion:
                            did=criterion.split('/definition_reviews/',1)[1].split('/')[0]
                            location='/spec/definitions/'+str(next(i for i,d in enumerate(baseline['spec']['definitions']) if d['id']==did))
                        else:location='/graph/inferences' if 'structure_review' in criterion else '/spec/full_target'
                    requirement=next((part for part in reversed(criterion.split('/')) if part in shared),None)
                    if requirement is None:
                        requirement=('definitions' if 'definition_reviews' in criterion else
                                     'sources' if 'source_reviews' in criterion else
                                     'target' if 'target_review' in criterion else
                                     'structure' if directory.name=='global' else 'argument')
                    note=value.get('notes') or value.get('explanation') or json.dumps(value)
                    issues.append({'id':'ISSUE'+str(len(issues)+1).zfill(3),'criterion':requirement,
                                   'location':location,'note':criterion+': '+note+' Original review locations: '+json.dumps(value.get('locations',[]))})
                for key,child in value.items():visit(child,criterion+'/'+key)
            elif isinstance(value,list):
                for child in value:visit(child,criterion)
        visit(record)
    return {'version':'yui-repair-obligations-1','baseline_input':'baseline.json',
            'baseline_content_sha256':digest(baseline),'issues':issues}


def author_stage(job, root, budget, *, baseline=None, obligations=None):
    if job.get('workflow_protocol'):
        import frozen_graph
        return frozen_graph.local_stage(job,root,budget,baseline=baseline,obligations=obligations)
    nl0_author.prepare(basis.problem_inputs(job),root,baseline=baseline,obligations=obligations)
    stage=ArtifactStage(root/'stage',(root/'prompt.txt').read_text(),phase='nl0-authoring',kind='nl0',
        case_id=job['case'],inputs=root/'inputs/inputs.json',timeout=f.stage_seconds(budget),budget=budget)
    if baseline:
        for path in source_preparation.evidence_paths(json.loads((baseline/'nl0.json').read_text()),baseline):
            relative=path.relative_to(baseline);destination=root/'stage/case'/relative
            if destination.exists() and destination.read_bytes()!=path.read_bytes():
                raise ValueError('Baseline evidence collides with a current explicit input')
            destination.parent.mkdir(parents=True,exist_ok=True)
            if not destination.exists():__import__('shutil').copyfile(path,destination)
    stage.execute();budget.execution.check();f.nl0_artifact_for_audit(root)
    source=root/'stage/case'
    if baseline:
        before=json.loads((baseline/'spec.json').read_text());after=json.loads((source/'spec.json').read_text())
        if any(before[k]!=after[k] for k in ('full_target','conclusion','parameters','hypotheses')):
            raise StageFailure('SOURCE_CHANGE_REQUIRES_USER','Local repair changed the approved problem')
    return source


def nl0_work(job, recorder, budget, progress, *, audit_budget=None, initial_source=None, review_history=(), sessions=None):
    if job['policy']!='first-pass':
        import nl0_review_loop
        restored=initial_source;prior=list(review_history);obligations=None
        mode=(job.get('resume') or {}).get('mode')
        if mode in {'audit-a','author-repair'} and not review_history:
            import interrupted
            if mode=='audit-a':restored=interrupted.restore_source(job);prior=list(job['resume']['campaigns'])
            else:restored,obligations,prior=interrupted.restore_repair(job)
        return nl0_review_loop.run(job,budget,audit_budget,progress,author_stage,repair_obligations,
            restored=restored,prior=prior,initial_issues=obligations,sessions=sessions,route_graph=bool(job.get('workflow_protocol')))
    root=Path(job['root']);baseline=None;obligations=None;prior=[];revision=0;seen=set()
    restored=initial_source
    if (job.get('resume') or {}).get('mode')=='audit-a':
        import interrupted
        restored=interrupted.restore_source(job);prior=list(job['resume']['campaigns'])
        progress(job['case'],'NL0_RELEASED_SOURCE_RESTORED',directory=str(restored),new_author_model_called=False)
    elif (job.get('resume') or {}).get('mode')=='author-repair':
        import interrupted
        baseline,obligations,prior=interrupted.restore_repair(job)
        seen.add(source_key(baseline))
        progress(job['case'],'NL0_REPAIR_CHECKPOINT_RESTORED',baseline=str(baseline),
                 original_repair=job['resume']['repair_directory'],new_author_required=True)
    while True:
        revision+=1;author=root/'nl0'/f'{revision:04d}';audit=root/'audit-a'/f'{revision:04d}'
        if restored is not None:
            source=restored;restored=None
        else:
            progress(job['case'],'NL0_AUTHORING' if baseline is None else 'NL0_LOCAL_REPAIR',directory=str(author))
            source=author_stage(job,author,budget,baseline=baseline,obligations=obligations)
        key=source_key(source)
        if key in seen:raise StageFailure('REPAIR_CYCLE','A previously rejected source reappeared; do not resample its audit')
        seen.add(key)
        audited=f.audit_source(job['case'],source,audit,budget,progress,problem=basis.problem_inputs(job),reuse_from=prior,
                               audit_budget=audit_budget)
        if audited['full_acceptance'] or audited.get('conditional_acceptance'):
            return {'graph':str(source/'nl0.json'),'spec':str(source/'spec.json'),'audit_a':str(source/'audit-a.json')}
        if job['policy']=='first-pass':
            raise StageFailure('AUDIT_A_NONPASS','The first actual Audit A did not pass',phase='audit-a',evidence=audit/'inspection.json')
        obligations=repair_obligations(source,audit)
        if not obligations['issues']:
            raise StageFailure('REVIEW_INCOMPLETE','No complete located diagnosis is available for automatic repair',phase='audit-a',evidence=audit/'inspection.json')
        prior.append(audit);baseline=source
        write(root/'repairs'/f'audit-a-{revision:04d}.json',obligations)


def translation_work(job, authority, budgets, progress):
    import lean_timeout_policy
    with lean_timeout_policy.scope(Path(job['root'])/'nl0-to-lean'/'lean-timeouts', budgets.serial):
        return translation_work_scoped(job, authority, budgets, progress)


def translation_work_scoped(job, authority, budgets, progress):
    root=Path(job['root']);original=dict(authority)
    before_native={p.name for p in (root/'native-checks').glob('*')}
    while True:
        try:return translation_attempt(job,original,budgets,progress)
        except StageFailure as error:
            if error.result.get('status')!='USER_REQUESTED_TRANSLATION_RESET':raise
            import translation_reset
            record=translation_reset.apply(root,original,budgets.serial.execution,error.result['user_decision'],before_native)
            progress(job['case'],'USER_REQUESTED_TRANSLATION_RESET',record=str(record),nl0_audit_a_preserved=True)


def translation_attempt(job, authority, budgets, progress):
    from role_sessions import Sessions
    sessions=Sessions();root=Path(job['root']);checkpoint=None
    if (job.get('resume') or {}).get('mode') in {'native-proof-cleanup','native-proof-io'}:
        if job['resume']['mode']=='native-proof-io':
            import proof_io_recovery
            proof_io_recovery.validate_descriptor(job)
        else:
            import native_cleanup_recovery
            native_cleanup_recovery.validate_descriptor(job)
        checkpoint=job['resume'];authority=checkpoint['source_authority']
        if checkpoint['mode']=='native-proof-io':
            checkpoint={**checkpoint,'prior_proof_run':str(proof_io_recovery.stage_checkpoint(job))}
    elif not job.get('workflow_protocol'):
        extraction=0;previous=None;findings=None
        while True:
            extraction+=1
            prepared=root/'nl0-to-lean'/('preparation' if extraction==1 else 'preparation-repairs/'+str(extraction).zfill(4))
            try:
                authority=source_refactor.run(authority,prepared,budgets.serial,sessions=sessions,
                    prior_artifact=previous,findings=findings)
                break
            except StageFailure as error:
                if error.result.get('phase')!='source-extraction-review':raise
                previous=prepared/'stage/accepted.json';findings=Path(error.result['evidence'])
                if not previous.is_file():raise
                progress(job['case'],'SOURCE_EXTRACTION_REPAIR',findings=str(findings))
    source=Path(authority['graph']).parent;prior_interface=None;diagnostics=None;attempt=0;internal_context=None
    resume=job.get('resume') or {}
    repair_prior_run=resume.get('prior_proof_run') if resume.get('mode')=='basis-revision' else None
    while True:
        attempt+=1;directory=root/'nl0-to-lean'/f'{attempt:04d}'
        current_interface=Path(checkpoint['interface']) if checkpoint else directory/'interface'
        try:
            if checkpoint:
                result=f.from_interface(job['case'],source,current_interface,directory/'workflow',budgets.serial,progress,
                    proof_budget=budgets.proof,authority=authority,prior_run=Path(checkpoint['prior_proof_run']),sessions=sessions)
                checkpoint=None
            else:
                result=f.translate(job['case'],source,current_interface,directory/'workflow',budgets.serial,progress,
                    proof_budget=budgets.proof,problem=basis.problem_inputs(job),authority=authority,
                    prior_interface=prior_interface,diagnostics=diagnostics,prior_run=repair_prior_run,sessions=sessions)
            summary={'status':result['audit_b']['status'],'workflow':str(directory/'workflow'),
                     'acceptance_basis':result['audit_b']['acceptance_basis']}
            if result['status']=='DIFFERENT_RESULT_DELIVERED':
                summary['delivery']={'findings':bind(result['audit_b']['findings']),
                    'decision':result['user_decision'],'proof':bind(result['proof']),
                    'review_coverage':result['audit_b']['review_coverage']}
            else:summary['review']=bind(result['audit_b']['receipt_path'])
            write(root/'audit-b'/f'{attempt:04d}.json',summary)
            if result['status']=='DIFFERENT_RESULT_DELIVERED':
                warning=json.loads((root/'warn.json').read_text()) if (root/'warn.json').exists() else {}
                warning.update(status='ORIGINAL_GOAL_NOT_COMPLETED',message=result['warning'],
                    actual_proof=result['proof'],findings=result['audit_b']['findings'])
                write(root/'warn.json',warning)
                with (root/'warn.md').open('a') as stream:stream.write('\n# Original goal not completed\n\n'+result['warning']+'\n')
            if result['audit_b'].get('freeze_deviation'):
                warning=json.loads((root/'warn.json').read_text()) if (root/'warn.json').exists() else {'status':'FROZEN_INTERFACE_DEVIATION'}
                warning['freeze_deviation']={'message':result['audit_b']['warning'],
                    'receipt':result['audit_b']['receipt_path'],'source_fidelity_accepted':True}
                write(root/'warn.json',warning)
                with (root/'warn.md').open('a') as stream:stream.write('\n## Frozen interface deviation\n\n'+result['audit_b']['warning']+'\n')
            return result
        except StageFailure as error:
            phase=error.result.get('phase')
            if phase not in {'interface-review','internal-interface-repair'} or job['policy']=='first-pass':raise
            if phase=='internal-interface-repair':
                internal_context=error.result['internal_repair']
                repair_prior_run=Path(error.result['prior_proof_run'])
                report=Path(error.result['evidence'])
                diagnostics={'report':json.loads(report.read_text()),'internal_repair':internal_context,
                    'scope':'Reviewed internal T revision; preserve all original source, H/E/P and public definitions.'}
            else:
                report=directory/'interface-review/report.json'
                diagnostics={'report':json.loads(report.read_text()),
                    'actual_review':json.loads((directory/'interface-review/stage/accepted.json').read_text()),
                    'scope':'Repair the located interface findings; preserve NL0 and its Audit A.'}
                if internal_context:diagnostics['internal_repair']=internal_context
            if not report.is_file():raise
            checkpoint=None;prior_interface=current_interface/'stage/accepted.json'
            if not prior_interface.is_file():raise
            write(root/'repairs'/f'interface-{attempt:04d}.json',{'diagnosis':bind(report),
                'route':'reviewed_internal_T_repair' if internal_context else 'same_pre_freeze_author_and_reviewer','source_unchanged':True})


def execute(job, root=None):
    jobs.validate(job);root=Path(job['root'])
    if (root/'execution-status.json').exists():raise ValueError('Preserve this run; prepare a new explicit run')
    resume=job.get('resume') or {}
    import lean_environment
    selected = job.get('lean_environment') if 'lean_environment' in job else (
        lean_environment.legacy() if job['track'] != 'nl0' else None)
    with use_profiles(job['profiles']), use_environment(selected):
        recorder=execution.Recorder(root,job['case'],a.concurrency.resolve(job['max_concurrency']),
            phase='nl0-authoring' if job['track'] in {'nl0','full'} else 'translation-preparation',
            time_budget_seconds=job['time_budget_seconds'],
            absolute_deadline=resume.get('deadline') if resume.get('mode')=='basis-revision' else None)
        budgets=a.concurrency.CaseBudgets(job['max_concurrency'],execution=recorder);result={}
        def progress(case,phase,**extra):
            from runtime_config import model_profile
            profile=model_profile('audit-a' if phase.startswith(('NL0_','ACTUAL_AUDIT_A','SOURCE_AUDIT_A','AUDIT_A_','BASIS_AUTHOR','BASIS_CHECKED','BASIS_SEMANTIC_REVIEW','BASIS_REVIEWED','BASIS_REVISION_')) else 'translation-preparation')
            # Delivery records an already-authorized artifact; it starts no new work.
            if phase=='DIFFERENT_RESULT_DELIVERED':
                if recorder.cancelled():raise execution.Cancelled('External cancellation requested during delivery')
            else:recorder.check()
            recorder.update(phase=phase,stage_artifacts=extra,model_selection=profile,
                model={'id':profile['id'],'effort':profile['reasoning_effort'],'speed':profile['speed']});recorder.flush(force=True)
        try:
            with execution.activate(recorder),recorder.signals():
                jobs.validate(job)
                if resume.get('mode')=='basis-final-closure':
                    import basis_closure_recovery
                    result=basis_closure_recovery.run(job,progress)
                elif job.get('workflow_protocol'):
                    import workflow_execution
                    result=workflow_execution.run(job,recorder,budgets,progress)
                elif job['track']=='audit-b':
                    import audit_b_continuation
                    result=audit_b_continuation.run(job['audit'],root/'audit-b',budget=budgets.serial)
                else:
                    if basis.mode(job)=='unconditional':basis.run(job,budgets.serial,progress)
                    authority=(nl0_work(job,recorder,budgets.serial,progress,audit_budget=budgets.audit) if job['track'] in {'nl0','full'} and resume.get('mode')!='native-proof-io' else
                               job['source_authority'])
                    selected_data=source_preparation.read_source(**authority)[0]
                    write(root/'source-selection.json',authority)
                    selected=selected_data[0]
                    if selected.get('source_warnings'):
                        import source_qualification
                        source_qualification.publish(root,selected_data)
                    result=({'status':'DRAFT-AUDIT-PASSED' if selected['current_standard_receipt_valid'] else 'DRAFT-AUDIT-CONDITIONAL',
                             'source':authority,'acceptance_scope':'NL0_AND_AUDIT_A_ONLY'}
                            if job['track']=='nl0' else translation_work(job,authority,budgets,progress))
                    if basis.mode(job)=='unconditional' and result.get('status')!='DIFFERENT_RESULT_DELIVERED':
                        import b2lean
                        progress(job['case'],'BASIS_FINAL_CLOSURE',workflow=result.get('directory',result.get('workflow')))
                        # The shared workflow report binds its final machine receipt.
                        selected_workflow=Path(result['audit_b']['receipt_path']).parent.parent
                        result=b2lean.finish(selected_workflow,root/'b2lean',
                            context=ir_context(job),intermediate=result)
        except execution.Cancelled as error:
            result={'status':'CANCELLED','task_outcome':'EXTERNAL_CANCELLED','error':str(error)}
        except execution.CaseDeadlineExceeded as error:
            result=recorder.deadline_result(error)
        except StageFailure as error:result=error.result
        except Exception as error:
            result={'status':'EXECUTION_FAULT','error':type(error).__name__+': '+str(error),'traceback':traceback.format_exc(),
                'recoverability':'VERIFIED_SOFTWARE_REPAIR_REQUIRED',
                'checkpoint':{'phase':recorder.state.get('phase'),'artifacts':recorder.state.get('stage_artifacts',{}),
                    'preserve_completed_work':True,'restart_whole_workflow':False}}
        finally:
            if not case_outcomes.terminal(root,result):
                from fault_control import Gate,outcome_error
                saved=dict(result)
                try:
                    with execution.activate(recorder),recorder.signals():
                        Gate(root/'logs/controller-errors',recorder=recorder,task='case-controller',
                             stage=recorder.state.get('phase')).pause(
                            outcome_error(saved),resumable=False,
                            checkpoint={'preserve_completed_work':True,'restart_whole_workflow':False,
                                **({'source_issue_notices':saved.get('checkpoint',{}).get('source_issue_notices',[])}
                                   if saved.get('status')=='PROOF_REVIEW_REQUIRED' else {})})
                except execution.Cancelled:
                    result={'status':'CANCELLED','task_outcome':'EXTERNAL_CANCELLED','retained_error':saved}
            passed=result.get('status') in case_outcomes.PASSED
            conditional=result.get('status') in case_outcomes.CONDITIONAL
            accepted_with_warning=bool(result.get('audit_b',{}).get('freeze_deviation') and not result['audit_b'].get('source_conditional',True))
            result.update(elapsed_case_seconds=__import__('time').monotonic()-recorder.started,
                completion={'acceptance_target_satisfied':passed or accepted_with_warning,'accepted_with_warning':accepted_with_warning,'workflow_completed':passed or conditional,
                            'follow_up_required':not passed},time_budget_seconds=job['time_budget_seconds'])
            result['formalization_goal']=basis.mode(job)
            if basis.mode(job)=='unconditional':
                result['completion']['acceptance_target_satisfied']=bool(result.get('closure',{}).get('unconditional') and passed)
                result['completion']['follow_up_required']=not result['completion']['acceptance_target_satisfied']
            if (root/'warn.json').is_file():result['warnings']=json.loads((root/'warn.json').read_text())
            while True:
                try:
                    recorder.close(result.get('status','EXECUTION_FAULT'),outcome=result)
                    break
                except Exception as error:
                    from fault_control import Gate
                    try:
                        with execution.activate(recorder),recorder.signals():
                            Gate(root/'logs/finalization-errors',recorder=recorder,task='case-controller',
                                 stage='finalization').pause(error,resumable=True,
                                    checkpoint={'retry_scope':'idempotent authorized cleanup only','no_model_call':True})
                    except execution.Cancelled:
                        result.update(status='CANCELLED',task_outcome='EXTERNAL_CANCELLED',
                            completion={'acceptance_target_satisfied':False,'workflow_completed':False,'follow_up_required':True})
            result['usage']=recorder.state['usage']
            with recorder.signals():
                published=final_write(root/'case-result.json',{'job':bind(root/'job.json'),'result':result,
                    'concurrency':budgets.report()},recorder=recorder)
            if not published:
                result.update(status='CANCELLED',task_outcome='EXTERNAL_CANCELLED',
                    completion={'acceptance_target_satisfied':False,'workflow_completed':False,'follow_up_required':True})
                recorder.update(result={'status':'CANCELLED','outcome':result})
                try:recorder.flush(force=True)
                except OSError:pass  # The user explicitly stopped an unwritable final report.
        return result


def ir_context(job):
    return json.loads((basis.problem_inputs(job)/basis.CONTEXT).read_text())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--job',type=Path,required=True)
    args=parser.parse_args();result=execute(json.loads(args.job.read_text()))
    raise SystemExit(0 if result['completion']['workflow_completed'] else 1)
