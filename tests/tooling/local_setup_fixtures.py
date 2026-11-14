"""Synthetic local readiness fixtures for software controls, never live receipts."""
from pathlib import Path
import sys
from controller_common import bind


def host(root):
    root=Path(root)
    for name in ('codex','code-mode-host','rg'):
        path=root/name;path.write_text('Synthetic executable identity, not a live provider.');path.chmod(0o700)
    return {'codex':{'binary_path':str(root/'codex'),'sha256':bind(root/'codex')['sha256'],
        'version':'codex-cli fixture','code_mode_host':bind(root/'code-mode-host'),'package_manifest':None},
        'ripgrep':bind(root/'rg'),'python':str(Path(sys.executable).absolute()),'auth_home':str(root/'auth')}


def configuration(root):
    import local_config
    from harness_support import PROFILES
    from setup_checks import record
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    (root/'program.py').write_text('# Synthetic implementation fixture\n')
    return {'version':local_config.rules.VERSION,'root':str(root),'mode':'nl0','host':host(root),
            'profiles':PROFILES,'lean_environment':None,'libraries':[],
            'implementation':{'program.py':bind(root/'program.py')['sha256']},
            'checks':{key:record(root,key,{'fixture':'synthetic software control only'})
                      for key in local_config.rules.BASE_CHECKS},'created_at':'fixture timestamp'}
