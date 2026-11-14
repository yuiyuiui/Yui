"""Attribute observed transport/controller health separately from mathematical outcomes."""
import json
import re
from pathlib import Path

from usage import json_rows
import remote_retry


class StageFailure(ValueError):
    """Located workflow outcome; never infer a false theorem from a runtime stop."""
    def __init__(self, status, message, *, phase=None, evidence=None, details=None):
        super().__init__(message)
        self.result = {'status':status, 'phase':phase, 'error':message,
                       'evidence':str(evidence) if evidence else None, **(details or {})}


def review_outcome(verdicts):
    verdicts=list(verdicts)
    return ('MATHEMATICAL_REVIEW_FAILED' if 'FAIL' in verdicts else
            'REVIEW_UNVERIFIED' if 'UNVERIFIED' in verdicts else
            'REVIEW_PASSED' if verdicts and all(v=='PASS' for v in verdicts) else 'REVIEW_INCOMPLETE')


def budget_outcome(stages):
    """A deadline and evidence qualification are independent observations."""
    stages=list(stages)
    if any(row.get('execution_health')=='FAULT' or row.get('execution_fault') for row in stages):
        return 'UNFINISHED_WITH_EXECUTION_FAULT'
    if stages and all(row.get('execution_health')=='NO_RECORDED_FAULT'
                      and row.get('identity_and_input_boundary_verified') is True for row in stages):
        return 'MODEL_BUDGET_EXHAUSTED'
    return 'UNFINISHED_ATTRIBUTION_UNVERIFIED'


def qualification(result):
    """Identity/input/health qualification is separate from usage completeness."""
    exposure=result.get('exposure', {})
    configured=json.loads((Path(__file__).resolve().parents[2]/'config.json').read_text())['model']['id']
    expected_model=result.get('model',configured)
    native=(exposure.get('status')=='NATIVE-CODEX-CONTEXT-CHECK-PASSED'
            and exposure.get('configured_model')==expected_model and not exposure.get('errors'))
    identity=native or (exposure.get('status')=='TRANSMITTED-EXPOSURE-CHECK-PASSED'
              and exposure.get('actual_model_ids')==[expected_model]
              and exposure.get('standard_tier_verified') is True)
    health=result.get('execution_health','UNVERIFIED')
    return {'execution_qualified':bool(identity and health=='NO_RECORDED_FAULT'),
            'identity_and_input_boundary_verified':bool(identity), 'execution_health':health,
            'measurement_complete':bool(result.get('usage',{}).get('complete')),
            'measurement_valid':bool(identity and health=='NO_RECORDED_FAULT'
                                     and result.get('usage',{}).get('complete'))}


def known_transport_recovery(result, *, archived=None):
    """A real submitted record survived a disclosed transport-only interruption."""
    if (result.get('status') not in {'ACCEPTED','BLOCKED'} or result.get('execution_health')!='FAULT'
            or result.get('isolation_violation') or result.get('execution_fault')
            or type(result.get('temporary_workspace_removed')) is not bool
            or not __import__('run_resources').safe_stage_workspace(result,archived=archived)):return False
    transport=result.get('transport_health',{});faults=transport.get('faults',[])
    if transport.get('status')!='FAULT' or not faults:return False
    numbers={f.get('request_number') for f in faults if type(f.get('request_number')) is int}
    def explicitly_resumed(category=None):
        import hashlib
        for row in result.get('error_pauses',[]):
            try:
                path=Path(row['path']) if archived is None else archived[0]/(row['sha256']+'.json')
                raw=path.read_bytes();value=json.loads(raw)
                if (hashlib.sha256(raw).hexdigest()==row['sha256'] and value.get('state')=='RESUMED'
                        and value.get('control',{}).get('incident')==value.get('incident')
                        and value.get('control',{}).get('action')=='resume'
                        and value.get('fault',{}).get('category') in {'model_auth','model_balance','model_quota','model_request_rejected'}
                        and (category is None or value['fault']['category']==category)):
                    return True
            except (OSError,ValueError,KeyError):continue
        return False
    if result.get('transport')=='native-codex-stdio-v1':
        for row in faults:
            if row.get('kind')!='NATIVE_PROVIDER_ERROR':return False
            diagnosis=remote_retry.diagnose(row.get('details'))
            if not diagnosis['retryable'] and not explicitly_resumed(diagnosis['category']):return False
        return not transport.get('uncertainty')
    if any(f.get('kind') not in {'RELAY_ERROR','HTTP_ERROR','PROVIDER_ERROR'} for f in faults):return False
    return all((u.get('kind')=='HTTP_EVIDENCE_INCOMPLETE'
                and set(u.get('missing_requests',[]))<=numbers)
               or (u.get('kind')=='PROVIDER_ERROR' and explicitly_resumed()
                   and remote_retry.diagnose(u.get('details'))['category'] in
                   {'model_auth','model_balance','model_quota','model_request_rejected'})
               for u in transport.get('uncertainty',[]))


def record_qualification(result,*,allow_blocked=False,archived=None):
    """Submitted evidence eligibility, never a mathematical or healthy-time PASS."""
    checked=qualification(result);recovered=known_transport_recovery(result,archived=archived)
    context=bool(checked['identity_and_input_boundary_verified']
        and not result.get('isolation_violation') and not result.get('execution_fault')
        and __import__('run_resources').safe_stage_workspace(result,archived=archived)
        and (checked['execution_health']=='NO_RECORDED_FAULT' or recovered))
    submitted=result.get('status') in ({'ACCEPTED','BLOCKED'} if allow_blocked else {'ACCEPTED'})
    return {**checked,'record_context_qualified':context,
        'submitted_record_qualified':bool(context and submitted),'recovered_transport':recovered,
        'record_scope':'Execution evidence only. Callers still validate exact artifact/coverage and actual judgments; a blocker cannot grant full acceptance.'}


def require_review_execution(result, path, *, phase=None):
    """Missing accounting preserves a qualified judgment, not a benchmark pass."""
    if result.get('status')=='CANCELLED':
        from execution_state import Cancelled
        raise Cancelled('Review cancelled: '+str(path))
    checked=record_qualification(result,allow_blocked=True)
    if not checked['record_context_qualified']:
        raise StageFailure('EXECUTION_UNQUALIFIED','Reviewer identity, input boundary or health is unqualified',
                           phase=phase,evidence=path,details=checked)
    if result.get('status')!='ACCEPTED':
        status=result.get('task_outcome') or ('REVIEW_INCOMPLETE' if result.get('status')!='BLOCKED' else 'MATHEMATICAL_REVIEW_FAILED')
        raise StageFailure(status,'Review did not deliver a complete accepted record',
                           phase=phase,evidence=path,details=checked)
    return checked


def read_rows(path):
    if path.exists():yield from json_rows(path)


def inspect(directory):
    root=Path(directory)
    if (root/'native-client.json').is_file():
        faults=[{'kind':'NATIVE_PROVIDER_ERROR','details':row.get('error'),'native_will_retry':row.get('native_will_retry',False)} for row in read_rows(root/'native-errors.jsonl')]
        faults.extend({'kind':'CARRIER_READER_ERROR','details':row.get('message')} for row in read_rows(root/'carrier-reader-errors.jsonl'))
        return {'status':'FAULT' if faults else 'NO_RECORDED_FAULT','faults':faults,'uncertainty':[],
            'scope':'Native Codex error and stdio-reader events; HTTP transport and actual service tier are not intercepted.'}
    return {'status':'UNVERIFIED','faults':[],
            'uncertainty':[{'kind':'NATIVE_RECORD_MISSING'}],
            'scope':'A current native-client record is required for execution health.'}
