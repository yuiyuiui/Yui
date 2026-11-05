"""Terminal case classification shared by the case owner and its batch."""
import json
from pathlib import Path
import re

from controller_common import bind

PASSED = {'DRAFT-AUDIT-PASSED', 'WORKFLOW-PASSED', 'AUDIT-B-PASSED'}
CONDITIONAL = {'DRAFT-AUDIT-CONDITIONAL', 'WORKFLOW-CONDITIONAL', 'AUDIT-B-CONDITIONAL'}


def verify_basis_decision(root, receipt, action):
    """Recheck a completed operator action after the decision-owner process exits."""
    root = Path(root).resolve()
    path = Path(receipt['path']).resolve()
    relative = path.relative_to(root).as_posix()
    match = re.fullmatch(r'2basis/([0-9]{4,})/decision/error-incidents/([a-f0-9]{32})\.json', relative)
    if not match or bind(path) != receipt:
        raise ValueError('Changed or foreign basis decision receipt')
    decision = path.parent.parent
    event = json.loads(path.read_text())
    control = json.loads((decision/'error-control'/path.name).read_text())
    artifact = decision.parent/'stage/accepted.json'
    residual = sorted(row['id'] for row in json.loads(artifact.read_text())['dependencies'] if row['category'] == 4)
    if (event['state'] != 'USER_DECIDED' or event['stage'] != 'basis-decision' or
            event['root'] != str(root) or event['logs'] != str(decision) or
            event['job_binding'] != bind(root/'job.json') or event['incident'] != match[2] or
            control != event['control'] or control['incident'] != match[2] or control['action'] != action or
            not residual or event['checkpoint'] != {'basis':bind(artifact),'residual_class4':residual,
                                                    'semantic_review':bind(decision.parent/'review/report.json')}):
        raise ValueError('Invalid basis decision authority')
    return event


def terminal(root, outcome):
    if not isinstance(outcome,dict) or not isinstance(outcome.get('status'),str):return False
    status = outcome['status']
    if status == 'STOPPED_BY_USER':
        try:
            verify_basis_decision(root, outcome['user_decision'], 'stop')
        except (KeyError, TypeError, ValueError, OSError):
            return False
        return True
    return status in PASSED or status in CONDITIONAL or status in {'CANCELLED', 'DIFFERENT_RESULT_DELIVERED'}
