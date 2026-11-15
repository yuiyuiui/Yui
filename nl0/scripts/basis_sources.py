"""Canonical pre-freeze sources; native identity is checked by Lean, never prose."""
from copy import deepcopy
from pathlib import Path

import ir
import lean_names
from controller_common import verify_bindings, write

PREFIX='__native__'
FIELDS=('declaration','module','signature','declaration_kind','mathlib_commit','source_path','source_sha256')


def direct(row):
    return row['category']==1 and row['compatibility']=='native'


def checks(rows):
    return [(PREFIX+r['id'],r['origin']['declaration'],'decl:YuiBasis.'+r['id'])
            for r in rows if direct(r)]


def native_sources(inspected, checks, environment):
    """Bind the actual imported theorem and source bytes from this one inspection."""
    selected=[c for c in checks if c[0].startswith(PREFIX)]
    if not selected:return {}
    ir.need(isinstance(inspected,dict),'Missing native source inspection')
    declarations={r['name']:r for r in inspected['dependencies']['declarations']}
    comparisons={r['id']:r for r in inspected['comparisons']}
    lock=ir.load_lock()
    ir.need(environment['mathlib_commit']==lock['mathlib']['rev'],'Changed source environment')
    root=Path(lock['mathlib']['local_path']).resolve()
    sources={}
    for key,name,expected in selected:
        name=lean_names.canonical(name);row=declarations.get(name)
        comparison=comparisons.get(key,{})
        ir.need(comparison.get('definitionally_equal') is True,
                key+': native source must supply the whole proposition; use a prepared adaptation/derivation')
        ir.need(row and row['kind']=='theorem' and row['imported'] and not row['project_owned']
                and row['module'].startswith('Mathlib.'),key+': source must be an imported proved Mathlib theorem')
        relative=row['module'].replace('.','/')+'.lean';file=root/relative
        ir.need(file.resolve().is_relative_to(root) and file.is_file(),key+': missing actual Mathlib source')
        sources[key[len(PREFIX):]]={'declaration':name,'module':row['module'],'declaration_kind':'theorem',
            'signature':'@'+name+' : '+row['type'],'source_path':relative,'source_sha256':ir.digest(file),
            'mathlib_commit':environment['mathlib_commit']}
    return sources


def material(artifact, native):
    import basis_native
    import basis_graph
    verify_bindings([native])
    receipt=basis_native.verify(native['path'])
    sources=receipt.get('native_sources',{})
    ir.need(set(sources)=={r['id'] for r in artifact['dependencies'] if r['lean'] is not None and direct(r)},'Changed native source inventory')
    result={}
    for row in artifact['dependencies']:
        key=row['id']
        if row['lean'] is None:
            result[key]={'mode':'not_prepared'}
            continue
        item={**basis_graph.handoff().source_reference(row),'lean_type':row['lean']['type']}
        if item['mode']=='native':
            ir.need(lean_names.canonical(row['origin']['declaration'])==sources[key]['declaration'],
                    key+': changed frozen native declaration')
            item['declaration']=sources[key]['declaration'];item['source']=deepcopy(sources[key])
        result[key]=item
    return result


def inherit(directory, context, registry, identifier, row, source):
    """Publish an explicitly inherited probe, with no new compiler/model request."""
    expected=material(registry,context['native'])[row['id']]['source']
    for field in FIELDS:
        if field in source and source[field]!=expected[field]:
            raise ValueError(f'{identifier}: changed frozen source {field} for {row["id"]}')
    report={'probe_version':1,'exit_code':0,'lean_version':ir.load_lock()['lean']['version'],
            'mathlib_commit':expected['mathlib_commit'],'sources':{identifier:expected},
            'inheritance':{'version':'yui-basis-source-1','basis_id':row['id'],'context':deepcopy(context)},
            'scope':'Inherited pre-freeze kernel source identity and complete type check; no new native execution or applicability verdict.'}
    path=Path(directory)/'library'/('basis-'+identifier)/'library-sources.json'
    write(path,report)
    source.update(expected)
    source['evidence']=[{'path':str(path.relative_to(directory)),'sha256':ir.digest(path)}]


def verify_probe(report, identifier, directory, spec, graph):
    """Check the portable projection against the same bound foundation inputs.

    The live NL0 author, Audit A preparation and Lean freeze separately call
    basis.source_context/verify_context for actual native and reviewer evidence.
    A portable delivery retains their accepted projection and Audit A hashes;
    reading it must not depend on disposable controller directories.
    """
    import basis
    import nl0
    origin=report['inheritance']
    ir.need(origin.get('version')=='yui-basis-source-1','Unknown inherited basis source')
    def document(name):
        refs=[r for r in spec['inputs'] if Path(r['path']).name==name]
        ir.need(len(refs)==1,'Missing or duplicate inherited foundation input: '+name)
        return nl0.load(nl0.local_path(Path(directory),refs[0]['path']))
    context=document(basis.CONTEXT);registry=document('basis-registry.json')
    ir.need(origin['context']==context and context['version']==basis.CONTEXT_VERSION,
            'Inherited source differs from the bound foundation context')
    row=basis.basis_graph.handoff().by_port(registry,graph).get(identifier)
    ir.need(row and direct(row) and row['id']==origin['basis_id'],'Changed inherited foundation identity')
    source=report['sources'].get(identifier,{})
    ir.need(set(report['sources'])=={identifier} and source.get('declaration')==lean_names.canonical(row['origin']['declaration']),
            'Changed inherited native declaration')
    ir.need(report['exit_code']==0 and report['mathlib_commit']==spec['pins']['mathlib_commit']
            and report['lean_version']==ir.load_lock()['lean']['version'],'Changed inherited source environment')

