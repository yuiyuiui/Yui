"""Legacy raw-event helpers and controller exception types.

Native Codex stages do not receive partial provider argument/SSE events and do
not install these raw-stream observers. Keep their standalone compatibility
tests distinct from current native integration coverage.
"""
from copy import deepcopy
import threading
import time


POLICY = {'version': 'function-json-whitespace-1', 'outside_string_whitespace_limit': 8192,
          'action': 'interrupt exact active turn and preserve this unfinished attempt',
          'partial_arguments_executed': False, 'automatic_model_retry': False}

PROVIDER_WAIT_POLICY = {'version': 'delivered-tool-terminal-wait-2', 'idle_seconds': None,
    'requires': 'actual completed function call and genuinely delivered tool result; no provider terminal or next request',
    'action': 'record pending tool delivery without an idle cutoff; explicit finite limits are opt-in',
    'automatic_model_retry': False, 'synthetic_terminal_or_usage': False}
TERMINAL_EVENTS = {'response.completed', 'response.incomplete', 'response.failed'}


def substantive_event(event):
    """Observable output progress, as distinct from a connection heartbeat."""
    kind=event.get('type','')
    if kind.endswith('.delta'):
        delta=event.get('delta')
        return isinstance(delta,str) and bool(delta.strip())
    return kind in {'response.output_item.added','response.output_item.done',
                    'response.content_part.added','response.content_part.done'}


class ProviderTerminalWaitExceeded(RuntimeError):
    def __init__(self,evidence):
        super().__init__('No provider terminal or next request after the recorded delivered-tool wait limit; cause UNVERIFIED')
        self.evidence=deepcopy(evidence)


class ProviderWaitGuard:
    """Monitor a narrow post-tool protocol wait, never mathematical difficulty."""
    def __init__(self,*,idle_seconds=None,clock=time.monotonic):
        self.limit=PROVIDER_WAIT_POLICY['idle_seconds'] if idle_seconds is None else idle_seconds
        self.limit = __import__('runtime_config').time_limit(self.limit)
        self.clock=clock;self.lock=threading.Lock()
        self.latest_request=None;self.calls={};self.terminals=set();self.waits={}

    def normalized(self,number):
        if number is None:return
        with self.lock:
            self.latest_request=max(number,self.latest_request or number)
            self.waits={r:v for r,v in self.waits.items() if r>=self.latest_request}

    def observe(self,event,number):
        if number is None:return
        with self.lock:
            kind=event.get('type')
            if kind=='response.output_item.done':
                item=event.get('item',{})
                if item.get('type')=='function_call' and item.get('call_id'):
                    self.calls[item['call_id']]={'request_number':number,'item_id':item.get('id'),'tool':item.get('name')}
            if kind in TERMINAL_EVENTS:
                self.terminals.add(number);self.waits.pop(number,None)
            elif substantive_event(event) and number in self.waits:
                self.waits[number]['last_substantive_monotonic']=self.clock()

    def delivered(self,call_id,at_utc):
        with self.lock:
            origin=self.calls.get(call_id)
            if not origin:return None
            number=origin['request_number']
            if number in self.terminals or (self.latest_request is not None and number<self.latest_request):return None
            mono=self.clock()
            old=self.waits.get(number,{})
            row={**origin,'call_ids':[*(old.get('call_ids',[])),call_id],
                'tool_result_delivered_at_utc':at_utc,'delivered_monotonic':mono,
                'last_substantive_monotonic':mono}
            self.waits[number]=row
            return deepcopy(row)

    def origin(self,call_id):
        with self.lock:return deepcopy(self.calls.get(call_id))

    def check(self):
        if self.limit is None:
            return None
        with self.lock:
            mono=self.clock()
            for row in self.waits.values():
                idle=mono-row['last_substantive_monotonic']
                if idle>=self.limit:
                    return {k:deepcopy(v) for k,v in row.items() if not k.endswith('_monotonic')} | {
                        'idle_seconds':idle,'seconds_since_tool_result':mono-row['delivered_monotonic'],
                        'latest_normalized_request':self.latest_request,'attribution':'UNVERIFIED',
                        'policy':{**deepcopy(PROVIDER_WAIT_POLICY),'idle_seconds':self.limit}}
        return None


class ModelOutputStalled(RuntimeError):
    def __init__(self, evidence):
        super().__init__('Model tool arguments exceeded the recorded consecutive JSON whitespace limit')
        self.evidence = deepcopy(evidence)


class ModelOutputLimit(RuntimeError):
    def __init__(self, evidence):
        super().__init__('Provider response reached its output-token limit before completing the artifact')
        self.evidence = deepcopy(evidence)


class ArgumentGuard:
    """Linear scan of actual tool-argument deltas, with quoted strings excluded."""
    def __init__(self, limit=None):
        self.limit = POLICY['outside_string_whitespace_limit'] if limit is None else limit
        if type(self.limit) is not int or self.limit < 1:
            raise ValueError('Positive whitespace limit required')
        self.states = {}

    def observe(self, event, request):
        kind = event.get('type')
        if kind == 'response.output_item.added':
            item = event.get('item', {})
            if item.get('type') == 'function_call' and item.get('id'):
                self.states[(request, item['id'])] = {
                    'name': item.get('name'), 'call_id': item.get('call_id'),
                    'quoted': False, 'escaped': False, 'whitespace': 0, 'reported': False}
            return None
        if kind in {'response.completed', 'response.incomplete', 'response.failed'}:
            self.states = {key: value for key, value in self.states.items() if key[0] != request}
            return None
        key = (request, event.get('item_id'))
        if kind == 'response.output_item.done':
            self.states.pop((request, event.get('item', {}).get('id')), None)
            return None
        state = self.states.get(key)
        if kind != 'response.function_call_arguments.delta' or state is None:
            return None
        for char in event.get('delta', ''):
            if state['quoted']:
                if state['escaped']: state['escaped'] = False
                elif char == '\\': state['escaped'] = True
                elif char == '"': state['quoted'] = False
                state['whitespace'] = 0
            elif char == '"':
                state['quoted'] = True
                state['whitespace'] = 0
            elif char in ' \r\n\t':
                state['whitespace'] += 1
            else:
                state['whitespace'] = 0
            if state['whitespace'] >= self.limit and not state['reported']:
                state['reported'] = True
                return {'request_number': request, 'item_id': key[1], 'tool': state['name'],
                        'call_id': state['call_id'], 'outside_string_whitespace': state['whitespace'],
                        'policy': deepcopy(POLICY)}
        return None
