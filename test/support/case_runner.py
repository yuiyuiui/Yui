"""One case-owned clean workflow, invoked by the finite test batch controller."""
from pathlib import Path
import argparse
import traceback
import json

import audit_a_campaign as a
import full_workflow as f
from clean_stage import ArtifactStage
import execution_state as execution


def execute(job,root):
    recorder=execution.Recorder(root,job['case'],a.concurrency.resolve(job.get('max_concurrency','auto')),phase='preparation')
    budget=a.concurrency.Budget(recorder.state['concurrency'],execution=recorder)
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
            if job['kind'] not in {'translate','checked_interface'}:f.audit_source(job['case'],source,job['audit'],budget,progress)
            result=(f.from_interface(job['case'],source,job['interface'],job['workflow'],budget,progress,candidate=job['candidate'])
                if job['kind']=='checked_interface' else f.translate(job['case'],source,job['interface'],job['workflow'],budget,progress))
    except execution.Cancelled as error:
        result={'status':'CANCELLED','task_outcome':'EXTERNAL_CANCELLED','error':str(error)}
    except Exception as error:
        result={'status':'CANCELLED' if recorder.cancelled() else 'REPAIR_REQUIRED',
                'error':type(error).__name__+': '+str(error),'traceback':traceback.format_exc()}
    finally:
        recorder.close(result.get('status','EXECUTION_FAULT'))
        a.write(Path(root)/'case-result.json',{'job':job,'result':result,'concurrency':budget.report()})
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();execute(json.loads(args.job.read_text()),args.out)
