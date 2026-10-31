"""Explicit user-selected translation reset; retain accepted NL0/A and cost totals."""
from pathlib import Path
import json
import shutil
import uuid
import re

from controller_common import bind,write
import execution_state
import source_preparation


def authorization(record,action):
    if bind(record['path'])!=record:raise ValueError('User decision evidence changed')
    value=json.loads(Path(record['path']).read_text())
    if value.get('state')!='USER_DECIDED' or value.get('control',{}).get('action')!=action:
        raise ValueError('An explicit matching final user decision is required')
    if not execution_state.same_process(value.get('owner_process',{})):
        raise ValueError('Decision owner has exited or changed')
    return value


def apply(root,authority,recorder,record,before_native):
    root=Path(root).resolve();decision=authorization(record,'reset-translation')
    if Path(decision['root']).resolve()!=root:raise ValueError('Decision belongs to another run')
    source_preparation.read_source(**authority)
    paths=[root/'nl0-to-lean',root/'audit-b']
    for raw in authority.values():
        if raw and any(Path(raw).resolve().is_relative_to(path) for path in paths):
            raise ValueError('Reset must preserve the original accepted NL0 authority')
    if recorder:
        recorder.release_retained('lean','USER_CANCELLED')
        if any(group=='lean' and not getattr(stage,'_resources_released',False) for stage,group in recorder.retained_stages):
            raise ValueError('Translation process cleanup is unconfirmed; preserve files')
        if any(task.get('current_lean_check') for task in recorder.state['tasks'].values()) or recorder.state.get('current_lean_check'):
            raise ValueError('A native check is still active; preserve files')
    native=root/'native-checks'
    if native.is_symlink():raise ValueError('Refuse symlink native-check ownership directory')
    removed=[p for p in native.glob('*') if p.name not in before_native and re.fullmatch(r'[0-9a-f]{32}\.(lean|json)',p.name)]
    for path in paths+removed:
        if path.is_symlink():raise ValueError('Refuse symlink in translation reset')
    archive=root/'translation-resets'/uuid.uuid4().hex
    write(archive/'user-decision.json',decision)
    if recorder:
        # Health metadata survives the authorized deletion; accepted mathematical
        # drafts/proofs do not. Rekey paths so the new translation can reuse them.
        history=recorder.state.get('stage_history',{})
        for number,(old,entry) in enumerate(list(history.items())):
            original=Path(entry['record']['path'])
            if not any(original.is_relative_to(path) for path in paths):continue
            if bind(original)!=entry['record']:raise ValueError('Stage health changed before explicit reset')
            target=archive/'health'/f'{number:04d}.json';target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(original,target)
            del history[old]
            history[str(target)]={**entry,'original_record':entry['record'],'record':bind(target)}
        # Only health metadata, ledgers and cost/state summaries survive this destructive
        # choice; mathematical translation artifacts and native source files do not.
        for task,row in recorder.state['tasks'].items():
            ledger=Path(row.get('usage_ledger','/nonexistent'))
            if not any(ledger.is_relative_to(path) for path in paths):continue
            target=archive/'usage'/task;target.mkdir(parents=True,exist_ok=True)
            for original in (ledger,ledger.with_name('usage-ledger.jsonl')):
                if original.is_file():shutil.copyfile(original,target/original.name)
            row['previous_usage_ledger']=str(ledger);row['usage_ledger']=str(target/ledger.name)
            recorder.state.setdefault('archived_usage_ledgers',[]).append(str(target/ledger.name))
        write(archive/'costs.json',{'usage':recorder.state['usage'],'tasks':recorder.state['tasks'],
            'scope':'Retained case totals and stage ledgers before user-requested reset; no new mathematical acceptance.'})
    write(archive/'reset.json',{'authority':authority,'removed_directories':[str(p) for p in paths],
        'removed_native_files':[p.name for p in removed],'user_decision':bind(archive/'user-decision.json')})
    for path in paths:
        if path.exists():shutil.rmtree(path)
    for path in removed:path.unlink()
    for path in (root/'repairs').glob('interface-*.json'):path.unlink()
    import source_qualification
    data=source_preparation.read_source(**authority)[0]
    if not source_qualification.publish(root,data):
        for name in ('warn.json','warn.md'):(root/name).unlink(missing_ok=True)
    if recorder:recorder.flush(force=True)
    return archive/'reset.json'
