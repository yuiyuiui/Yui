"""Provider-reported, deduplicated response usage; unknown usage is never zero."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def json_rows(path):
    """Read one JSONL record at a time, including large retained request logs."""
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip():yield json.loads(line)




def number(value):
    if type(value) is not int or value < 0:
        raise ValueError('Usage count is missing, negative or not an integer')
    return value




def summarize_native(directory, phase):
    """Native cumulative counters are snapshots, never additive request totals."""
    directory=Path(directory);path=directory/'native-usage.jsonl';errors=[];observed=None;baseline={};last=None
    fields={'input_tokens':'inputTokens','cached_input_tokens':'cachedInputTokens',
            'output_tokens':'outputTokens','reasoning_tokens':'reasoningOutputTokens','total_tokens':'totalTokens'}
    snapshots=0
    for row in json_rows(path) if path.exists() else ():
        snapshots+=1;total=(row.get('token_usage') or {}).get('total');baseline=row.get('baseline',{})
        try:
            value={k:number(total.get(v))-number(baseline.get(v,0)) for k,v in fields.items()}
            if any(v<0 for v in value.values()) or value['total_tokens']!=value['input_tokens']+value['output_tokens']:
                raise ValueError('Native cumulative usage decreased or is inconsistent')
            if last and any(value[k]<last[k] for k in fields):raise ValueError('Native usage regressed')
            if value['cached_input_tokens']>value['input_tokens'] or value['reasoning_tokens']>value['output_tokens']:raise ValueError('Native usage subsets exceed totals')
            last=value;observed=value
        except (ValueError,TypeError,AttributeError) as error:errors.append(str(error))
    result={'phase':phase,'status':'PARTIAL' if observed else 'NOT_RECORDED','complete':False,
        'requests':None,'requests_with_usage':None,'coverage':None,'unique_responses':None,
        'observed_usage':observed,'total_usage':None,'missing_requests':None,'duplicate_events':[],
        'errors':errors,'observed_service_tiers':[],'standard_speed_observation':'UNVERIFIED',
        'native_usage_snapshots':snapshots,'accounting_source':'native_thread_cumulative_delta',
        'definition':'Cumulative native thread counters minus the saved role baseline. Duplicate snapshots are not summed. Per-provider-response coverage and actual tier are not exposed; cached/reasoning are subsets.'}
    (directory/'usage.json').write_text(json.dumps(result,indent=2)+'\n')
    (directory/'usage-ledger.jsonl').write_text('' if observed is None else json.dumps({
        'record_id':'native-stage:'+str(directory.resolve()),'phase':phase,'usage':observed,
        'source':'native-usage.jsonl','source_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})+'\n')
    return result


def summarize_stage(directory, *, phase='unassigned'):
    directory = Path(directory)
    if phase == 'unassigned':
        for name, field in [('execution-manifest.json', 'phase'), ('result.json', 'mode')]:
            source = directory/name
            if source.exists():
                phase = json.loads(source.read_text()).get(field, phase)
                if phase != 'unassigned':
                    break
    # Startup can fail before the native descriptor is written. Missing usage
    # remains unknown; obsolete HTTP/response logs are never interpreted.
    return summarize_native(directory,phase)


def aggregate(directory):
    directory = Path(directory)
    stages, unique, conflicts = [], {}, []
    paths=set(directory.rglob('native-client.json'))
    seen=set()
    for path in sorted(paths):
        if path.parent in seen:continue
        result_path=path.parent/'result.json'
        if result_path.is_file():
            canonical=json.loads(result_path.read_text()).get('stage_log_path')
            if canonical and Path(canonical).resolve()!=path.parent.resolve():continue
        if any(p in {'review-evidence','runtime','harness-snapshot'} for p in path.relative_to(directory).parts):continue
        seen.add(path.parent)
        stage = summarize_stage(path.parent)
        stages.append({'path': str(path.parent.relative_to(directory)), **stage})
        for line in (path.parent / 'usage-ledger.jsonl').read_text().splitlines():
            row = json.loads(line)
            identifier=row.get('response_id') or row['record_id']
            if identifier in unique and unique[identifier]['usage'] != row['usage']:
                conflicts.append(identifier)
            unique[identifier] = row
    complete = bool(stages) and all(x['complete'] for x in stages) and not conflicts
    totals = {k: sum(x['usage'][k] for x in unique.values()) for k in ['input_tokens', 'output_tokens', 'total_tokens']}
    for k in ['cached_input_tokens', 'reasoning_tokens']:
        totals[k] = sum(x['usage'][k] for x in unique.values()) if unique and all(x['usage'][k] is not None for x in unique.values()) else None
    return {'status': 'COMPLETE' if complete else 'PARTIAL' if unique else 'NOT_RECORDED',
            'complete': complete, 'stages': stages, 'unique_responses': None if any(k.startswith('native-stage:') for k in unique) else len(unique),
            'observed_usage': totals if unique else None, 'total_usage': totals if complete else None,
            'conflicting_responses': conflicts,
            'scope': 'Only recorded model calls under this run; uninstrumented owner work must be disclosed separately.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    print(json.dumps(aggregate(args.directory), indent=2))
