"""Shared Audit B input/receipt fixtures; synthetic judgments are not audits."""
from pathlib import Path
import harness_support
import ir
import audit_b as audit

def fixture(directory,variant='identity'):
    directory.mkdir(parents=True,exist_ok=True)
    mathlib=ir.load_lock()['mathlib']['rev']
    source={'mathematical_input':'Let p be a proposition. Given H001: p, prove P: p.',
            'source_steps':[{'id':'S001','text':'Apply H001 directly.'}]}
    params=[{'name':'p','type':'Prop'}]
    premises=[{'id':'H001','kind':'hypothesis','type':'p','statement':'p holds.'}]
    target='p';body='exact h_H001'
    props=[{'id':'H001','kind':'hypothesis','statement':'p holds.'},{'id':'P','kind':'target','statement':'p holds.'}]
    if variant in {'mathlib','unmapped_mathlib'}:
        source={'mathematical_input':'For natural numbers a,b, prove a+b=b+a by the declared commutativity result.',
                'source_steps':[{'id':'S001','text':'Instantiate the declared addition commutativity theorem at a,b.'}]}
        params=[{'name':'a','type':'ℕ'},{'name':'b','type':'ℕ'}]
        premises=[{'id':'M001','kind':'mathlib','type':'a+b=b+a','statement':'For these a,b, addition commutes.'}] if variant=='mathlib' else []
        target='a+b=b+a';body='exact h_M001' if premises else 'exact Nat.add_comm a b'
        props=([{'id':'M001','kind':'mathlib','statement':'For all natural a,b, a+b=b+a.',
                 'source':{'declaration':'Nat.add_comm'}}] if premises else []) + [
                 {'id':'P','kind':'target','statement':'For these a,b, a+b=b+a.'}]
    if variant=='weakened_external':
        source={'mathematical_input':'Let p,q be propositions. The supplied external input E001 states p. Prove p.',
                'source_steps':[{'id':'S001','text':'Apply exactly the supplied external statement E001: p.'}]}
        params=[{'name':'p','type':'Prop'},{'name':'q','type':'Prop'}]
        premises=[{'id':'E001','kind':'external','type':'p ∧ q','statement':'Intentionally strengthened external input.'}]
        target='p';body='exact h_E001.1'
        props=[{'id':'E001','kind':'external','statement':'p holds.'},{'id':'P','kind':'target','statement':'p holds.'}]
    if variant=='unmapped_instance':
        source={'mathematical_input':'An unregistered mathematical property of the reals.',
                'source_steps':[{'id':'S001','text':'Attempt to use a library instance as the entire proof.'}]}
        params=[];premises=[];target='IsTopologicalRing ℝ';body='exact instIsTopologicalRingReal'
        props=[{'id':'P','kind':'target','statement':'The real numbers form a topological ring.'}]
    (directory/'source.json').write_text(__import__('json').dumps(source,indent=2)+'\n')
    header='import Mathlib\n'
    if variant=='hidden_field':
        header+='\nstructure Box (q : Prop) where\n  hidden : q\n'
        params.append({'name':'box','type':'Box p'})
    if variant=='equivalent_target': target='p ∧ True';body='exact ⟨h_H001, True.intro⟩'
    if variant=='wrong_target': target='True';body='exact True.intro'
    if variant=='extra_axiom':
        header+='axiom hiddenProof : False\n'
        body='exact False.elim hiddenProof'
    c={'version':1,'id':'audit_control','source':{'path':'source.json','sha256':ir.digest(directory/'source.json')},
       'source_steps':source['source_steps'],'pins':{'lean_version':ir.load_lock()['lean']['version_number'],'mathlib_commit':mathlib},
       'header':header,'parameters':params,'premises':premises,
       'endpoint_correspondence':{p['id']:{'mode':'direct','explanation':'The displayed binders and assertion encode the source '+p['id']+'.'} for p in props if p['kind'] in {'external','target'}},
       'conclusion':{'statement':props[-1]['statement'],'type':target},'representation':{'scope':'propositional/Nat controls'},
       'review':{'mode':'development_owner_review','scope':'Synthetic Audit B controls; no whole-case certification.'}}
    if variant=='equivalent_target':
        c['endpoint_correspondence']['P']={'mode':'equivalent','explanation':'The encoding pairs the original assertion with True; take the first projection to recover the original, and pair it with True.intro in the other direction.'}
    cpath=directory/'contract.json';ir.write(cpath,c)
    plan={'version':1,'contract_sha256':ir.digest(cpath),'representation_notes':'Preserve the fixed proposition or natural-number statement.',
          'steps':[{'id':'T001','statement':target,'inputs':[p['id'] for p in premises],
                    'source_steps':['S001'],'explanation':source['source_steps'][0]['text']}],'terminal':'T001'}
    ppath=directory/'plan.json';ir.write(ppath,plan)
    bpath=directory/'proofs.json';ir.write(bpath,{'contract_sha256':ir.digest(cpath),'plan_sha256':ir.digest(ppath),'proofs':{'T001':body}})
    inventory={'scope':'development_fragment','source_sha256':c['source']['sha256'],
               'full_target':source['mathematical_input'],'parameters':[p for p in params if p['name']!='box'],
               'definitions':[],'logic':{'classical':False,'calculations':[]},'propositions':props,
               'inferences':[{'id':'R001','inputs':[p['id'] for p in premises],'output':'P','argument':source['source_steps']}]}
    ipath=directory/'inventory.json';ir.write(ipath,inventory)
    return cpath,ppath,bpath,ipath

