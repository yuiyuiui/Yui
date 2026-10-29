"""Attribute observed transport/controller health separately from mathematical outcomes."""
import json
import re
from pathlib import Path

from usage import events, json_rows
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


def qualification(result):
    """Identity/input/health qualification is separate from usage completeness."""
    exposure=result.get('exposure', {})
    configured=json.loads((Path(__file__).resolve().parents[2]/'config.json').read_text())['model']['id']
    expected_model=result.get('model',configured)
    identity=(exposure.get('status')=='TRANSMITTED-EXPOSURE-CHECK-PASSED'
              and exposure.get('actual_model_ids')==[expected_model]
              and exposure.get('standard_tier_verified') is True)
    health=result.get('execution_health','UNVERIFIED')
    return {'execution_qualified':bool(identity and health=='NO_RECORDED_FAULT'),
            'identity_and_input_boundary_verified':bool(identity), 'execution_health':health,
            'measurement_complete':bool(result.get('usage',{}).get('complete')),
            'measurement_valid':bool(identity and health=='NO_RECORDED_FAULT'
                                     and result.get('usage',{}).get('complete'))}


def known_transport_recovery(result):
    """A real submitted record survived a disclosed transport-only interruption."""
    if (result.get('status') not in {'ACCEPTED','BLOCKED'} or result.get('execution_health')!='FAULT'
            or result.get('isolation_violation') or result.get('execution_fault')
            or result.get('temporary_workspace_removed') is not True):return False
    transport=result.get('transport_health',{});faults=transport.get('faults',[])
    if transport.get('status')!='FAULT' or not faults:return False
    if any(f.get('kind') not in {'RELAY_ERROR','HTTP_ERROR','PROVIDER_ERROR'} for f in faults):return False
    numbers={f.get('request_number') for f in faults if type(f.get('request_number')) is int}
    return all(u.get('kind')=='HTTP_EVIDENCE_INCOMPLETE'
               and set(u.get('missing_requests',[]))<=numbers
               for u in transport.get('uncertainty',[]))


def record_qualification(result,*,allow_blocked=False):
    """Submitted evidence eligibility, never a mathematical or healthy-time PASS."""
    checked=qualification(result);recovered=known_transport_recovery(result)
    context=bool(checked['identity_and_input_boundary_verified']
        and not result.get('isolation_violation') and not result.get('execution_fault')
        and result.get('temporary_workspace_removed') is not False
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
    requests={row['request_number'] for row in read_rows(root/'requests.jsonl')}
    http=list(read_rows(root/'http.jsonl'))
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
    for row in read_rows(root/'model-output-events.jsonl'):
        if row.get('event')=='PROVIDER_TERMINAL_WAIT_EXCEEDED':
            uncertain.append({'kind':'PROVIDER_TERMINAL_WAIT_EXCEEDED',
                'request_number':row.get('request_number'),'call_ids':row.get('call_ids'),
                'details':'Recorded post-tool nonterminal wait; cause UNVERIFIED, not a mathematical failure.',
                'idle_seconds':row.get('idle_seconds')})
    for path in root.glob('response-*.sse'):
        for event in events(path):
            response=event.get('response') or {}
            error=response.get('error') or event.get('error')
            if event.get('type')=='error' and not error:
                error={'code':event.get('code'),'message':event.get('message')}
            if error:
                code=error.get('code') if isinstance(error,dict) else None
                match=re.fullmatch(r'response-(\d+)\.sse',path.name)
                row={'kind':'PROVIDER_ERROR','source':path.name,'code':code,'details':error,
                     'request_number':int(match.group(1)) if match else None}
                if remote_retry.classify(error):
                    faults.append(row)
                else:
                    uncertain.append(row)
    known={r.get('request_number') for r in http if r.get('path','').rstrip('/')=='/responses'}
    missing=sorted(requests-known)
    if not requests or missing:
        uncertain.append({'kind':'HTTP_EVIDENCE_INCOMPLETE','missing_requests':missing})
    status='FAULT' if faults else 'UNVERIFIED' if uncertain else 'NO_RECORDED_FAULT'
    return {'status':status,'faults':faults,'uncertainty':uncertain,
            'scope':'Recorded HTTP/provider health and delivered-tool protocol waits; rejected mathematical/tool candidates are ordinary feedback.'}
