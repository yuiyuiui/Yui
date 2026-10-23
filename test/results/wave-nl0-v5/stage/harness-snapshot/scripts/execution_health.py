"""Attribute observed transport/controller health separately from mathematical outcomes."""
import json
from pathlib import Path

from usage import events


def read_rows(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


def inspect(directory):
    root=Path(directory)
    requests=read_rows(root/'requests.jsonl')
    http=read_rows(root/'http.jsonl')
    faults=[]
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
