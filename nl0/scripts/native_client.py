"""Official Codex stdio integration. Model networking belongs to Codex, not Yui."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

TRANSPORT = 'native-codex-stdio-v1'
OUTPUT_POLICY = {'version':'native-stdio-output-observation-1',
    'observation_boundary':'completed native tool calls and typed native events',
    'partial_argument_deltas_available':False, 'partial_arguments_executed':False,
    'automatic_whitespace_interrupt':False}
PROVIDER_WAIT_POLICY = {'version':'native-stdio-completion-wait-1', 'idle_seconds':None,
    'action':'wait for native completion/error or authorized cancellation',
    'raw_provider_terminal_observer':False, 'synthetic_terminal_or_usage':False}


def configuration(stage):
    return f'''model = {json.dumps(stage.model)}
model_provider = "yui-native"
model_reasoning_effort = {json.dumps(stage.model_selection['reasoning_effort'])}
service_tier = "default"
web_search = "disabled"
project_doc_max_bytes = 0
model_verbosity = {json.dumps(getattr(stage,"output_verbosity","low"))}
tool_output_token_limit = 262144
[model_providers.yui-native]
name = "Yui direct native OpenAI client"
requires_openai_auth = true
request_max_retries = 0
stream_max_retries = 0
[agents]
enabled = false
[features]
apps = false
plugins = false
memories = false
hooks = false
multi_agent = false
multi_agent_v2 = false
shell_tool = false
shell_snapshot = false
view_image = false
image_generation = false
computer_use = false
browser_use = false
in_app_browser = false
daemon_auto_start = false
recommended_plugins = false
tool_suggest = false
'''


def bind_inputs(stage, user, continuation):
    path=stage.logs/'native-client.json'
    if not path.is_file():return
    receipt=json.loads(path.read_text())
    receipt['allowed_user_message_sha256']=[hashlib.sha256(value.encode()).hexdigest() for value in (user,continuation)]
    path.write_text(json.dumps(receipt,indent=2)+'\n')


def thread_parameters(stage):
    return {'model': stage.model, 'modelProvider': 'yui-native',
        'serviceTier': 'default', 'allowProviderModelFallback': False,
        'ephemeral': True, 'cwd': str(stage.work/'input'),
        'approvalPolicy': 'never', 'sandbox': 'read-only',
        'developerInstructions': stage.system,
        'dynamicTools': getattr(stage, 'native_tools', stage.tools),
        'environments': [], 'experimentalRawEvents': True}


def verify_thread(stage, response):
    """Reject exposed native configuration drift before any work is dispatched."""
    expected={'model':stage.model,'modelProvider':'yui-native',
        'reasoningEffort':stage.model_selection['reasoning_effort'],'serviceTier':'default'}
    for key,value in expected.items():
        if response.get(key) is not None and response[key]!=value:
            raise ValueError('Native thread configuration differs from selection: '+key)


def append(stage, name, row):
    # Import lazily: both native stages inherit the same controller implementation.
    from run_pilot import append as record
    record(stage.logs/name, row)


def fault(error):
    """Narrow compatibility for native error variants emitted by this Codex version.

    Only called on Codex error/failed-turn events, never tool/math output. Keep
    the original event and do not extract HTTP statuses from arbitrary prose.
    """
    if not isinstance(error,dict):return error
    value=dict(error)
    if value.get('codexErrorInfo')=='other' and not value.get('code'):
        text=value.get('message','')
        if text.startswith('stream disconnected before completion: idle timeout waiting for SSE'):
            value['code']='request_timeout'
        elif text.startswith('stream disconnected before completion: Transport error: network error:'):
            value['code']='response_stream_disconnected'
        elif text=='stream disconnected before completion: error sending request' or text.startswith('stream disconnected before completion: error sending request:'):
            value['code']='network_error'
        elif not value.get('code'):value['code']='native_unknown_error'
    return value


def observe(stage, message):
    method=message.get('method');params=message.get('params',{})
    if not isinstance(params,dict):raise ValueError('Native notification parameters must be an object')
    thread=params.get('threadId')
    if thread and getattr(stage,'thread_id',None) and thread!=stage.thread_id:
        raise PermissionError('Native notification belongs to another role thread')
    turn=params.get('turnId') or (params.get('turn') or {}).get('id')
    if method not in {'turn/started','thread/tokenUsage/updated'} and turn and getattr(stage,'active_turn_id',None) and turn!=stage.active_turn_id:
        # Delayed events remain in events.jsonl but cannot mutate the current job.
        return False
    if method=='model/rerouted' and params.get('toModel')!=stage.model:
        raise PermissionError('Native model reroute differs from the selected model')
    if method=='rawResponseItem/completed':
        item=params.get('item',{})
        if item.get('type')=='custom_tool_call' and item.get('name')=='exec':
            if not hasattr(stage,'native_code_calls'):stage.native_code_calls={}
            stage.native_code_calls[item.get('call_id')]={'turn_id':turn,'tool':'exec'}
        if item.get('type')=='custom_tool_call_output':
            origin=getattr(stage,'native_code_calls',{}).get(item.get('call_id'))
            if origin and origin['turn_id']==turn:
                origin['output_received']=True
            output=item.get('output')
            # This is a native host-start error for a known actual exec call,
            # not prose supplied by an author, paper or Yui validation tool.
            if (origin and origin['turn_id']==turn and isinstance(output,str)
                    and output.startswith('failed to spawn code-mode host ')):
                error={'code':'harness_bug','origin':'native_code_mode_host',
                    'message':output,'thread_id':thread,'turn_id':turn,'call_id':item.get('call_id')}
                if not getattr(stage,'native_infrastructure_fault',None):
                    stage.native_infrastructure_fault=error
                    append(stage,'native-errors.jsonl',{'thread_id':thread,'turn_id':turn,
                        'error':error,'native_will_retry':False})
        if item.get('type')=='function_call':
            call=item.get('call_id')
            previous=stage.model_calls.get(call)
            if previous and any(previous.get(k)!=item.get(k) for k in ('name','arguments')):
                raise PermissionError('Native tool-call identity changed')
            stage.model_calls[call]=item
    if method=='thread/tokenUsage/updated':
        append(stage,'native-usage.jsonl',{'thread_id':thread,'turn_id':turn,
            'baseline':getattr(stage,'native_usage_baseline',{}), 'token_usage':params.get('tokenUsage')})
        total=(params.get('tokenUsage') or {}).get('total')
        if isinstance(total,dict):stage.native_usage_total=total
    if method=='error':
        append(stage,'native-errors.jsonl',{'thread_id':thread,'turn_id':turn,
            'error':fault(params.get('error')),'native_will_retry':params.get('willRetry',False)})
        stage.last_native_error=params.get('error')
    recorder=getattr(stage,'execution',None)
    counts=None
    if method=='thread/tokenUsage/updated':
        fields={'input_tokens':'inputTokens','output_tokens':'outputTokens','total_tokens':'totalTokens',
                'cached_input_tokens':'cachedInputTokens','reasoning_tokens':'reasoningOutputTokens'}
        total=(params.get('tokenUsage') or {}).get('total');baseline=getattr(stage,'native_usage_baseline',{})
        if isinstance(total,dict) and all(type(total.get(v)) is int and total[v]>=baseline.get(v,0) for v in fields.values()):
            counts={k:total[v]-baseline.get(v,0) for k,v in fields.items()}
            if (counts['total_tokens']!=counts['input_tokens']+counts['output_tokens']
                    or counts['cached_input_tokens']>counts['input_tokens']
                    or counts['reasoning_tokens']>counts['output_tokens']):counts=None
    if recorder:recorder.native_event(getattr(stage,'execution_task',None),stage.logs,method or '',counts)
    if method=='turn/completed':
        value=params.get('turn',{})
        if value.get('status')=='failed':
            append(stage,'native-errors.jsonl',{'thread_id':thread,'turn_id':turn,'error':fault(value.get('error'))})
        elif value.get('status')=='completed' and not getattr(stage,'native_infrastructure_fault',None):
            stage.last_response_success={'request_number':stage.api_calls,
                'turn_generation':stage.native_turn_generation,'source':'native_completed_turn'}
    return True


def validate_tool(stage, params):
    if params.get('threadId')!=stage.thread_id or params.get('turnId')!=stage.active_turn_id:
        raise PermissionError('Tool request is outside the active role thread/turn')
    name=params.get('tool');call=params.get('callId');args=params.get('arguments')
    if name not in stage.tool_names or params.get('namespace') not in (None,''):
        raise PermissionError('Native tool is not in the assigned role tool catalog')
    if not isinstance(call,str) or not call or not isinstance(args,dict):
        raise ValueError('Native tool request requires a call ID and object arguments')
    origin=stage.model_calls.get(call)
    if origin and (origin.get('name')!=name or json.loads(origin['arguments'])!=args):
        raise PermissionError('Repeated native call ID has different tool/arguments')
    stage.model_calls[call]={'name':name,'arguments':json.dumps(args,ensure_ascii=False)}


def audit(directory, *, write_receipt=True):
    """Check native configuration and controller-supplied inputs, never HTTP bytes."""
    root=Path(directory);receipt=root/'native-client.json';errors=[]
    if not receipt.is_file():raise ValueError('Native client receipt is missing')
    data=json.loads(receipt.read_text());config=root/'effective-config.toml'
    if hashlib.sha256(config.read_bytes()).hexdigest()!=data['config_sha256']:errors.append('native_config_changed')
    import tomllib
    settings=tomllib.loads(config.read_text());profile=data['profile']
    if settings.get('model')!=profile['id'] or settings.get('model_reasoning_effort')!=profile['reasoning_effort'] or settings.get('service_tier')!='default':errors.append('native_profile_changed')
    if settings.get('model_provider')!='yui-native':errors.append('provider_is_not_official')
    if any(settings.get('features',{}).get(k) is not False for k in ('memories','plugins','shell_tool','multi_agent')):errors.append('native_isolation_changed')
    calls=[]
    for line in (root/'client.jsonl').read_text().splitlines():
        row=json.loads(line);method=row.get('method');params=row.get('params') or {}
        if method in {'thread/start','turn/start'}:calls.append(row)
        if method=='thread/start':
            if params.get('allowProviderModelFallback') is not False or params.get('model')!=profile['id'] or params.get('serviceTier')!='default':errors.append('thread_profile')
            if params.get('developerInstructions')!=(root/'system.txt').read_text().removesuffix('\n'):errors.append('role_instructions_changed')
            tools=json.loads((root/'tools.json').read_text());active={x['name']:x for x in tools}
            registered={x['name']:x for x in params.get('dynamicTools',[])}
            if any(registered.get(k)!=v for k,v in active.items()):errors.append('role_tool_catalog_changed')
        if method=='turn/start':
            for item in params.get('input',[]):
                if item.get('type')!='text' or hashlib.sha256(item.get('text','').encode()).hexdigest() not in data.get('allowed_user_message_sha256',[]):errors.append('unbound_work_input')
        if method=='turn/start' and (params.get('model')!=profile['id'] or params.get('effort')!=profile['reasoning_effort'] or params.get('serviceTierForTurn')!='default'):errors.append('turn_profile')
    # A reused role has its original registration in its immutable ancestor logs.
    if not calls:errors.append('no_native_work_dispatched')
    if hashlib.sha256((root/'prompt.txt').read_text().removesuffix('\n').encode()).hexdigest() not in data.get('allowed_user_message_sha256',[]):errors.append('unbound_initial_prompt')
    shared=None
    manifest=root/'execution-manifest.json'
    if manifest.is_file():
        bound=json.loads(manifest.read_text())
        for row in bound.get('frozen_task_files',[]):
            try:
                path=(root/row['path']).resolve()
                if not path.is_relative_to(root.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:errors.append('task_input_changed')
            except (KeyError,OSError):errors.append('task_input_changed')
        for relative,digest in bound.get('rule_documents',{}).items():
            try:
                path=(root/'harness-snapshot'/('SKILL.md.snapshot.txt' if relative=='SKILL.md' else relative)).resolve()
                if not path.is_relative_to((root/'harness-snapshot').resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:errors.append('role_rule_changed')
            except OSError:errors.append('role_rule_changed')
        if bound.get('model_selection')!=profile:errors.append('manifest_profile_changed')
        declared_native=bound.get('resolved_environment',{}).get('codex')
        if declared_native and 'code_mode_host' in declared_native and data.get('native_components')!=declared_native:
            errors.append('native_components_changed')
        shared=bound.get('acceptance_contract')
        if bound.get('arm')=='yui' and (bound.get('artifact_contract')=='nl0' or bound.get('phase','').startswith('audit-a')) and not shared:errors.append('shared_acceptance_authority_missing')
        if shared:
            from acceptance import AcceptanceContract
            try:
                source=shared['source']
                if source not in {'nl0/references/audit-a.md','references/audit-a.md'}:raise ValueError('Unknown shared authority source')
                authority=AcceptanceContract((root/'harness-snapshot'/source).read_text(),source=source)
                if authority.metadata()!=shared or authority.instructions() not in (root/'system.txt').read_text():errors.append('shared_acceptance_authority_binding')
            except (ValueError,KeyError,OSError):errors.append('shared_acceptance_authority_binding')
        if hashlib.sha256((root/'system.txt').read_text().removesuffix('\n').encode()).hexdigest()!=data.get('role_system_sha256'):errors.append('role_instructions_changed')
    result={'status':'NATIVE-CODEX-CONTEXT-CHECK-PASSED' if not errors else 'VALIDATION_FAILED',
        'errors':errors,'transport':TRANSPORT,'configured_model':profile['id'],
        'acceptance_contract':shared,'allowed_tools':[t['name'] for t in json.loads((root/'tools.json').read_text())],
        'requested_service_tier':'default','actual_model_ids':[],
        'standard_tier_verified':False,'terminal_service_tiers':[],
        'scope':'Hash-bound native configuration, supplied role instructions and stdio tool/work requests. Native built-in instructions and context management are retained. Provider HTTP payloads and actual tier are not intercepted or certified.'}
    if write_receipt:
        (root/'exposure-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
