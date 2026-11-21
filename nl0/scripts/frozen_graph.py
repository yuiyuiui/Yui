"""Versioned NL0 outlines, local proofs and proof-derived working graphs."""
from copy import deepcopy
import json
import os
import tempfile
from pathlib import Path

import artifact_protocol as protocol
import basis_graph
import graph_outline
import graph_refinement
import nl0
from artifact_validation import NL0Contract
from controller_common import bind, manifest, verify_bindings, write
from staging_storage import copy_input

ORIGINAL_FIELDS = ('full_target', 'conclusion', 'parameters', 'hypotheses')
GLOBAL_FIELDS = ('id', 'inputs', 'output', 'definitions')
BODY_FIELDS = ('rules', 'locals', 'argument', 'applications')
ASSIGNED = 'assigned-global.json'
ASSIGNED_PROOFS = 'assigned-local-proofs.json'
PRIOR_OUTLINE = 'prior-proof-outline.json'
DIRECT = 'nl0-global'
BASIS = 'nl0-global-from-basis'
LOCAL = 'nl0-local-authoring'
OBJECT = {'type':'object', 'additionalProperties':True}
LOCAL_PROOF = protocol.obj({'id':protocol.STRING,'rules':protocol.array(protocol.STRING),
                            'locals':protocol.array(OBJECT),'argument':protocol.array(OBJECT,minItems=1),
                            'applications':protocol.array(OBJECT)})
LOCAL_PROOFS = protocol.array(LOCAL_PROOF,minItems=1)

def shape(graph):
    return {'propositions':graph['propositions'],
            'inferences':[{name:row[name] for name in GLOBAL_FIELDS} for row in graph['inferences']],
            **({'foundation_ports':graph['foundation_ports']} if 'foundation_ports' in graph else {})}

def indexed(rows):
    if not isinstance(rows,list) or any(not isinstance(row,dict) or not isinstance(row.get('id'),str) for row in rows):
        raise ValueError('Supply an ID on each global or local node')
    result = {row['id']:row for row in rows}
    if len(rows) != len(result):
        raise ValueError('Repeated global or local node ID')
    return result

def evidence(source, graph, target):
    import source_preparation
    for path in source_preparation.evidence_paths(graph, source):
        dest = target / path.relative_to(source)
        if dest.exists():
            if nl0.sha(dest) != nl0.sha(path):
                raise ValueError('Frozen evidence collision at '+str(dest))
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            copy_input(path, dest)

def checked_receipt(source, owner, *, foundation=None, previous=None):
    source = Path(source)
    _, graph, _, *_ = nl0.validate(source/'nl0.json',source/'spec.json',global_only=True)
    if not all('usage' in prop for prop in graph['propositions']):
        raise ValueError('USAGE: new working graphs must index every proposition before selection')
    receipt = source/'checked-global.json'
    record = {'version':'yui-working-graph-4','owner':owner,'previous':previous,'spec':bind(source/'spec.json'),
              'graph':bind(source/'nl0.json'),**({'foundation':foundation} if foundation else {})}
    outline = source/graph_outline.FILENAME
    if outline.is_file():
        record.update(version='yui-working-graph-5', outline=bind(outline))
        read_outline(record)
    write(receipt, record)
    return bind(receipt)

def read_outline(record):
    reference = record.get('outline')
    expected = Path(record['graph']['path']).with_name(graph_outline.FILENAME)
    if not reference or Path(reference['path']) != expected:
        raise ValueError('OUTLINE_BINDING: missing or foreign proof outline')
    verify_bindings([reference])
    outline = nl0.load(expected)
    if (outline.get('schema') != graph_outline.VERSION
            or outline.get('spec_sha256') != record['spec']['sha256']
            or outline.get('graph_sha256') != record['graph']['sha256']):
        raise ValueError('OUTLINE_BINDING: proof outline belongs to a different graph or specification')
    return outline

def read_receipt(binding):
    verify_bindings([binding])
    record = nl0.load(binding['path'])
    owners={'yui-working-graph-2':(DIRECT,BASIS),'yui-working-graph-3':(BASIS,),
            'yui-working-graph-4':(DIRECT,BASIS),'yui-working-graph-5':(DIRECT,BASIS)}
    if record['owner'] not in owners.get(record['version'],()):
        raise ValueError('Unknown global graph authority')
    verify_bindings([record['spec'],record['graph']]+([record['foundation']] if 'foundation' in record else []))
    _, graph, spec, *_ = nl0.validate(record['graph']['path'],record['spec']['path'],global_only=True)
    if record['version'] in ('yui-working-graph-4','yui-working-graph-5'):
        if not all('usage' in prop for prop in graph['propositions']):
            raise ValueError('USAGE: the working graph must index every proposition')
        if ('foundation_ports' in graph) != (record['owner']==BASIS):
            raise ValueError('Working graph labels do not match its producing entry')
    elif record['version']=='yui-working-graph-3' and 'foundation_ports' not in graph:
        raise ValueError('Missing reviewed foundation labels in working graph')
    if record['version']=='yui-working-graph-5':
        read_outline(record)
    return {'spec':spec, 'graph':graph}

