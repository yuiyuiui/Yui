"""One case-owned clean workflow, invoked by the finite test batch controller."""
from pathlib import Path
import argparse
import traceback
import json

import audit_a_campaign as a
import full_workflow as f
from clean_stage import ArtifactStage
import execution_state as execution
from execution_health import StageFailure


def execute(job,root):
    is_translation=job['kind'] in {'translate','checked_interface','submitted_interface'}
    seconds=job.get('time_budget_seconds',json.loads((a.CORE/'config.json').read_text())['timeouts']['case_seconds'] if is_translation else None)
    recorder=execution.Recorder(root,job['case'],a.concurrency.resolve(job.get('max_concurrency','auto')),phase='translation-preparation' if is_translation else 'preparation',time_budget_seconds=seconds)
    budgets=a.concurrency.CaseBudgets(job.get('max_concurrency','auto'),execution=recorder)
    budget=budgets.serial
    result={};author_artifact=None
    def progress(case,phase,**extra):
        recorder.check();recorder.update(phase=phase,stage_artifacts=extra)
        if phase.startswith(('INTERFACE','FROZEN_LEAN','AUDIT_B','WORKFLOW')):
            profile=__import__('runtime_config').model_profile('translation-preparation')
            recorder.update(model={'id':profile['id'],'effort':profile['reasoning_effort'],'speed':profile['speed']},model_selection=profile)
        recorder.flush(force=True)
    try:
        with execution.activate(recorder),recorder.signals():
            if job['kind']=='nl0':
                out=a.ROOT/'test/results'/job['run'];progress(job['case'],'NL0_AUTHORING',directory=str(out))
                stage=ArtifactStage(out/'stage',(out/'prompt.txt').read_text(),phase='nl0-authoring',kind='nl0',case_id=job['case'],
                    inputs=out/'inputs.json',timeout=1800,budget=budget)
                stage.execute();recorder.check();author_artifact=f.nl0_artifact_for_audit(out)
                a.write(Path(root)/'author-artifact-eligibility.json',author_artifact)
                source=out/'stage/case'
            else:source=(a.ROOT/'test/results'/job['source']).resolve()
            if job['kind'] not in {'translate','checked_interface','submitted_interface'}:
                audited=f.audit_source(job['case'],source,job['audit'],budget,progress,
                    reuse_from=[a.ROOT/'test/results'/name for name in job.get('reuse_audits',[])],
                    controls=(a.ROOT/'test/results'/job['audit_controls']/'behavioral-summary.json') if job.get('audit_controls') else None)
                if job.get('stop_after')=='audit_a':
                    result={'status':'DRAFT-AUDIT-PASSED','acceptance_scope':'NL0_AND_AUDIT_A_ONLY',
                            'source':str(source),'audit':str(a.ROOT/'test/results'/job['audit']),
                            'full_acceptance':audited['full_acceptance']}
                    return result
            result=(f.from_interface(job['case'],source,job['interface'],job['workflow'],budget,progress,
                    candidate=job.get('candidate'),review_name=job.get('review'),
                    proof_budget=budgets.proof)
                if job['kind'] in {'checked_interface','submitted_interface'} else f.translate(job['case'],source,job['interface'],job['workflow'],budget,progress,
                    proof_budget=budgets.proof))
    except execution.Cancelled as error:
        result={'status':'CANCELLED','task_outcome':'EXTERNAL_CANCELLED','stop_reason':'EXTERNAL_CANCEL','error':str(error)}
    except execution.CaseDeadlineExceeded as error:
        stages=[t['stage_result'] for t in recorder.state['tasks'].values() if t.get('stage_result')]
        fault=any(t.get('execution_health')=='FAULT' for t in stages)
        unknown=any(t.get('execution_health') not in {'FAULT','NO_RECORDED_FAULT'} for t in stages)
        outcome='UNFINISHED_WITH_EXECUTION_FAULT' if fault else 'UNFINISHED_ATTRIBUTION_UNVERIFIED' if unknown else 'MODEL_BUDGET_EXHAUSTED'
        result={'status':'UNFINISHED','task_outcome':outcome,'stop_reason':'CASE_DEADLINE','error':str(error),
                'execution_health':'FAULT' if fault else 'UNVERIFIED' if unknown else 'NO_RECORDED_FAULT'}
    except StageFailure as error:
        result=error.result
    except Exception as error:
        result={'status':'CANCELLED' if recorder.cancelled() else 'ARTIFACT_OR_CONTRACT_REJECTED' if isinstance(error,ValueError) else 'EXECUTION_FAULT',
                'error':type(error).__name__+': '+str(error),'traceback':traceback.format_exc()}
    finally:
        result['time_budget_seconds']=seconds
        result['elapsed_case_seconds']=__import__('time').monotonic()-recorder.started
        if author_artifact is not None:result['author_artifact']=author_artifact
        target='AUDIT_A_PASS' if job.get('stop_after')=='audit_a' else 'AUDIT_B_PASS'
        passed=result.get('status')==('DRAFT-AUDIT-PASSED' if target=='AUDIT_A_PASS' else 'WORKFLOW-PASSED')
        result['completion']={'acceptance_target':target,'acceptance_target_satisfied':passed,
            'logical_worker':'NL0 worker' if target=='AUDIT_A_PASS' else 'translation workflow',
            'case_state':'ACCEPTED' if passed else 'INCOMPLETE',
            'follow_up_required':not passed,
            'scope':'Executor exit does not imply acceptance; follow-up follows the authorized outer run policy.'}
        recorder.close(result.get('status','EXECUTION_FAULT'),outcome=result)
        a.write(Path(root)/'case-result.json',{'job':job,'result':result,'concurrency':budgets.report()})
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();execute(json.loads(args.job.read_text()),args.out)
