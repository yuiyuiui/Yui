"""Case-local investigation of hard foundation items and proof of a selected route."""
from pathlib import Path
import tempfile
import re

import artifact_protocol as p
import basis_graph
import ir
import local_helpers
from controller_common import bind, copy_problem_documents, manifest, verify_bindings, write
from proof_obligations import parallel, private_proof

ITEM = p.obj({'id':basis_graph.BASIS,'statement':p.TEXT,'consumers':p.array(
    p.obj({'id':p.TEXT,'required_use':p.TEXT}),minItems=1)})
FRONTIER = p.obj({'obligations':p.array(ITEM,minItems=1)})
PLAN = p.obj({'candidate':{'type':'integer','minimum':1}})
RESULT = p.obj({'route':{'enum':['mathlib','public-library','derivation','open']},'statement':p.TEXT,
    'argument':p.TEXT,'source':p.TEXT,'consumer_uses':p.array(p.obj({'id':p.TEXT,'application':p.TEXT})),
    'evidence':p.array(p.obj({'path':p.TEXT,'sha256':p.TEXT}))})
PROMPT = """Investigate only your assigned foundation in frontier-item.json. Try existing pinned Mathlib
and public Lean source first. Trace a textbook argument to simpler proved facts, or specialize
to the weakest statement sufficient for every listed consumer. Account for each application, with its
hypotheses. Record the exact public declaration/revision or source and a concrete derivation or gap.
Provide only files actually retrieved by this role in evidence, relative to its stage. Return open when
appropriate. The owner decides the final route. Tool/resource failures do not classify a theorem."""


def investigate(stage, args):
    from clean_stage import ArtifactStage
    from execution_health import require_review_execution, StageFailure
    p.validate(args,FRONTIER)
    items=args['obligations']
    if len({r['id'] for r in items})!=len(items):
        raise ValueError('A frontier batch needs unique basis IDs')
    authority=bind(stage.validator.out/'inputs/inputs.json')
    def solve(item,budget):
        consumers={r['id'] for r in item['consumers']}
        if len(consumers)!=len(item['consumers']):
            raise ValueError('Duplicate consumer for '+item['id'])
        key=local_helpers.digest([authority,item,PROMPT])
        directory=stage.logs/'frontier'/item['id']/key
        directory.mkdir(parents=True,exist_ok=True)
        checkpoint=directory/'checked.json'
        if checkpoint.exists():
            old=ir.load(checkpoint)
            verify_bindings([old['result'],*old['files']])
            return ir.load(old['result']['path'])
        attempt=Path(tempfile.mkdtemp(prefix='attempt-',dir=directory))
        inputs=attempt/'inputs';inputs.mkdir()
        copy_problem_documents(stage.validator.out/'inputs',inputs)
        write(inputs/'frontier-item.json',item)
        manifest(inputs)
        def check(value):
            p.validate(value,RESULT)
            actual=[r['id'] for r in value['consumer_uses']]
            if len(actual)!=len(consumers) or set(actual)!=consumers:
                raise ValueError('Explain the proposed theorem at every actual consumer')
            for row in value['evidence']:
                external=(attempt/'stage/external-sources').resolve()
                file=(attempt/'stage'/row['path']).resolve()
                if not file.is_relative_to(external) or not file.is_file() or bind(file)['sha256']!=row['sha256']:
                    raise ValueError('Unknown or changed retrieved evidence '+row['path'])
            return {'checked_consumers':len(actual)}
        check.schema=RESULT
        worker=ArtifactStage(attempt/'stage',PROMPT,phase='basis-frontier',inputs=inputs/'inputs.json',
                             validator=check,budget=budget)
        result,value=worker.execute()
        try:require_review_execution(result,attempt/'stage/result.json',phase='basis-frontier')
        except StageFailure as error:
            if error.result['status']=='EXECUTION_UNQUALIFIED':raise RuntimeError(str(error)) from error
            raise
        check(value)
        value={**value,'id':item['id'],'request_sha256':key}
        files=[]
        for row in value['evidence']:
            file=(attempt/'stage'/row['path']).resolve()
            files.append(bind(file))
            from staging_storage import copy_input
            shared=stage.logs/'external-sources'/(row['sha256']+file.suffix)
            shared.parent.mkdir(parents=True,exist_ok=True)
            if not shared.exists():copy_input(file,shared)
            if bind(shared)['sha256']!=row['sha256']:raise RuntimeError('Shared retained source changed')
            row['path']=str(shared.relative_to(stage.logs))
        write(attempt/'proposal.json',value)
        write(checkpoint,{'result':bind(attempt/'proposal.json'),'files':files})
        from proof_obligations import complete_private
        complete_private(worker,checkpoint)
        return value
    results=parallel(stage,items,solve,requested=stage.validator.concurrency)
    return {'proposals':results,'stage_complete':False}


