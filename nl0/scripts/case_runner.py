"""One owned, independent case lifecycle for an installed Yui skill."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import traceback

from controller_common import write, bind
import audit_a_campaign as a
import full_workflow as f
import jobs
import nl0_author
from clean_stage import ArtifactStage
from execution_health import StageFailure
import execution_state as execution
from runtime_config import use_profiles
import source_preparation
import source_refactor


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
    nl0_author.prepare(Path(job['root'])/'inputs',root,baseline=baseline,obligations=obligations)
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
        if source_key(source)==source_key(baseline):
            raise StageFailure('REPAIR_UNCHANGED','No source change after an actual failed audit; no repeated review is started')
    return source


def nl0_work(job, recorder, budget, progress, *, audit_budget=None):
    root=Path(job['root']);baseline=None;obligations=None;prior=[];revision=0;seen=set()
    restored=None
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
        audited=f.audit_source(job['case'],source,audit,budget,progress,problem=root/'inputs',reuse_from=prior,
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
    root=Path(job['root'])
    authority=source_refactor.run(authority,root/'nl0-to-lean/preparation',budgets.serial)
    source=Path(authority['graph']).parent;prior_interface=None;diagnostics=None;attempt=0
    while True:
        attempt+=1;directory=root/'nl0-to-lean'/f'{attempt:04d}'
        try:
            result=f.translate(job['case'],source,directory/'interface',directory/'workflow',budgets.serial,progress,
                proof_budget=budgets.proof,problem=root/'inputs',authority=authority,
                prior_interface=prior_interface,diagnostics=diagnostics)
            write(root/'audit-b'/f'{attempt:04d}.json',{'status':'AUDIT-B-PASSED' if result['status']=='WORKFLOW-PASSED' else 'AUDIT-B-CONDITIONAL',
                'review':bind(directory/'audit-b-review/review.json'),'workflow':str(directory/'workflow')})
            return result
        except StageFailure as error:
            report=directory/'audit-b-review/report.json'
            if error.result.get('phase')!='audit-b' or job['policy']=='first-pass' or not report.is_file():raise
            report_value=json.loads(report.read_text())
            if report_value.get('review_status')!='MATHEMATICAL_REVIEW_FAILED':raise
            diagnostics={'report':report_value,'actual_review':json.loads((directory/'audit-b-review/stage/accepted.json').read_text()),
                         'review_packet':json.loads((directory/'workflow/audit-b/review-packet.json').read_text())}
            prior_interface=directory/'interface/stage/accepted.json'
            if not prior_interface.is_file():raise
            write(root/'repairs'/f'audit-b-{attempt:04d}.json',{'diagnosis':bind(report),
                'route':'interface_and_affected_proofs','source_unchanged':True})


def execute(job, root=None):
    jobs.validate(job);root=Path(job['root'])
    if (root/'execution-status.json').exists():raise ValueError('Preserve this run; prepare a new explicit run')
    with use_profiles(job['profiles']):
        recorder=execution.Recorder(root,job['case'],a.concurrency.resolve(job['max_concurrency']),
            phase='nl0-authoring' if job['track'] in {'nl0','full'} else 'translation-preparation',
            time_budget_seconds=job['time_budget_seconds'])
        budgets=a.concurrency.CaseBudgets(job['max_concurrency'],execution=recorder);result={}
        def progress(case,phase,**extra):
            from runtime_config import model_profile
            profile=model_profile('audit-a' if phase.startswith(('NL0_','ACTUAL_AUDIT_A','SOURCE_AUDIT_A','AUDIT_A_')) else 'translation-preparation')
            recorder.check();recorder.update(phase=phase,stage_artifacts=extra,model_selection=profile,
                model={'id':profile['id'],'effort':profile['reasoning_effort'],'speed':profile['speed']});recorder.flush(force=True)
        try:
            with execution.activate(recorder),recorder.signals():
                jobs.validate(job)
                if job['track']=='audit-b':
                    import audit_b_continuation
                    result=audit_b_continuation.run(job['audit'],root/'audit-b',budget=budgets.serial)
                else:
                    authority=(nl0_work(job,recorder,budgets.serial,progress,audit_budget=budgets.audit) if job['track'] in {'nl0','full'} else
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
        except execution.Cancelled as error:
            result={'status':'CANCELLED','task_outcome':'EXTERNAL_CANCELLED','error':str(error)}
        except execution.CaseDeadlineExceeded as error:
            stages=[row['stage_result'] for row in recorder.state['tasks'].values() if row.get('stage_result')]
            fault=any(row.get('execution_health')=='FAULT' for row in stages)
            healthy=bool(stages) and all(row.get('execution_health')=='NO_RECORDED_FAULT'
                and row.get('identity_and_input_boundary_verified') for row in stages)
            result={'status':'UNFINISHED','stop_reason':'CASE_DEADLINE','error':str(error),
                'task_outcome':'UNFINISHED_WITH_EXECUTION_FAULT' if fault else 'MODEL_BUDGET_EXHAUSTED' if healthy else 'UNFINISHED_ATTRIBUTION_UNVERIFIED'}
        except StageFailure as error:result=error.result
        except Exception as error:
            result={'status':'EXECUTION_FAULT','error':type(error).__name__+': '+str(error),'traceback':traceback.format_exc(),
                'recoverability':'VERIFIED_SOFTWARE_REPAIR_REQUIRED',
                'checkpoint':{'phase':recorder.state.get('phase'),'artifacts':recorder.state.get('stage_artifacts',{}),
                    'preserve_completed_work':True,'restart_whole_workflow':False}}
        finally:
            passed=result.get('status') in {'DRAFT-AUDIT-PASSED','WORKFLOW-PASSED','AUDIT-B-PASSED'}
            conditional=result.get('status') in {'DRAFT-AUDIT-CONDITIONAL','WORKFLOW-CONDITIONAL','AUDIT-B-CONDITIONAL'}
            result.update(elapsed_case_seconds=__import__('time').monotonic()-recorder.started,
                completion={'acceptance_target_satisfied':passed,'workflow_completed':passed or conditional,
                            'follow_up_required':not passed},time_budget_seconds=job['time_budget_seconds'])
            if (root/'warn.json').is_file():result['warnings']=json.loads((root/'warn.json').read_text())
            recorder.close(result.get('status','EXECUTION_FAULT'),outcome=result);result['usage']=recorder.state['usage']
            write(root/'case-result.json',{'job':bind(root/'job.json'),'result':result,'concurrency':budgets.report()})
        return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--job',type=Path,required=True)
    args=parser.parse_args();result=execute(json.loads(args.job.read_text()))
    raise SystemExit(0 if result['completion']['workflow_completed'] else 1)
