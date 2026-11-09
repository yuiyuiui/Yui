"""Native actions selected by the versioned public graph."""
from pathlib import Path
from contextlib import nullcontext
import json
import time
from datetime import datetime, timezone

import basis
import frozen_graph
import graph_repair
import jobs
from controller_common import bind, verify_bindings, write
from execution_health import StageFailure


class Case:
    def __init__(self, job, recorder, budgets, progress):
        self.job = job
        self.root = Path(job['root'])
        self.recorder, self.budgets, self.progress = recorder, budgets, progress
        self.failure = self.result = None
        self.timings=[]
        from role_sessions import Sessions
        self.reviews=Sessions()

    def save(self, name, value):
        path = self.root/'handoffs'/(name+'.json')
        write(path,value)
        return bind(path)

    def read(self, binding):
        verify_bindings([binding])
        return json.loads(Path(binding['path']).read_bytes())

    def working(self, data):
        chosen=self.read(bind(self.root/'global-selection.json'))
        if chosen!=data['global']:
            raise ValueError('This finding or author submission belongs to a superseded NL0 graph')
        return frozen_graph.read_working(chosen)

    def reviewed(self,data):
        import source_preparation
        from source_qualification import usable
        working=self.working(data)
        receipt=self.read(data['authority'])
        if receipt['global']!=data['global']:raise ValueError('Different audited NL0 version')
        verify_bindings(list(receipt['files'].values()))
        authority={k:v['path'] for k,v in receipt['files'].items()}
        selected=source_preparation.read_source(**authority)[0]
        if not usable(selected[0]):raise ValueError('No usable independent Audit A')
        frozen_graph.check_assignment(working,selected[2],selected[1])
        return authority,selected

    def repair(self,data,request):
        self.working(data)
        if self.job['policy']=='first-pass':
            raise StageFailure(graph_repair.STATUS,'First pass located an NL0 graph defect',
                               phase='nl0',evidence=request.evidence[0] if request.evidence else None)
        old=self.read(data['history']) if 'history' in data else {}
        case=request.baseline
        campaigns={str(p) for p in request.prior}
        campaigns.update(str(Path(b['path']).parent) for b in old.get('campaigns',[]))
        report={'global':data['global'],'job':data['job'],'obligations':request.obligations,
                'evidence':[bind(p) for p in request.evidence],
                'baseline':{name:bind(case/(name+'.json')) for name in ('spec','nl0')} if case else {},
                'campaigns':[bind(Path(p)/'campaign.json') for p in sorted(campaigns)]}
        path=self.save('graph-repair-'+Path(data['global']['path']).parents[2].name,report)
        return {'port':'repair','data':{k:data[k] for k in ('job','goal','global')} | {'repair':path}}

    def dispatch(self, name, ctx, data, routes):
        start=time.monotonic()
        row={'block':ctx.node,'started_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':None}
        self.timings.append(row)
        self.save('blocks',self.timings)
        try:
            return self.execute_block(name,data,ctx,routes)
        finally:
            row['elapsed_seconds']=time.monotonic()-start
            self.save('blocks',self.timings)

    def execute_block(self, name, data, ctx, routes):
        import case_runner
        import source_preparation
        from workflow_checkpoint import stop_at
        try:
            late_choice=name=='publish' and self.read(data['outcome']).get('status')=='DIFFERENT_RESULT_DELIVERED'
            if not late_choice:self.recorder.check()
            elif self.recorder.cancelled():
                from execution_state import Cancelled
                raise Cancelled('Cancelled during explicit alternate delivery')
            for value in data.values():
                if isinstance(value,dict):
                    verify_bindings([value])
            if data['job']!=bind(self.root/'job.json'):
                raise ValueError('Transition belongs to a different job')
            goal = 'audit' if self.job['track']=='nl0' else basis.mode(self.job)
            if name.startswith('request_'):
                jobs.validate(self.job)
                if name != 'request_'+goal:
                    raise ValueError('Prepared job goal differs from public entry')
                return routes.outcome('selected',{**data,'goal':goal})
            if data['goal']!=goal:
                raise ValueError('The public goal changed')
            common={'job':data['job'],'goal':goal}
            if name=='reduce':
                try:
                    basis.run(self.job,self.budgets.serial,self.progress)
                except StageFailure as error:
                    if error.result['status']!='STOPPED_BY_USER': raise
                    from case_outcomes import verify_basis_decision
                    verify_basis_decision(self.root,error.result['user_decision'],'stop')
                    return routes.outcome('stopped',{**common,'outcome':self.save('stopped',error.result)})
                return routes.outcome('prepared',{**common,'basis':self.save('foundations',basis.foundation_record(self.job))})
            if name=='freeze_basis':
                basis.verify_foundations(self.job,data['basis'])
                stop_at(self,'2basis',data['basis'])
                return routes.outcome('frozen',data)
            if name in ('direct_outline','basis_outline','revise_graph'):
                previous=findings=None
                owner=frozen_graph.DIRECT
                foundation=None
                if goal=='unconditional':
                    foundation=data['basis'] if 'basis' in data else self.read(data['global'])['foundation']
                    basis.verify_foundations(self.job,foundation)
                    owner=frozen_graph.BASIS
                if name=='revise_graph':
                    self.working(data)
                    report=self.read(data['repair'])
                    if report['job']!=data['job'] or report['global']!=data['global']:
                        raise ValueError('Stale or foreign NL0 graph repair')
                    verify_bindings(report['evidence']+report['campaigns']+list(report['baseline'].values()))
                    previous,findings=data['global'],report['obligations']
                self.progress(self.job['case'],'NL0_GLOBAL_REVISION' if previous else 'NL0_GLOBAL_REVIEW',owner=owner)
                checked=frozen_graph.global_stage(self.job,self.budgets.serial,owner=owner,previous=previous,findings=findings,foundation=foundation)
                selected=frozen_graph.select(self.job,checked,previous=previous)
                return routes.outcome('selected',{**common,'global':selected,**({'history':data['repair']} if previous else {})})
            if name=='detail':
                self.working(data)
                self.progress(self.job['case'],'NL0_LOCAL_AUTHORING')
                history=self.read(data['history']) if 'history' in data else {}
                baseline=history.get('baseline',{})
                verify_bindings(list(baseline.values()))
                directory=self.root/'nl0'/('local-'+Path(data['global']['path']).parents[2].name if history else 'local')
                role='nl0-author'
                session=self.reviews.use(role) if role in self.reviews.roles else nullcontext()
                with session:
                    source=case_runner.author_stage(self.job,directory,self.budgets.serial,
                        baseline=Path(baseline['nl0']['path']).parent if baseline else None,
                        obligations=history.get('obligations') if baseline else None)
                self.working(data)
                return routes.outcome('detailed',{**data,'local':bind(source/'nl0.json')})
            if name=='audit':
                self.working(data)
                history=self.read(data['history']) if 'history' in data else {}
                prior=history.get('campaigns',[])
                verify_bindings(prior)
                authority=case_runner.nl0_work(self.job,self.recorder,self.budgets.serial,self.progress,
                    audit_budget=self.budgets.audit,initial_source=Path(data['local']['path']).parent,
                    review_history=[Path(b['path']).parent for b in prior], sessions=self.reviews)
                frozen=self.working(data)
                selected=source_preparation.read_source(**authority)[0]
                frozen_graph.check_assignment(frozen,selected[2],selected[1])
                receipt={'global':data['global'],'files':{k:bind(v) for k,v in authority.items() if v is not None}}
                binding=self.save('audited-nl0',receipt)
                return routes.outcome('reviewed',{**common,'global':data['global'],'authority':binding})
            if name=='seal_audit':
                self.reviewed(data)
                return routes.outcome('sealed',data)
            if name=='audit_exit':
                authority,selected=self.reviewed(data)
                if selected[0].get('source_warnings'):
                    import source_qualification
                    source_qualification.publish(self.root,selected)
                write(self.root/'source-selection.json',authority)
                checked={'status':'DRAFT-AUDIT-PASSED' if selected[0]['current_standard_receipt_valid']
                         else 'DRAFT-AUDIT-CONDITIONAL','source':authority,'acceptance_scope':'NL0_AND_AUDIT_A_ONLY'}
                stop_at(self,'nl0',bind(self.root/'source-selection.json'))
                return routes.after_audit(data,data['authority'],self.save('audit',checked))
            if name=='translate':
                authority,_=self.reviewed(data)
                result=case_runner.translation_work(self.job,authority,self.budgets,self.progress)
                intermediate=self.save('translation',result)
                different=result.get('status')=='DIFFERENT_RESULT_DELIVERED'
                if not different:stop_at(self,'nl02lean',intermediate)
                return routes.after_translation(data,intermediate,different=different)
            if name=='close':
                import b2lean
                intermediate=self.read(data['intermediate'])
                directory=Path(intermediate['audit_b']['receipt_path']).parent.parent
                self.progress(self.job['case'],'BASIS_FINAL_CLOSURE',workflow=str(directory))
                result=b2lean.finish(directory,self.root/'b2lean',context=case_runner.ir_context(self.job),intermediate=intermediate)
                return routes.outcome('finish',{**common,'outcome':self.save('closure',result)})
            if name=='publish':
                import delivery
                result=self.read(data['outcome'])
                port,scope=routes.classify(goal,result['status'],closed=result.get('closure',{}).get('kernel_closed',False),
                    qualified=result.get('source_conditional',False))
                inventory,extra=delivery.publish(self.job,result,scope,self.recorder)
                self.result={**result,'delivery':str(self.root/'delivery'),'public_result':scope}
                return routes.outcome(port,{'scope':scope,'extra_premises':extra,
                    'inventory':ctx.put_file(json.dumps(inventory,sort_keys=True).encode())})
            raise ValueError('Missing Yui handler '+name)
        except graph_repair.Request as request:
            if name not in ('detail','audit'):raise
            try:
                return self.repair(data,request)
            except Exception as failure:
                self.failure=failure
                raise
        except StageFailure as error:
            self.failure=error
            raise
        except Exception as error:
            self.failure=error
            raise
