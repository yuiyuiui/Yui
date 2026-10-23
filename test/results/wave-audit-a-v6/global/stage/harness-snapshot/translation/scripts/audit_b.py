#!/usr/bin/env python3
"""NL0/Lean concordance ledger, kernel inspection and review-bound Audit B.

Semantic reviews remain actual reviewer work. Pending templates never pass.
This adapter audits the candidate's generated conditional graph, not arbitrary
Lean repositories or the truth of external publications.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

import ir
import source_preparation
from shared_lemmas import hashed

HERE = Path(__file__).resolve().parents[1]
VERSION = 1
NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$')
KINDS = {'hypothesis','external','mathlib','internal','target'}
FOUNDATION = {
    'Eq.refl','Eq.rec','Eq.recOn','Eq.ndrec','Eq.ndrecOn','Eq.casesOn',
    'Eq.symm','Eq.trans','Eq.subst','Eq.mp','Eq.mpr','Eq.congr','cast',
    'congrArg','congrFun','congr','funext','propext','Quot.sound',
    'True.intro','False.elim','False.rec','False.recOn','False.casesOn',
    'And.intro','And.left','And.right','And.rec','And.recOn','And.casesOn',
    'Or.inl','Or.inr','Or.elim','Or.rec','Or.recOn','Or.casesOn',
    'Iff.intro','Iff.mp','Iff.mpr','Iff.rfl','Iff.refl','Iff.symm','Iff.trans',
    'Exists.intro','Exists.elim','Exists.rec','Exists.recOn','Exists.casesOn',
    'HEq.refl','HEq.rec','HEq.ndrec','HEq.symm','HEq.trans','eq_of_heq','heq_of_eq',
    'Classical.choice'}
CLASSICAL = {'Classical.em','Classical.byContradiction','Classical.not_not','byContradiction'}
AXIOMS = {'propext','Classical.choice','Quot.sound'}
REVIEW_CHECKS = ('inventory_and_scope','parameters_definitions_and_representations',
                 'complete_signature_and_hidden_fields','direct_dependencies_and_route',
                 'shared_proofs_and_final_closure','library_and_calculation_correspondence',
                 'warnings_and_trusted_environment')


def environment():
    lock=ir.load_lock();lean=Path(lock['lean']['local_path'])/'bin/lean'
    ir.need(ir.digest(lean)==lock['lean']['binary_sha256'],'pinned Lean binary changed')
    ml=Path(lock['mathlib']['local_path'])
    revision=subprocess.run(['git','-C',str(ml),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
    dirty=subprocess.run(['git','-C',str(ml),'status','--porcelain','--untracked-files=no'],capture_output=True,text=True,check=True).stdout.strip()
    ir.need(revision==lock['mathlib']['rev'] and not dirty,'pinned mathlib source changed')
    ir.need(ir.digest(ml/'lake-manifest.json')==lock['mathlib']['manifest_sha256'],'pinned dependency manifest changed')
    return {'lean_binary_sha256':ir.digest(lean),'mathlib_commit':revision,
            'mathlib_tracked_changes':dirty,'dependency_manifest_sha256':ir.digest(ml/'lake-manifest.json')}


def source_data(cpath, *, graph=None, spec=None, audit_a=None, incremental=None, fragment=None):
    c = ir.contract(cpath)
    if graph is not None:
        ir.need(spec is not None and fragment is None, 'provide graph/spec or a fragment inventory')
        data, authority_paths = source_preparation.read_source(graph, spec, audit_a, incremental)
        result,g,s,props,inferences,defs,*_ = data
        inventory = {'scope':'whole_structured_nl0','propositions':list(props.values()),
            'parameters':s['parameters'],'definitions':list(defs.values()),'logic':s['logic'],
            'inferences':list(inferences.values()),'full_target':s['full_target'],
            'audit_a_current_passed':result['current_standard_receipt_valid'],
            'audit_a_status':result.get('audit_status','UNVERIFIED'),
            'audit_a_unresolved_reviews':result.get('unresolved_reviews',[]),
            'audit_a_review_disclosure':result.get('reviewer'),
            'source_hashes':{'graph':ir.digest(graph),'spec':ir.digest(spec),
                             'audit_a':ir.digest(audit_a) if audit_a else None,
                             'incremental':ir.digest(incremental) if incremental else None}}
        inputs = authority_paths
    else:
        ir.need(fragment is not None and audit_a is None and incremental is None, 'an independent source inventory is required')
        inventory = ir.load(fragment)
        ir.need(inventory['scope'] == 'development_fragment', 'plain inventories cannot claim whole NL0 coverage')
        ir.need(inventory['source_sha256'] == c['source']['sha256'], 'fragment inventory/source mismatch')
        inventory['audit_a_current_passed'] = False
        inventory['audit_a_status'] = 'DEVELOPMENT_SOURCE_NOT_AUDIT_A_CERTIFIED'
        inputs = [Path(fragment)]
    props = inventory['propositions']
    ir.need(len({p['id'] for p in props}) == len(props), 'duplicate source proposition')
    ir.need(all(p['kind'] in KINDS and p['statement'].strip() for p in props), 'invalid source proposition')
    ir.need([p['id'] for p in props if p['kind']=='target'] == ['P'], 'source must have one target P')
    definitions = inventory.get('definitions',[])
    ir.need(len({d['id'] for d in definitions}) == len(definitions), 'duplicate source definition')
    return inventory, inputs


def proof_bundle(cpath, ppath, bpath):
    plan = ir.load(ppath)
    _, nodes, _ = ir.validate(cpath,plan)
    bundle = ir.load(bpath)
    ir.need(bundle['contract_sha256'] == ir.digest(cpath), 'stale proof contract')
    if 'plan_sha256' in bundle:
        ir.need(bundle['plan_sha256'] == ir.digest(ppath), 'stale proof plan')
    else:
        ir.need(bundle.get('plan_digest') == hashed(plan), 'stale proof plan digest')
    ir.need(set(bundle['proofs']) == set(nodes), 'missing/extra proof bodies')
    for body in bundle['proofs'].values(): ir.proof_text(body)
    return plan,bundle['proofs']


def full_type(c, output, inputs):
    binders = [ir.parameter_text(p) for p in c['parameters']]
    binders += [f"(h_{p['id']} : {p['type']})" for p in inputs]
    return ('∀ '+' '.join(binders)+', ' if binders else '') + output


def prepare(cpath,ppath,bpath,out,**source):
    env=environment()
    cpath,ppath,bpath = [Path(p).resolve() for p in (cpath,ppath,bpath)]
    c = ir.contract(cpath)
    plan,proofs = proof_bundle(cpath,ppath,bpath)
    inventory, source_paths = source_data(cpath,**source)
    out.mkdir(parents=True,exist_ok=False)
    ir.write(out/'source-inventory.json',inventory)
    mapping = {'version':VERSION,'source_inventory_sha256':ir.digest(out/'source-inventory.json'),
               'entries':{},'calculation_links':{}}
    premises = {p['id']:p for p in c['premises']}
    retained = [p for p in c['premises'] if p['kind']!='mathlib']
    for item in inventory['propositions']:
        sid = item['id']
        row = {'selector':None,'expected_type':None}
        if sid == 'P':
            row = {'selector':'decl:AuditBExport.P',
                   'expected_type':full_type(c,c['conclusion']['type'],retained)}
        elif sid in premises:
            before = c['premises'][:next(i for i,p in enumerate(c['premises']) if p['id']==sid)]
            row = {'selector':'premise:'+sid,'expected_type':full_type(c,premises[sid]['type'],before)}
        if item['kind']=='mathlib':
            row.update({'library_declaration':item.get('source',{}).get('declaration'),
                        'library_type':None,'library_term':None})
        mapping['entries'][sid] = row
    for definition in inventory.get('definitions',[]):
        mapping['entries'][definition['id']] = {'selector':None,'expected_type':None}
    ir.write(out/'mapping.json',mapping)
    source_file = (cpath.parent/c['source']['path']).resolve()
    originals = [cpath,ppath,bpath,source_file,*[p.resolve() for p in source_paths]]
    tools = [Path(__file__),Path(source_preparation.__file__),HERE/'scripts/audit_probe.lean',Path(ir.__file__),
             HERE/'scripts/shared_lemmas.py',HERE.parent/'scripts/nl0.py',HERE.parent/'scripts/closure.py',
             ir.ROOT/'scripts/pilot_common.py',ir.ROOT/'toolchain/lock.json']
    inputs = out/'input-bytes';inputs.mkdir()
    bound = []
    for i,p in enumerate(dict.fromkeys(originals)):
        destination = inputs/f'{i:03d}-{p.name}'
        shutil.copyfile(p,destination)
        bound.append({'path':str(p),'sha256':ir.digest(p),'snapshot':str(destination.relative_to(out))})
    snapshots = out/'tool-snapshot';snapshots.mkdir()
    for p in tools: shutil.copyfile(p,snapshots/p.name)
    ir.write(out/'manifest.json',{'version':VERSION,'contract':str(cpath),'plan':str(ppath),'proofs':str(bpath),
        'inputs':bound,'source_inventory_sha256':ir.digest(out/'source-inventory.json'),
        'tool_sha256':{str(p.resolve()):ir.digest(p) for p in tools},
        'authority':{key:str(Path(value).resolve()) if value is not None else None for key,value in source.items()},
        'environment':env,'review_status':'UNVERIFIED','scope':inventory['scope']})
    return {'status':'AUDIT-B-PREPARED','semantic_review':'UNVERIFIED','directory':str(out)}


def bound_inputs(out):
    manifest = ir.load(out/'manifest.json')
    ir.need(manifest['version']==VERSION,'unsupported Audit B manifest')
    for item in manifest['inputs']:
        ir.need(ir.digest(item['path'])==item['sha256'],'stale audit input: '+item['path'])
        ir.need(ir.digest(out/item['snapshot'])==item['sha256'],'changed audit snapshot')
    for path,sha in manifest['tool_sha256'].items():
        ir.need(ir.digest(path)==sha,'changed audit tool; start a new audit run')
    ir.need(ir.digest(out/'source-inventory.json')==manifest['source_inventory_sha256'],'changed source inventory')
    ir.need(environment()==manifest['environment'],'changed audit environment')
    authority={key:Path(value) if value is not None else None for key,value in manifest['authority'].items()}
    current,_=source_data(Path(manifest['contract']),**authority)
    ir.need(hashed(current)==hashed(ir.load(out/'source-inventory.json')),'changed source/Audit A authority')
    return manifest


def dependency_correspondence(inventory,mapping,plan,declarations):
    """Stop at mapped source N nodes; implementation-only T helpers may expand."""
    nodes={s['id']:s for s in plan['steps']}
    boundary={row['selector'][len('decl:Translation.'):]:sid for sid,row in mapping['entries'].items()
              if row['selector'].startswith('decl:Translation.T')}
    byname={d['name']:d for d in declarations}
    library={row['library_declaration']:sid for sid,row in mapping['entries'].items() if row.get('library_declaration')}
    def constants(name,seen):
        if name in seen: return set()
        seen.add(name)
        if name in library: return {library[name]}
        d=byname.get(name)
        if not d or d['imported']: return set()
        return set().union(*(constants(x,seen) for x in d['direct_constants'])) if d['direct_constants'] else set()
    def inputs(tid,start,seen):
        if tid not in nodes: return {tid}
        if tid!=start and tid in boundary: return {boundary[tid]}
        if tid in seen: return set()
        seen.add(tid)
        result=set().union(*(inputs(dep,start,seen) for dep in nodes[tid]['inputs'])) if nodes[tid]['inputs'] else set()
        result |= constants('Translation.'+tid,set())
        return result
    rows=[]
    for inference in inventory.get('inferences',[]):
        source_id=inference['output'];selector=mapping['entries'][source_id]['selector']
        tid=plan['terminal'] if source_id=='P' else selector.removeprefix('decl:Translation.')
        actual=inputs(tid,tid,set());expected=set(inference['inputs'])
        rows.append({'inference':inference['id'],'source_output':source_id,'source_inputs':sorted(expected),
                     'actual_boundary_inputs':sorted(actual),'matched':actual==expected})
    return rows


def validate_mapping(c,inventory,mapping):
    ids = {p['id'] for p in inventory['propositions']} | {d['id'] for d in inventory.get('definitions',[])}
    ir.need(mapping['version']==VERSION and set(mapping['entries'])==ids,'missing/extra source correspondence')
    ir.need(mapping['entries']['P']['selector']=='decl:AuditBExport.P','audit must inspect the actual assembled root')
    source_props = {p['id']:p for p in inventory['propositions']}
    for p in c['premises']:
        ir.need(p['id'] in source_props and source_props[p['id']]['kind']==p['kind'],'extra/changed root assumption')
        if inventory['scope']=='whole_structured_nl0':
            ir.need(p['kind'] in {'hypothesis','external','mathlib'},'internal NL0 result remains an unproved root premise')
    roots = {p['id'] for p in c['premises']}
    required = {p['id'] for p in inventory['propositions'] if p['kind'] in {'hypothesis','external'}}
    ir.need(required <= roots,'missing original hypothesis/external source input')
    for sid,row in mapping['entries'].items():
        ir.need(isinstance(row['selector'],str),'unmapped source node: '+sid)
        if row['selector'].startswith('decl:'):
            ir.need(NAME.fullmatch(row['selector'][5:]) is not None,'unsupported declaration name')
        else:
            ir.need(row['selector']=='premise:'+sid and sid in roots,'invalid premise selector')
        ir.type_text(row['expected_type'])
        item = source_props.get(sid,{})
        if item.get('kind') in {'hypothesis','external'}:
            ir.need(row['selector']=='premise:'+sid,'source premise cannot be replaced by another theorem')
        if item.get('kind')=='internal' and inventory['scope']=='whole_structured_nl0':
            ir.need(row['selector'].startswith('decl:Translation.T'),'internal source node lacks an actual local proof')
        if item.get('kind')=='mathlib':
            name = row['library_declaration']
            ir.need(isinstance(name,str) and NAME.fullmatch(name) is not None,'missing mathlib declaration')
            declared = item.get('source',{}).get('declaration')
            ir.need(not declared or declared==name,'changed named source mathlib theorem')
            ir.type_text(row['library_type'])
            if sid in roots: ir.proof_text(row['library_term'])
    calculations = inventory.get('logic',{}).get('calculations',[])
    for name,index in mapping['calculation_links'].items():
        ir.need(NAME.fullmatch(name) is not None and type(index) is int and 0 <= index < len(calculations),
                'unregistered foundational calculation')


def export_source(c,mapping):
    retained = [p for p in c['premises'] if p['kind']!='mathlib']
    context = ir.binder_text(c)
    ins = ' '.join(f"(h_{p['id']} : {p['type']})" for p in retained)
    arguments = ' '.join([p['name'] for p in c['parameters']] + ['h_'+p['id'] for p in retained])
    text = '\nnamespace AuditBExport\nset_option autoImplicit false\n'
    for p in c['premises']:
        if p['kind']=='mathlib':
            text += f"theorem resolved_{p['id']} {context} {ins} : {p['type']} := by\n{ir.proof_text(mapping['entries'][p['id']]['library_term'])}\n\n"
    actual = []
    for p in c['premises']:
        actual.append(f"(@resolved_{p['id']} {arguments})" if p['kind']=='mathlib' else 'h_'+p['id'])
    args = ' '.join([p['name'] for p in c['parameters']] + actual)
    text += f"theorem P {context} {ins} : {c['conclusion']['type']} := by\n  exact @Translation.P {args}\n\n#check @P\n#print axioms P\nend AuditBExport\n"
    return text


def build(out):
    start = time.monotonic()
    manifest = bound_inputs(out)
    ir.need(not (out/'mechanical.json').exists(),'preserve the old audit; build in a new audit directory')
    cpath,ppath,bpath = [Path(manifest[k]) for k in ('contract','plan','proofs')]
    c = ir.contract(cpath);plan,proofs = proof_bundle(cpath,ppath,bpath)
    inventory = ir.load(out/'source-inventory.json');mapping = ir.load(out/'mapping.json')
    ir.need(mapping['source_inventory_sha256']==ir.digest(out/'source-inventory.json'),'stale mapping inventory')
    validate_mapping(c,inventory,mapping)
    checks = [(sid,row['selector'],row['expected_type']) for sid,row in mapping['entries'].items()]
    for p in inventory['propositions']:
        if p['kind']=='mathlib':
            row=mapping['entries'][p['id']]
            checks.append((p['id']+'/library','decl:'+row['library_declaration'],row['library_type']))
    # Inspect every T even when the source mapper omitted an implementation helper.
    for sid,node in ir.validate(cpath,plan)[1].items():
        types={**ir.premises(c),**{s['id']:s['statement'] for s in plan['steps']}}
        params=[{'id':k,'type':types[k]} for k in node['inputs']]
        checks.append(('implementation/'+sid,'decl:Translation.'+sid,full_type(c,node['statement'],params)))
    array = '#['+', '.join('('+', '.join(json.dumps(x,ensure_ascii=False) for x in row)+')' for row in checks)+']'
    probe = (HERE/'scripts/audit_probe.lean').read_text().replace('__AUDIT_CHECKS__',array)
    formal = ir.render(cpath,plan,proofs)
    # Header commands are reviewed input, but missing proofs or executable
    # metaprogramming cannot serve as administrative project definitions.
    forbidden_header = re.search(r'\b(sorry|admit|axiom|opaque|unsafe|run_meta|run_elab|run_tac|initialize|elab|macro)\b',c['header'])
    local = {sid:ir.check(cpath,plan,{sid:proofs[sid]},only=sid) for sid in ir.validate(cpath,plan)[2]}
    work = Path(tempfile.mkdtemp(prefix='audit-b-build-'))
    (work/'input').mkdir();(work/'output').mkdir()
    source = formal+export_source(c,mapping)+'\n'+probe
    file = work/'output/Audit.lean';file.write_text(source)
    result = ir.run_lean(file,work)
    (out/'Audit.lean').write_text(source)
    ir.write(out/'compiler.json',result)
    found = re.findall(r'NL2LEAN_AUDIT_JSON:(\{[^\n]*\})',result['stdout'])
    evidence = json.loads(found[-1]) if found else None
    ir.write(out/'elaborated.json',evidence)
    errors=[]
    dependency_rows=[]
    if forbidden_header: errors.append('UNPROVED_OR_EXECUTABLE_HEADER_DECLARATION')
    if result['exit_code'] != 0 or evidence is None: errors.append('FRESH_BUILD_OR_INSPECTION_FAILED')
    if any(r['exit_code'] for r in local.values()): errors.append('LOCAL_INPUT_CLOSURE_FAILED')
    imported=[]
    if evidence:
        if not all(r['definitionally_equal'] for r in evidence['comparisons']): errors.append('ELABORATED_SIGNATURE_MISMATCH')
        deps=evidence['dependencies']
        if deps['truncated']: errors.append('DEPENDENCY_INSPECTION_TRUNCATED')
        allowed=set(FOUNDATION)
        if inventory.get('logic',{}).get('classical'): allowed |= CLASSICAL
        allowed.update(mapping['calculation_links'])
        allowed.update(row['library_declaration'] for row in mapping['entries'].values() if row.get('library_declaration'))
        for d in deps['declarations']:
            if set(d['axioms'])-AXIOMS: errors.append('UNPERMITTED_AXIOM:'+d['name'])
            if not d['imported'] and d['kind'] in {'axiom','opaque'}: errors.append('UNPROVED_PROJECT_DECLARATION:'+d['name'])
            if d['imported'] and d['proof_valued'] and d['name'] not in allowed: imported.append(d['name'])
        if imported: errors.append('UNMAPPED_IMPORTED_MATHEMATICAL_RESULT')
        dependency_rows=dependency_correspondence(inventory,mapping,plan,deps['declarations'])
        if any(not r['matched'] for r in dependency_rows): errors.append('NL0_DIRECT_DEPENDENCY_MISMATCH')
        byname={d['name']:d for d in deps['declarations']}
        for p in inventory['propositions']:
            if p['kind']=='mathlib':
                name=mapping['entries'][p['id']]['library_declaration'];d=byname.get(name)
                if not d or not d['imported'] or not d['proof_valued']: errors.append('SOURCE_M_NOT_A_PROVED_LIBRARY_RESULT:'+p['id'])
                module=p.get('source',{}).get('module')
                if d and module and module!=d['module']: errors.append('SOURCE_M_MODULE_MISMATCH:'+p['id'])
    packet={'inventory':inventory,'mapping':mapping,'contract':c,'plan':plan,
        'actual_elaborated_evidence':evidence,'dependency_correspondence':dependency_rows,
        'original_source_text':(cpath.parent/c['source']['path']).read_text(),'lean_source':source,
        'source_and_proof_bytes':manifest['inputs'],
        'warning':'Read actual sources and signatures. A template or compiler pass is not semantic review.'}
    ir.write(out/'review-packet.json',packet)
    required_locations={}
    comparisons=evidence['comparisons'] if evidence else []
    for group in ('propositions','definitions'):
        for i,item in enumerate(inventory.get(group,[])):
            matches=[j for j,q in enumerate(comparisons) if q['id'] in {item['id'],item['id']+'/library'}]
            required_locations[item['id']]=['/inventory/'+group+'/'+str(i)]+[
                '/actual_elaborated_evidence/comparisons/'+str(j) for j in matches]
    declarations=evidence['dependencies']['declarations'] if evidence else []
    for i,d in enumerate(declarations):
        if not d['imported']:
            required_locations['implementation/'+d['name']]=['/lean_source','/actual_elaborated_evidence/dependencies/declarations/'+str(i)]
    for name,index in mapping['calculation_links'].items():
        locations=['/inventory/logic/calculations/'+str(index)]
        locations += ['/actual_elaborated_evidence/dependencies/declarations/'+str(i) for i,d in enumerate(declarations) if d['name']==name]
        ir.need(len(locations)==2,'unused/uninspected calculation link')
        required_locations['calculation/'+name]=locations
    required_rows=set(required_locations)
    receipts={key:{'verdict':'UNVERIFIED','notes':'Read the complete paired statements and actual elaborated evidence.',
                   'locations':[],'evidence':[]} for key in sorted(required_rows)}
    review={'version':VERSION,'mapping_sha256':ir.digest(out/'mapping.json'),
            'reviewer':{'identity':'UNASSIGNED','mode':'UNVERIFIED','independent':False,'disclosure':'UNVERIFIED'},
            'nodes':receipts,'checks':{k:{'verdict':'UNVERIFIED','notes':'Not performed.','locations':[],'evidence':[]} for k in REVIEW_CHECKS}}
    mechanical={'version':VERSION,'passed':not errors,'errors':sorted(set(errors)),
        'required_review_locations':required_locations,'dependency_correspondence':dependency_rows,
        'unmapped_imported_proofs':sorted(set(imported)),'wall_seconds':time.monotonic()-start,
        'local_checks':local,'compiler_exit_code':result['exit_code'],
        'source_counts':{k:sum(p['kind']==k for p in inventory['propositions']) for k in KINDS},
        'mapping_sha256':ir.digest(out/'mapping.json'),'manifest_sha256':ir.digest(out/'manifest.json'),
        'artifacts':{name:ir.digest(out/name) for name in ('Audit.lean','compiler.json','elaborated.json','review-packet.json')},
        'semantic_review_performed':False}
    ir.write(out/'mechanical.json',mechanical)
    review['mechanical_sha256']=ir.digest(out/'mechanical.json')
    ir.write(out/'review-template.json',review)
    return {'status':'AUDIT-B-MECHANICAL-PASSED' if not errors else 'AUDIT-B-MECHANICAL-FAILED',
            'errors':mechanical['errors'],'unmapped_imported_proofs':mechanical['unmapped_imported_proofs'],
            'semantic_review':'UNVERIFIED'}


def resolve(value,pointer):
    ir.need(pointer.startswith('/'),'review location must be a JSON pointer into review-packet.json')
    for key in pointer[1:].split('/'):
        key=key.replace('~1','/').replace('~0','~')
        value=value[int(key)] if isinstance(value,list) else value[key]
    return value


def check(out,review_path):
    bound_inputs(out)
    mechanical=ir.load(out/'mechanical.json')
    ir.need(mechanical['manifest_sha256']==ir.digest(out/'manifest.json'),'changed audit manifest')
    ir.need(mechanical['mapping_sha256']==ir.digest(out/'mapping.json'),'changed semantic mapping')
    for name,sha in mechanical['artifacts'].items(): ir.need(ir.digest(out/name)==sha,'changed kernel audit artifact')
    ir.need(mechanical['passed'] and not mechanical['errors'],'mechanical audit failed')
    review=ir.load(review_path);packet=ir.load(out/'review-packet.json')
    ir.need(review['version']==VERSION,'unsupported semantic receipt')
    ir.need(review['mechanical_sha256']==ir.digest(out/'mechanical.json') and
            review['mapping_sha256']==ir.digest(out/'mapping.json'),'stale semantic receipt')
    reviewer=review['reviewer']
    ir.need(reviewer['identity'].strip() not in {'','UNASSIGNED'} and reviewer['disclosure'].strip() not in {'','UNVERIFIED'},'undisclosed reviewer')
    ir.need(type(reviewer['independent']) is bool,'invalid reviewer independence')
    ir.need(reviewer['mode'] in {'human','same_context_self_audit','fresh_model_review','external_review'},'invalid reviewer mode')
    ir.need(not (reviewer['mode']=='same_context_self_audit' and reviewer['independent']),'self-review cannot claim independence')
    ir.need(set(review['nodes'])==set(mechanical['required_review_locations']) and set(review['checks'])==set(REVIEW_CHECKS),'missing/extra semantic reviews')
    for key,row in {**review['nodes'],**review['checks']}.items():
        ir.need(row['verdict']=='PASS','unperformed/failed semantic review: '+key)
        ir.need(row['notes'].strip() and row['notes'] not in {'Not performed.','Read the complete paired statements and actual elaborated evidence.'},'generic unperformed note')
        ir.need(row['locations'] and row['evidence'],'missing located review evidence: '+key)
        expected=mechanical['required_review_locations'].get(key,['/inventory','/actual_elaborated_evidence'])
        ir.need(set(expected)<=set(row['locations']),'missing paired source/kernel review locations: '+key)
        for pointer in row['locations']: resolve(packet,pointer)
        for item in row['evidence']:
            path=(Path(review_path).parent/item['path']).resolve()
            ir.need(path.is_file() and ir.digest(path)==item['sha256'],'stale semantic evidence')
    inventory=ir.load(out/'source-inventory.json')
    certified=inventory['scope']=='whole_structured_nl0' and inventory['audit_a_current_passed']
    return {'status':'AUDIT-B-PASSED' if certified else 'DEVELOPMENT-AUDIT-B-PASSED',
            'checks_passed':True,'scope':inventory['scope'],'upstream_audit_a':inventory['audit_a_status'],
            'whole_nl0_and_current_audit_a':certified,'reviewer':reviewer,
            'kernel_correct_relative_to_declared_externals':True,
            'external_publications_proved_by_lean':False,'semantic_review_automatically_verified':False,
            'receipt_sha256':ir.digest(review_path),'mechanical_sha256':ir.digest(out/'mechanical.json')}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command',choices=['prepare','build','check'])
    ap.add_argument('directory',type=Path)
    ap.add_argument('--contract',type=Path);ap.add_argument('--plan',type=Path);ap.add_argument('--proofs',type=Path)
    ap.add_argument('--graph',type=Path);ap.add_argument('--spec',type=Path);ap.add_argument('--audit-a',type=Path)
    ap.add_argument('--incremental',type=Path)
    ap.add_argument('--fragment-inventory',type=Path);ap.add_argument('--review',type=Path)
    args=ap.parse_args()
    try:
        if args.command=='prepare':
            result=prepare(args.contract,args.plan,args.proofs,args.directory.resolve(),
                graph=args.graph,spec=args.spec,audit_a=args.audit_a,incremental=args.incremental,fragment=args.fragment_inventory)
        elif args.command=='build':result=build(args.directory.resolve())
        else:result=check(args.directory.resolve(),args.review)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 1 if result['status']=='AUDIT-B-MECHANICAL-FAILED' else 0
    except (ir.Invalid,ValueError,TypeError,KeyError,OSError) as error:
        print(json.dumps({'status':'AUDIT-B-NOT-PASSED','error':str(error)},ensure_ascii=False))
        return 1


if __name__=='__main__':raise SystemExit(main())