def check_types(stage,candidate):
    import basis_native
    rows=candidate['dependencies']
    source=candidate['lean_header']+'\nnamespace YuiBasisTypes\nset_option autoImplicit false\n'
    checks=[]
    for row in rows:
        source+=ir.checked_expression(row['id'],row['lean']['type'],proposition=True)
        checks.append((row['id'],'YuiBasisTypes.'+row['id'],row['lean']['type']))
    source+='\nend YuiBasisTypes\n'
    directory=stage.logs/'selected-types'/local_helpers.digest([source,checks])
    directory.mkdir(parents=True,exist_ok=True)
    saved=directory/'selected.json'
    if saved.is_file():
        ref=ir.load(saved);verify_bindings([ref]);basis_native.verify(ref['path']);return
    attempt=Path(tempfile.mkdtemp(prefix='candidate-',dir=directory))/'native'
    result=basis_native.check(source,checks,[r[1] for r in checks],attempt)
    if not result['passed']:
        raise ValueError('Repair the selected foundation types before launching proofs: '+ir.compiler_feedback(ir.load(attempt/'compiler.json')))
    write(saved,bind(attempt/'check.json'))


def prepare(stage,args):
    import basis
    from copy import deepcopy
    p.validate(args,PLAN)
    n=args['candidate']
    if n not in stage.validator.drafts:
        raise ValueError('Save the proposed complete route before dispatch')
    candidate=basis_graph.optimize(stage.validator.drafts[n])
    pending=[r for r in candidate['dependencies'] if r['category']!=4 and r['lean']['proof'] is None]
    # Validate the complete graph, names, source paths and typed interfaces before paying workers.
    shape=deepcopy(candidate)
    for row in shape['dependencies']:
        if row['category']!=4 and row['lean']['proof'] is None:row['lean']['proof']='trivial'
    rows,_=basis.validate(shape,stage.validator.target)
    basis.evidence_bindings(shape,stage.validator.out/'inputs',stage.logs)
    if pending:check_types(stage,candidate)
    if pending and any(r['category']==4 for r in candidate['dependencies']):
        import basis_preapproval
        basis_preapproval.approve(stage,candidate)
    def solve(row,budget):
        inputs=[]
        definitions=[]
        for i,dep in enumerate(row['uses'],1):
            name=f'H{i:03d}';up=rows[dep]
            inputs.append({'id':name,'kind':'hypothesis','statement':up['statement'],'type':up['lean']['type']})
            definitions.append('have h_'+name+' : '+up['lean']['type']+' := @YuiBasis.'+dep)
        consumers=[step for step in candidate['global_graph']['inferences'] if row['id'] in step['basis']]
        identity=local_helpers.digest([row,consumers,candidate['full_target']])
        body=private_proof(stage.logs/'foundation-proofs',identity=identity[:20],header=candidate['lean_header'],
                parameters=[],premises=inputs,target=row['lean']['type'],statement=row['statement'],
                route=row['justification']+'\nOriginal target: '+candidate['full_target']+'\nSource: '+str(row['origin'])+
                      '\nConsumers: '+str(consumers)+'\nUse the supplied direct hypothesis binders for the selected dependencies.',
                budget=budget,evidence=basis.evidence_bindings({'dependencies':[row,*[rows[d] for d in row['uses']]]},
                    stage.validator.out/'inputs',stage.logs))
        return '\n'.join([*definitions,body])
    proofs=parallel(stage,pending,solve,requested=stage.validator.concurrency)
    for row,proof in zip(pending,proofs):
        row['lean']['proof']=proof
    new,_=stage.validator.save(candidate)
    return {'candidate':stage.validator.attempt,'prepared':[r['id'] for r in pending],
            'active':[r['id'] for r in new['dependencies']],'stage_complete':False,
            'next':'check_draft or submit_draft with accept_candidate and this candidate number'}
