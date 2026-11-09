"""Author-separated, batch comparison of prepared basis statements to native propositions."""
from copy import deepcopy
import json
from pathlib import Path

from audit_reuse import hashed
from controller_common import bind, manifest, verify_bindings, write
from execution_health import StageFailure, require_review_execution
from review_contract import ReviewContract
import artifact_protocol as protocol
import ir

VERSION = 'yui-basis-fidelity-1'
PACKET = 'basis-comparison.json'
ROLE = 'basis-reviewer'
STAGE_FILES = ('accepted.json', 'execution-manifest.json', 'exposure-audit.json', 'result.json', 'tools.jsonl')

PROMPT = """Independently compare each required basis dependency in basis-comparison.json.
Read its source/revision, actual evidence, the full target, basis proof and the actual Lean
proposition produced by the pinned compiler. Use the declared source documents and Mathlib
tools as needed. Locate its use in the rewritten argument. Compare quantifier order,
uniformity and constants, domains, binder/instance assumptions, implication direction,
definitions, and any adapter or specialization. Compare the original H and target to the rewritten application. For class 4 review the exact residual
assumption and the complete textbook evidence; this does not prove the theorem. For each prepared class 3 check its actual derivation and every consumer, including the scope of any specialization. Review the required set in this one role.
Use the generated submission schema for the selected items and coverage.
In notes explain the specific correspondence or
mismatch. locations must include the exact pointers /items/B001/statement and
/items/B001/actual_type for that item. In source identify the declaration/text and why it
supports the claim, or precisely what is missing. If revision_objection names this item, include
a resolution field that answers that exact earlier objection against the revised proposition and use. In application identify the actual use
and whether the available hypotheses suffice. Assess every required item. Do not rewrite
the proof or approve residual assumptions for the user. Report all located findings."""
RULE = hashed([VERSION, PROMPT, ir.digest(Path(__file__).resolve().parents[1]/'references/basis.md')])


def native_basis_dependencies(name, declarations, basis_names):
    """Resolve real B declarations through compiler-generated local helpers.

    A helper such as YuiBasis.B001._simp_1 is not a registry ID. Follow its
    checked native dependencies until an exact registered declaration is met.
    Imported library constants need no project dependency expansion.
    """
    found=set();seen={name};pending=list(declarations[name]['direct_constants'])
    while pending:
        current=pending.pop()
        if current in seen:continue
        seen.add(current)
        if current in basis_names:
            found.add(basis_names[current])
        elif current in declarations and not declarations[current]['imported']:
            pending.extend(declarations[current]['direct_constants'])
    return sorted(found)


def material(artifact, native, originals, evidence, revision_report=None):
    """Same projection for the initial reviewer and a later receipt readback."""
    inspected = ir.load(Path(native['path']).parent/'elaborated.json')
    types = {r['id']:r['actual_type'] for r in inspected['comparisons']}
    declarations = {r['name']:r for r in inspected['dependencies']['declarations']}
    basis_names={'YuiBasis.'+r['id']:r['id'] for r in artifact['dependencies'] if r['category']!=4 and r['lean'] is not None}
    items = {}
    source_docs = {Path(r['path']).name:r['sha256'] for r in originals}
    external = {r['sha256']:'basis-source-'+r['sha256']+'.txt' for r in evidence}
    for row in artifact['dependencies']:
        item = deepcopy(row)
        if row['lean'] is not None:
            item['actual_type'] = types[row['id']]
            name = ('YuiBasis.type_' if row['category']==4 else 'YuiBasis.')+row['id']
            item['signature'] = declarations[name]['signature'] if row['category']!=4 else None
            item['native_dependencies'] = native_basis_dependencies(name,declarations,basis_names)
        item['documents'] = [ref['input'] if 'input' in ref else external[ref['sha256']]
                             for ref in row['origin']['evidence']]
        items[row['id']] = item
    objection=None
    if revision_report:
        verify_bindings([revision_report])
        objection=ir.load(revision_report['path'])['finding']
    return {'revision_objection':objection,'target':artifact['full_target'], 'proof':artifact['proof'], 'header':artifact['lean_header'],
            **({'global_graph':artifact['global_graph']} if 'global_graph' in artifact else {}),
            'replacements':artifact['replacements'], 'documents':source_docs, 'items':items}


LEGACY_RULE='3abe1dc3c52b4314c9baad29e85c38c39cc48785afd8916b97393e2cbc5fdf98'
# Read previously issued reports under their original comparison key. Newly
# assigned reports always use RULE, including when computing reuse keys.
PRE_NUMBERING_RULE='adf3fcd09c4a7f9b019a55237c1045619366a0abd48f05ddfd9868f30464fd6b'


