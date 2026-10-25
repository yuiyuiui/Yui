#!/usr/bin/env python3
"""External/complete-target fidelity and review-bound Audit B.

Semantic reviews remain actual reviewer work. Pending templates never pass.
This adapter audits the candidate's actual source-facing export, not arbitrary
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
import background
import background_inputs
import assembly
import lean_names
import correspondence
from shared_lemmas import hashed

HERE = Path(__file__).resolve().parents[1]
VERSION = 2
KINDS = {'hypothesis','external','mathlib','internal','target'}
AXIOMS = {'propext','Classical.choice','Quot.sound'}
REVIEW_CHECKS = ('endpoint_inventory_and_scope', 'external_statement_fidelity',
                 'complete_target_and_representations', 'kernel_closure_and_trust')


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
        selected = background_inputs.mode(c)
        props,inferences=background_inputs.effective(data, selected)
        if result.get('background_note_count',0):
            ir.need(c['source'].get('background_supplement_sha256') == result['background_supplement']['sha256']
                    and c['source'].get('background_supplement')==result['background_supplement'],
                    'Audit B interface omitted/changed accepted background notes')
        inventory = {'scope':'whole_structured_nl0','propositions':list(props.values()),
            'background_mode':selected,
            'background_supplement':result.get('background_supplement'),
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
    mapping = {'version':VERSION,'policy':correspondence.POLICY,
               'source_inventory_sha256':ir.digest(out/'source-inventory.json'),
               'entries':{},'library_terms':{}}
    premises = {p['id']:p for p in c['premises']}
    retained = [p for p in c['premises'] if p['kind']!='mathlib']
    notes = c.get('endpoint_correspondence', {})
    for item in inventory['propositions']:
        sid = item['id']
        if item['kind'] not in {'external', 'target'}:
            continue
        if sid == 'P':
            selector = 'decl:AuditBExport.P'
            expected = full_type(c,c['conclusion']['type'],retained)
        else:
            ir.need(sid in premises, 'missing external root: '+sid)
            before = retained[:next(i for i,p in enumerate(retained) if p['id']==sid)]
            selector = 'premise:'+sid
            expected = full_type(c,premises[sid]['type'],before)
        mapping['entries'][sid] = {'selector':selector,'expected_type':expected,
                                  'correspondence':notes.get(sid)}
    # Compatibility ports are proof obligations, never a library whitelist.
    mapping['library_terms'] = {p['id']:None for p in c['premises'] if p['kind']=='mathlib'}
    ir.write(out/'mapping.json',mapping)
    source_file = (cpath.parent/c['source']['path']).resolve()
    originals = [cpath,ppath,bpath,source_file,*[p.resolve() for p in source_paths]]
    tools = [Path(__file__),Path(source_preparation.__file__),HERE/'scripts/audit_probe.lean',Path(ir.__file__),
             Path(assembly.__file__),Path(lean_names.__file__),Path(correspondence.__file__),
             HERE/'scripts/shared_lemmas.py',HERE.parent/'scripts/nl0.py',HERE.parent/'scripts/closure.py',
             ir.ROOT/'scripts/pilot_common.py',ir.ROOT/'scripts/background.py',
             Path(background_inputs.__file__),ir.ROOT/'toolchain/lock.json']
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


def validate_mapping(c,inventory,mapping):
    ids = set(correspondence.endpoint_ids(inventory['propositions']))
    ir.need(mapping.get('version')==VERSION and mapping.get('policy')==correspondence.POLICY,
            'unsupported Audit B policy; create a new endpoint audit')
    ir.need(isinstance(mapping.get('entries'),dict) and set(mapping['entries'])==ids,
            'missing/extra endpoint correspondence')
    ir.need(mapping['entries']['P']['selector']=='decl:AuditBExport.P',
            'audit must inspect the actual assembled root')
    source_props = {p['id']:p for p in inventory['propositions']}
    for p in c['premises']:
        if p['kind']=='mathlib':
            continue  # Proven during assembly, independent of any NL0 M list.
        ir.need(p['id'] in source_props and source_props[p['id']]['kind']==p['kind'],
                'extra/changed root assumption')
        if inventory['scope']=='whole_structured_nl0':
            ir.need(p['kind'] in {'hypothesis','external'},
                    'internal NL0 result remains an unproved root premise')
    roots = {p['id'] for p in c['premises']}
    required = {p['id'] for p in inventory['propositions'] if p['kind'] in {'hypothesis','external'}}
    ir.need(required <= roots,'missing original hypothesis/external source input')
    for sid,row in mapping['entries'].items():
        ir.need(isinstance(row,dict) and set(row)=={'selector','expected_type','correspondence'},
                'invalid endpoint correspondence fields: '+sid)
        wanted = 'decl:AuditBExport.P' if sid=='P' else 'premise:'+sid
        ir.need(row['selector']==wanted,'endpoint must select its actual exported statement: '+sid)
        ir.type_text(row['expected_type'])
        correspondence.validate_note(row['correspondence'],sid)
    terms = mapping.get('library_terms')
    ir.need(isinstance(terms,dict) and set(terms)=={p['id'] for p in c['premises'] if p['kind']=='mathlib'},
            'provide exactly the intermediate Mathlib-port discharge proofs')
    for body in terms.values():
        ir.proof_text(body)
    ir.need(set(mapping)=={'version','policy','source_inventory_sha256','entries','library_terms'},
            'obsolete or unexpected mapping fields; no library permission ledger is used')


def export_source(c,mapping,level_metadata=None):
    return assembly.export_source(c,mapping,level_metadata)


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
    rows = [(*row, lean_names.parts(row[1][5:]) if row[1].startswith('decl:') else []) for row in checks]
    array = '#['+', '.join('('+', '.join(('#['+', '.join(json.dumps(p,ensure_ascii=False) for p in x)+']')
                          if isinstance(x,list) else json.dumps(x,ensure_ascii=False) for x in row)+')' for row in rows)+']'
    probe = (HERE/'scripts/audit_probe.lean').read_text().replace('__AUDIT_CHECKS__',array)
    formal = ir.render(cpath,plan,proofs)
    # Header commands are reviewed input, but missing proofs or executable
    # metaprogramming cannot serve as administrative project definitions.
    forbidden_header = re.search(r'\b(sorry|admit|axiom|opaque|unsafe|run_meta|run_elab|run_tac|initialize|elab|macro)\b',c['header'])
    local = {sid:ir.check(cpath,plan,{sid:proofs[sid]},only=sid) for sid in ir.validate(cpath,plan)[2]}
    work = Path(tempfile.mkdtemp(prefix='audit-b-build-'))
    try:
        (work/'input').mkdir();(work/'output').mkdir()
        assembled = assembly.build(c,mapping,formal,out,work)
        inspected = {'status':'NOT_STARTED','compiler_exit_code':None}
        if assembled['status']=='ASSEMBLY-PASSED':
            source = (out/'Proof.lean').read_text()+'\n'+probe
            file = work/'output/Audit.lean';file.write_text(source)
            result = ir.run_lean(file,work)
            inspected = {'status':'KERNEL_INSPECTION_PASSED' if result['exit_code']==0 else 'KERNEL_INSPECTION_FAILED',
                         'compiler_exit_code':result['exit_code'],'wall_seconds':result['wall_seconds']}
            if result['exit_code'] and 'maximum number of heartbeats' in result['stdout']:
                inspected['status']='INSPECTION_HEARTBEAT_EXHAUSTED'
        else:
            result=ir.load(out/'assembly-compiler.json')
            source=(out/('Proof.lean' if (out/'Proof.lean').exists() else 'AssemblyInputs.lean')).read_text()
        ir.write(out/'inspection.json',inspected)
        (out/'Audit.lean').write_text(source)
        ir.write(out/'compiler.json',result)
        found = re.findall(r'NL2LEAN_AUDIT_JSON:(\{[^\n]*\})',result['stdout'])
        evidence = json.loads(found[-1]) if found else None
        ir.write(out/'elaborated.json',evidence)
        errors=[]
        if forbidden_header: errors.append('UNPROVED_OR_EXECUTABLE_HEADER_DECLARATION')
        if assembled['status']!='ASSEMBLY-PASSED': errors.append('SOURCE_FACING_ASSEMBLY_FAILED')
        if inspected['status']=='INSPECTION_HEARTBEAT_EXHAUSTED': errors.append('INSPECTION_HEARTBEAT_EXHAUSTED')
        if result['exit_code'] != 0 or evidence is None: errors.append('FRESH_BUILD_OR_INSPECTION_FAILED')
        if any(r['exit_code'] for r in local.values()): errors.append('LOCAL_INPUT_CLOSURE_FAILED')
        if evidence:
            if not all(r['definitionally_equal'] for r in evidence['comparisons']):
                errors.append('ELABORATED_SIGNATURE_MISMATCH')
            deps=evidence['dependencies']
            if deps['truncated']: errors.append('DEPENDENCY_INSPECTION_TRUNCATED')
            for d in deps['declarations']:
                if set(d['axioms'])-AXIOMS: errors.append('UNPERMITTED_AXIOM:'+d['name'])
                if not d['imported'] and d['kind'] in {'axiom','opaque'}:
                    errors.append('UNPROVED_PROJECT_DECLARATION:'+d['name'])
        # Imported theorems in the pinned environment are globally available.
        # No name, count, per-node edge or arithmetic-permission comparison
        # against the NL0 M inventory belongs to endpoint Audit B.
        packet={'inventory':inventory,'mapping':mapping,'contract':c,'plan':plan,
            'actual_elaborated_evidence':evidence,'policy':correspondence.POLICY,
            'original_source_text':(cpath.parent/c['source']['path']).read_text(),'lean_source':source,
            'source_and_proof_bytes':manifest['inputs'],
            'assembly':assembled,'inspection':inspected,
            'warning':'Read actual sources and signatures. A template or compiler pass is not semantic review.'}
        ir.write(out/'review-packet.json',packet)
        required_locations={}
        comparisons=evidence['comparisons'] if evidence else []
        for i,item in enumerate(inventory['propositions']):
            sid=item['id']
            if sid not in mapping['entries']:
                continue
            matches=[j for j,q in enumerate(comparisons) if q['id']==sid]
            required_locations[sid]=['/inventory/propositions/'+str(i),
                '/mapping/entries/'+sid+'/correspondence']+[
                '/actual_elaborated_evidence/comparisons/'+str(j) for j in matches]
            if sid=='P':
                required_locations[sid] += ['/inventory/full_target','/inventory/parameters']
        required_rows=set(required_locations)
        receipts={key:{'verdict':'UNVERIFIED','notes':'Read the complete paired statements and actual elaborated evidence.',
                       'locations':[],'evidence':[]} for key in sorted(required_rows)}
        review={'version':VERSION,'mapping_sha256':ir.digest(out/'mapping.json'),
                'reviewer':{'identity':'UNASSIGNED','mode':'UNVERIFIED','independent':False,'disclosure':'UNVERIFIED'},
                'nodes':receipts,'checks':{k:{'verdict':'UNVERIFIED','notes':'Not performed.','locations':[],'evidence':[]} for k in REVIEW_CHECKS}}
        mechanical={'version':VERSION,'passed':not errors,'errors':sorted(set(errors)),
            'policy':correspondence.POLICY,
            'required_review_locations':required_locations,'wall_seconds':time.monotonic()-start,
            'local_checks':local,'compiler_exit_code':result['exit_code'],
            'assembly':assembled,'inspection':inspected,
            'source_counts':{k:sum(p['kind']==k for p in inventory['propositions']) for k in KINDS},
            'mapping_sha256':ir.digest(out/'mapping.json'),'manifest_sha256':ir.digest(out/'manifest.json'),
            'artifacts':{name:ir.digest(out/name) for name in ('Audit.lean','compiler.json','elaborated.json','review-packet.json',
                'AssemblyInputs.lean','assembly-inputs-compiler.json','assembly-compiler.json','assembly.json','inspection.json',
                *(['Proof.lean'] if (out/'Proof.lean').exists() else []))},
            'semantic_review_performed':False}
        ir.write(out/'mechanical.json',mechanical)
        review['mechanical_sha256']=ir.digest(out/'mechanical.json')
        ir.write(out/'review-template.json',review)
        return {'status':'AUDIT-B-MECHANICAL-PASSED' if not errors else 'AUDIT-B-MECHANICAL-FAILED',
                'errors':mechanical['errors'],'policy':correspondence.POLICY,
                'assembly':assembled['status'],'inspection':inspected['status'],
                'semantic_review':'UNVERIFIED'}
    finally:
        shutil.rmtree(work)


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
            'checks_passed':True,'policy':correspondence.POLICY,'scope':inventory['scope'],'upstream_audit_a':inventory['audit_a_status'],
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
