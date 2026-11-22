"""Case outcomes shared by the case owner and its batch."""
import json
from pathlib import Path
import re

from controller_common import bind

PASSED = {'DRAFT-AUDIT-PASSED', 'WORKFLOW-PASSED', 'AUDIT-B-PASSED'}
CONDITIONAL = {'DRAFT-AUDIT-CONDITIONAL', 'WORKFLOW-CONDITIONAL', 'AUDIT-B-CONDITIONAL'}


def saved_pause(root, record):
    """Read an exited-case pause from its bound incident, independently of acceptance."""
    try:
        root=Path(root).resolve()
        result=record['result']
        if result['status'] not in {'PAUSED_ERROR','CANCELLED'} or 'pause_incident' not in result:
            return None
        ref=result['pause_incident']
        path=Path(ref['path'])
        logs=root/'logs/controller-errors'
        if path.parent!=logs/'error-incidents' or not re.fullmatch(r'[a-f0-9]{32}',path.stem) or path.suffix!='.json':
            return None
        if bind(path)!=ref or record['job']!=bind(root/'job.json'):
            return None
        event=json.loads(path.read_text())
        if (event['state']=='PAUSED_ERROR' and event['resumable'] is False and event['wait_for_control'] is False
                and event['incident']==path.stem and event['root']==str(root) and event['logs']==str(logs)
                and event['job_binding']==record['job']):
            return event
    except (OSError, ValueError, KeyError, TypeError):
        return None


def basis_checkpoint(artifact, review, *, scoped):
    from basis_graph import residual_scope
    data=json.loads(Path(artifact).read_bytes())
    residual=sorted(r['id'] for r in data['dependencies'] if r['category']==4)
    checkpoint={'basis':bind(artifact),'residual_class4':residual,'semantic_review':review}
    if scoped:checkpoint['approved_scope']=residual_scope(data)
    return checkpoint


def verify_basis_decision(root, receipt, action):
    """Recheck a completed operator action after the decision-owner process exits."""
    root = Path(root).resolve()
    path = Path(receipt['path']).resolve()
    relative = path.relative_to(root).as_posix()
    match = re.fullmatch(r'2basis/([0-9]{4,})/(?:plans/[a-f0-9]{64}/)?decision/error-incidents/([a-f0-9]{32})\.json', relative)
    if not match or bind(path) != receipt:
        raise ValueError('Changed or foreign basis decision receipt')
    decision = path.parent.parent
    event = json.loads(path.read_text())
    control = json.loads((decision/'error-control'/path.name).read_text())
    artifact = decision.parent/'stage/accepted.json'
    checkpoint=basis_checkpoint(artifact,bind(decision.parent/'review/report.json'),
                                scoped=event.get('error',{}).get('scope_version')=='yui-residual-scope-1')
    if (event['state'] != 'USER_DECIDED' or event['stage'] != 'basis-decision' or
            event['root'] != str(root) or event['logs'] != str(decision) or
            event['job_binding'] != bind(root/'job.json') or event['incident'] != match[2] or
            control != event['control'] or control['incident'] != match[2] or control['action'] != action or
            not checkpoint['residual_class4'] or event['checkpoint'] != checkpoint):
        raise ValueError('Invalid basis decision authority')
    return event


def verify_dependency_exhaustion(root, receipt):
    from lean_imports import DEPENDENCY_LIMIT,UNFINISHED,dependency_key
    root=Path(root).resolve();path=Path(receipt['path'])
    if (path.resolve()!=path or not path.is_relative_to(root)
            or not re.fullmatch(r'2basis/[0-9]{4,}/stage/lean-dependency-exhausted\.json',path.relative_to(root).as_posix())
            or bind(path)!=receipt):
        raise ValueError('Changed or foreign Lean dependency outcome')
    result=json.loads(path.read_bytes()); attempts=result['attempts']
    if (result['version']!=UNFINISHED or result['job']!=bind(root/'job.json') or len(attempts)!=DEPENDENCY_LIMIT
            or len({item['path'] for item in attempts})!=DEPENDENCY_LIMIT):
        raise ValueError('Incomplete Lean dependency attempt record')
    for item in attempts:
        attempt=Path(item['path'])
        if (attempt.resolve()!=attempt or attempt.parent.parent!=path.parent/'imported-lean' or attempt.name!='result.json'
                or not re.fullmatch(r'request-[0-9a-f]{32}',attempt.parent.name) or bind(attempt)!=item):
            raise ValueError('Changed or foreign Lean dependency attempt')
        last=json.loads(attempt.read_bytes())
        if dependency_key(last)!=result['dependency']:raise ValueError('Changed Lean dependency identity')
    if last['diagnostics']!=result['diagnostics']:raise ValueError('Changed Lean dependency diagnostic')
    return result


def terminal(root, outcome):
    if not isinstance(outcome,dict) or not isinstance(outcome.get('status'),str):return False
    status = outcome['status']
    if status=='UNFINISHED_LEAN_DEPENDENCY':
        try:verify_dependency_exhaustion(root,outcome['dependency_exhaustion'])
        except (KeyError,TypeError,ValueError,OSError):return False
        return True
    if status == 'STOPPED_BY_USER':
        try:
            verify_basis_decision(root, outcome['user_decision'], 'stop')
        except (KeyError, TypeError, ValueError, OSError):
            return False
        return True
    if status in PASSED or status in CONDITIONAL or status=='DIFFERENT_RESULT_DELIVERED':
        try:
            root=Path(root)
            job=json.loads((root/'job.json').read_text()) if (root/'job.json').is_file() else {}
            recovery=job.get('resume',{}).get('mode')=='basis-final-closure'
            if job.get('workflow_protocol') or recovery:
                import delivery
                if outcome.get('delivery')!=str(root/'delivery'):return False
                if job.get('workflow_protocol'):delivery.cleanup_anchor(root)
                else:delivery.finalization_anchor(root)
        except (OSError,ValueError,KeyError,TypeError):return False
        return True
    return status=='CANCELLED'