def rule_for(packet, rule):
    if rule not in (RULE,PRE_NUMBERING_RULE) and (rule!=LEGACY_RULE or 'global_graph' in packet):
        raise ValueError('Unknown basis review rules for this protocol')
    return rule


def item_keys(packet, rule=None):
    common = {k:v for k,v in packet.items() if k not in {'items','required'}}
    items = packet['items']
    links = {k:set(row['uses']) | set(row.get('native_dependencies',[])) for k,row in items.items()}
    unknown=set().union(*links.values())-items.keys() if links else set()
    if unknown:raise ValueError('Unknown basis dependency IDs: '+', '.join(sorted(unknown)))
    # A changed consumer can change the application being assessed.
    for key,related in list(links.items()):
        for other in list(related):
            if other in links:links[other].add(key)
    result = {}
    for key,row in items.items():
        if row['lean'] is None:continue
        seen=set();pending=[key]
        while pending:
            current=pending.pop()
            if current in seen:continue
            seen.add(current);pending.extend(links[current]-seen)
        result[key]=hashed([rule_for(packet,rule or RULE),common,{k:items[k] for k in sorted(seen)}])
    return result


JUDGMENT_FIELDS = {
    'verdict': protocol.VERDICT,
    'notes': protocol.TEXT, 'source': protocol.TEXT, 'application': protocol.TEXT,
    'locations': {'type':'array','items':{'type':'string'}},
}


def row_schema(key, objection=None):
    properties=dict(JUDGMENT_FIELDS)
    if objection and key==objection['basis_id']:properties['resolution']=protocol.TEXT
    return protocol.obj(properties)


def review_shape(required, objection=None):
    return protocol.ReviewShape(groups={'items':{key:row_schema(key,objection) for key in required}})


def judgment_schema(objection):
    return protocol.nullable(protocol.choice(row_schema(None),row_schema(objection['basis_id'],objection))
                             if objection else row_schema(None))


def validate_judgment(key, row, objection=None, packet=None):
    path = '/items/' + key
    protocol.validate(row,row_schema(key,objection),path)
    locations = row['locations']
    if not isinstance(locations, list) or not all(isinstance(p, str) and p.startswith('/') for p in locations):
        raise ValueError(f'{path}/locations: expected a list of absolute JSON pointers')
    missing = {path+'/statement', path+'/actual_type'} - set(locations)
    if missing:
        raise ValueError(f'{path}/locations: include {sorted(missing)}')
    if packet is not None:
        from nl0 import closure
        for location in locations:
            closure.resolve(packet, location)


def validate_rows(value, required, objection=None, packet=None):
    review_shape(required,objection).validate(value)
    for key,row in value['items'].items():
        validate_judgment(key, row, objection, packet)
    return {'scope':'Reviewed basis interfaces only', 'whole_proof_acceptance':False}


def complete_submission(stage, raw):
    """Require the final tool handoff and the reviewer's own judgments for every saved item."""
    expected=raw['items']
    covered={'/items/'+key:'assessed' for key in expected}
    seen=set()
    for line in (stage/'tools.jsonl').read_text().splitlines():
        call=json.loads(line);name=call.get('tool');args=call.get('arguments',{});reply=call.get('result',{})
        if name=='record_review_item':
            pointer=args.get('pointer')
            if (pointer in covered and args.get('coverage')=='assessed' and reply.get('recorded')==pointer and
                    args.get('judgment')==expected[pointer.split('/')[-1]]):
                seen.add(pointer)
            continue
        if name not in {'check_draft','check_artifact','submit_draft','submit_artifact'}:
            continue
        try:
            value=args['artifact'] if name.endswith('_draft') else json.loads(args['artifact_json'])
        except (KeyError,TypeError,ValueError):
            continue  # A rejected earlier malformed wrapper supplies no judgments.
        if not isinstance(value,dict):continue
        coverage=value.get('coverage');items=value.get('items')
        saved = reply.get('accepted') is True or str(reply.get('error','')).startswith('REVIEW_INCOMPLETE:')
        if saved and isinstance(coverage,dict) and isinstance(items,dict):
            for key,row in items.items():
                pointer='/items/'+key
                if pointer in covered and coverage.get(pointer)=='assessed' and row==expected[key]:
                    seen.add(pointer)
        if not name.startswith('submit_') or reply.get('stage_complete') is not True:continue
        if value=={'from_saved_review':True,'summary':{}}:return seen==set(covered)
        return coverage==covered and {k:v for k,v in value.items() if k!='coverage'}==raw
    return False


