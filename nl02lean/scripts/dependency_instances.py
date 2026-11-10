"""Checked universe instances of direct Lean dependencies. No new graph premises."""
from functools import lru_cache
import json
import re

import ir
import artifact_protocol as protocol
from payload_protocols import parameter_schema


def step_schema():
    strings=protocol.array(protocol.STRING)
    arguments=protocol.array(protocol.choice(protocol.TEXT,{'type':'integer','minimum':1}))
    use=protocol.obj({'args':arguments,'parameters':protocol.array(parameter_schema()),
                      'expected':protocol.TEXT,'explicit':{'type':'boolean'}},required=['args'])
    instance=protocol.obj({'levels':strings,'uses':protocol.array(use,minItems=1)})
    return protocol.obj({'id':protocol.TEXT,'statement':protocol.TEXT,'inputs':strings,
        'source_steps':strings,'explanation':protocol.TEXT,'background_notes':strings,
        'shared_lemma':protocol.TEXT,'universe_params':strings,
        'input_instances':protocol.obj({},extra=protocol.array(instance,minItems=1)),
        'representations':protocol.array(protocol.obj({'object':protocol.TEXT,'view':protocol.TEXT,'expression':protocol.TEXT})),
        'bridges':protocol.array(protocol.obj({'input':protocol.TEXT,'object':protocol.TEXT,'from':protocol.TEXT,
                                               'to':protocol.TEXT,'explanation':protocol.TEXT}))},
        required=['id','statement','inputs','source_steps','explanation'])


STEP_FIELDS = set(step_schema()['properties'])
ANONYMOUS = re.compile(r'\b(?:Type|Sort)\s*\*')
LEVEL = re.compile(r'[A-Za-z0-9_+() ]+')
USE_PARSER = '''
open Lean Elab Term
elab "yui_use_term% " text:str : term <= expectedType => do
  let parsed ← ofExcept <| Parser.runParserCategory (← getEnv) `term text.getString
  let located := parsed.rewriteBottomUp fun node => node.setInfo text.raw.getHeadInfo
  Term.elabTerm located expectedType
'''


def quoted_term(text):
    return '(yui_use_term% '+json.dumps(text, ensure_ascii=False)+')'


def check_fields(step, location):
    extra = set(step) - STEP_FIELDS
    ir.need(not extra, f'{location}: unsupported step fields {sorted(extra)}')


@lru_cache(maxsize=1)
def sources():
    from workflow_execution import block_module
    return block_module(ir.ROOT / 'workflow', 'lean_input_instances')


def validate(step, nodes, prepared=None):
    sid = step['id']
    check_fields(step,sid)
    params = step.get('universe_params', [])
    ir.need(isinstance(params, list) and all(isinstance(p,str) and ir.IDENTIFIER.fullmatch(p) for p in params)
            and len(set(params)) == len(params), f'{sid}/universe_params: expected distinct universe names')
    instances = step.get('input_instances', {})
    ir.need(isinstance(instances, dict) and set(instances) <= set(step['inputs']),
            f'{sid}/input_instances: use direct input IDs')
    for dep, rows in instances.items():
        where = f'{sid} <- {dep}'
        source = sources().resolve(dep, nodes, prepared or {})
        ir.need(source is not None, f'{where}: specialization requires a direct internal input or a checked polymorphic foundation declaration')
        ir.need(isinstance(rows,list) and rows, f'{where}: declare at least one instance')
        for row in rows:
            ir.need(isinstance(row,dict) and set(row)=={'levels','uses'}, f'{where}: expected levels and uses')
            levels = row['levels']
            ir.need(isinstance(levels,list) and len(levels)==len(source.levels)
                    and all(isinstance(s,str) and LEVEL.fullmatch(s) and s.strip()
                            and not re.search(r'\b_\b',s) for s in levels),
                    f'{where}: levels must match the producer universe_params in order ({source.levels})')
            ir.need(isinstance(row['uses'],list) and row['uses'], f'{where}: supply actual consumer applications')
            for use in row['uses']:
                ir.need(isinstance(use,dict) and {'args'} <= set(use) <= {'args','parameters','expected','explicit'},
                        f'{where}: expected args and optional parameters/expected/explicit')
                ir.need(type(use.get('explicit',False)) is bool, f'{where}: explicit must be boolean')
                local = use.get('parameters',[])
                ir.need(isinstance(local,list), f'{where}: expected a list of use parameters')
                names = set()
                for p in local:
                    ir.need(isinstance(p,dict) and {'name','type'} <= set(p) <= {'name','type','binder_kind'}
                            and isinstance(p['name'],str) and ir.IDENTIFIER.fullmatch(p['name'])
                            and p['name'] not in names and not p['name'].startswith('h_'),
                            f'{where}: invalid or shadowing use parameter')
                    names.add(p['name']); ir.type_text(p['type']); ir.parameter_text(p)
                args = use['args']
                ir.need(isinstance(args,list) and (args or 'expected' in use), f'{where}: give arguments or an expected type')
                if 'expected' in use: ir.type_text(use['expected'])
                for arg in args:
                    if type(arg) is int:
                        ir.need(arg > 0, f'{where}: projections start at 1')
                    else:
                        ir.type_text(arg)