def read_working(binding):
    if Path(binding['path']).name not in ('working.json','frozen.json'):
        raise ValueError('A selected NL0 working revision is required')
    return read_receipt(binding)


def check_assignment(frozen, spec, graph):
    before = {k:v for k,v in frozen['spec'].items() if k!='inputs'}
    after = {k:v for k,v in spec.items() if k!='inputs'}
    if before != after or shape(graph) != shape(frozen['graph']):
        raise ValueError('Assigned global specification or dependency changed; report a graph issue to its NL0 owner')

class AuthorContract(NL0Contract):
    def __init__(self, directory, documents, case_id, phase):
        import graph_repair
        super().__init__(directory, documents, case_id, global_only=phase!=LOCAL)
        self.expected_inputs = [r for r in self.expected_inputs if Path(r['path']).name not in
            {ASSIGNED,graph_outline.FILENAME,PRIOR_OUTLINE,'numbered-basis-graph.json','protected-roots.json',
             'prior-global.json','global-findings.json','baseline.json','repair-obligations.json'}]
        self.phase = phase
        self.prior = json.loads(documents['prior-global.json']) if 'prior-global.json' in documents and phase!=LOCAL else None
        self.earlier=json.loads(documents.get('protected-roots.json','[]'))
        self.frozen = json.loads(documents[ASSIGNED]) if phase==LOCAL else None
        self.graph_feedback = json.loads(documents.get(graph_repair.FEEDBACK,'{}'))
        if self.frozen:
            self.local_scope = self.frozen
            self.assigned_proposition_ids = set(indexed(self.frozen['graph']['propositions']))
            outline = json.loads(documents.get(graph_outline.FILENAME,'{}')).get('inferences',{})
            self.local_outline = {rid:{'steps':entry['steps']} for rid,entry in outline.items()}
            self.proposed_outline = None
            self.granularity_pending = {}
            self.assigned_proofs = graph_repair.proof_rows(self.frozen,self.graph_feedback.get('local_proofs',[]))
        self.registry = json.loads(documents['basis-registry.json']) if phase==BASIS else None
        if self.registry:
            self.seed, self.labels = basis_graph.handoff().numbered_seed(self.registry, self.prior['graph'] if self.prior else None)
        step = protocol.obj({'id':protocol.STRING, 'inputs':protocol.array(protocol.STRING),
                             'output':protocol.STRING, 'definitions':protocol.array(protocol.STRING)})
        if phase in (DIRECT,BASIS):
            proposition = basis_graph.with_usage(OBJECT, allow_index=True)
            form = protocol.obj({'spec':OBJECT,'propositions':protocol.array(proposition),
                                 'inferences':protocol.array(step,minItems=1),
                                 graph_outline.FIELD:graph_outline.schema()})
            if phase==BASIS:
                # A revised route can name B identities directly on its inference rows.
                step['properties']['basis'] = protocol.array(protocol.STRING,uniqueItems=True)
                compact = protocol.obj({'spec':OBJECT, 'proposition_details':protocol.obj({}, extra=proposition),
                                        'inference_definitions':OBJECT,graph_outline.FIELD:graph_outline.schema()})
                for option in (compact,form):
                    option['properties']['rename_foundations'] = OBJECT
                form['properties']['foundation_ports'] = OBJECT
                form = protocol.choice(form,compact)
        else:
            form = protocol.obj({'local_proofs':protocol.array(LOCAL_PROOF)})
        from payload_protocols import editable
        self.schema = editable(form) if phase==LOCAL else protocol.choice(form,protocol.obj({'accept_candidate':{'type':'integer','minimum':1}}))
        if phase==LOCAL and self.local_outline:
            self.schema = protocol.choice(self.schema,graph_refinement.schema())

    def __call__(self, value):
        protocol.validate(value,self.schema)
        if self.phase==LOCAL:
            return self.local_candidate(value)
        if set(value) & {'accept_candidate','base_candidate','base_input'}:
            return super().__call__(value)
        spec = deepcopy(value['spec'])
        spec.setdefault('format_version',2)
        if 'propositions' in value:
            props, steps = deepcopy(value['propositions']), deepcopy(value['inferences'])
        else:
            details = value['proposition_details']
            definitions = value['inference_definitions']
            if set(details)!=set(indexed(self.seed['propositions'])) or set(definitions)!=set(indexed(self.seed['inferences'])):
                missing = sorted(set(indexed(self.seed['propositions'])) - set(details))
                raise ValueError(f'Supply metadata for the numbered-basis-graph.json IDs; missing {missing}')
            props, steps = [], []
            for row in self.seed['propositions']:
                extra=details[row['id']]
                if not isinstance(extra,dict) or {'id','statement'} & extra.keys():
                    raise ValueError('Basis proposition identities and statements are supplied by the controller')
                props.append({**row,**extra})
            for row in self.seed['inferences']:
                steps.append({k:row[k] for k in ('id','inputs','output')} |
                             {'definitions':definitions[row['id']]})
        expanded={'spec':spec,'graph':{'format_version':2,'propositions':props,'inferences':steps,
                                      graph_outline.FIELD:deepcopy(value[graph_outline.FIELD])}}
        if self.registry:
            if 'foundation_ports' in value and (not self.prior or value['foundation_ports']!=self.prior['graph'].get('foundation_ports')):
                raise ValueError('Use rename_foundations to revise the controller-owned foundation labels')
            self.bind_graph(expanded['graph'], value.get('rename_foundations',{}))
        result=super().__call__(expanded)
        value.clear()
        value.update(expanded)
        return result

    def local_candidate(self, value):
        from graph_repair import proof_rows

        last = self.valid_drafts.get(self.last_valid_candidate)
        if 'refine_candidate' in value:
            if last is None or value['refine_candidate'] != self.last_valid_candidate:
                raise ValueError(f'NL0_REFINEMENT: first check the written local proof, then refine the latest '
                                 f'checked candidate ({self.last_valid_candidate})')
            expanded, self.proposed_outline = graph_refinement.apply(last, self.local_outline, value)
        elif 'local_proofs' in value:
            rows = proof_rows(self.local_scope,value['local_proofs'])
            if last is None:
                self.assigned_proofs.update(rows)
                self.save_assigned_proofs()
                rows = self.assigned_proofs
                missing = sorted(indexed(self.frozen['graph']['inferences']).keys() - rows.keys())
                if missing:
                    return {'status':'LOCAL_DRAFT_SAVED','remaining_local_proofs':missing,'draft_pending':True,
                            'mathematical_acceptance':False}
            expanded = deepcopy(last or self.frozen)
            for step in expanded['graph']['inferences']:
                if step['id'] in rows:
                    step.update({name:deepcopy(rows[step['id']][name]) for name in BODY_FIELDS})
        else:
            return super().__call__(value)
        try:
            result = super().__call__(expanded)
        finally:
            self.proposed_outline = None
        value.clear()
        value.update(expanded)
        return result

    def save_assigned_proofs(self):
        write(self.directory/ASSIGNED_PROOFS,list(self.assigned_proofs.values()))

    def validate_local(self, expanded):
        spec, graph = expanded['spec'], expanded['graph']
        if self.proposed_outline is None:
            check_assignment(self.local_scope,spec,graph)
            outline = deepcopy(self.local_outline)
            if any('keep_together' in entry for entry in outline.values()):
                last = indexed(self.local_scope['graph']['inferences'])
                for step in graph['inferences']:
                    if step != last[step['id']]:
                        outline[step['id']].pop('keep_together',None)
        else:
            outline = self.proposed_outline
        report = graph_outline.check(graph,outline,self.outline_documents(),provisional=True) if outline else None
        result = super()._validate(expanded)
        if report:
            graph_outline.include_written_size(report,graph)
            report.update(spec_sha256=graph['spec_sha256'],graph_sha256=nl0.sha(self.directory/'nl0.json'))
            write(self.directory/graph_outline.FILENAME,report)
            self.granularity_pending[self.attempt] = graph_outline.pending(report)
            result['granularity_pending'] = self.granularity_pending[self.attempt]
        if shape(graph)==shape(self.frozen['graph']):
            self.assigned_proofs = {row['id']:{key:row[key] for key in ('id',*BODY_FIELDS)}
                                    for row in graph['inferences']}
            self.save_assigned_proofs()
        self.local_scope,self.local_outline = expanded,outline
        return result

    def outline_documents(self):
        return {Path(row['path']).name:self.documents[Path(row['path']).name] for row in self.expected_inputs}

    def bind_graph(self, graph, renames):
        rules = basis_graph.handoff()
        seed_steps = indexed(self.seed['inferences'])
        labels = dict(self.labels)
        props = indexed(graph['propositions'])
        rows = indexed(self.registry['dependencies'])
        for step in graph['inferences']:
            seed = seed_steps.get(step['id'])
            # Omitted foundation uses inherit from the seed. Explicit uses describe the revised edges.
            uses = step.pop('basis', None)
            if uses is None:
                uses = seed['basis'] if not self.prior and seed and seed['output']==step['output'] else []
            for key in uses:
                if key not in labels:
                    if key not in rows:
                        raise ValueError(f'{step["id"]}: unknown frozen foundation {key}')
                    preferred = rows[key]['port']
                    occupied = set(labels.values()) | {p['id'] for p in self.registry['global_graph']['propositions']
                                                       if p['id']!=preferred}
                    labels[key] = preferred if preferred and preferred not in occupied else rules.allocate(rows[key],occupied)
                label = labels[key]
                if label not in props:
                    raise ValueError(f'{step["id"]} uses {key}: supply {label} source metadata from the frozen registry; its input edge is automatic')
                if label not in step['inputs']:
                    step['inputs'].append(label)
        for source in self.seed['propositions']:
            if source['id'] in props:
                rules.inherit_usage(props[source['id']], source)
        for key, label in labels.items():
            if label in props:
                rules.inherit_usage(props[label], rows[key])
        rules.attach(self.registry,graph,labels)
        if renames:
            previous=dict(graph[rules.FIELD]['labels'])
            rules.rename(self.registry,graph,renames)
            old_label={destination:previous[key] for key,destination in renames.items() if previous[key]!=destination}
            for row in graph['propositions']:
                source=row.get('source')
                if row['id'] in old_label and isinstance(source,dict) and source.get('verification'):
                    from source_qualification import relabel
                    source.setdefault('statement',row.get('statement'))
                    relabel(self.directory,source,old_label[row['id']],row['id'])

    def _validate(self, expanded):
        if self.prior:
            spec = expanded['spec']
            if any(spec.get(key) != self.prior['spec'][key] for key in ORIGINAL_FIELDS):
                raise ValueError('SOURCE_CHANGE_REQUIRES_USER: preserve the original target, parameters and hypotheses')
            prior_props = indexed(self.prior['graph']['propositions'])
            for prop in expanded['graph']['propositions']:
                prior = prior_props.get(prop['id'], {}).get('usage', {})
                if prior and 'usage' not in prop:
                    prop['usage'] = {'references': deepcopy(prior.get('references', []))}
                usage = prop.get('usage')
                if isinstance(usage,dict) and 'inferences' in usage and usage['inferences'] == prior.get('inferences'):
                    # Recompute the inherited reverse index from the revised edges.
                    del usage['inferences']
        if self.frozen:
            return self.validate_local(expanded)
        # Keep the outline with each draft. Publish it beside the canonical NL0 graph.
        graph = expanded['graph']
        outline = graph[graph_outline.FIELD]
        canonical = {'spec':expanded['spec'], 'graph':{k:v for k,v in graph.items() if k!=graph_outline.FIELD}}
        report = graph_outline.check(canonical['graph'],outline,self.outline_documents(),provisional=True)
        result = super()._validate(canonical)
        report.update(spec_sha256=canonical['graph']['spec_sha256'],
                      graph_sha256=nl0.sha(self.directory/'nl0.json'))
        write(self.directory/graph_outline.FILENAME,report)
        expanded['graph'] = {**canonical['graph'], graph_outline.FIELD:outline}
        result['candidate_number'] = self.attempt
        result['outline_reviewed'] = [rid for rid,entry in report['workload'].items() if entry['review_reasons']]
        return result

    def validate_canonical(self,spec,graph):
        from graph_repair import check_revision, context
        current={'spec':spec,'graph':graph}
        if self.prior:
            for prior in [self.prior,*self.earlier]:
                preserve_originals(prior,current,basis=self.phase==BASIS)
        if self.global_only:
            from nl0 import closure
            scopes = context(current)
            if self.prior and self.graph_feedback.get('blockers'):
                check_revision(self.prior,scopes,self.graph_feedback['blockers'])
            for step in graph['inferences']:
                closure.check_definition_guards(step,scopes[step['id']][2])

