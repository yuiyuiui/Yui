"""Explicit recovery of a recorded provider access denial, never automatic retry.

The live check reads authenticated model metadata through the carrier's route.
It makes no inference call and never persists credentials or response bodies.
"""
from datetime import datetime, timezone
import hashlib
import http.client
import json
from pathlib import Path
import re
from urllib.parse import urlencode
import uuid

from controller_common import bind, write
from runtime_config import auth_home, load_lock
import remote_retry

VERSION = 'yui-restored-provider-access-1'
HOST = 'chatgpt.com'
MAX_BYTES = 8 * 1024 * 1024
NETWORK_ERRORS = {'SSLEOFError', 'SSLError', 'TimeoutError', 'IncompleteRead',
                  'RemoteDisconnected', 'ConnectionResetError', 'ConnectionAbortedError'}


def denied(error):
    """Recognize only the native structured HTTP-connection 403 shape."""
    if not isinstance(error, dict):
        return False
    info = error.get('codexErrorInfo')
    if not isinstance(info, dict) or set(info) != {'httpConnectionFailed'}:
        return False
    details = info['httpConnectionFailed']
    if (not isinstance(details, dict) or type(details.get('httpStatusCode')) is not int
            or details['httpStatusCode'] != 403):
        return False
    def veto(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if remote_retry.normalized(key) in remote_retry.PERMANENT:
                    return True
                if key in {'code', 'type', 'reason'} and isinstance(item, str) and item:
                    return True
                if key in {'httpStatusCode', 'http_status', 'status_code'} and item != 403:
                    return True
                if isinstance(item, (dict, list)) and veto(item):
                    return True
        elif isinstance(value, list):
            return any(veto(item) for item in value)
        return False
    return not veto(error)


def rows(path, limit=131072):
    """Bounded metadata suffix, not a model-history reader."""
    path = Path(path)
    if not path.is_file():
        return []
    with path.open('rb') as stream:
        size = stream.seek(0, 2); offset = max(0, size-limit); stream.seek(offset)
        if offset:
            stream.readline()
        values = stream.read().splitlines()
    result = []
    for line in values:
        try:
            value = json.loads(line)
        except (ValueError, UnicodeError):
            continue
        if isinstance(value, dict):
            result.append(value)
    return result


def last_failed_turn(stage):
    for event in reversed(rows(Path(stage)/'events.jsonl')):
        if event.get('method') == 'turn/completed':
            turn = event.get('params', {}).get('turn', {})
            return turn if turn.get('status') == 'failed' else None
    return None


def boundary(stage, failure):
    """Reject local/unknown causes instead of treating every 403 as transient."""
    stage = Path(stage)
    turn = last_failed_turn(stage)
    if (failure.get('status') != 'UNFINISHED'
            or failure.get('identity_and_input_boundary_verified') is not True
            or failure.get('isolation_violation') or not turn or not denied(turn.get('error'))):
        raise ValueError('Access recovery requires the actual final qualified provider HTTP403 stop')
    for name in ['tool-provenance-rejections.jsonl', 'isolation-violations.jsonl',
                 'local-protocol-faults.jsonl']:
        if (stage/name).exists():
            raise ValueError('Local/provenance faults cannot become access recovery')
    http = [r for r in rows(stage/'http.jsonl') if r.get('path', '').rstrip('/') == '/responses']
    if not http or http[-1].get('status') != 403:
        raise ValueError('No matching terminal upstream HTTP403 evidence')
    relay = {r.get('request_number'): r for r in rows(stage/'relay-errors.jsonl')}
    health = failure.get('transport_health') or {}
    faults = health.get('faults', [])
    if not faults:
        raise ValueError('Missing actual transport fault evidence')
    for fault in faults:
        kind = fault.get('kind')
        if kind == 'HTTP_ERROR':
            status = fault.get('status')
            if status != 403 and not (type(status) is int and (status in {408, 429} or 500 <= status < 600)):
                raise ValueError('Unrelated permanent HTTP failure blocks access recovery')
        elif kind == 'RELAY_ERROR':
            row = relay.get(fault.get('request_number'), {})
            if row.get('upstream_opened') is not True or row.get('error_type') not in NETWORK_ERRORS:
                raise ValueError('Unknown/local relay failure blocks access recovery')
        elif kind == 'PROVIDER_ERROR':
            if not remote_retry.classify(fault.get('details')):
                raise ValueError('Permanent provider failure blocks access recovery')
        else:
            raise ValueError('Unknown/local execution failure blocks access recovery')
    numbers = {f.get('request_number') for f in faults}
    if any(u.get('kind') != 'HTTP_EVIDENCE_INCOMPLETE'
           or not set(u.get('missing_requests', [])) <= numbers for u in health.get('uncertainty', [])):
        raise ValueError('Unexplained execution uncertainty blocks access recovery')
    return {'kind': 'EXPLICIT_PROVIDER_HTTP403_RECOVERY', 'failed_turn_id': turn.get('id'),
            'http_status': 403, 'http_request_number': http[-1].get('request_number')}


def confirm_exit(prior):
    from owner_observation import snapshot
    observed = snapshot([Path(prior)])
    if not observed.get('all_terminal') or not observed.get('all_process_exits_verified'):
        raise ValueError('Access recovery requires exact owned process and group exits')
    return {'at_utc': datetime.now(timezone.utc).isoformat(), 'process_exit_verified': True}


def check(profiles):
    """One authenticated GET, using the same verified-TLS/system-proxy route."""
    from run_pilot import system_https_proxy
    auth = json.loads((auth_home()/'auth.json').read_text())
    tokens = auth.get('tokens') or {}
    token, account = tokens.get('access_token'), tokens.get('account_id')
    if not isinstance(token, str) or not token or not isinstance(account, str) or not account:
        raise ValueError('Restored-access check requires existing subscription authentication')
    if any(c in token+account for c in '\r\n'):
        raise ValueError('Malformed subscription credential header; value withheld')
    lock = load_lock()
    match = re.search(r'\b(\d+\.\d+\.\d+[A-Za-z0-9.+_-]*)\b', lock['codex']['version'])
    if not match:
        raise ValueError('Cannot establish the actual native client version')
    path = '/backend-api/codex/models?' + urlencode({'client_version': match[1]})
    proxy = system_https_proxy()
    connection = None
    try:
        if proxy:
            connection = http.client.HTTPSConnection(*proxy, timeout=25)
            connection.set_tunnel(HOST, 443)
        else:
            connection = http.client.HTTPSConnection(HOST, timeout=25)
        connection.request('GET', path, headers={'Authorization': 'Bearer '+token,
            'ChatGPT-Account-Id': account, 'Accept': 'application/json',
            'Accept-Encoding': 'identity', 'User-Agent': 'codex_cli_rs/'+match[1],
            'originator': 'codex_cli_rs'})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError('Provider access is not restored: metadata HTTP '+str(response.status))
        if 'application/json' not in (response.getheader('Content-Type') or '').lower():
            raise ValueError('Provider access check did not return model JSON')
        body = response.read(MAX_BYTES+1)
        if len(body) > MAX_BYTES:
            raise ValueError('Provider metadata exceeds the bounded access check')
        try:
            catalog = json.loads(body)
        except (ValueError, UnicodeError) as error:
            raise ValueError('Malformed provider model metadata') from error
        models = catalog.get('models') if isinstance(catalog, dict) else None
        if not isinstance(models, list) or any(not isinstance(row, dict) for row in models):
            raise ValueError('Provider metadata has no model catalog')
        for profile in profiles.values():
            matched = [row for row in models if row.get('slug') == profile['id']]
            if len(matched) != 1 or profile['reasoning_effort'] not in {
                    r.get('effort') for r in matched[0].get('supported_reasoning_levels', []) if isinstance(r, dict)}:
                raise ValueError('Restored channel does not advertise the selected model/effort')
        return {'at_utc': datetime.now(timezone.utc).isoformat(), 'method': 'GET',
                'host': HOST, 'path': path, 'http_status': 200,
                'request_id': (response.getheader('x-request-id') or '')[:256] or None,
                'catalog_sha256': hashlib.sha256(body).hexdigest(),
                'verified_profiles': profiles, 'system_https_proxy': proxy,
                'inference_calls': 0, 'credential_values_logged': False,
                'scope': 'Authenticated metadata access, not a guarantee of future inference health'}
    except (OSError, http.client.HTTPException) as error:
        raise ValueError('Provider access check failed: '+type(error).__name__) from None
    finally:
        if connection:
            connection.close()


def record(prior, stage, profiles, denial, exited, restored):
    path = Path(prior)/'owner-provenance'/('access-recovery-'+uuid.uuid4().hex+'.json')
    write(path, {'version': VERSION, 'prior_run': str(Path(prior).resolve()),
                 'failed_stage': str(Path(stage).resolve()), 'denial': denial,
                 'exit_verification': exited, 'restored_access': restored, 'profiles': profiles,
                 'explicit_operator_request': True, 'automatic_retry': False})
    return path


def validate_receipt(job):
    value = job['resume']; prior = Path(value['prior_run']).resolve()
    path = Path(value['access_recovery_receipt'])
    if path.is_symlink() or not path.resolve().is_relative_to(prior/'owner-provenance'):
        raise ValueError('Access receipt escapes its original owned run')
    if bind(path) not in job['authority_bindings']:
        raise ValueError('Missing immutable restored-access receipt binding')
    data = json.loads(path.read_text())
    result = json.loads((prior/'case-result.json').read_text()); result = result.get('result', result)
    stage = Path(result.get('evidence', '')).parent
    if not stage.resolve().is_relative_to(prior):
        raise ValueError('Access receipt lacks its exact old failed stage')
    failure = json.loads((stage/'result.json').read_text())
    restored = data.get('restored_access') or {}
    if (data.get('version') != VERSION or data.get('prior_run') != str(prior)
            or data.get('failed_stage') != str(stage) or data.get('profiles') != job['profiles']
            or data.get('denial') != boundary(stage, failure)
            or data.get('explicit_operator_request') is not True or data.get('automatic_retry') is not False
            or data.get('exit_verification', {}).get('process_exit_verified') is not True
            or restored.get('host') != HOST or restored.get('method') != 'GET'
            or restored.get('http_status') != 200 or restored.get('inference_calls') != 0
            or restored.get('verified_profiles') != job['profiles']
            or restored.get('credential_values_logged') is not False):
        raise ValueError('Invalid bound restored-access recovery receipt')
    required = [stage/name for name in ['events.jsonl', 'http.jsonl']]
    if (stage/'relay-errors.jsonl').exists():
        required.append(stage/'relay-errors.jsonl')
    if not all(bind(p) in job['authority_bindings'] for p in required):
        raise ValueError('Missing immutable access-denial evidence binding')
    if (not re.fullmatch(r'/backend-api/codex/models\?client_version=[A-Za-z0-9_.%+\-]+', restored.get('path', ''))
            or not re.fullmatch('[0-9a-f]{64}', restored.get('catalog_sha256', ''))
            or type(restored.get('inference_calls')) is not int):
        raise ValueError('Invalid non-inference provider access metadata')
    try:
        if datetime.fromisoformat(restored['at_utc']).tzinfo is None:
            raise ValueError('Access receipt timestamp must have a timezone')
    except (KeyError, TypeError):
        raise ValueError('Access receipt lacks its observed timestamp') from None
    return data


def before_launch(job):
    if not (job.get('resume') or {}).get('access_recovery_receipt'):
        return
    validate_receipt(job)
    confirm_exit(job['resume']['prior_run'])
    restored = check(job['profiles'])
    write(Path(job['root'])/'owner-provenance/access-recovery-launch.json', restored)
