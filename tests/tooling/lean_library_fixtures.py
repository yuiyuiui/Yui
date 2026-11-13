"""Actual tiny external Lean libraries; fixture code is not a mathematical audit."""
import json
from pathlib import Path
import subprocess

from controller_common import bind
from runtime_config import require_environment


def library(root, *, modern=False):
    root=Path(root).resolve();source=root/'source';build=root/'build'
    for folder in (source,build):(folder/'FixtureLib').mkdir(parents=True)
    path=source/'FixtureLib/Leaf.lean'
    text=('module\npublic import Init\n' if modern else '')+'namespace FixtureLib\n'
    text+=('public ' if modern else '')+'theorem witness : True := True.intro\nend FixtureLib\n'
    path.write_text(text)
    selected=require_environment();binary=Path(selected['lean']['local_path'])/'bin/lean'
    compiled=build/'FixtureLib/Leaf.olean'
    cp=subprocess.run([str(binary),'-R',str(source),'-o',str(compiled),str(path)],
                      capture_output=True,text=True,timeout=30)
    if cp.returncode:raise AssertionError(cp.stdout+cp.stderr)
    row={'module':'FixtureLib.Leaf','source_sha256':bind(path)['sha256'],'olean_sha256':bind(compiled)['sha256']}
    companions={suffix:bind(build/('FixtureLib/Leaf'+suffix))['sha256']
                for suffix in ('.olean.private','.olean.server','.ir','.ir.sig')
                if (build/('FixtureLib/Leaf'+suffix)).is_file()}
    if companions:row['companions']=companions
    value={'version':'yui-lean-library-1','name':'FixtureLib',
           'lean_version':selected['lean']['version_number'],'mathlib_commit':selected['mathlib']['rev'],
           'source_root':str(source),'build_root':str(build),'imports':['FixtureLib.Leaf'],'modules':[row]}
    specification=root/'library.json';specification.write_text(json.dumps(value,indent=2)+'\n')
    return specification