def preserve_originals(prior, current, *, basis):
    before,after=prior['spec'],current['spec']
    if any(before[k]!=after[k] for k in ORIGINAL_FIELDS):
        raise ValueError('SOURCE_CHANGE_REQUIRES_USER: original problem changed')
    old,new=indexed(prior['graph']['propositions']),indexed(current['graph']['propositions'])
    old_labels=prior['graph'].get('foundation_ports',{}).get('labels',{})
    new_labels=current['graph'].get('foundation_ports',{}).get('labels',{})
    next_label={label:new_labels.get(b) for b,label in old_labels.items()}
    protected={k for k in old if k=='P' or k.startswith('H') or (basis and k.startswith(('M','E')))}
    used_definitions=set()
    for key in protected:
        row=old[key]
        target=next_label.get(key,key)
        if target in new:
            expected={**row,'id':target}
            expected.pop('usage',None)
            actual={k:v for k,v in new[target].items() if k!='usage'}
            if row['kind']=='mathlib':
                # Each revision independently verifies these probe receipts against pinned source bytes.
                expected=deepcopy(expected)
                expected['source']['evidence']=actual['source']['evidence']
            elif key!=target and row['kind']=='external' and 'verification' in row['source']:
                expected=deepcopy(expected)
                previous=expected['source']['verification']['record']
                current_record=actual['source'].get('verification',{}).get('record')
                if not current_record:
                    raise ValueError('A graph label change cannot remove a source qualification')
                expected['source']['verification']['record']=current_record
                expected['source']['evidence']=[current_record if r==previous else r for r in expected['source']['evidence']]
            if expected!=actual:
                raise ValueError('Original or foundation declaration changed at '+key)
            used_definitions.update(row['definitions'])
        elif key=='P' or key.startswith('H'):
            raise ValueError('Original proposition omitted: '+key)
    old_defs,new_defs=indexed(before['definitions']),indexed(after['definitions'])
    pending=list(used_definitions)
    while pending:
        rid=pending.pop()
        definition=old_defs[rid]
        if definition!=new_defs.get(rid):
            raise ValueError('Definition used by a protected declaration changed: '+rid)
        dependencies=set(definition.get('depends_on',[]))-used_definitions
        used_definitions.update(dependencies)
        pending.extend(dependencies)


