"""Small basis controls; source/reviewer metadata is synthetic, never certification."""
from pathlib import Path

import basis
import basis_native
import ir
from controller_common import bind, write, manifest

TARGET='For natural numbers a and b, if a=b, then a+0=b.'


def dependency(key='B001', category=1, *, port=None, compatibility=None, typ='∀ n : ℕ, n + 0 = n', proof='intro n; exact Nat.add_zero n'):
    compatibility=compatibility or {1:'native',2:'adapted',3:'internal',4:'unresolved'}[category]
    if category in {2,4} or compatibility=='adapted':port=port or 'E'+key[1:]
    return {'id':key,'category':category,'statement':'For every natural number n, n+0=n.',
        'origin':{'kind':{1:'mathlib',2:'lean-library',3:'derivation',4:'textbook'}[category],
            'reference':'SYNTHETIC attribution control; the actual native proof is elementary.',
            'revision':'SYNTHETIC fixture version','evidence':[{'input':'problem.md'}] if category==4 else []},
        'compatibility':compatibility,'uses':['B001'] if category==3 else [],'port':port,
        'lean':None if category==3 else {'type':typ,'proof':None if category==4 else proof},
        'justification':'Software fixture only; source and semantic classifications are not independently certified.'}


def artifact(*rows):
    return {'version':basis.VERSION,'full_target':TARGET,
        'proof':'From a=b and the additive identity a+0=a, obtain a+0=b.',
        'dependencies':list(rows),'replacements':[],'lean_header':'import Mathlib\n'}


def checked_context(root, value, *, approved=False):
    root=Path(root);inputs=root/'inputs';inputs.mkdir(parents=True)
    (inputs/'problem.md').write_text(TARGET+'\nSYNTHETIC source fixture, not a publication.\n')
    manifest(inputs);write(root/'basis.json',value)
    declarations,checks,roots=basis.declarations(value)
    native=basis_native.check(value['lean_header']+declarations,checks,roots,root/'native')
    if not native['passed']:raise AssertionError(ir.load(root/'native/compiler.json'))
    residual=sorted(r['id'] for r in value['dependencies'] if r['category']==4)
    context={'version':basis.VERSION,'formalization':'unconditional','full_target':value['full_target'],
        'basis':bind(root/'basis.json'),'native':bind(root/'native/check.json'),
        'original_inputs':[bind(inputs/'problem.md')],
        'evidence':basis.evidence_bindings(value,inputs,root),'approval':None,'residual_class4':residual}
    if approved:
        context['approval']={'state':'USER_DECIDED','incident':'SYNTHETIC-USER-CHOICE',
            'control':{'incident':'SYNTHETIC-USER-CHOICE','action':'accept-conditional'},
            'checkpoint':{'basis':context['basis'],'residual_class4':residual}}
    return context
