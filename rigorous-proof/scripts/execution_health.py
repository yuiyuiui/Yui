"""Attribute observed transport/controller health separately from mathematical outcomes."""
import json
from pathlib import Path

from usage import events


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


def qualification(result):
    """Identity/input/health qualification is separate from usage completeness."""
    exposure=result.get('exposure', {})
    identity=(exposure.get('status')=='TRANSMITTED-EXPOSURE-CHECK-PASSED'
              and exposure.get('actual_model_ids')==['gpt-6-luna']
              and exposure.get('standard_tier_verified') is True)
    health=result.get('execution_health','UNVERIFIED')
    return {'execution_qualified':bool(identity and health=='NO_RECORDED_FAULT'),
            'identity_and_input_boundary_verified':bool(identity), 'execution_health':health,
            'measurement_complete':bool(result.get('usage',{}).get('complete')),
            'measurement_valid':bool(identity and health=='NO_RECORDED_FAULT'
                                     and result.get('usage',{}).get('complete'))}


def require_review_execution(result, path, *, phase=None):
    """Missing accounting preserves a qualified judgment, not a benchmark pass."""
    if result.get('status')=='CANCELLED':
        from execution_state import Cancelled
        raise Cancelled('Review cancelled: '+str(path))
    checked=qualification(result)
    if not checked['execution_qualified']:
        raise StageFailure('EXECUTION_UNQUALIFIED','Reviewer identity, input boundary or health is unqualified',
                           phase=phase,evidence=path,details=checked)
    if result.get('status')!='ACCEPTED':
        status=result.get('task_outcome') or ('REVIEW_INCOMPLETE' if result.get('status')!='BLOCKED' else 'MATHEMATICAL_REVIEW_FAILED')
        raise StageFailure(status,'Review did not deliver a complete accepted record',
                           phase=phase,evidence=path,details=checked)
    return checked


def read_rows(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


def inspect(directory):
    root=Path(directory)
    requests=read_rows(root/'requests.jsonl')
    http=read_rows(root/'http.jsonl')
    faults=[]
    for row in read_rows(root/'relay-errors.jsonl'):
        faults.append({'kind':'RELAY_ERROR','request_number':row.get('request_number'),
                       'details':row.get('error'),'at_utc':row.get('timestamp_utc')})
    for row in read_rows(root/'tools.jsonl'):
        if row.get('result',{}).get('infrastructure_error') is True:
            faults.append({'kind':'TOOL_SERVICE_ERROR','tool':row.get('tool'),
                           'details':row['result'].get('error')})
    for row in http:
        if isinstance(row.get('status'),int) and not 200<=row['status']<300:
            faults.append({'kind':'HTTP_ERROR','request_number':row.get('request_number'),'status':row['status']})
    uncertain=[]
    for path in root.glob('response-*.sse'):
        for event in events(path):
            response=event.get('response') or {}
            error=response.get('error') or event.get('error')
            if event.get('type')=='error' and not error:
                error={'code':event.get('code'),'message':event.get('message')}
            if error:
                code=error.get('code') if isinstance(error,dict) else None
                row={'kind':'PROVIDER_ERROR','source':path.name,'code':code,'details':error}
                if code in {'server_error','internal_error','rate_limit_exceeded','service_unavailable','timeout','request_timeout'}:
                    faults.append(row)
                else:
                    uncertain.append(row)
    known={r.get('request_number') for r in http if r.get('path','').rstrip('/')=='/responses'}
    missing=sorted({r['request_number'] for r in requests}-known)
    if not requests or missing:
        uncertain.append({'kind':'HTTP_EVIDENCE_INCOMPLETE','missing_requests':missing})
    status='FAULT' if faults else 'UNVERIFIED' if uncertain else 'NO_RECORDED_FAULT'
    return {'status':status,'faults':faults,'uncertainty':uncertain,
            'scope':'Recorded HTTP/provider health only; rejected mathematical/tool candidates are ordinary feedback.'}
