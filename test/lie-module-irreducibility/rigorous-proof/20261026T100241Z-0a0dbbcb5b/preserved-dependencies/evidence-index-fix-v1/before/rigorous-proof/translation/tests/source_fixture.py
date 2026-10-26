"""Small actual propositional proof; synthetic review helpers are format controls only."""
import copy
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE/'scripts'))
import ir
import source_preparation as source
import workflow


def case(directory):
    directory.mkdir(parents=True,exist_ok=True)
    problem=directory/'problem.txt'
    problem.write_text('Let p and q be propositions. Given p ∧ q, prove (p ∧ p) ∧ (p ∨ q).\n')
    spec={'format_version':2,'case_id':'shared-projection-functional-control',
          'full_target':problem.read_text().strip(),'conclusion':'(p ∧ p) ∧ (p ∨ q).',
          'parameters':[{'symbol':x,'type':'proposition'} for x in ('p','q')],
          'hypotheses':[{'id':'H001','statement':'p ∧ q.','origin':'problem.txt:1'}],
          'definitions':[],'logic':{'classical':False,'rules':['direct'],'calculations':[],'primitives':[]},
          'pins':{'lean_version':'4.32.2','mathlib_commit':ir.load_lock()['mathlib']['rev'],
                  'mathlib_root':ir.load_lock()['mathlib']['local_path']},
          'inputs':[{'path':'problem.txt','sha256':ir.digest(problem)}]}
    sp=directory/'spec.json';ir.write(sp,spec)
    def prop(pid,kind,text,objects):
        value={'id':pid,'kind':kind,'statement':text,'definitions':[],'binders':[],'objects':objects}
        if kind=='internal':value['origin']='The supplied direct propositional proof.'
        return value
    def inference(rid,inputs,output,text):
        return {'id':rid,'inputs':inputs,'output':output,'definitions':[],'rules':['direct'],'locals':[],
                'argument':[{'id':'S001','text':text,'uses':inputs,'uses_local':[],'objects':['p','q'],
                             'produces':[],'introduces':[],'discharges':[]}],'applications':[]}
    graph={'format_version':2,'case_id':spec['case_id'],'spec_sha256':ir.digest(sp),
           'propositions':[prop('H001','hypothesis','p ∧ q.',['p','q']),
                           prop('N001','internal','p ∧ p.',['p']),
                           prop('N002','internal','p ∨ q.',['p','q']),
                           prop('P','target',spec['conclusion'],['p','q'])],
           'inferences':[inference('R001',['H001'],'N001','H001 gives p ∧ q. Its first conjunct is p. Conjunction introduction gives p ∧ p.'),
                         inference('R002',['H001'],'N002','H001 gives p ∧ q. Its first conjunct is p. Left disjunction introduction gives p ∨ q.'),
                         inference('R003',['N001','N002'],'P','N001 gives p ∧ p and N002 gives p ∨ q. Conjunction introduction gives (p ∧ p) ∧ (p ∨ q).')]}
    gp=directory/'nl0.json';ir.write(gp,graph)
    source.nl0.validate(gp,sp)
    new=prop('N003','internal','p.',['p'])
    producer=inference('R004',['H001'],'N003','H001 gives p ∧ q. Conjunction elimination gives p.')
    consumers=[]
    for r,text in zip(graph['inferences'][:2],('N003 gives p. Conjunction introduction gives p ∧ p.',
                                             'N003 gives p. Left disjunction introduction gives p ∨ q.')):
        para=copy.deepcopy(r['argument'][0]);para.update(text=text,uses=['N003'])
        consumers.append({'inference':r['id'],'before_sha256':source.hashed(r),'inputs':['N003'],
            'replacements':[{'paragraph':'S001','before_sha256':source.hashed(r['argument'][0]),'after':para}],
            'cut':{'old_conclusion':'p holds after taking the first conjunct of p ∧ q.',
                   'shared_instantiation':'Use N003, the same fixed proposition p.', 'supplied_conclusion':'p holds.',
                   'conditions':[],'continuation':'The original conjunction/disjunction introduction still receives precisely p; no witness escapes.'}})
    patch={'version':source.VERSION,'baseline_graph_sha256':ir.digest(gp),'spec_sha256':ir.digest(sp),
           'candidates':[{'id':'C001','proposition':new,'producer':producer,
                          'derivation':{'inference':'R001','paragraphs':['S001']},
                          'expected_avoided_work':'Functional deduplication control only; too small to infer economic benefit.',
                          'consumers':consumers}]}
    pp=directory/'patch.json';ir.write(pp,patch)
    return gp,sp,pp


