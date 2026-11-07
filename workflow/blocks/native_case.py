"""Native actions selected by the versioned public graph."""
from pathlib import Path
import json
import time
from datetime import datetime, timezone

import basis
import frozen_graph
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

    def save(self, name, value):
        path = self.root/'handoffs'/(name+'.json')
        write(path,value)
        return bind(path)

    def read(self, binding):
        verify_bindings([binding])
        return json.loads(Path(binding['path']).read_bytes())

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
                return routes.outcome('prepared',{**common,'basis':bind(basis.problem_inputs(self.job)/basis.CONTEXT)})
            if name in ('direct_outline','basis_outline'):
                owner=frozen_graph.DIRECT
                if 'basis' in data:
                    basis.verify_context(self.read(data['basis']))
                    owner=frozen_graph.BASIS
                self.progress(self.job['case'],'NL0_GLOBAL_FREEZE',owner=owner)
                frozen=frozen_graph.global_stage(self.job,self.budgets.serial,owner=owner)
                frozen_graph.select(self.job,frozen)
                if owner==frozen_graph.BASIS:stop_at(self,'2basis',frozen)
                return routes.outcome('frozen',{**common,'global':frozen})
            if name=='detail':
                self.progress(self.job['case'],'NL0_LOCAL_AUTHORING')
                if self.read(bind(self.root/'global-selection.json'))!=data['global']:
                    raise ValueError('Wrong frozen global selection')
                source=case_runner.author_stage(self.job,self.root/'nl0/local',self.budgets.serial)
                return routes.outcome('detailed',{**data,'local':bind(source/'nl0.json')})
            if name=='audit':
                authority=case_runner.nl0_work(self.job,self.recorder,self.budgets.serial,self.progress,
                    audit_budget=self.budgets.audit,initial_source=Path(data['local']['path']).parent)
                selected=source_preparation.read_source(**authority)[0]
                frozen=self.read(bind(self.root/'global-selection.json'))
                frozen_graph.check_frozen(frozen_graph.read_frozen(frozen),selected[2],selected[1])
                if selected[0].get('source_warnings'):
                    import source_qualification
                    source_qualification.publish(self.root,selected)
                write(self.root/'source-selection.json',authority)
                checked={'status':'DRAFT-AUDIT-PASSED' if selected[0]['current_standard_receipt_valid']
                         else 'DRAFT-AUDIT-CONDITIONAL','source':authority,'acceptance_scope':'NL0_AND_AUDIT_A_ONLY'}
                stop_at(self,'nl0',bind(self.root/'source-selection.json'))
                return routes.after_audit({**data,'global':frozen},bind(self.root/'source-selection.json'),self.save('audit',checked))
            if name=='translate':
                authority=self.read(data['authority'])
                source_preparation.read_source(**authority)
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
        except StageFailure as error:
            if name=='audit' and error.result['status']=='STOPPED_BY_USER':
                from case_outcomes import verify_basis_decision
                verify_basis_decision(self.root,error.result['user_decision'],'stop')
                return routes.outcome('finish',routes.final_data(data,self.save('stopped',error.result)))
            self.failure=error
            raise
        except Exception as error:
            self.failure=error
            raise
