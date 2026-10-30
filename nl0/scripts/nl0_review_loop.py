"""Global author/reviewer handoff followed by isolated parallel node repair."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from copy import deepcopy
import json
from pathlib import Path
import shutil
import threading

import audit_a_campaign as campaign
import audit_reuse
from clean_stage import ArtifactStage
from controller_common import bind, manifest, write
from execution_health import StageFailure, require_review_execution
from role_sessions import Sessions
import nl0


def copy_source(source, destination):
    shutil.copytree(source,destination)
    for name in ('audit-a.json','audit-a.pending.json'):
        (destination/name).unlink(missing_ok=True)


class NodePatch:
    def __init__(self, source, rid, out):
        self.source=Path(source);self.rid=rid;self.out=Path(out);self.selected=None;self.attempt=0
        self.graph=json.loads((self.source/'nl0.json').read_text())
        self.original=next(r for r in self.graph['inferences'] if r['id']==rid)

    def __call__(self,value):
        if value.get('status')=='GLOBAL_REPAIR_REQUIRED':
            if set(value)!={'status','explanation','locations'} or not isinstance(value['explanation'],str) or not value['explanation'].strip() or not value['locations']:
                raise ValueError('Global issue requires a concrete explanation and local packet locations')
            packet=nl0.packet(nl0.validate(self.source/'nl0.json',self.source/'spec.json'),self.rid)
            for pointer in value['locations']:nl0.closure.resolve(packet,pointer)
            self.selected='global'
            return {'scope':'Located global issue only; no mathematical acceptance'}
        if set(value)!={'inference'}:raise ValueError('Submit {inference:<complete own R>} or a located GLOBAL_REPAIR_REQUIRED report')
        row=value['inference']
        if any(row.get(k)!=self.original[k] for k in ('id','inputs','output','definitions')):
            raise ValueError('Public node interface changed; report GLOBAL_REPAIR_REQUIRED instead')
        graph=deepcopy(self.graph)
        graph['inferences']=[deepcopy(row) if r['id']==self.rid else r for r in graph['inferences']]
        self.attempt+=1;case=self.out/'candidates'/str(self.attempt).zfill(4)
        copy_source(self.source,case);write(case/'nl0.json',graph)
        nl0.validate(case/'nl0.json',case/'spec.json')
        self.selected=case
        return {'scope':'Own R structural validation only; independent local review still required',
                'candidate':self.attempt}


def run(job, budget, audit_budget, progress, author_stage, repair_obligations, *, restored=None, prior=(),initial_issues=None):
    root=Path(job['root']);sessions=Sessions();source=restored;issues=initial_issues;prior=list(prior);epoch=0
    while True:
        epoch+=1
        # A restored global role uses the saved accepted draft and actual local
        # findings; it does not restart the original proof from an empty prompt.
        while True:
            if source is None or issues is not None:
                directory=root/'nl0'/f'{epoch:04d}-{len(prior)+1:04d}'
                with sessions.use('nl0-author'):
                    source=author_stage(job,directory,budget,baseline=source,obligations=issues)
                issues=None
            global_dir=root/'audit-a'/f'{epoch:04d}-{len(prior)+1:04d}'
            campaign.prepare(source,root/'inputs',global_dir,reuse_from=prior)
            progress(job['case'],'AUDIT_A_GLOBAL',directory=str(global_dir))
            campaign.run(global_dir,budget=budget,audit_budget=audit_budget,only='global',sessions=sessions)
            gate=campaign.global_acceptance(global_dir)
            if gate['accepted']:break
            issues=repair_obligations(source,global_dir);prior.append(global_dir)
            if not issues['issues']:raise StageFailure('REVIEW_INCOMPLETE','Global review has no complete located repair findings',evidence=global_dir/'global-acceptance.json')
        sessions.close(['nl0-author','audit-a-global'],'GLOBAL_REVIEW_PASSED',[global_dir/'global-acceptance.json'])
        prior.append(global_dir)
        data=nl0.validate(source/'nl0.json',source/'spec.json');stop=threading.Event();outcomes={}

        def local(rid):
            own=source;revision=0
            while not stop.is_set():
                revision+=1
                directory=root/'audit-a'/f'local-{epoch:04d}-{rid}-{revision:04d}'
                prepared=campaign.prepare(own,root/'inputs',directory,reuse_from=prior)
                if 'packet:'+rid in prepared['inherited']:
                    campaign.global_acceptance(directory)
                    return {'case':own,'campaign':directory,'rid':rid}
                # Admission still checks the exact inherited global scope.
                campaign.run(directory,budget=budget,audit_budget=audit_budget,only=rid,sessions=sessions)
                stage=directory/rid/'stage';result=json.loads((stage/'result.json').read_text())
                try:require_review_execution(result,stage/'result.json',phase='audit-a-local')
                except StageFailure as error:
                    if not error.result.get('record_context_qualified'):raise
                review=json.loads((stage/'accepted.json').read_text())
                if review.get('verdict')=='PASS' and audit_reuse.all_pass(review):
                    return {'case':own,'campaign':directory,'rid':rid}
                if stop.is_set():return None
                author=root/'nl0'/f'local-{epoch:04d}-{rid}-{revision:04d}'
                inputs=author/'inputs';inputs.mkdir(parents=True)
                write(inputs/'packet.json',nl0.packet(nl0.validate(own/'nl0.json',own/'spec.json'),rid))
                write(inputs/'findings.json',review);manifest(inputs)
                validator=NodePatch(own,rid,author)
                prompt=('Repair only the supplied R proof under its unchanged public input/output and definitions. '
                    'Return {inference:<complete repaired own R>}. Read packet.json and findings.json. '
                    'If shared definitions, assumptions, public input/output or graph edges must change, submit '
                    '{status:GLOBAL_REPAIR_REQUIRED, explanation:<located need>, locations:[<packet pointers>]}. '
                    'Do not invent premises, edit another node or self-certify a proof. The same reviewer will assess your revision.')
                candidate=ArtifactStage(author/'stage',prompt,phase='nl0-local-repair',inputs=inputs/'inputs.json',
                    validator=validator,budget=audit_budget,library=False)
                with sessions.use('nl0-author:'+rid):candidate.execute()
                require_review_execution(json.loads((author/'stage/result.json').read_text()),author/'stage/result.json',phase='nl0-local-repair')
                if validator.selected=='global':
                    stop.set()
                    return {'global':json.loads((author/'stage/accepted.json').read_text()),'rid':rid,'campaign':directory}
                own=validator.selected
                if own is None:raise StageFailure('LOCAL_REPAIR_INCOMPLETE','No selected own-node patch')
            return None

        progress(job['case'],'AUDIT_A_LOCAL',workers=audit_budget.configuration['effective'])
        with ThreadPoolExecutor(max_workers=audit_budget.configuration['effective']) as pool:
            pending={rid:pool.submit(copy_context().run,local,rid) for rid in sorted(data[4])}
            for rid,future in pending.items():outcomes[rid]=future.result()
        # No new local work is started after a global issue; current assignments
        # reach their normal handoffs before the serial global author is restored.
        global_issues=[v for v in outcomes.values() if v and 'global' in v]
        merged=root/'nl0'/f'merged-{epoch:04d}';copy_source(source,merged)
        graph=json.loads((source/'nl0.json').read_text())
        for rid,value in outcomes.items():
            if value and 'case' in value:
                patch=next(r for r in json.loads((value['case']/'nl0.json').read_text())['inferences'] if r['id']==rid)
                graph['inferences']=[patch if r['id']==rid else r for r in graph['inferences']]
                prior.append(value['campaign'])
        write(merged/'nl0.json',graph);nl0.validate(merged/'nl0.json',merged/'spec.json')
        if global_issues:
            issues={'version':'yui-repair-obligations-1','baseline_input':'baseline.json',
                'baseline_content_sha256':__import__('author_check').digest({'spec':json.loads((merged/'spec.json').read_text()),'graph':graph}),
                'issues':[{'id':'ISSUE'+str(i+1).zfill(3),'criterion':'structure','location':'/graph/inferences',
                    'note':v['rid']+': '+v['global']['explanation']} for i,v in enumerate(global_issues)]}
            source=merged
            continue
        final=root/'audit-a'/f'final-{epoch:04d}'
        campaign.prepare(merged,root/'inputs',final,reuse_from=prior)
        # Every scope must be inherited from an actual current reviewed version.
        campaign.run(final,budget=budget,audit_budget=audit_budget,sessions=sessions)
        accepted=campaign.collect(final,None)
        if not (accepted['full_acceptance'] or accepted.get('conditional_acceptance')):
            raise StageFailure('AUDIT_A_MERGE_REJECTED','Merged source is not the actual accepted set of reviewed versions',evidence=final/'inspection.json')
        current_rids={r['id'] for r in graph['inferences']}
        obsolete={role for role in sessions.roles if role.startswith(('audit-a:','nl0-author:'))
            and role.split(':',1)[1] not in current_rids}
        sessions.close_all('LOCAL_REVIEWS_PASSED',[final/'inspection.json'],superseded=obsolete)
        return {'graph':str(merged/'nl0.json'),'spec':str(merged/'spec.json'),'audit_a':str(merged/'audit-a.json')}
