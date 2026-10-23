"""Independent readback of transmitted semantic requests and observed model/tier metadata."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from usage import events


def audit_stage(directory):
    directory = Path(directory)
    system = (directory/'system.txt').read_text()
    system = system[:-1] if system.endswith('\n') else system
    tools = json.loads((directory/'tools.json').read_text())
    expected = [{'type':'function','name':t['name'],'description':t['description'],
                 'parameters':t['inputSchema'],'strict':False} for t in tools]
    requests = [json.loads(x) for x in (directory/'requests.jsonl').read_text().splitlines() if x.strip()]
    errors, models, tiers, removals = [], set(), set(), 0
    allowed_fields = {'model','stream','input','instructions','tools','tool_choice','parallel_tool_calls',
                      'reasoning','include','store','text','prompt_cache_key','service_tier'}
    for row in requests:
        sent = row['sent_payload']
        number = row['request_number']
        checks = {'model':sent.get('model')=='gpt-6-luna',
                  'effort':sent.get('reasoning',{}).get('effort')=='high',
                  'standard_requested':sent.get('service_tier')=='default',
                  'exact_instructions':sent.get('instructions')==system,
                  'exact_tools':sent.get('tools')==expected,
                  'semantic_fields_only':set(sent)<=allowed_fields,
                  'no_server_state':not sent.get('store') and not sent.get('previous_response_id') and not sent.get('conversation'),
                  'no_foreign_instruction_roles':all(x.get('role') not in {'developer','system'} for x in sent.get('input',[]))}
        digest = hashlib.sha256(json.dumps(sent,ensure_ascii=False).encode()).hexdigest()
        checks['transmitted_body_binding'] = digest == row['sent_body_sha256']
        for check, passed in checks.items():
            if not passed:errors.append({'request':number,'check':check})
        removals += len(row.get('removed_items',[]))
    for path in directory.glob('response-*.sse'):
        for event in events(path):
            response = event.get('response') or {}
            if response.get('model'):
                models.add(response['model'])
            if event.get('type') in {'response.completed','response.failed','response.incomplete'} and response.get('service_tier'):
                tiers.add(response['service_tier'])
    if models-{'gpt-6-luna'}:errors.append({'check':'actual_model','observed':sorted(models)})
    if tiers-{'default','standard','auto'}:errors.append({'check':'actual_service_tier','observed':sorted(tiers)})
    result = {'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED' if requests and not errors else 'VALIDATION_FAILED',
              'requests_checked':len(requests),'errors':errors,'removed_foreign_items':removals,
              'actual_model_ids':sorted(models),'terminal_service_tiers':sorted(tiers),
              'standard_tier_verified':bool(tiers) and tiers<= {'default','standard'},
              'allowed_tools':[t['name'] for t in tools],
              'scope':'Actual transmitted instruction/tool/model/tier readback; within-stage origin guards are enforced by the carrier. Provider internals are not independently observable.'}
    (directory/'exposure-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def audit_run(directory):
    directory = Path(directory)
    return [dict(path=str(p.parent.relative_to(directory)),**audit_stage(p.parent))
            for p in sorted(directory.rglob('requests.jsonl'))]
