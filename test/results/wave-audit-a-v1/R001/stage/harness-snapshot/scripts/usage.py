"""Provider-reported, deduplicated response usage; unknown usage is never zero."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def events(path):
    for line in Path(path).read_text().splitlines():
        if line.startswith('data: '):
            try:
                yield json.loads(line[6:])
            except ValueError:
                continue


def number(value):
    if type(value) is not int or value < 0:
        raise ValueError('Usage count is missing, negative or not an integer')
    return value


def normalize(usage):
    inp, out = number(usage.get('input_tokens')), number(usage.get('output_tokens'))
    cached = usage.get('input_tokens_details', {}).get('cached_tokens')
    reasoning = usage.get('output_tokens_details', {}).get('reasoning_tokens')
    cached = None if cached is None else number(cached)
    reasoning = None if reasoning is None else number(reasoning)
    total = number(usage.get('total_tokens'))
    if total != inp + out or (cached is not None and cached > inp) or (reasoning is not None and reasoning > out):
        raise ValueError('Inconsistent usage totals/subcategories')
    return {'input_tokens': inp, 'cached_input_tokens': cached, 'output_tokens': out,
            'reasoning_tokens': reasoning, 'total_tokens': total}


def summarize_stage(directory, *, phase='unassigned'):
    directory = Path(directory)
    if phase == 'unassigned':
        for name, field in [('execution-manifest.json', 'phase'), ('result.json', 'mode')]:
            source = directory/name
            if source.exists():
                phase = json.loads(source.read_text()).get(field, phase)
                if phase != 'unassigned':
                    break
    requests = []
    request_path = directory / 'requests.jsonl'
    if request_path.exists():
        requests = [json.loads(x) for x in request_path.read_text().splitlines() if x.strip()]
    numbers = {r['request_number'] for r in requests}
    responses, covered, errors, duplicates = {}, set(), [], []
    tiers = set()
    for path in sorted(directory.glob('response-*.sse')):
        request = int(path.stem.split('-')[-1])
        for event in events(path):
            response = event.get('response') or {}
            if not isinstance(response, dict):
                continue
            # Created events can say auto before dispatch resolves the actual
            # tier. Only terminal execution metadata describes used service.
            if event.get('type') in {'response.completed', 'response.incomplete', 'response.failed'} and response.get('service_tier') is not None:
                tiers.add(response['service_tier'])
            if not isinstance(response.get('usage'), dict):
                continue
            rid = response.get('id')
            if not rid:
                errors.append({'request': request, 'error': 'response ID unavailable'})
                continue
            try:
                counts = normalize(response['usage'])
            except ValueError as e:
                errors.append({'request': request, 'response_id': rid, 'error': str(e)})
                continue
            row = {'response_id': rid, 'request_number': request, 'phase': phase,
                   'model': response.get('model'), 'service_tier': response.get('service_tier'),
                   'response_status': response.get('status'), 'usage': counts,
                   'source': path.name, 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            if rid in responses:
                duplicates.append({'response_id': rid, 'request_number': request})
                if responses[rid]['usage'] != counts:
                    errors.append({'response_id': rid, 'error': 'conflicting repeated usage'})
            else:
                responses[rid] = row
            covered.add(request)
    rows = list(responses.values())
    totals = {key: sum(x['usage'][key] for x in rows) for key in ['input_tokens', 'output_tokens', 'total_tokens']}
    for key in ['cached_input_tokens', 'reasoning_tokens']:
        totals[key] = sum(x['usage'][key] for x in rows) if rows and all(x['usage'][key] is not None for x in rows) else None
    complete = bool(numbers) and numbers <= covered and not errors
    result = {'phase': phase, 'status': 'COMPLETE' if complete else 'PARTIAL' if rows else 'NOT_RECORDED',
              'complete': complete, 'requests': len(numbers), 'requests_with_usage': len(numbers & covered),
              'coverage': len(numbers & covered) / len(numbers) if numbers else None,
              'unique_responses': len(rows), 'observed_usage': totals if rows else None,
              'total_usage': totals if complete else None, 'missing_requests': sorted(numbers - covered),
              'duplicate_events': duplicates, 'errors': errors, 'observed_service_tiers': sorted(tiers),
              'standard_speed_observation': 'UNVERIFIED' if not tiers else 'CONSISTENT' if tiers <= {'default', 'standard'} else 'MISMATCH',
              'definition': 'cached input and reasoning output are subsets; observed partial sums are not complete totals'}
    (directory / 'usage-ledger.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in rows))
    (directory / 'usage.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def aggregate(directory):
    directory = Path(directory)
    stages, unique, conflicts = [], {}, []
    for path in sorted(directory.rglob('requests.jsonl')):
        stage = summarize_stage(path.parent)
        stages.append({'path': str(path.parent.relative_to(directory)), **stage})
        for line in (path.parent / 'usage-ledger.jsonl').read_text().splitlines():
            row = json.loads(line)
            if row['response_id'] in unique and unique[row['response_id']]['usage'] != row['usage']:
                conflicts.append(row['response_id'])
            unique[row['response_id']] = row
    complete = bool(stages) and all(x['complete'] for x in stages) and not conflicts
    totals = {k: sum(x['usage'][k] for x in unique.values()) for k in ['input_tokens', 'output_tokens', 'total_tokens']}
    for k in ['cached_input_tokens', 'reasoning_tokens']:
        totals[k] = sum(x['usage'][k] for x in unique.values()) if unique and all(x['usage'][k] is not None for x in unique.values()) else None
    return {'status': 'COMPLETE' if complete else 'PARTIAL' if unique else 'NOT_RECORDED',
            'complete': complete, 'stages': stages, 'unique_responses': len(unique),
            'observed_usage': totals if unique else None, 'total_usage': totals if complete else None,
            'conflicting_responses': conflicts,
            'scope': 'Only recorded model calls under this run; uninstrumented owner work must be disclosed separately.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    print(json.dumps(aggregate(args.directory), indent=2))