def synthetic_audit(graph,spec):
    """Deliberately synthetic receipt-shape test. Not evidence of actual replay."""
    data=source.nl0.validate(graph,spec)
    audit=source.nl0.closure.audit_template(data,source.nl0.CHECKS,source.nl0.EXTERNAL_CHECKS,Path(graph).name,Path(spec).name)
    base=Path(graph).parent;note=base/'TEST_ONLY_RECEIPT_SHAPE.txt'
    note.write_text('SYNTHETIC VALIDATOR CONTROL. No actual model replay or mathematical certification.\n')
    evidence=[{'path':note.name,'sha256':ir.digest(note)}]
    audit['reviewer']={'identity':'TEST_ONLY_RECEIPT_SHAPE','mode':'same_context_self_audit','independent':False,
                       'disclosure':'Synthetic validator input; does not establish that a real replay occurred.'}
    for row in [audit['target_review'],*audit['definition_reviews'].values(),*audit['source_reviews'].values()]:
        row.update(verdict='PASS',notes='Synthetic receipt-shape regression only.',evidence=evidence)
    for rid,row in audit['inference_reviews'].items():
        row.update(verdict='PASS',notes='Synthetic receipt-shape regression only.',evidence=evidence)
        for check in row['checks'].values():
            check.update(verdict='PASS',notes='Synthetic located shape control.',evidence=evidence,
                         locations=['/inputs','/output','/inference'])
        packet=source.nl0.packet(data,rid)
        row['replay'].update(mode='fresh_packet_only',carrier='TEST_ONLY_NOT_A_REAL_REPLAY',
                             prior_exposure=[],read_materials=['packet:'+packet['packet_sha256']])
    path=base/'audit-test-only.json';ir.write(path,audit)
    return path


def synthetic_local_reviews(directory):
    """Unit-test format fixture; real model reviews are produced separately."""
    directory=Path(directory);base=directory/'case'
    gp,sp=base/'nl0.json',base/'spec.json'
    ap=synthetic_audit(gp,sp);full=ir.load(ap)
    producer=ir.load(base/'producer-review.json');producer['reviewer']=full['reviewer']
    producer['reviews']={rid:full['inference_reviews'][rid] for rid in producer['reviews']}
    ir.write(base/'producer-review.json',producer)
    cut=ir.load(base/'cut-review.json');cut['reviewer']=dict(full['reviewer'],mode='delta_review_with_baseline')
    for row in cut['cuts'].values():
        row.update(verdict='PASS',notes='Synthetic paired substitution receipt format only.',
                   checks={key:'PASS' for key in row['checks']},
                   locations=['/before','/after','/contract','/old_derivation','/shared_statement',
                              '/producer_source_derivation','/input_statements_before','/input_statements_after','/global_context'],
                   evidence=full['target_review']['evidence'])
    ir.write(base/'cut-review.json',cut)


