"""The frozen global NL0 handoff and the active closure of its foundation DAG."""
from copy import deepcopy
import re

import artifact_protocol as p

VERSION = 'yui-basis-2'
PROP = {'type':'string','pattern':r'^(?:[HEMN]\d{3,}|P)$'}
BASIS = {'type':'string','pattern':r'^B\d{3,}$'}


def schema():
    return p.obj({'propositions':p.array(p.obj({'id':PROP,'statement':p.TEXT}),minItems=1),
        'inferences':p.array(p.obj({'id':{'type':'string','pattern':r'^R\d{3,}$'},
            'inputs':p.array(PROP,uniqueItems=True),'output':PROP,
            'basis':p.array(BASIS,uniqueItems=True)}),minItems=1)})


def indexed(rows):
    result = {r['id']:r for r in rows}
    if len(rows)!=len(result):
        raise ValueError('Duplicate graph identifier')
    return result


def projection(graph):
    return ({r['id']:r['statement'] for r in graph['propositions']},
            {r['id']:(sorted(r['inputs']),r['output']) for r in graph['inferences']})


def active(value, *, prune=False):
    graph = value['global_graph']
    p.validate(graph,schema())
    props, steps = indexed(graph['propositions']), indexed(graph['inferences'])
    rows = indexed(value['dependencies'])
    by_port = {r['port']:r for r in rows.values() if r['port']}
    if len(by_port)!=sum(bool(r['port']) for r in rows.values()):raise ValueError('Duplicate basis port')
    origins = {}
    for key,step in steps.items():
        out = step['output']
        if out in origins or out not in props or not (out.startswith('N') or out=='P'):
            raise ValueError('Invalid or repeated inference output '+out)
        if set(step['inputs'])-props.keys() or set(step['basis'])-rows.keys():
            raise ValueError('Unknown global input or basis dependency at '+key)
        expected = {by_port[k]['id'] for k in step['inputs'] if k in by_port}
        ported = {k for k in step['basis'] if rows[k]['port']}
        if expected != ported or any(rows[k]['category']!=1 and not rows[k]['port'] for k in step['basis']):
            raise ValueError('Basis use and frozen input ports disagree at '+key)
        origins[out] = step
    if 'P' not in origins or set(origins)!={k for k in props if k=='P' or k.startswith('N')}:
        raise ValueError('Every derived proposition needs exactly one producer')
    seen=set()
    visiting=set()
    selected=set()

    def visit(key):
        if key in visiting:
            raise ValueError('Cyclic global proof or basis dependencies: '+key)
        if key in seen:
            return
        visiting.add(key)
        if key in rows:
            selected.add(key)
            children = rows[key]['uses']
        elif key in origins:
            children = origins[key]['inputs']+origins[key]['basis']
        elif key in props:
            children = []
        else:
            raise ValueError('Unknown foundation dependency '+key)
        for other in children:
            visit(other)
        seen.add(key)
        visiting.remove(key)
    visit('P')
    if set(props)-seen-{k for k in props if k.startswith('H')}:
        raise ValueError('Disconnected proposition in the frozen proof route')
    for k,r in props.items():
        if k.startswith('E') and k not in by_port:
            raise ValueError('External proposition has no basis authority: '+k)
        if k in by_port and r['statement']!=by_port[k]['statement']:
            raise ValueError('Basis statement differs from frozen proposition '+k)
    if not prune and selected!=set(rows):
        raise ValueError('Unused basis rows must be removed from the active proof route')
    for key in selected:
        port=rows[key]['port']
        if port and port not in props:
            raise ValueError('Only direct consumers may have a global port: '+key)
    return selected


def optimize(value):
    """Keep the submitted alternatives in the draft; only pay for the active closure."""
    selected=active(value,prune=True)
    result=deepcopy(value)
    result['dependencies']=[r for r in result['dependencies'] if r['id'] in selected]
    for mapping in result['replacements']:
        if set(mapping['replacement'])-selected:
            raise ValueError('Resolve the original replacement map before pruning alternatives')
    return result


def verify_handoff(registry, graph):
    if registry['version']==VERSION and projection(registry['global_graph'])!=projection(graph):
        raise ValueError('NL0 changed a frozen global statement, inference or input edge; revise the basis graph first')