def require_instances(nodes):
    """At current preflight, an escaping anonymous universe needs an explicit use."""
    for sid, step in nodes.items():
        for key in step['inputs']:
            if key not in nodes:
                continue
            producer = nodes[key]
            if ANONYMOUS.search(producer['statement']):
                raise ir.Invalid(f'{sid} <- {key}: name internal Type*/Sort* levels with universe_params '
                                 'and record their input_instances and actual uses before proof dispatch')
            if producer.get('universe_params') and key not in step.get('input_instances',{}):
                raise ir.Invalid(f'{sid} <- {key}: missing input_instances for a universe-polymorphic producer')


def level_suffix(levels):
    return sources().suffix(levels)


def with_args(name, args):
    return ' '.join([name, *args])


def type_header(c, nodes, keys):
    if not keys:
        return ''
    context = ir.binder_text(c)
    lines = ['namespace YuiPortTypes']
    for key in sorted(keys):
        if key not in nodes:
            # Foundation signatures are closed over their own declaration levels.
            lines.append(f"abbrev {key} : Prop :=\n  {ir.premises(c)[key]}")
            continue
        step = nodes[key]
        levels = level_suffix(step.get('universe_params', []))
        lines.append(f"abbrev {key}{levels} {context} : Prop :=\n  {step['statement']}")
    return '\n'.join(lines) + '\nend YuiPortTypes\n'


def universe_line(step):
    names = step.get('universe_params', [])
    return 'universe ' + ' '.join(names) + '\n' if names else ''


def level_check(nodes, consumers):
    """Find escaping levels even when the statement hides them behind a Lean abbreviation."""
    if not consumers:
        return ''
    policies = []
    for producer, uses in sorted(consumers.items()):
        names = ', '.join(json.dumps(v) for v in nodes[producer].get('universe_params', []))
        label = ', '.join(uses)+' <- '+producer
        policies.append(f'(`YuiPortTypes.{producer}, [{names}], {json.dumps(label)})')
    return '''
open Lean Elab Command in
run_cmd do
  let specs : List (Name × List String × String) := [''' + ', '.join(policies) + ''']
  for (name, declared, label) in specs do
    let info ← getConstInfo name
    let publicLevels := (collectLevelParams {} info.type).params.toList
    let missing := info.levelParams.filter fun l => !publicLevels.contains l && !declared.contains l.toString
    unless missing.isEmpty do
      throwError "{label}: undeclared internal universes {missing}; name them in universe_params and supply input_instances"
'''


