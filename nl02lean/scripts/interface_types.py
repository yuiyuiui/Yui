"""Bind a successful authoring type check to the interface it compiled."""
from pathlib import Path

import ir
from controller_common import bind, write


NAME = 'receipt.json'
VERSION = 'yui-interface-type-check-1'
FILES = {'program':'Check.lean','native':'result.json'}


def create(contract, plan):
    root=Path(contract).parent/'types'
    path=root/NAME
    write(path,{'version':VERSION,'contract_sha256':ir.digest(contract),'plan_sha256':ir.digest(plan),
                'renderer_sha256':ir.digest(ir.__file__),
                **{key:bind(root/name) for key,name in FILES.items()}})
    return bind(path)


def read(contract, plan, ref):
    import lean_environment
    import lean_libraries
    import runtime_config

    root=Path(contract).resolve().parent/'types'
    error='Changed or invalid author type check evidence'
    try:
        path=root/NAME
        ir.need(path.resolve()==path and ref==bind(path),error)
        receipt=ir.load(path)
        ir.need(receipt['version']==VERSION and receipt['contract_sha256']==ir.digest(contract)
                and receipt['plan_sha256']==ir.digest(plan) and receipt['renderer_sha256']==ir.digest(ir.__file__),error)
        for key,name in FILES.items():
            member=root/name
            ir.need(member.resolve()==member and receipt[key]==bind(member),error)
        native=ir.load(root/FILES['native'])
        expected=lean_environment.identity(runtime_config.require_environment())
        libraries=lean_libraries.identity()
        if libraries:expected['lean_libraries']=libraries
        ir.need(ir.native_succeeded(native) and native['status']=='IR-TYPES-CHECKED'
                and native['contract_sha256']==receipt['contract_sha256']
                and native['lean_sha256']==receipt['program']['sha256']
                and native['selected_environment']==expected,error)
        return native
    except (OSError,KeyError,TypeError) as cause:
        raise ValueError(error) from cause
