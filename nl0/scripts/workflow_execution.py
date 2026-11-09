"""Execute the versioned route captured when this public Yui case was prepared."""
from contextvars import ContextVar
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import sys

import basis
from controller_common import bind

active = ContextVar("yui_public_workflow", default=None)


def block_module(project, name):
    spec=spec_from_file_location('yui_public_'+name,project/'blocks'/(name+'.py'))
    module=module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(job,recorder,budgets,progress):
    from runtime_snapshot import root_for
    project=root_for(job)/'workflow'
    sys.path.insert(0,str(project/'scripts'))
    try:
        from wfcore.engine import start
    except ModuleNotFoundError as error:
        if error.name not in ('jsonschema','referencing','yaml'): raise
        # Prepared cases can outlive an update of the skill. Only interpreter
        # dependencies are shared. All workflow sources come from this job.
        import site
        original=Path(json.loads((Path(job['root'])/'runtime-manifest.json').read_text())['original_core'])
        site.addsitedir(str(original/'.venv/lib'/f'python{sys.version_info.major}.{sys.version_info.minor}'/'site-packages'))
        try: from wfcore.engine import start
        except ModuleNotFoundError as missing:
            raise RuntimeError('Install workflow/requirements.txt for this interpreter or in Yui/.venv') from missing
    session=block_module(project,'native_case').Case(job,recorder,budgets,progress)
    token=active.set(session)
    try:
        root=Path(job['root'])
        entry='audit' if job['track']=='nl0' else basis.mode(job)
        view=start(project,root/'protocol',entry,{'job':bind(root/'job.json')})
        if session.failure: raise session.failure
        if (view['status']=='paused' and view['node']=='nl0-local/revise-graph'
                and 'visit budget' in str(view.get('error'))):
            from execution_health import StageFailure
            from graph_repair import LIMIT
            raise StageFailure(LIMIT,str(view['error']),phase='nl0-global',
                               evidence=root/'protocol/work/state.json')
        if view['status']!='completed' or session.result is None:
            raise ValueError('Public workflow stopped at '+str(view))
        return session.result
    finally:
        active.reset(token)