def read_batch(binding):
    verify_bindings([binding])
    path=Path(binding['path']);batch=ir.load(path);stage=path.parent/'stage';inputs=path.parent/'inputs'
    if path.name!='assessment.json' or batch['version']!=VERSION:raise ValueError('Wrong basis assessment or rules')
    names={r['id']:r for r in ir.load(inputs/'inputs.json')['inputs']}
    if batch['manifest']!=bind(inputs/'inputs.json'):raise ValueError('Basis review inputs changed')
    for name,doc in names.items():
        if Path(name).name!=name or doc['path']!=name or ir.digest(inputs/name)!=doc['sha256']:
            raise ValueError('Changed basis reviewer document')
    packet=ir.load(inputs/PACKET);keys=item_keys(packet,rule_for(packet,batch['rule']));required=packet['required']
    if any(names[name]['sha256']!=digest for name,digest in packet['documents'].items()):
        raise ValueError('Basis review did not receive the bound original source bytes')
    external={name for row in packet['items'].values() for name in row['documents'] if name not in packet['documents']}
    if set(names)!={PACKET,*packet['documents'],*external} or set(batch['evidence_views'])!=external:
        raise ValueError('Wrong basis reviewer source projection')
    for name,view in batch['evidence_views'].items():
        if name!='basis-source-'+view['source']['sha256']+'.txt' or view['text_sha256']!=names[name]['sha256']:
            raise ValueError('Changed basis reviewer evidence projection')
        verify_bindings([view['source']])
    if not required or sorted(set(required))!=required or not set(required)<=keys.keys():
        raise ValueError('Invalid basis assessment scope')
    if batch['execution']!=[bind(stage/n) for n in STAGE_FILES]:raise ValueError('Basis reviewer execution changed')
    result=ir.load(stage/'result.json');exposure=ir.load(stage/'exposure-audit.json');m=ir.load(stage/'execution-manifest.json')
    require_review_execution(result,stage/'result.json',phase='basis-semantic-review')
    if (result['exposure']!=exposure or m['task_documents']!={k:r['sha256'] for k,r in names.items()}
            or m.get('phase')!='basis-semantic-review' or (m.get('role_session') or {}).get('role')!=ROLE
            or m.get('role_session')!=result.get('role_session')):
        raise ValueError('Basis assessment lacks a separate bound reviewer')
    actual_author=path.parents[1]/'stage/result.json'
    early=path.parents[1]/'planning-author.json'
    if result.get('native_thread_id') and early.is_file():
        origin=ir.load(early);planned=path.parents[1];owner=planned.parents[1]
        if planned.parent.name!='plans' or origin['manifest']!=bind(owner/'stage/execution-manifest.json'):
            raise ValueError('Wrong originating planning author')
        verify_bindings([origin['candidate']])
        import basis_graph, basis_preapproval
        candidate=Path(origin['candidate']['path'])
        if (candidate.parent.parent!=owner/'candidates' or not origin['thread_id'] or
                origin['thread_id']==result['native_thread_id'] or
                ir.load(origin['manifest']['path']).get('role_session',{}).get('role')!='basis-author' or
                basis_preapproval.projection(basis_graph.optimize(ir.load(candidate)))!=ir.load(planned/'stage/accepted.json')):
            raise ValueError('Residual reviewer did not receive an independent, bound planning candidate')
        final_author=owner/'stage/result.json'
        if final_author.is_file() and ir.load(final_author).get('native_thread_id')!=origin['thread_id']:
            raise ValueError('Changed planning author identity')
    elif result.get('native_thread_id'):
        author=ir.load(actual_author)
        require_review_execution(author,actual_author,phase='basis-authoring')
        if ((author.get('role_session') or {}).get('role')!='basis-author' or not author.get('native_thread_id')
                or result['native_thread_id']==author['native_thread_id']):
            raise ValueError('The basis author cannot review its own submission')
    for doc in m['frozen_task_files']:
        transmitted=(stage/doc['path']).resolve()
        if (transmitted.parent!=stage/'task-inputs' or doc['sha256']!=names[doc['id']]['sha256']
                or ir.digest(transmitted)!=doc['sha256']):
            raise ValueError('Changed basis reviewer disclosed input')
    if {row['id'] for row in m['frozen_task_files']}!=set(names):raise ValueError('Incomplete reviewer documents')
    raw=ir.load(stage/'accepted.json');validate_rows(raw,required,packet['revision_objection'],packet)
    progress=path.parent/'review-work/progress.json'
    expected={'/items/'+key:{'coverage':'assessed','judgment':row} for key,row in raw['items'].items()}
    if (batch['progress']!=bind(progress) or ir.load(progress)['items']!=expected or
            not complete_submission(stage,raw)):
        raise ValueError('Missing complete basis reviewer submission evidence')
    return keys,raw['items']