def interface(graph,spec,directory):
    directory.mkdir(parents=True,exist_ok=True)
    graph=Path(graph);data=source.nl0.validate(graph,spec)
    # The canonical graph itself is the source; no reference Lean proof is supplied.
    import shutil
    shutil.copyfile(graph,directory/'nl0.json')
    statements={'N001':'p ∧ p','N002':'p ∨ q','N003':'p','P':'(p ∧ p) ∧ (p ∨ q)'}
    outputs={r['output']:'T'+r['id'][1:] for r in data[4].values()}
    source_steps=[];mapping={};steps=[]
    for index,(rid,r) in enumerate(data[4].items(),1):
        sid=f'S{index:03d}'
        source_steps.append({'id':sid,'text':r['argument'][0]['text']})
        mapping[sid]={'inference':rid,'paragraph':'S001'}
        steps.append({'id':outputs[r['output']],'statement':statements[r['output']],
                      'inputs':[outputs.get(x,x) for x in r['inputs']],'source_steps':[sid],
                      'explanation':r['argument'][0]['text']})
    c={'version':2,'id':'shared_projection_functional','source':{'path':'nl0.json','sha256':ir.digest(graph)},
       'source_steps':source_steps,'pins':{'lean_version':'4.32.2','mathlib_commit':ir.load_lock()['mathlib']['rev']},
       'header':'import Mathlib\n','parameters':[{'name':x,'type':'Prop'} for x in ('p','q')],
       'premises':[{'id':'H001','kind':'hypothesis','type':'p ∧ q','statement':'p ∧ q.'}],
       'conclusion':{'type':statements['P'],'statement':data[3]['P']['statement']},
       'representation':{'logic':'The same fixed propositions and constructive ∧/∨.'},
       'objects':[],'shared_obligations':[],
       'review':{'mode':'upstream_audited_packet','scope':'Requires actual source and interface reviews before workflow acceptance.'}}
    if 'N003' in outputs:
        c['shared_obligations']=[{'id':'L001','statement':'p','inputs':['H001'],
            'source_steps':next(s['source_steps'] for s in steps if s['id']==outputs['N003']),
            'route':'Take the first conjunct of the original H001: p ∧ q.',
            'review':{'classification':'existing_nl0_lemma','status':'UPSTREAM_AUDITED',
                      'reviewer':'Actual source audit required by workflow.freeze', 'basis':'Frozen source node N003 and producer R004.'}}]
        next(s for s in steps if s['id']==outputs['N003'])['shared_lemma']='L001'
    cp=directory/'contract.json';ir.write(cp,c)
    plan={'version':2,'contract_sha256':ir.digest(cp),'representation_notes':'All objects are fixed propositions p,q; no coercion, new assumption, or representation conversion.',
          'steps':steps,'terminal':outputs['P']}
    pp=directory/'plan.json';ir.write(pp,plan)
    review={'version':workflow.VERSION,'source_graph_sha256':ir.digest(graph),'contract_sha256':ir.digest(cp),
            'plan_sha256':ir.digest(pp),'reviewer':{'identity':'UNASSIGNED','mode':'unperformed','independent':False,'disclosure':'Not yet reviewed.'},
            'checks':{name:{'verdict':'UNVERIFIED','notes':'Not reviewed.'} for name in workflow.INTERFACE_CHECKS},
            'paragraph_mapping':mapping,'source_outputs':outputs,'evidence':[]}
    rp=directory/'interface-review.json';ir.write(rp,review)
    return cp,pp,rp


def synthetic_interface_review(path):
    value=ir.load(path);note=Path(path).parent/'TEST_ONLY_INTERFACE_SHAPE.txt'
    note.write_text('SYNTHETIC INTERFACE RECEIPT FORMAT ONLY.\n')
    value['reviewer']={'identity':'TEST_ONLY_RECEIPT_SHAPE','mode':'same_context_self_audit','independent':False,
                       'disclosure':'Synthetic format fixture, not mathematical acceptance evidence.'}
    for row in value['checks'].values():row.update(verdict='PASS',notes='Synthetic schema-control judgment only.')
    value['evidence']=[{'path':note.name,'sha256':ir.digest(note)}];ir.write(path,value)
