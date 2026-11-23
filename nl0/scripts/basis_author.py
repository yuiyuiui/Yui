"""Own-stage draft tools for long basis reductions; no additional model roles."""
from __future__ import annotations

import json
import time

from clean_stage import ArtifactStage
from read_views import read_json
import model_pilot as pilot


class BasisStage(ArtifactStage):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.validator.owner_stage=self
        self.tools += [pilot.carrier.tool('save_basis_draft',
            'Save actual partial basis work without claiming completeness or running Lean. Read/revise it after feedback or context reset.',
            {'artifact':{'type':'object'}},['artifact']),
            pilot.carrier.tool('read_basis_draft',
            'Read your actual saved basis drafts. kind=index lists candidate IDs; kind=candidate reads a bounded JSON-pointer view with continuation offsets. No other agent/case files.',
            {'kind':{'type':'string','enum':['index','candidate']},'candidate':{'type':'integer'},
                'pointer':{'type':'string'},'offset':{'type':'integer'},'limit':{'type':'integer'}},['kind'])]
        import basis_planning as planning
        for name,description,shape in [
                ('investigate_basis_frontier','Investigate the remaining independent foundations in parallel. Give each statement and every consumer and required use. Read the returned proposals and select a compatible route.',planning.FRONTIER),
                ('prepare_basis_graph','Select the saved COMPLETE natural-language route before writing Lean proofs. Use prove:false to select without workers, or leave prove:true to prove its missing dependencies. New proof bodies are accepted only after route selection.',planning.PLAN)]:
            self.tools.append(pilot.carrier.tool(name,description,shape['properties'],shape['required']))
        self.tool_names={t['name'] for t in self.tools};self.native_tools=list(self.tools)
        self.input_prompt+='''\nUse save_basis_draft for actual partial work and
read_basis_draft kind=index after context reset. Read exact fields/long proof
strings with kind=candidate, pointer and continuation offset; no need to restart
from the original proof. Saving is not machine or mathematical acceptance.
Ordinary unfinished drafting/reduction is not a terminal obstacle: continue a
concrete step. Only actual located source/math/execution blockers justify stopping.
Follow the next action in imported Lean diagnostics for retained source. Continue
other foundations while investigating the affected dependency. Use
prepare_basis_graph with prove=false to select a complete route with pending
imports. Bind them before starting Lean proof workers or submitting proof bodies.
For an original-name port use check_imported_lean with bind_public=true, the
failed public build reference in source.failure, and the complete edited source in candidate.
Use wait_for_lean_dependency when an outstanding receipt names an operator
action. Use the remaining dependency attempts for concrete fixes or a checked
alternative. Use MISSING_SOURCE_STATEMENT for genuinely missing readable material.
'''

    def controller_checkpoint(self):
        return {'kind':'YUI_BASIS_AUTHOR_CHECKPOINT','candidates':sorted(self.validator.drafts),
            'latest_candidate':self.validator.attempt or None,
            'last_machine_checked_candidate':self.validator.last_checked,
            'mathematical_acceptance':False,
            'next_actions':['read_basis_draft kind=index',
                'Read the newest own candidate and continue its concrete reduction/proof work.',
                'A saved partial or rejected draft is not a completed basis.']}

    def dispatch(self,name,args):
        if name=='check_imported_lean' and args.get('candidate') is not None:
            import basis_planning
            try:basis_planning.require_selected_route(self.validator,self.validator.drafts[self.validator.attempt])
            except (ValueError,KeyError) as error:return {'accepted':False,'stage_complete':False,'error':str(error)}
        if name=='report_obstacle':
            value=args
            if isinstance(value,dict) and value.get('status')=='TASK_INCOMPLETE':
                result={'accepted':False,'stage_complete':False,'feedback_kind':'author_action_required',
                    'error':'Save the actual partial basis and continue; ordinary unfinished work is not a mathematical gap.'}
                pilot.carrier.append(self.logs/'tools.jsonl',{'tool':name,'arguments':args,'result':result,'wall_seconds':0})
                return result
        if name not in {'save_basis_draft','read_basis_draft','investigate_basis_frontier','prepare_basis_graph'}:return super().dispatch(name,args)
        started=time.monotonic()
        try:
            if self.accepted is not None:raise ValueError('Stage is already complete')
            if name=='investigate_basis_frontier':
                import basis_planning
                result=basis_planning.investigate(self,args)
            elif name=='prepare_basis_graph':
                import basis_planning
                result=basis_planning.prepare(self,args)
            elif name=='save_basis_draft':
                self.validator.save(args['artifact'])
                result={'saved':True,'candidate':self.validator.attempt,'stage_complete':False,'mathematical_acceptance':False}
            elif args['kind']=='index':
                result=read_json(self.controller_checkpoint(),args.get('pointer',''),
                    offset=args.get('offset',0),limit=args.get('limit',250))
            else:
                if args['kind']!='candidate':raise ValueError('Unknown basis draft view')
                number=args['candidate']
                if type(number) is not int or number<1 or number not in self.validator.drafts:
                    raise ValueError('Select a saved own-stage candidate')
                result=read_json(self.validator.drafts[number],args.get('pointer',''),
                    offset=args.get('offset',0),limit=args.get('limit',250),metadata={'candidate':number})
        except (ValueError,KeyError,TypeError,IndexError) as error:
            result={'accepted':False,'stage_complete':False,'error':str(error)}
        except Exception as error:
            self.record_tool_fault(name,args,error,started)
            raise
        pilot.carrier.append(self.logs/'tools.jsonl',{'tool':name,'arguments':args,'result':result,'wall_seconds':time.monotonic()-started})
        return result
