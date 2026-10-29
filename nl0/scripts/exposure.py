"""Independent readback of transmitted semantic requests and observed model/tier metadata."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from acceptance import AcceptanceContract
import own_state

from usage import events, json_rows as request_rows


def audit_stage(directory):
    directory = Path(directory)
    system = (directory/'system.txt').read_text()
    system = system[:-1] if system.endswith('\n') else system
    tools = json.loads((directory/'tools.json').read_text())
    expected = [{'type':'function','name':t['name'],'description':t['description'],
                 'parameters':t['inputSchema'],'strict':False} for t in tools]
    requests = request_rows(directory/'requests.jsonl')
    requests_checked=0
    manifest_path=directory/'execution-manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    requested_model=manifest.get('model') or json.loads((Path(__file__).resolve().parents[2]/'config.json').read_text())['model']['id']
    verbosity=manifest.get('output_verbosity','low')
    if verbosity not in {'low','medium','high'}:raise ValueError('Unknown controller-selected output verbosity')
    errors, models, tiers, removals = [], set(), set(), 0
    shared=manifest.get('acceptance_contract')
    requires_shared=(manifest.get('arm')=='yui' and
        (manifest.get('artifact_contract')=='nl0' or manifest.get('phase','').startswith('audit-a')))
    tool_results={}
    if manifest.get('own_state_policy'):
        for line in (directory/'tools.jsonl').read_text().splitlines() if (directory/'tools.jsonl').exists() else []:
            item=json.loads(line)
            tool_results[(item.get('tool'),own_state.digest(item.get('result')))]=item.get('result')
    if requires_shared and not shared:
        errors.append({'check':'shared_acceptance_authority_missing'})
    if shared:
        try:
            # Historical runs retain their original source identity and snapshot.
            identity=shared.get('source')
            if identity not in {'nl0/references/audit-a.md','references/audit-a.md'}:
                raise ValueError('Unknown frozen authority source')
            source=directory/'harness-snapshot'/identity
            authority=AcceptanceContract(source.read_text(),source=identity)
            if authority.metadata()!=shared or authority.instructions() not in system:
                raise ValueError('Frozen authority or actually transmitted instructions differ')
        except (OSError,ValueError):
            errors.append({'check':'shared_acceptance_authority_binding'})
    allowed_fields = {'model','stream','input','instructions','tools','tool_choice','parallel_tool_calls',
                      'reasoning','include','store','text','prompt_cache_key','service_tier'}
    for row in requests:
        requests_checked+=1
        sent = row['sent_payload']
        number = row['request_number']
        checks = {'model':sent.get('model')==requested_model,
                  'effort':sent.get('reasoning',{}).get('effort')==manifest.get('effort','high'),
                  'standard_requested':sent.get('service_tier')=='default',
                  'exact_output_verbosity':sent.get('text')=={'verbosity':verbosity},
                  'exact_instructions':sent.get('instructions')==system,
                  'exact_tools':sent.get('tools')==expected,
                  'semantic_fields_only':set(sent)<=allowed_fields,
                  'no_server_state':not sent.get('store') and not sent.get('previous_response_id') and not sent.get('conversation'),
                  'no_foreign_instruction_roles':all(x.get('role') not in {'developer','system'} for x in sent.get('input',[]))}
        digest = hashlib.sha256(json.dumps(sent,ensure_ascii=False).encode()).hexdigest()
        checks['transmitted_body_binding'] = digest == row['sent_body_sha256']
        checkpoint=row.get('controller_checkpoint')
        if checkpoint is not None:
            data=checkpoint.get('data',{})
            keys={'kind','candidate_number','latest_check','last_structurally_valid_candidate','acceptance_scope','resume','remaining_stage_seconds'}
            modern=manifest.get('own_state_policy') is not None
            if modern:keys|={'checkpoint_version','own_state'}
            text='Current-stage machine checkpoint (no new mathematical premise): '+json.dumps(data,ensure_ascii=False,sort_keys=True)
            checkpoint_ok=(checkpoint.get('text')==text and checkpoint.get('text_sha256')==hashlib.sha256(text.encode()).hexdigest()
                and set(data)==keys
                and data.get('kind')=='YUI_OWN_STAGE_CHECKPOINT'
                and data.get('acceptance_scope')=='NL0_STRUCTURE_ONLY_NOT_AUDIT_A'
                and data.get('resume')=='Use read_draft with this exact own-stage candidate and a narrow JSON pointer. Preserve its edits with base_candidate. A passed structural candidate still needs actual Audit A; submit it only when your drafting is complete.'
                and any(i.get('role')=='user' and i.get('content')==[{'type':'input_text','text':text}] for i in sent['input']))
            records={}
            for source in checkpoint.get('sources',[]):
                path=(directory/source.get('path','')).resolve()
                checkpoint_ok=checkpoint_ok and path.is_relative_to(directory.resolve()) and path.is_file()
                allowed=r'case/(candidate|check-result)-[0-9]{4}\.json'
                if modern:allowed+=r'|case/own-state-[a-f0-9]{64}\.json|'+own_state.SOURCE_PATH_PATTERN
                checkpoint_ok=checkpoint_ok and bool(re.fullmatch(allowed,source.get('path','')))
                if path.is_file() and path.is_relative_to(directory.resolve()):
                    checkpoint_ok=checkpoint_ok and hashlib.sha256(path.read_bytes()).hexdigest()==source.get('sha256')
                    records[source['path']]=json.loads(path.read_text())
            number=data.get('candidate_number')
            if type(number) is not int or number<1:checkpoint_ok=False
            else:
                checkpoint_ok=checkpoint_ok and f'case/candidate-{number:04d}.json' in records
                checkpoint_ok=checkpoint_ok and records.get(f'case/check-result-{number:04d}.json')==data.get('latest_check')
                last=data.get('last_structurally_valid_candidate')
                if last is not None:
                    checkpoint_ok=checkpoint_ok and type(last) is int and last<=number
                    if type(last) is int:
                        checkpoint_ok=checkpoint_ok and records.get(f'case/check-result-{last:04d}.json',{}).get('status')=='STRUCTURE_PASSED'
            if modern:
                try:checkpoint_ok=checkpoint_ok and own_state.verify(directory,data,records,tool_results,manifest)
                except (ValueError,KeyError,TypeError,OSError):checkpoint_ok=False
            checks['own_stage_checkpoint_binding']=bool(checkpoint_ok)
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
    if models-{requested_model}:errors.append({'check':'actual_model','observed':sorted(models)})
    if tiers-{'default','standard','auto'}:errors.append({'check':'actual_service_tier','observed':sorted(tiers)})
    result = {'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED' if requests_checked and not errors else 'VALIDATION_FAILED',
              'requests_checked':requests_checked,'errors':errors,'removed_foreign_items':removals,
              'actual_model_ids':sorted(models),'terminal_service_tiers':sorted(tiers),
              'standard_tier_verified':bool(tiers) and tiers<= {'default','standard'},
              'output_verbosity_requested':verbosity,
              'acceptance_contract':shared,
              'allowed_tools':[t['name'] for t in tools],
              'scope':'Actual transmitted instruction/tool/model/tier readback; within-stage origin guards are enforced by the carrier. Provider internals are not independently observable.'}
    (directory/'exposure-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def audit_run(directory):
    directory = Path(directory)
    return [dict(path=str(p.parent.relative_to(directory)),**audit_stage(p.parent))
            for p in sorted(directory.rglob('requests.jsonl'))]
