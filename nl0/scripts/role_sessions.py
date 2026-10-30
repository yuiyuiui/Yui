"""Retained role conversations at explicit controller handoffs, not a scheduler."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
from pathlib import Path
import shutil
import threading

from controller_common import bind, write
import execution_state

_active = ContextVar('yui_role_session', default=None)
BOUNDARIES = {'GLOBAL_REVIEW_PASSED', 'LOCAL_REVIEWS_PASSED', 'INTERFACE_FROZEN', 'WORKFLOW_FINALIZED'}


def current():
    return _active.get()


class Sessions:
    """One conversation per assigned role; idle roles do not acquire model slots."""
    def __init__(self):
        self.roles = {}
        self.history = {}
        self.lock = threading.RLock()

    @contextmanager
    def use(self, role):
        token = _active.set((self, role))
        try:
            yield
        finally:
            _active.reset(token)

    def execute(self, template, role):
        with self.lock:
            entry = self.roles.get(role)
            if entry is None:
                entry = {'stage': template, 'records': [], 'native_tools': {t['name'] for t in getattr(template,'native_tools',template.tools)}}
                self.roles[role] = entry
                stage = template
            else:
                stage = entry['stage']
                if getattr(stage, '_resources_released', False):
                    raise ValueError('A released role must be restored explicitly from its saved handoff')
                if not getattr(stage, 'submission_closed', False):
                    raise ValueError('Role has no completed submission handoff')
                for row in entry['records']:
                    if bind(row['path']) != row:
                        raise ValueError('Retained role evidence changed')
                if any(template.model_selection[k] != stage.model_selection[k] for k in ('id','reasoning_effort','speed','automatic_fallback')):
                    raise ValueError('A retained role cannot change its model profile')
                if not {t['name'] for t in template.tools} <= entry['native_tools']:
                    raise ValueError('Role handoff requires tools absent from its original native registration')
                stage.drain_relay_streams()
                stage.check_argument_guard()
                transport = {k: getattr(stage, k) for k in (
                    'proc', 'relay', 'work', 'reader_thread', 'inbox', 'rpc_id', 'thread_id',
                    'model_history', 'model_calls', 'tool_history', 'allowed_user_messages',
                    'prompt_cache_key', 'network_proxy','handoff_results',
                    'relay_stream_lock') if hasattr(stage, k)}
                owner_logs = getattr(stage, 'workspace_owner_logs', stage.logs)
                if stage.mode=='proof' and template.mode=='proof':
                    template.own_lean_drafts=stage.own_lean_drafts
                    for path in (stage.logs/'lean-drafts').glob('*.json'):
                        target=template.logs/'lean-drafts'/path.name
                        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
                for path in (stage.logs/'library').glob('*/library-sources.json'):
                    target=template.logs/path.relative_to(stage.logs)
                    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
                if hasattr(stage,'library_probes'):template.library_probes=stage.library_probes
                if hasattr(stage,'type_probes') and hasattr(template,'type_probes'):
                    template.type_probes=stage.type_probes
                    for path in (stage.logs/'type-probes').rglob('*'):
                        if path.is_file():
                            target=template.logs/path.relative_to(stage.logs)
                            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
                if hasattr(stage.validator if hasattr(stage,'validator') else None,'drafts') and hasattr(getattr(template,'validator',None),'drafts'):
                    template.validator.drafts.update(stage.validator.drafts)
                    template.validator.attempt=max(template.validator.attempt,stage.validator.attempt)
                # This constructor-only workspace has never hosted a task.
                shutil.rmtree(template.work)
                stage.__class__ = template.__class__
                stage.__dict__.clear()
                stage.__dict__.update(template.__dict__)
                stage.__dict__.update(transport)
                if 'relay_stream_lock' in transport:
                    stage.relay_streams={}
                stage.workspace_owner_logs = owner_logs
                stage.provider_wait_guard = __import__('output_guard').ProviderWaitGuard()
            stage._role_dispatching = True
            stage.role_session = {'role': role, 'prior_submissions': list(entry['records']),
                'restored_role': bool(self.history.get(role)),
                'disclosure': 'Distinct author/reviewer roles; this role retains its own prior conversation and findings.'}
            manifest = stage.logs/'execution-manifest.json'
            if manifest.is_file():
                value = json.loads(manifest.read_text()); value['role_session'] = stage.role_session
                write(manifest, value)
        try:
            recorder=getattr(stage.budget,'execution',None) or execution_state.current()[0]
            with execution_state.activate(recorder,entry.get('task')):
                result = stage.execute()
            entry['task']=stage.execution_task
        finally:
            stage._role_dispatching = False
        with self.lock:
            entry['records'].extend(bind(stage.logs/name) for name in ('result.json', 'accepted.json','execution-manifest.json','tools.jsonl','exposure-audit.json')
                if (stage.logs/name).is_file())
            entry['records'].extend(bind(path) for path in (stage.logs/'library').glob('*/library-sources.json'))
        return result

    def close(self, roles, boundary, evidence, *, superseded=()):
        if boundary not in BOUNDARIES or not evidence:
            raise ValueError('Role closure requires a specified successful boundary and saved evidence')
        superseded=set(superseded)
        if superseded and (boundary!='LOCAL_REVIEWS_PASSED' or not superseded<=set(roles)
                or any(not role.startswith(('audit-a:','nl0-author:')) for role in superseded)):
            raise ValueError('Only obsolete local roles may close with an accepted replacement NL0')
        bindings = [bind(Path(p)) for p in evidence]
        for role in roles:
            entry = self.roles.get(role)
            if entry is None:
                continue
            stage = entry['stage']
            result = json.loads((stage.logs/'result.json').read_text())
            obsolete_review=(role in superseded and result.get('status')=='BLOCKED'
                and result.get('task_outcome')=='MATHEMATICAL_REVIEW_FAILED'
                and result.get('execution_health')=='NO_RECORDED_FAULT'
                and json.loads((stage.logs/'accepted.json').read_text()).get('status')=='REVIEW_BLOCKED_INCOMPLETE')
            if (result.get('status') != 'ACCEPTED' and not obsolete_review) or result.get('execution_fault'):
                raise ValueError('An unfinished/faulted role cannot be released as completed')
            write(stage.logs/'role-completion.json', {'boundary': boundary, 'evidence': bindings,
                'submission': bind(stage.logs/'accepted.json'), 'role': role,
                'superseded_by_accepted_revision':role in superseded})
            stage.release_resources('ROLE_COMPLETED')
            if getattr(stage,'execution',None):
                values={'role_state':'CLOSED','role_closed_at_utc':execution_state.now()}
                if stage.step is None:values.update(state='FINISHED',activity='ROLE_CLOSED',finished_at_utc=execution_state.now())
                stage.execution.task(stage.execution_task,**values)
            self.history.setdefault(role, []).extend(entry['records'])
            del self.roles[role]

    def close_all(self, boundary, evidence, *, superseded=()):
        self.close(list(self.roles), boundary, evidence, superseded=superseded)

    def cancel_all(self):
        """Only called for an explicit user-selected delivery/reset/cancellation."""
        for role,entry in list(self.roles.items()):
            entry['stage'].release_resources('USER_CANCELLED')
            self.history.setdefault(role,[]).extend(entry['records'])
            del self.roles[role]
