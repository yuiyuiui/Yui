"""Child-process control for linked delivery tests; all judgments are synthetic."""
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import harness_support
from unittest.mock import patch
import audit_b_review
import case_runner
import fault_control
import full_workflow
import ir
import workflow as workflow_module
from final_acceptance_fixtures import qualified_artifact
from review_contract import ReviewContract


def run(job, workflow, mode):
    original_pause = fault_control.Gate.pause
    authority = workflow_module.bound(workflow)['authority']
    reviews=[];choices=[]

    def review(directory, *args, **kwargs):
        directory = Path(directory)
        reviews.append(directory)
        mechanical = ir.load(directory/'mechanical.json')
        packet = ir.load(directory/'inputs/review-packet.json')
        def row(locations):
            return {'verdict':'FAIL', 'notes':'SYNTHETIC located fidelity nonpass for controller regression.',
                    'locations':locations}
        if mode.startswith('incomplete') or mode=='recheck-then-deliver' and len(reviews)==1:
            required = ['/nodes/'+key for key in mechanical['required_review_locations']]
            required += ['/checks/'+key for key in audit_b_review.audit_b.REVIEW_CHECKS]
            contract = ReviewContract(directory/'review-work', {'nodes':{},'checks':{}}, required,
                                      lambda value:audit_b_review.validate(value, directory))
            key, locations = next(iter(mechanical['required_review_locations'].items()))
            contract.record('/nodes/'+key, 'assessed', row(locations))
            raw = contract.blocker({'verdict':'FAIL','explanation':'SYNTHETIC located actual-target defect.',
                                    'locations':locations})
            qualified_artifact(directory/'stage', raw)
            result = ir.load(directory/'stage/result.json')
            result.update(status='BLOCKED', task_outcome='MATHEMATICAL_REVIEW_FAILED', review_coverage='INCOMPLETE')
            ir.write(directory/'stage/result.json', result)
        else:
            raw = {'nodes':{key:row(locations) for key,locations in mechanical['required_review_locations'].items()},
                   'checks':{key:row(audit_b_review.review_materials.locations(packet))
                             for key in audit_b_review.audit_b.REVIEW_CHECKS}, 'findings':[]}
            qualified_artifact(directory/'stage', raw)

    def decide(gate, error, **kwargs):
        if kwargs.get('decisions'):
            gate.notify = lambda *_:{'status':'QUEUED', 'synthetic':True}
            def choose(_):
                action='recheck' if mode=='recheck-then-deliver' and not choices else 'deliver-actual'
                if mode=='incomplete-expired':gate.recorder.deadline=time.monotonic()-1
                choices.append(action)
                fault_control.final_decision(gate.root,gate.state['incident'],action)
            gate.wait = choose
            return original_pause(gate, error, **kwargs)
        # A software regression must fail promptly rather than wait forever.
        raise AssertionError('Unexpected controller pause: '+repr(error))

    def translate(case, source, interface, destination, budget, progress, **kwargs):
        result=full_workflow.finish_translation(case, workflow, budget, progress)
        # Exercise the actual case progress callback used at from_interface's
        # final handoff, including delivery after time spent awaiting the user.
        progress(case,result['status'],directory=str(workflow))
        return result

    with patch.object(case_runner, 'nl0_work', return_value=authority), \
         patch.object(case_runner.source_refactor, 'run', return_value=authority), \
         patch.object(full_workflow, 'translate', side_effect=translate), \
         patch.object(audit_b_review, 'run', side_effect=review), \
         patch.object(fault_control.Gate, 'pause', decide):
        return case_runner.execute(job)


if __name__ == '__main__':
    import json
    result = run(json.loads(Path(sys.argv[1]).read_text()), Path(sys.argv[2]), sys.argv[3])
    raise SystemExit(0 if result['completion']['acceptance_target_satisfied'] else 1)