def prior_versions(binding,root):
    seen=set()
    while binding:
        path=Path(binding['path'])
        if path in seen or not path.is_relative_to(root/'global-graphs'):
            raise ValueError('Invalid NL0 working revision history')
        seen.add(path)
        checked=read_working(binding)
        record=nl0.load(path)
        yield checked,record
        binding=record.get('previous')


def global_stage(job, budget, *, owner, previous=None, findings=None, foundation=None):
    import basis
    from clean_stage import ArtifactStage
    from full_workflow import stage_seconds
    from full_workflow import accepted
    from controller_common import copy_problem_documents
    from graph_repair import RULE
    directory=Path(job['root'])/'global-graphs'
    directory.mkdir(exist_ok=True)
    number=max((int(p.name) for p in directory.iterdir() if p.name.isdecimal()),default=0)
    while True:
        number+=1
        attempt=directory/f'{number:04d}'
        try:
            attempt.mkdir()
            break
        except FileExistsError:
            continue
    inputs=attempt/'inputs'
    inputs.mkdir(parents=True)
    copy_problem_documents(basis.problem_inputs(job),inputs)
    if previous:
        versions=prior_versions(previous,Path(job['root']).resolve())
        latest,prior_record=next(versions)
        write(inputs/'prior-global.json',latest)
        if 'outline' in prior_record:
            copy_input(Path(prior_record['outline']['path']),inputs/PRIOR_OUTLINE)
        roots=[]
        for old,_ in versions:
            spec={k:old['spec'][k] for k in (*ORIGINAL_FIELDS,'definitions')}
            props=[p for p in old['graph']['propositions'] if p['id']=='P' or p['id'].startswith(('H','E','M'))]
            saved={'spec':spec,'graph':{'propositions':props,**{k:v for k,v in old['graph'].items() if k=='foundation_ports'}}}
            if saved not in roots:roots.append(saved)
        if roots:write(inputs/'protected-roots.json',roots)
        write(inputs/'global-findings.json',findings)
    if owner==BASIS:
        registry=nl0.load(inputs/'basis-registry.json')
        numbered,labels=basis.basis_graph.handoff().numbered_seed(registry,latest['graph'] if previous else None)
        write(inputs/'numbered-basis-graph.json',{'version':basis.basis_graph.handoff().VERSION,
              'labels':labels,'graph':numbered})
    manifest(inputs)
    prompt=('Work backward from the target and sketch the mathematical fact each consumer needs. '
            'Give each R a manageable source-backed block. Break very long arguments into medium-size blocks first. '
            'Inside each block list the distinct main derivations so the local author can write and extract their precise interfaces. '
            'Keep routine calculations local. Record the shared witnesses, sets, parameters and scope at drafted boundaries. '
            'Preserve the complete target, original H, parameters and foundation material. You own the intermediate statements and edges. '
            'Use the NL0 specification and proposition fields, including nontrivial M/E source evidence. '
            'Write the mathematical claim in statement. For source uses add usage.references with '
            'document (exact inputs/ path) and locator (e.g. Lemma 2.1). The controller derives usage.inferences from the graph edges. '
            'Supply id, inputs, output and definitions for each inference. Include proof_outline keyed by the actual R IDs. '
            'Each step states its conclusion, what it uses (direct inputs, optionally B IDs, or earlier steps named S001, S002, ...), '
            'and the actual source_spans using from_task, start_line, end_line. All earlier steps and direct inputs must feed the final step. '
            'Use actual inclusive task-input line numbers; an inference derived directly from its inputs can use empty source_spans. '
            'Make the source assignments manageable and flag the actual main steps, including substantial single-use work. '
            'A short final combination of previously proved inputs is one step. This is a provisional outline. '
            'The next author writes the proofs and resolves granularity before independent audit. '
            +RULE+' For a checked candidate, read_author_packet shows a proposed receiving scope. ')
    if owner==BASIS:
        prompt+=('Read numbered-basis-graph.json for the allocated M/E nodes, their exact statements and all consumer edges. '
                 'Native M technical source metadata is inherited automatically from the pre-freeze checked source; '
                 'you may omit its source except hypotheses. Do not query or replace the frozen declaration. '
                 'Prepared E references the checked YuiBasis.B proof; supply its semantic attribution and notation map. '
                 'Use declared document IDs in E evidence, e.g. {"input":"problem.md"}. '
                 'For the numbered seed submit spec, '
                 'proposition_details and inference_definitions. To revise N/R statements or dependencies, submit '
                 'spec, propositions and inferences. In a changed inference, list its direct B IDs in basis. '
                 'Use rename_foundations (B ID to new graph ID) to rename all uses together. On revisions, start with '
                 'the prior working labels. Omit case_id; the controller fills it. ')
    else:
        prompt+='Submit spec, propositions and inferences. Direct conditional external sources remain available.'
    if previous:
        prompt+=(' Repair the located global findings in the supplied prior version. Preserve the original target and H. '
                 'Reuse prior outline entries whose inference and source ranges still apply.')
    stage=ArtifactStage(attempt/'stage',prompt,phase=owner,kind='nl0',case_id=job['case'],
                        inputs=inputs/'inputs.json',budget=budget,timeout=stage_seconds(budget))
    if previous:
        prior_record=nl0.load(previous['path'])
        prior_graph=read_working(previous)['graph']
        evidence(Path(prior_record['graph']['path']).parent,prior_graph,stage.validator.directory)
    from role_sessions import Sessions
    owner_sessions=Sessions()
    with owner_sessions.use(owner):
        stage.execute()
    accepted(attempt)
    source=stage.logs/'case'
    submitted=nl0.load(stage.logs/'accepted.json')
    outline=submitted['graph'].pop(graph_outline.FIELD)
    canonical={'spec':nl0.load(source/'spec.json'),'graph':nl0.load(source/'nl0.json')}
    if canonical!=submitted or outline!=nl0.load(source/graph_outline.FILENAME)['inferences']:
        raise ValueError('Global submit differs from the accepted graph')
    receipt=checked_receipt(source,owner,foundation=foundation,previous=previous)
    if previous:
        before, after=read_working(previous),read_receipt(receipt)
        if any(before['spec'][key]!=after['spec'][key] for key in ORIGINAL_FIELDS):
            from execution_health import StageFailure
            raise StageFailure('SOURCE_CHANGE_REQUIRES_USER','Global revision changed the original target or hypotheses',
                               phase=owner,evidence=receipt['path'])
    owner_sessions.close_all('GLOBAL_GRAPH_CHECKED',[Path(receipt['path'])])
    return receipt

