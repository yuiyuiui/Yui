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
BOUNDARIES = {'GLOBAL_REVIEW_PASSED', 'LOCAL_REVIEWS_PASSED', 'INTERFACE_FROZEN', 'WORKFLOW_FINALIZED', 'BASIS_PREPARED','PRIVATE_WORK_DELIVERED'}


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
                restored=list(self.history.get(role,[]))
                for row in restored:
                    if bind(row['path'])!=row:raise ValueError('Saved role handoff changed before restoration')
                entry = {'stage': template, 'records': restored, 'native_tools': {t['name'] for t in getattr(template,'native_tools',template.tools)}}
                self.roles[role] = entry
                stage = template
                if restored:
                    stage.input_prompt+='\nThis role is restored in a fresh carrier from its own bound saved handoff and the explicitly supplied current inputs. It does not retain a surviving native conversation; prior verdicts are not new acceptance.'
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
                stage.check_runtime_state()
                transport = {k: getattr(stage, k) for k in (
                    'proc', 'work', 'reader_thread', 'inbox', 'rpc_id', 'thread_id',
                    'model_calls', 'tool_history', 'allowed_user_messages',
                    'network_proxy','handoff_results',
                    'native_usage_total','process_owner') if hasattr(stage, k)}
                owner_logs = getattr(stage, 'workspace_owner_logs', stage.logs)
                if stage.mode=='proof' and template.mode=='proof':
                    import ir
                    if ir.local_packet(stage.cpath,stage.plan,stage.step)==ir.local_packet(template.cpath,template.plan,template.step):
                        template.own_lean_drafts=stage.own_lean_drafts
                        template.local_helpers=stage.local_helpers
                        if template.local_helpers:
                            write(template.logs/'local-helpers.json',template.local_helpers)
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
                stage.native_usage_baseline=transport.get('native_usage_total',{})
                for name in ('native-client.json','effective-config.toml'):
                    original=Path(owner_logs)/name
                    if original.is_file():shutil.copyfile(original,stage.logs/name)
                if (stage.logs/'native-client.json').is_file():
                    receipt=json.loads((stage.logs/'native-client.json').read_text())
                    receipt['role_system_sha256']=__import__('hashlib').sha256(stage.system.encode()).hexdigest()
                    write(stage.logs/'native-client.json',receipt)
                stage.workspace_owner_logs = owner_logs
            stage._role_dispatching = True
            stage.role_session = {'role': role, 'prior_submissions': list(entry['records']),
                'restored_role': bool(self.history.get(role)),
                'disclosure': 'Distinct author/reviewer roles; prior_submissions records retained or explicitly restored own handoffs. A restored closed role uses a fresh carrier and explicit saved inputs.'}
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
            entry['records'].extend(bind(stage.logs/name) for name in ('result.json','accepted.json','execution-manifest.json','tools.jsonl','exposure-audit.json',
                'native-client.json','effective-config.toml','client.jsonl','prompt.txt','system.txt')
                if (stage.logs/name).is_file())
            entry['records'].extend(bind(path) for path in (stage.logs/'library').glob('*/library-sources.json'))
        return result

    def close(self, roles, boundary, evidence, *, superseded=()):
        if boundary not in BOUNDARIES or not evidence:
            raise ValueError('Role closure requires a specified successful boundary and saved evidence')
        superseded=set(superseded)
        nl0_supersession=(boundary=='LOCAL_REVIEWS_PASSED' and
            all(role.startswith(('audit-a:','nl0-author:')) for role in superseded))
        proof_supersession=(boundary=='WORKFLOW_FINALIZED' and
            all(role.startswith('lean:') for role in superseded))
        if superseded and (not superseded<=set(roles) or not (nl0_supersession or proof_supersession)):
            raise ValueError('Only obsolete local roles may close at their accepted replacement boundary')
        bindings = [bind(Path(p)) for p in evidence]
        for role in roles:
            entry = self.roles.get(role)
            if entry is None:
                continue
            stage = entry['stage']
            result = json.loads((stage.logs/'result.json').read_text())
            obsolete_review=(role in superseded and nl0_supersession and result.get('status')=='BLOCKED'
                and result.get('task_outcome')=='MATHEMATICAL_REVIEW_FAILED'
                and result.get('execution_health')=='NO_RECORDED_FAULT'
                and json.loads((stage.logs/'accepted.json').read_text()).get('status')=='REVIEW_BLOCKED_INCOMPLETE')
            obsolete_proof=(role in superseded and proof_supersession
                and result.get('status') in {'REPAIR_REQUESTED','REPAIR_WAIT'}
                and result.get('execution_health')=='NO_RECORDED_FAULT')
            if (result.get('status') != 'ACCEPTED' and not obsolete_review and not obsolete_proof) or result.get('execution_fault'):
                raise ValueError('An unfinished/faulted role cannot be released as completed')
            write(stage.logs/'role-completion.json', {'boundary': boundary, 'evidence': bindings,
                'submission': bind(stage.logs/('result.json' if obsolete_proof else 'accepted.json')), 'role': role,
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
