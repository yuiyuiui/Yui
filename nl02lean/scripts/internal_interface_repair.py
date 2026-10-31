"""Bound same-case T-plan revisions; original source and public contract stay fixed."""
from pathlib import Path

import ir
from controller_common import bind

SCHEMA = 'internal-interface-repair-1'
PROTECTED = ('id', 'pins', 'header', 'parameters', 'premises', 'conclusion',
             'source_steps', 'objects', 'shared_obligations', 'representation')


def context(directory):
    import workflow, interface_review
    directory = Path(directory).resolve()
    frozen = workflow.bound(directory)
    ir.need(frozen.get('interface_review'), 'Internal repair needs actual semantic authority')
    interface_review.verify_receipt(frozen['interface_review'], frozen['contract'],
                                   frozen['plan'], ir.digest(frozen['authority']['graph']))
    return {'schema': SCHEMA, 'workflow': str(directory),
            'contract': bind(Path(frozen['contract'])), 'plan': bind(Path(frozen['plan'])),
            'review': bind(Path(frozen['interface_review']))}


def unchanged(value):
    import source_preparation, workflow, interface_review
    ir.need(value.get('schema') == SCHEMA, 'Unknown internal repair authority')
    for key in ('contract', 'plan', 'review'):
        source_preparation.unchanged(value[key])
    frozen = workflow.bound(value['workflow'])
    ir.need(all(str(Path(frozen[key]).resolve()) == value[name]['path'] for key, name in
                [('contract', 'contract'), ('plan', 'plan'), ('interface_review', 'review')]),
            'Internal repair authority belongs to another frozen workflow')
    interface_review.verify_receipt(value['review']['path'], value['contract']['path'],
        value['plan']['path'], ir.digest(frozen['authority']['graph']))
    return frozen


def protect_candidate(value, prior):
    """The author may edit steps only; a rejected edit stays author feedback."""
    ir.need({k: v for k, v in value.items() if k != 'steps'} ==
            {k: v for k, v in prior.items() if k != 'steps'},
            'Internal repair may change T steps only; preserve H/E/P, public definitions and source outputs')
    ir.need(value['steps'] != prior['steps'], 'Repair the located internal defect; unchanged candidate')


def verify_contract(value, contract):
    old = ir.contract(value['contract']['path']); new = ir.contract(contract)
    ir.need(all(old.get(k) == new.get(k) for k in PROTECTED)
            and {k:v for k,v in old['source'].items() if k!='path'} ==
                {k:v for k,v in new['source'].items() if k!='path'},
            'Internal repair changed the protected source/public contract')


def delta(before, after):
    old = {s['id']: s for s in before['steps']}; new = {s['id']: s for s in after['steps']}
    changed = {sid for sid in old.keys() | new.keys() if old.get(sid) != new.get(sid)}
    affected = set(changed)
    dependencies={sid:set(old.get(sid,{}).get('inputs',[])) | set(new.get(sid,{}).get('inputs',[]))
                  for sid in old.keys() | new.keys()}
    while True:
        consumers = {sid for sid, inputs in dependencies.items() if inputs & affected}
        expanded = affected | consumers
        if expanded == affected:break
        affected = expanded
    return {'changed_steps': sorted(changed), 'affected_steps': sorted(affected)}


def verify_revision(value, contract, plan):
    unchanged(value); verify_contract(value, contract)
    before = ir.load(value['plan']['path']); after = ir.load(plan)
    actual = delta(before, after)
    ir.need(actual['changed_steps'], 'Internal repair has no changed obligation')
    for key in ('changed_steps', 'affected_steps'):
        if key in value:ir.need(value[key] == actual[key], 'Internal repair impact map changed')
    return actual
