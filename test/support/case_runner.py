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
    recorder=execution.Recorder(root,job['case'],a.concurrency.resolve(job.get('max_concurrency','auto')),phase='preparation')
    budgets=a.concurrency.CaseBudgets(job.get('max_concurrency','auto'),execution=recorder)
    budget=budgets.serial
    result={}
    def progress(case,phase,**extra):
        recorder.check();recorder.update(phase=phase,stage_artifacts=extra);recorder.flush(force=True)
    try:
        with execution.activate(recorder),recorder.signals():
            if job['kind']=='nl0':
                out=a.ROOT/'test/results'/job['run'];progress(job['case'],'NL0_AUTHORING',directory=str(out))
                stage=ArtifactStage(out/'stage',(out/'prompt.txt').read_text(),phase='nl0-authoring',kind='nl0',case_id=job['case'],
                    inputs=out/'inputs.json',timeout=1800,budget=budget)
                stage.execute();recorder.check();f.accepted(out);source=out/'stage/case'
            else:source=(a.ROOT/'test/results'/job['source']).resolve()
            if job['kind'] not in {'translate','checked_interface','submitted_interface'}:
                f.audit_source(job['case'],source,job['audit'],budget,progress,
                    reuse_from=[a.ROOT/'test/results'/name for name in job.get('reuse_audits',[])])
            result=(f.from_interface(job['case'],source,job['interface'],job['workflow'],budget,progress,
                    candidate=job.get('candidate'),review_name=job.get('review'),
                    proof_budget=budgets.proof)
                if job['kind'] in {'checked_interface','submitted_interface'} else f.translate(job['case'],source,job['interface'],job['workflow'],budget,progress,
                    proof_budget=budgets.proof))
    except execution.Cancelled as error:
        result={'status':'CANCELLED','task_outcome':'EXTERNAL_CANCELLED','stop_reason':'EXTERNAL_CANCEL','error':str(error)}
    except StageFailure as error:
        result=error.result
    except Exception as error:
        result={'status':'CANCELLED' if recorder.cancelled() else 'ARTIFACT_OR_CONTRACT_REJECTED' if isinstance(error,ValueError) else 'EXECUTION_FAULT',
                'error':type(error).__name__+': '+str(error),'traceback':traceback.format_exc()}
    finally:
        recorder.close(result.get('status','EXECUTION_FAULT'),outcome=result)
        a.write(Path(root)/'case-result.json',{'job':job,'result':result,'concurrency':budgets.report()})
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();execute(json.loads(args.job.read_text()),args.out)