def assess(out, context, artifact, sessions, budget, history):
    from clean_stage import ArtifactStage
    from jobs import stage_document
    from runtime_config import configured_timeout
    directory=out/'review';inputs=directory/'inputs'
    packet=material(artifact,context['native'],context['original_inputs'],context['evidence'],context.get('revision_report'))
    keys=item_keys(packet);required=sorted(k for k,v in keys.items() if v not in history)
    sources={k:history[v] for k,v in keys.items() if v in history}
    if required:
        inputs.mkdir(parents=True)
        for row in context['original_inputs']:
            stage_document(Path(row['path']),inputs/Path(row['path']).name)
        external={name for row in packet['items'].values() for name in row['documents'] if name not in packet['documents']}
        views={}
        for row in context['evidence']:
            name='basis-source-'+row['sha256']+'.txt'
            if name not in external or name in views:continue
            stage_document(Path(row['path']),inputs/name)
            views[name]={'source':row,'text_sha256':ir.digest(inputs/name)}
        write(inputs/PACKET,{**packet,'required':required});manifest(inputs)
        contract=ReviewContract.structured(directory/'review-work',review_shape(required,packet['revision_objection']),
            lambda value:validate_rows(value,required,packet['revision_objection'],packet),
            row_validator=lambda pointer,row:validate_judgment(pointer.split('/')[-1],row,packet['revision_objection'],packet),
            complete_assessment=True)
        stage=ArtifactStage(directory/'stage',PROMPT,phase='basis-semantic-review',validator=contract,
            inputs=inputs/'inputs.json',budget=budget,timeout=configured_timeout('stage'))
        with sessions.use(ROLE):stage.execute()
        result=ir.load(directory/'stage/result.json')
        require_review_execution(result,directory/'stage/result.json',phase='basis-semantic-review')
        path=directory/'assessment.json'
        write(path,{'version':VERSION,'rule':RULE,'manifest':bind(inputs/'inputs.json'),'evidence_views':views,
                    'progress':bind(directory/'review-work/progress.json'),
                    'execution':[bind(directory/'stage'/name) for name in STAGE_FILES]})
        ref=bind(path);read_batch(ref)
        for key in required:
            sources[key]=ref;history[keys[key]]=ref
    report={'version':VERSION,'rule':RULE,'basis':context['basis'],'native':context['native'],
            'original_inputs':context['original_inputs'],'evidence':context['evidence'],'assessments':sources}
    path=directory/'report.json';write(path,report)
    ref=bind(path)
    findings=verify(ref,context,artifact,require_pass=False)
    if findings and not required:
        raise StageFailure('REPAIR_CYCLE','Unchanged rejected basis correspondence',phase='basis-semantic-review',evidence=path)
    return ref,findings


def verify(ref, context, artifact, *, require_pass=True):
    verify_bindings([ref]);path=Path(ref['path']);report=ir.load(path)
    revision=Path(context['basis']['path']).parent.parent
    if path!=revision/'review/report.json' or report.get('version')!=VERSION or any(
            report[k]!=context[k] for k in ('basis','native','original_inputs','evidence')):
        raise ValueError('Basis semantic receipt belongs to different inputs')
    packet=material(artifact,context['native'],context['original_inputs'],context['evidence'],context.get('revision_report'))
    keys=item_keys(packet,rule_for(packet,report.get('rule')))
    if set(keys)!=set(report['assessments']):raise ValueError('Incomplete basis semantic coverage')
    batches={};findings={}
    for key,binding in report['assessments'].items():
        batch_path=Path(binding['path'])
        if batch_path.parent.name!='review' or batch_path.parents[2]!=path.parents[2]:
            raise ValueError('Cross-run basis review inheritance')
        identity=(binding['path'],binding['sha256'])
        if identity not in batches:batches[identity]=read_batch(binding)
        old,rows=batches[identity]
        if key not in rows or keys[key]!=old[key]:raise ValueError('Stale basis correspondence: '+key)
        if rows[key]['verdict']!='PASS':findings[key]=rows[key]
    if findings and require_pass:raise ValueError('Basis semantic review did not pass')
    return findings
