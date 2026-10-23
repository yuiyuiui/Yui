"""Conservative, evidence-bound Audit A item inheritance. Never synthesize PASS."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

from execution_health import qualification
from execution_state import atomic

VERSION='yui-review-reuse-1'
SEMANTIC_RULES=('references/nl0-format.md','references/self-containment.md',
                'references/audit-a.md','references/external-theorems.md','references/logical-rules.md')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())
def hashed(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def rules():
    core=Path(__file__).resolve().parents[1]
    return {name:sha(core/name) for name in SEMANTIC_RULES}


def data_from_files(graph_path,spec_path):
    """Reconstruct a review view from hashed bytes; caller validates live sources."""
    graph=load(graph_path);spec=load(spec_path)
    props={p['id']:p for p in graph['propositions']};steps={r['id']:r for r in graph['inferences']}
    defs={d['id']:d for d in spec['definitions']}
    def closure(ids):
        result=set();active=set()
        def visit(key):
            if key in active:raise ValueError('Cyclic definition context')
            if key in result:return
            active.add(key)
            for dep in defs[key]['depends_on']:visit(dep)
            active.remove(key);result.add(key)
        for key in ids:visit(key)
        return result
    return ({'graph_sha256':sha(graph_path),'spec_sha256':sha(spec_path)},graph,spec,props,steps,defs,closure,None)


def context(data,scope,*,semantic_rules=None):
    import nl0
    _,graph,spec,props,steps,defs,closure,_=data
    common={'version':VERSION,'semantic_rules':rules() if semantic_rules is None else semantic_rules,
            'approved_task':{k:spec[k] for k in ['case_id','full_target','conclusion','parameters','hypotheses','logic','pins']}}
    kind,_,key=scope.partition(':')
    if kind=='packet':
        packet=deepcopy(nl0.packet(data,key))
        # Only these known envelope fields are excluded. Other hashes, guards,
        # types, complete prose/scopes, source contracts and pins remain.
        for field in ['graph_sha256','spec_sha256','packet_sha256']:packet.pop(field)
        common['packet']=packet
        common['source_contracts']={p:props[p]['source'] for p in steps[key]['inputs'] if props[p]['kind'] in {'external','mathlib'}}
    elif kind=='definition':
        common['definitions']=[defs[d] for d in sorted(closure([key]))]
        common['guards']={p:props[p] for d in closure([key]) for p in defs[d]['requires']}
    elif kind=='source':
        common['source']=props[key]
        common['definitions']=[defs[d] for d in sorted(closure(props[key]['definitions']))]
        common['applications']=[r for r in steps.values() if key in r['inputs']]
    elif kind=='target':
        common['target']=props['P']
        common['definitions']=[defs[d] for d in sorted(closure(props['P']['definitions']))]
    elif kind=='structure':
        common['graph']={k:v for k,v in graph.items() if k!='spec_sha256'}
        common['definitions']=spec['definitions']
    else:raise ValueError('Unknown review scope '+scope)
    return common


def all_pass(row):
    if isinstance(row,dict):
        if 'verdict' in row and row['verdict']!='PASS':return False
        return all(all_pass(v) for v in row.values())
    if isinstance(row,list):return all(all_pass(v) for v in row)
    return True


def select(data,campaigns):
    """Explicit prior campaigns only; no cross-case or implicit warm cache."""
    import nl0
    hits={}
    for campaign in campaigns:
        campaign=Path(campaign).resolve();plan=load(campaign/'campaign.json')
        for key in ['graph','spec']:
            if sha(plan[key]['path'])!=plan[key]['sha256']:raise ValueError('Previous audit source changed')
        old=nl0.validate(plan['graph']['path'],plan['spec']['path'])
        if old[2]['case_id']!=data[2]['case_id']:raise ValueError('Review reuse cannot cross case identities')
        for job in plan['jobs']:
            directory=campaign/job['id'];stage=directory/'stage'
            if not (stage/'accepted.json').is_file():continue
            result=load(stage/'result.json')
            if result.get('status')!='ACCEPTED' or not qualification(result)['execution_qualified']:continue
            manifest=load(stage/'execution-manifest.json')
            if {k:manifest.get('rule_documents',{}).get(k) for k in SEMANTIC_RULES}!=rules():continue
            raw=load(stage/'accepted.json');items=[]
            if job['library']:
                if any(f.get('verdict')=='FAIL' or str(f.get('severity','')).upper() in {'BLOCKING','FAIL','ERROR','FATAL'} for f in raw.get('findings',[])):continue
                for name in ['spec.json','nl0.json']:
                    if manifest['task_documents'].get(name)!=sha(directory/name):raise ValueError('Previous review input identity changed')
                if sha(directory/'nl0.json')!=old[0]['graph_sha256'] or sha(directory/'spec.json')!=old[0]['spec_sha256']:
                    raise ValueError('Previous global review did not see the bound source')
                if 'target_review' in raw:items.append(('target','/target_review',raw['target_review']))
                if 'structure_review' in raw:items.append(('structure','/structure_review',raw['structure_review']))
                for group,kind in [('definition_reviews','definition'),('source_reviews','source')]:
                    items.extend((kind+':'+key,'/'+group+'/'+key,row) for key,row in raw.get(group,{}).items())
            else:
                packet=load(directory/'packet.json')
                if manifest['task_documents'].get('packet.json')!=sha(directory/'packet.json') or packet!=nl0.packet(old,job['id']):
                    raise ValueError('Previous packet review saw a different input')
                if raw.get('packet_sha256')!=packet['packet_sha256'] or raw.get('inference')!=job['id']:continue
                if any(f.get('verdict')=='FAIL' or str(f.get('severity','')).upper() in {'BLOCKING','FAIL','ERROR','FATAL'} for f in raw.get('findings',[])):continue
                if set(raw.get('checks',{}))!=nl0.CHECKS|nl0.closure.CLOSURE_CHECKS:continue
                items=[('packet:'+job['id'],'',raw)]
            for scope,selector,row in items:
                if scope in hits or row.get('verdict')!='PASS' or not row.get('notes') or not all_pass(row):continue
                try:old_context=context(old,scope);new_context=context(data,scope)
                except (KeyError,ValueError):continue
                if old_context!=new_context:continue
                hits[scope]={'scope':scope,'selector':selector,'row':deepcopy(row),
                    'campaign':str(campaign),'directory':str(directory),'context_sha256':hashed(old_context),
                    'graph':plan['graph'],'spec':plan['spec'],'measurement':qualification(result)}
    return hits


def materialize(hit,case):
    """Copy bounded original evidence once by content hash, keeping it portable."""
    case=Path(case).resolve();folder=case/'review-evidence/reuse';folder.mkdir(parents=True,exist_ok=True)
    directory=Path(hit['directory']);previous={}
    files={'graph':Path(hit['graph']['path']),'spec':Path(hit['spec']['path']),
           **{name:directory/'stage'/filename for name,filename in [('raw','accepted.json'),('result','result.json'),
               ('manifest','execution-manifest.json'),('exposure','exposure-audit.json')]}}
    if hit['scope'].startswith('packet:'):files['packet']=directory/'packet.json'
    for name,path in files.items():
        digest=sha(path);target=folder/(digest+'-'+path.name)
        if target.exists() and sha(target)!=digest:raise ValueError('Cached evidence was changed')
        if not target.exists():shutil.copyfile(path,target)
        previous[name]={'path':str(target.relative_to(case)),'sha256':digest}
    record={'version':VERSION,'scope':hit['scope'],'selector':hit['selector'],
            'previous':previous,'context_sha256':hit['context_sha256'],'previous_campaign':hit['campaign'],
            'qualification':hit['measurement'],
            'cost_policy':'Warm inherited judgment; original result retains actual usage. No cold benchmark or parent campaign acceptance is inferred.'}
    path=folder/(hashed(record)+'.json');atomic(path,record)
    return {'path':str(path.relative_to(case)),'sha256':sha(path)}


def read_binding(case,binding):
    case=Path(case).resolve()
    def checked(row):
        path=(case/row['path']).resolve()
        if not path.is_relative_to(case) or not path.is_file() or sha(path)!=row['sha256']:
            raise ValueError('Stale or escaping inherited review evidence')
        return path
    record=load(checked(binding))
    if record['version']!=VERSION:raise ValueError('Unsupported review inheritance')
    paths={key:checked(row) for key,row in record['previous'].items()}
    return record,paths


def raw_from_binding(case,binding):
    record,paths=read_binding(case,binding)
    raw=load(paths['raw'])
    for part in record['selector'].split('/')[1:]:raw=raw[part]
    return raw


def validate(case,binding,data,scope,entry=None):
    import nl0
    record,paths=read_binding(case,binding)
    if record['scope']!=scope:raise ValueError('Inherited review scope changed')
    kind,_,key=scope.partition(':')
    selector={'packet':'','target':'/target_review','structure':'/structure_review',
              'definition':'/definition_reviews/'+key,'source':'/source_reviews/'+key}[kind]
    if record['selector']!=selector:raise ValueError('Inherited review selector differs from its scope')
    old=data_from_files(paths['graph'],paths['spec'])
    old_context=context(old,scope);new_context=context(data,scope)
    if old_context!=new_context or hashed(new_context)!=record['context_sha256']:
        raise ValueError('Inherited review mathematical context changed')
    result=load(paths['result']);manifest=load(paths['manifest']);exposure=load(paths['exposure'])
    if result.get('status')!='ACCEPTED' or not qualification(result)['execution_qualified'] or exposure!=result['exposure']:
        raise ValueError('Inherited review execution is unqualified')
    if {k:manifest.get('rule_documents',{}).get(k) for k in SEMANTIC_RULES}!=rules():
        raise ValueError('Inherited review semantic rules changed')
    if scope.startswith('packet:'):
        packet=load(paths['packet']);rid=scope.split(':')[1]
        if packet!=nl0.packet(old,rid) or manifest['task_documents'].get('packet.json')!=sha(paths['packet']):
            raise ValueError('Inherited packet does not match actual reviewed input')
        previous_packet=packet['packet_sha256']
    else:
        if (manifest['task_documents'].get('nl0.json')!=sha(paths['graph']) or
                manifest['task_documents'].get('spec.json')!=sha(paths['spec'])):
            raise ValueError('Inherited source does not match actual review inputs')
        previous_packet=None
    raw=raw_from_binding(case,binding)
    if not all_pass(raw) or raw.get('verdict')!='PASS':raise ValueError('Only qualified actual passing items can be inherited')
    if entry is not None:match_judgment(entry,raw)
    return {'previous_packet_sha256':previous_packet,'record':record,'raw':raw}


def match_judgment(entry,raw):
    if entry['verdict']!=raw['verdict']:raise ValueError('Inherited verdict differs from actual review')
    notes=raw['notes']
    permitted=[notes,notes+' Actual locations: '+json.dumps(raw.get('locations',[]),ensure_ascii=False)]
    if entry['notes'] not in permitted:raise ValueError('Inherited judgment notes changed')
    if 'locations' in entry and entry['locations']!=list(dict.fromkeys(raw.get('locations',[]))):
        raise ValueError('Inherited judgment locations changed')
    for group in ['checks','citation_checks','external_applications']:
        if group in raw:
            if set(entry[group])!=set(raw[group]):raise ValueError('Inherited child review coverage changed')
            for key,row in raw[group].items():match_judgment(entry[group][key],row)
    for name in ['bindings_review','conclusion_review']:
        if name in raw:match_judgment(entry[name],raw[name])
    if 'hypothesis_reviews' in raw:
        if len(entry['hypothesis_reviews'])!=len(raw['hypothesis_reviews']):raise ValueError('Inherited hypothesis coverage changed')
        for left,right in zip(entry['hypothesis_reviews'],raw['hypothesis_reviews']):match_judgment(left,right)
        if entry['input']!=raw['input'] or entry['bridges']!=raw['bridges']:raise ValueError('Inherited application mapping changed')