def select(job, checked, *, previous=None):
    import fcntl
    with (Path(job['root'])/'global-graphs/.selection.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        return _select(job,checked,previous)


def _select(job, checked, previous):
    """Assign a checked working revision to local authors, retaining older versions."""
    root = Path(job['root']).resolve()
    source = Path(checked['path']).resolve()
    if (not source.is_relative_to(root/'global-graphs') or
            source.relative_to(root/'global-graphs').parts[1:] != ('stage','case','checked-global.json')):
        raise ValueError('Expected a checked global graph from this case')
    revision=source.with_name('working.json')
    selection=root/'global-selection.json'
    current=nl0.load(selection) if selection.exists() else None
    if current and current['path']==str(revision) and current['sha256']==checked['sha256']:
        read_working(current)
        return current
    if current!=previous:
        raise ValueError('Stale NL0 global selection')
    with tempfile.TemporaryDirectory(dir=source.parent) as temp:
        candidate=Path(temp)/'receipt.json'
        candidate.write_bytes(source.read_bytes())
        if bind(candidate)['sha256']!=checked['sha256']:
            raise ValueError('The checked global receipt changed before assignment')
        record=nl0.load(candidate)
        if (record['spec']!=bind(source.with_name('spec.json')) or record['graph']!=bind(source.with_name('nl0.json'))
                or record.get('previous')!=previous):
            raise ValueError('The checked global specification, parent or graph differs from this stage')
        proposed=read_receipt(bind(candidate))
        for old,record_old in prior_versions(current,root):
            if record_old.get('foundation')!=record.get('foundation') or record_old['owner']!=record['owner']:
                raise ValueError('Cannot replace the selected foundation or entry during graph revision')
            preserve_originals(old,proposed,basis=record['owner']==BASIS)
            if ({k:v for k,v in old['spec'].items() if k!='inputs'}==
                    {k:v for k,v in proposed['spec'].items() if k!='inputs'}
                    and shape(old['graph'])==shape(proposed['graph'])):
                from execution_health import StageFailure
                from graph_repair import UNRESOLVED
                raise StageFailure(UNRESOLVED,'The graph owner returned an unchanged or previously rejected revision',
                                   phase='nl0-global',evidence=source)
        try:
            os.link(candidate,revision)
        except FileExistsError:
            pass
    selected=bind(revision)
    if selected['sha256']!=checked['sha256']:
        raise ValueError('The assigned global receipt differs from the checked revision')
    write(selection,selected)
    return selected


def select_detail(job, previous, source):
    """Use the delivered local graph at the Audit A receiving boundary."""
    import fcntl

    root = Path(job['root']).resolve()
    graphs = root/'global-graphs'
    source = Path(source).resolve()
    provisional = read_working(previous)
    record = nl0.load(previous['path'])
    spec_path, graph_path = source/'spec.json', source/'nl0.json'
    spec, graph = nl0.load(spec_path), nl0.load(graph_path)
    if 'outline' in record:
        report = read_outline({'spec':bind(spec_path),'graph':bind(graph_path),
                               'outline':bind(source/graph_outline.FILENAME)})
        if graph_outline.pending(report):
            raise ValueError('The detailed NL0 handoff still has blocks requiring refinement')
    if shape(provisional['graph'])==shape(graph):
        check_assignment(provisional,spec,graph)
        return previous

    assignment = Path(previous['path'])
    if not assignment.is_relative_to(graphs) or not source.is_relative_to(root/'nl0') or 'outline' not in record:
        raise ValueError('Refined NL0 must belong to the current outlined assignment')
    staged_assignment = source.parent.parent/'inputs'/ASSIGNED
    if nl0.load(staged_assignment)!=provisional:
        raise ValueError('Refined NL0 author used a different assignment')
    dirname = assignment.relative_to(graphs).parts[0]
    destination = graphs/(dirname+'-detail')/'stage/case'
    checked = destination/'checked-global.json'
    projection = {**graph,**shape(graph)}
    with (graphs/'.selection.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        current = nl0.load(root/'global-selection.json')
        if current!=previous and current['path']!=str(destination/'working.json'):
            raise ValueError('Stale outlined assignment for NL0 refinement')
        if checked.exists():
            binding = bind(checked)
            if ({'spec':spec,'graph':projection}!=read_receipt(binding)
                    or report['inferences']!=read_outline(nl0.load(checked))['inferences']):
                raise ValueError('A different refined graph already owns this selection')
        else:
            destination.mkdir(parents=True,exist_ok=True)
            for item in spec['inputs']:
                target = destination/item['path']
                target.parent.mkdir(parents=True,exist_ok=True)
                copy_input(source/item['path'],target)
            evidence(source,projection,destination)
            copy_input(spec_path,destination/'spec.json')
            write(destination/'nl0.json',projection)
            write(destination/graph_outline.FILENAME,{**report,'graph_sha256':nl0.sha(destination/'nl0.json')})
            binding = checked_receipt(destination,record['owner'],foundation=record.get('foundation'),previous=previous)
        return _select(job,binding,previous)


def issue_owner(issue, global_owner=None):
    """Audit findings on shared declarations and ports belong to the global NL0 author."""
    fields=issue.get('location','').strip('/').split('/')
    if fields[0]=='spec' or fields[:2]==['graph','propositions']:return 'global'
    if fields[:2]==['graph','inferences']:
        if len(fields)<=2 or (len(fields)==3 and issue.get('criterion')=='structure'):
            return 'global'
        if len(fields)>3 and fields[3] in GLOBAL_FIELDS:return 'global'
    return 'local'


def local_stage(job, directory, budget, *, baseline=None, obligations=None, check_handoff=None, graph_history=None):
    import basis
    import nl0_author
    import full_workflow
    import graph_repair
    from clean_stage import ArtifactStage
    root=Path(job['root'])
    previous=nl0.load(root/'global-selection.json')
    frozen=read_working(previous)
    author_obligations = ({k:obligations[k] for k in ('version','baseline_input','baseline_content_sha256','issues')}
                          if baseline else None)
    nl0_author.prepare(basis.problem_inputs(job),directory,baseline=baseline,obligations=author_obligations)
    inputs=directory/'inputs'
    write(inputs/ASSIGNED,frozen)
    record=nl0.load(previous['path'])
    if graph_history:
        write(inputs/graph_repair.FEEDBACK,graph_repair.revision_feedback(graph_history,previous,frozen))
    if 'outline' in record:
        copy_input(Path(record['outline']['path']),inputs/graph_outline.FILENAME)
    manifest(inputs)
    prompt=('Read assigned-global.json and the original proof. Draft the written derivation of each assigned R '
            'with its rules, scoped locals, argument and actual applications. Read read_author_packet with '
            'just inference for its scope. Save local_proofs in manageable batches with check_draft. '
            'Use the NL0 authoring and closure rules. Report genuine mathematical gaps via report_obstacle. '
            'Inspect the final candidate packets and record_author_checks before submitting accept_candidate. '
            +graph_repair.RULE+' Work on independent inferences while collecting actual blockers you encounter. '
            'Return them together with report_graph_issue and include any ready local_proofs in that call. '
            'Read global-findings.json when supplied, focusing on changed_inferences and the located remedies. '
            'Send local_proofs containing only new or updated bodies. The same merge supplies compatible drafts '
            'whether the graph was returned by the author or by Audit A. Closing inspection checks the complete result.')
    if 'outline' in record:
        prompt+=(' Read proof-outline.json for the planned derivations and precise source ranges. '
                 'For a large block, first write medium-size parts using explicit S steps and F facts. '
                 'After checking the written derivations, use check_draft with refine_candidate and splits to extract '
                 'substantial independently provable arguments, including single-use ones. Use fresh N/R IDs. '
                 'A split supplies its original R, the new propositions, full replacement inferences with their bodies, '
                 'and their local proof_outline. Move the relevant S/F reasoning and source uses from the draft '
                 'into the new node and replace that derivation at the consumer by its explicit use. Preserve the '
                 'old conclusion, outside premises, and all other blocks. Refine each remaining large subargument '
                 'in the same way. Keep routine calculations local. For a genuinely indivisible flagged argument, '
                 'give keep_together on the checked body, naming the inseparable S steps in at and explaining why an '
                 'explicit scoped parameter, assumption or witness would not make a useful cut. '
                 'Before submitting accept_candidate, use read_author_packet on the final written graph. '
                 'For each new cut compare the supplied producer scope and the actual receiving use side by side. '
                 'Check the exact clause, quantifiers, local assumptions, same witness and effective timing. '
                 'Record the concrete S/F use in dependency_and_local_assumption_check. '
                 'Use record_author_checks to close the final graph for independent Audit A.')
    stage=ArtifactStage(directory/'stage',prompt,phase=LOCAL,kind='nl0',case_id=job['case'],
                        inputs=inputs/'inputs.json',budget=budget,timeout=full_workflow.stage_seconds(budget),
                        check_handoff=check_handoff)
    evidence(Path(record['graph']['path']).parent,frozen['graph'],stage.validator.directory)
    stage.execute()
    budget.execution.check()
    if nl0.load(stage.logs/'result.json').get('task_outcome')==graph_repair.STATUS:
        report=graph_repair.verify_local(stage.logs,previous)
        prior=None
        if (stage.validator.last_valid_candidate is not None
                and shape(stage.validator.local_scope['graph'])==shape(frozen['graph'])):
            from author_check import digest
            prior=stage.validator.directory
            candidate={'spec':nl0.load(prior/'spec.json'),'graph':nl0.load(prior/'nl0.json')}
            check_assignment(frozen,candidate['spec'],candidate['graph'])
            report.update(version='yui-repair-obligations-1',baseline_input='baseline.json',
                          baseline_content_sha256=digest(candidate))
        raise graph_repair.Request(report,baseline=prior,evidence=[stage.logs/'accepted.json'])
    full_workflow.nl0_artifact_for_audit(directory)
    source=stage.validator.directory
    check_assignment(stage.validator.local_scope,nl0.load(source/'spec.json'),nl0.load(source/'nl0.json'))
    return source