def prepare_control(base,variant='identity'):
    c,p,b,i=fixture(base/'case',variant)
    directory=base/'audit'
    audit.prepare(c,p,b,directory,fragment=i)
    mapping=ir.load(directory/'mapping.json')
    if variant in {'wrong_target','hidden_field'}:
        # Independent expected type follows the original NL statement, rather
        # than the formalizer's weakened goal or added Box parameter.
        mapping['entries']['P']['expected_type']='∀ (p : Prop) (h_H001 : p), p'
    if variant=='weakened_external':
        mapping['entries']['P']['expected_type']='∀ (p q : Prop) (h_E001 : p), p'
        mapping['entries']['E001']['expected_type']='∀ (p q : Prop), p'
    if variant=='mathlib':
        mapping['library_terms']['M001']='exact Nat.add_comm a b'
    ir.write(directory/'mapping.json',mapping)
    return directory

def synthetic_receipt(directory, *, independent=False):
    """Receipt-format control, not an automated semantic audit."""
    record=ir.load(directory/'review-template.json')
    note=directory/'test-only-evidence.txt';note.write_text('TEST RECEIPT SHAPE ONLY. No independent certification or new mathematical review.\n')
    evidence=[{'path':note.name,'sha256':ir.digest(note)}]
    mechanical=ir.load(directory/'mechanical.json')
    record['reviewer']={'identity':'TEST_RECEIPT_SHAPE_ONLY','mode':'same_context_self_audit',
                        'independent':False,'disclosure':'Synthetic validator regression, not a substantive audit.'}
    if independent:
        record['reviewer'].update(mode='external_review',independent=True,
            disclosure='Fabricated independent-review fields for a positive control only; not an actual mathematical audit.')
    for key,row in record['nodes'].items():
        row.update(verdict='PASS',notes='Synthetic located receipt for validator regression only.',
                   locations=mechanical['required_review_locations'][key],evidence=evidence)
    for row in record['checks'].values():
        row.update(verdict='PASS',notes='Synthetic complete receipt; semantic quality is not being certified.',
                   locations=audit.review_materials.locations(ir.load(directory/'review-packet.json')),evidence=evidence)
    path=directory/'test-only-review.json';ir.write(path,record)
    return path
