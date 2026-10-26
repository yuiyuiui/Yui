"""Prepare/run neutral semantic controls; expected answers stay owner-only."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys

CORE=Path(__file__).resolve().parents[2]
for directory in (CORE/'nl0/scripts',CORE/'nl02lean/scripts'):
    sys.path.insert(0,str(directory))

import audit_a_campaign as a
import interface_review
from execution_health import qualification
from runtime_config import load_lock


def logic_source(parameters,hypotheses,target,text,objects):
    full='For '+', '.join(p['symbol']+': '+p['type'] for p in parameters)+', assume '+ '; '.join(h[1] for h in hypotheses)+' Then '+target
    spec={'format_version':2,'case_id':'neutral-interface-control','full_target':full,
          'conclusion':target,'parameters':parameters,
          'hypotheses':[{'id':key,'statement':statement,'origin':'problem.md'} for key,statement,_ in hypotheses],
          'definitions':[],'logic':{'classical':False,'rules':['direct','modus_ponens'],'calculations':[],'primitives':[]}}
    props=[{'id':key,'kind':'hypothesis','statement':statement,'definitions':[],'binders':[],'objects':used} for key,statement,used in hypotheses]
    props.append({'id':'P','kind':'target','statement':target,'definitions':[],'binders':[],'objects':objects})
    keys=[key for key,_,_ in hypotheses]
    graph={'format_version':2,'case_id':spec['case_id'],'propositions':props,
        'inferences':[{'id':'R001','inputs':keys,'output':'P','definitions':[],'rules':['direct'], 'locals':[],
            'argument':[{'id':'S001','text':text,'uses':keys,'uses_local':[],'objects':objects,'produces':[],
                         'introduces':[],'discharges':[]}],'applications':[]}]}
    return spec,graph


def examples():
    parameters=[{'symbol':name,'type':kind} for name,kind in [('C','type'),('F','type'),('pc','predicate on C'),('pf','predicate on F'),('c','element of C'),('f','element of F')]]
    s,g=logic_source(parameters,[('H001','pc(c).',['pc','c']),('H002','pc(c) implies pf(f).',['pc','c','pf','f'])],
                       'pf(f).','Apply H002 to H001 to obtain pf(f).',['pc','c','pf','f'])
    same={'id':'different-carriers','spec':s,'graph':g,'parameters':[{'name':name,'type':kind} for name,kind in
        [('C','Type'),('F','Type'),('pc','C → Prop'),('pf','F → Prop'),('c','C'),('f','F')]],
        'types':{'H001':'pc c','H002':'pc c → pf f'},'target':'pf f','expected':'PASS',
        'reason':'An allowed predicate on the source carrier is distinct from the target predicate on another carrier.'}
    s,g=logic_source([{'symbol':'p','type':'proposition'},{'symbol':'q','type':'proposition'}],
                       [('H001','p.',['p'])],'p.','H001 is exactly the required conclusion.',['p'])
    stronger={'id':'stronger-hypothesis','spec':s,'graph':g,'parameters':[{'name':'p','type':'Prop'},{'name':'q','type':'Prop'}],
              'types':{'H001':'p ∧ q'},'target':'p','expected':'FAIL','reason':'The source assumes p, not p and q.'}
    s,g=logic_source([{'symbol':'r','type':'predicate on natural numbers'}],[('H001','For every natural number n, r(n).',['r'])],
                       'For every natural number n, r(n).','H001 supplies the full universally quantified conclusion, including zero.',['r'])
    endpoint={'id':'omitted-zero','spec':s,'graph':g,'parameters':[{'name':'r','type':'ℕ → Prop'}],
              'types':{'H001':'∀ n : ℕ, r n'},'target':'∀ n : ℕ, 0 < n → r n','expected':'FAIL',
              'reason':'The formal target omits the zero case without an explicit equivalence/closure obligation.'}
    for proposition in g['propositions']:
        proposition['binders']=[{'symbol':'n','type':'natural number'}];proposition['objects']=['r','n']
    hidden=deepcopy(same);hidden['id']='hidden-target-field';hidden['parameters'].append({'name':'solved','type':'pf f'})
    hidden.update(expected='FAIL',reason='An added proof-valued global parameter assumes the target.')
    fixture=a.CORE/'tests/fixtures/closed-addition'
    bridge={'id':'planned-bridge','spec':a.nl0.load(fixture/'spec.json'),'graph':a.nl0.load(fixture/'nl0.json'),
            'parameters':[{'name':'a','type':'ℕ'},{'name':'b','type':'ℕ'}], 'types':{'H001':'a = b'},'target':'a + 0 = b',
            'expected':'PASS','reason':'Typed bridge obligations may be planned without completed proof bodies at the interface stage.'}
    return [same,stronger,endpoint,hidden,bridge]


def prepare(directory):
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=False)
    owner={};lock=load_lock()
    for item in examples():
        case=directory/item['id'];inputs=case/'inputs';inputs.mkdir(parents=True)
        problem='Neutral semantic comparison control only. The supplied logical source is the comparison authority; no Audit A, proof execution or exercise acceptance is claimed.\n'
        (inputs/'problem.md').write_text(problem)
        spec=deepcopy(item['spec']);graph=deepcopy(item['graph'])
        spec['pins']={'lean_version':'4.32.2','mathlib_commit':lock['mathlib']['rev'],'mathlib_root':lock['mathlib']['local_path']}
        spec['inputs']=[{'path':'problem.md','sha256':a.bind(inputs/'problem.md')['sha256']}]
        a.write(inputs/'spec.json',spec);graph['spec_sha256']=a.bind(inputs/'spec.json')['sha256'];a.write(inputs/'nl0.json',graph)
        a.nl0.validate(inputs/'nl0.json',inputs/'spec.json')
        paragraphs=[{'id':f'S{n:03d}','text':p['text']} for n,p in enumerate(
            (p for r in graph['inferences'] for p in r['argument']),1)]
        contract={'version':2,'id':'neutral_control','source':{'path':'nl0.json','sha256':a.bind(inputs/'nl0.json')['sha256']},
            'source_steps':paragraphs,'pins':spec['pins'],'header':'import Mathlib\n','parameters':item['parameters'],
            'premises':[{'id':key,'kind':'hypothesis','statement':next(p['statement'] for p in graph['propositions'] if p['id']==key),'type':value} for key,value in item['types'].items()],
            'conclusion':{'statement':spec['conclusion'],'type':item['target']},'representation':'Explicit logical types in a neutral semantic control.',
            'objects':[],'shared_obligations':[],'review':{'mode':'development_owner_review','status':'CALIBRATION_ONLY_NOT_AUDITED'}}
        a.write(inputs/'contract.json',contract)
        steps=[{'id':'T001','statement':item['target'],'inputs':list(item['types']),
                'source_steps':[p['id'] for p in paragraphs],'explanation':'Follow the supplied explicit logical source.'}]
        if item['id']=='planned-bridge':
            steps=[{'id':'T001','statement':'b = a','inputs':['H001'],'source_steps':['S001'],'explanation':'Equality symmetry.'},
                   {'id':'T002','statement':'a + 0 = a','inputs':[],'source_steps':['S002'],'explanation':'The explicitly permitted additive identity; planned proof, not a source assumption.'},
                   {'id':'T003','statement':'a + 0 = b','inputs':['T001','T002'],'source_steps':['S003'],'explanation':'Substitution with actual antecedents required at assembly.'}]
        a.write(inputs/'plan.json',{'version':2,'contract_sha256':a.bind(inputs/'contract.json')['sha256'],
            'representation_notes':contract['representation'],'steps':steps,'terminal':steps[-1]['id']})
        a.manifest(inputs)
        (case/'prompt.txt').write_text(interface_review.PROMPT+'\nThis is a neutral semantic comparison control, not an exercise or a claim of upstream mathematical certification.\n')
        a.write(case/'bindings.json',{'adjudication':None,'scope':'CALIBRATION_ONLY_NOT_WORKFLOW'})
        owner[item['id']]={'expected_verdict':item['expected'],'reason':item['reason']}
    (directory/'owner').mkdir();a.write(directory/'owner/expected.json',owner)
    return {'status':'PREPARED_NOT_RUN','cases':list(owner),'scope':'Owner labels are outside every reviewer input manifest.'}


def run(directory,timeout=None):
    directory=Path(directory).resolve();expected=a.nl0.load(directory/'owner/expected.json');results=[]
    budget=a.concurrency.serial_budget()
    for name,label in expected.items():
        case=directory/name;result=interface_review.run(case,timeout,budget=budget)
        actual=a.nl0.load(case/'stage/accepted.json') if (case/'stage/accepted.json').is_file() else None
        verdict=('FAIL' if any(row['verdict']=='FAIL' for row in actual.get('checks',{}).values()) else
                 'UNVERIFIED' if any(row['verdict']=='UNVERIFIED' for row in actual.get('checks',{}).values()) else 'PASS') if actual and 'checks' in actual else None
        results.append({'case':name,'expected':label,'actual_verdict':verdict,'qualification':qualification(result),
                        'matches':verdict==label['expected_verdict']})
    report={'status':'CONTROLS_PASSED' if all(r['matches'] and r['qualification']['execution_qualified'] for r in results) else 'CONTROLS_NOT_PASSED',
            'results':results,'scope':'Finite disclosed development calibration, not a proof/benchmark or a guarantee of judge accuracy.'}
    a.write(directory/'report.json',report);return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','run']);parser.add_argument('directory',type=Path)
    args=parser.parse_args();print(json.dumps(prepare(args.directory) if args.command=='prepare' else run(args.directory),indent=2))