def ports(c, nodes, step):
    source_types = ir.premises(c)
    args = [p['name'] for p in c['parameters']]
    bindings = []
    for key in step['inputs']:
        rows = step.get('input_instances',{}).get(key)
        if rows is None:
            typ = nodes[key]['statement'] if key in nodes else source_types[key]
            bindings.append({'id':key,'binder':'h_'+key,'type':typ})
            continue
        for i,row in enumerate(rows):
            suffix = level_suffix(row['levels'])
            name = 'h_'+key + (f'_{i+1}' if i else '')
            inner = key in nodes
            bindings.append({'id':key,'binder':name,'type':with_args(f'@YuiPortTypes.{key}{suffix}',args if inner else []),
                             'producer_statement':nodes[key]['statement'] if inner else source_types[key],
                             'levels':row['levels'],'uses':row['uses']})
    return bindings


def probes(c, step, ports, binders):
    out = []
    for port in ports:
        for i,use in enumerate(port.get('uses',[]),1):
            local = use.get('parameters',[])
            ir.need(not {p['name'] for p in local} & {p['name'] for p in c['parameters']},
                    f"{step['id']} <- {port['id']}: use parameters shadow the public context")
            context = ' '.join([binders, *(ir.parameter_text({**p,'type':quoted_term(p['type'])})
                                            for p in local)]).strip()
            term = ('@' if use.get('explicit') else '') + port['binder']
            for arg in use['args']:
                term = f'({term}).{arg}' if type(arg) is int else f'({term} {quoted_term(arg)})'
            if 'expected' in use:
                term = f"({term} : {quoted_term(use['expected'])})"
            label = f"{step['id']} <- {port['id']} ({port['binder']}, use {i})"
            out.append('-- YUI-USE '+label+'\nnoncomputable '+ir.checked_expression(
                '__use_'+step['id']+'_'+port['binder']+f'_{i}',term,context)+'-- YUI-END-USE\n')
    return ''.join(out)


def connectors(c, nodes, order, terminal, *, preflight):
    """Keep the connected producer a theorem constant until each use selects its levels."""
    args = [p['name'] for p in c['parameters']]
    context = ir.binder_text(c)
    roots = ir.premises(c)
    needed = {}
    out = []
    check_arg = ['__yui_preflight'] if preflight else []
    check_binder = ' (__yui_preflight : False)' if preflight else ''
    for key in order:
        step = nodes[key]
        used = set()
        for dep in step['inputs']:
            if dep in nodes:
                used.update(needed[dep])
            elif dep not in step.get('input_instances', {}):
                used.add(dep)
        needed[key] = [p for p in roots if p in used]
        binders = ' '.join(f'(h_{p} : {roots[p]})' for p in needed[key])
        ins = []
        for port in ports(c, nodes, step):
            dep = port['id']
            if dep in nodes or 'levels' in port:
                source = sources().resolve(dep, nodes, c.get('prepared_instances', {}).get('ports', {}))
                context_args = args + ['h_'+p for p in needed.get(dep, [])] + check_arg
                ins.append(sources().application(source, port.get('levels', []), context_args))
            else:
                ins.append(port['binder'])
        levels = level_suffix(step.get('universe_params', []))
        theorem_name = '__preflight_'+key if preflight else key
        call = with_args('@'+theorem_name,args+ins+check_arg)
        out.append(f"private theorem __connected_{key}{levels} {context} {binders}{check_binder} :\n"
                   f"    {step['statement']} := by\n  exact {call}\n")
    final = with_args('@__connected_'+terminal,args+['h_'+p for p in needed[terminal]]+check_arg)
    binders = ' '.join(f'(h_{p} : {typ})' for p,typ in roots.items())
    declaration = 'private theorem __preflight_P' if preflight else 'theorem P'
    out.append(f"{declaration} {context} {binders}{check_binder} : {c['conclusion']['type']} := by\n  exact {final}\n")
    return '\n'.join(out)


def failed_uses(source, output):
    """Map Lean's actual error lines to the generated application, without parsing its mathematics."""
    failed_lines = {int(n) for n in re.findall(r'Check\.lean:(\d+):\d+: error:', output)}
    labels = []
    current = None
    for number,line in enumerate(source.splitlines(),1):
        if line.startswith('-- YUI-USE '): current = line.removeprefix('-- YUI-USE ')
        if line == '-- YUI-END-USE': current = None
        if number in failed_lines and current and current not in labels:
            labels.append(current)
    return labels
