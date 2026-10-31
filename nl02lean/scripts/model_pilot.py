#!/usr/bin/env python3
"""Fresh subscription-carried Yui model stages for typed Lean obligations.

Uses the official native Codex client; exposes neither owner references
nor shell/filesystem access. All actual transmitted inputs and usage are retained.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import sys
import tempfile
import threading
import time
import traceback

import ir
import strategy_bank
import scheduler
import concurrency
import execution_state as execution
import proof_repair
from shared_lemmas import Store

sys.path.insert(0, str(ir.ROOT/'nl0/scripts'))
import run_pilot as carrier
from runtime_config import model_profile
from native_client import OUTPUT_POLICY, PROVIDER_WAIT_POLICY
from pilot_common import sha256, load_lock as runtime_lock

REMOTE_RETRY_POLICY = carrier.REMOTE_RETRY_POLICY


def load_lock():
    return runtime_lock()


carrier.load_lock = load_lock

HARNESS = 'yui-0.1.3'
BACKGROUND_NOTE_POLICY = 'local-background-on-demand-1'
LEAN_WRITING_PATH = ir.HERE/'references/lean-writing.md'
STAGE_LIMITER = None
carrier.CONTINUE_PROMPT = ('The requested artifact has not passed submission. '
                          'Continue with the same inputs and tools; preserve the fixed specification.')
SYSTEM = ('You translate the supplied natural-language proof faithfully into Lean 4. '
          'Use the explicit project premises and any proved result in the pinned Mathlib environment. '
          'Preserve all assumptions, conclusions, equality modes and the supplied proof route. '
          'No reference answers, personal context, other tasks, shell or external services are available. '
          'Use the submit tool when the requested artifact is complete; if rejected, repair it. '
          'A strategy is advice, never an additional theorem or assumption.')


def json_tool(name, description, field):
    return carrier.tool(name, description, {field:{'type':'string'}}, [field])


class Stage(carrier.Trial):
    def __init__(self, logs, cpath, mode, timeout, plan=None, step=None, bank_enabled=False, budget=None, instruction_arm='yui', timeout_policy=None):
        from run_resources import check_cleanup_lock, register_workspace
        check_cleanup_lock(logs)
        self.logs = Path(logs)
        self.logs.mkdir(parents=True, exist_ok=False)
        self.work = Path(tempfile.mkdtemp(prefix='nl0-ir-model-')).resolve()
        register_workspace(self.work, self.logs)
        for n in ('input','output','tmp','home','state'):
            (self.work/n).mkdir(mode=0o700)
        self.cpath = Path(cpath)
        self.mode, self.plan, self.step = mode, plan, step
        self.model_selection = model_profile(mode)
        self.budget = budget
        self.timeout = __import__('runtime_config').time_limit(timeout)
        self.harness_version = HARNESS
        self.strict = True
        self.system = SYSTEM
        if instruction_arm not in {'yui','direct'}:
            raise ValueError('Unknown instruction arm')
        self.instruction_arm = instruction_arm
        self.proof_progress=proof_repair.Progress() if mode=='proof' and instruction_arm=='yui' else None
        self.repair_request=None
        self.lean_writing_rules = None
        self.native_timeout_snapshot = None
        self.native_timeout_lean_version = None
        if mode == 'proof' and instruction_arm == 'yui':
            self.lean_writing_rules = LEAN_WRITING_PATH.read_text(encoding='utf-8')
            self.system += '\n\n'+self.lean_writing_rules
            self.native_timeout_lean_version = ir.contract(self.cpath)['pins']['lean_version']
            if timeout_policy is not None and timeout_policy.get('status')!='READY':
                self.native_timeout_snapshot={**timeout_policy,'files':[]}
            else:
                self.native_timeout_snapshot = strategy_bank.freeze_native_timeout_policy(
                    self.logs/'harness-snapshot/nl02lean/bank',
                    bank=timeout_policy['bank_root'] if timeout_policy is not None else None)
            self.system += (' A native resource failure may include repair_advice from frozen ST020. '
                'Use its applicable diagnostic branch first, repair in this same stage and recheck '
                'the unchanged target. Advice does not add assumptions or establish acceptance.')
        if instruction_arm == 'direct':
            if bank_enabled:
                raise ValueError('The direct arm cannot use the Yui strategy bank')
            self.system = ('Prove the exact supplied Lean target from its explicit mathematical inputs. '
                           'Use only the declared library and checking tools. Submit a tactic proof body '
                           'through submit_transition; preserve the target and permitted assumptions.')
        if bank_enabled:
            self.system += (' Strategy lookup is optional. Continue directly when the next repair is clear. '
                'If repeated attempts make no progress, you may query find_strategies with an observed diagnostic. Families: representation, '
                'analysis, calculation, interface, provenance, execution, unknown. Example tags: norm, '
                'supremum, ENNReal, ae, representative, weight, Lp, measurability, coercion, API. '
                'Only put established conditions in facts. Verify suggested preconditions; never assume a missing one.')
        self.system += (' End this stage immediately when a submit tool reports stage_complete:true; '
                        'the controller handles later stages. Within a proof stage, checked helper attempts '
                        'are available through read_lean_draft. After a context reset, query its index '
                        'before claiming no draft or helper exists. Helpers never become new premises.')
        self.phase = 'proof'
        self.tools = [dict(t) for t in carrier.TOOLS[:2]]
        self.tools[0]['description']='Search the pinned mathlib Lean source using a regular expression; at most 100 lines.'
        self.tools[1]['description']='Read specified lines of a Mathlib/*.lean source file from the pinned checkout.'
        if mode == 'interface':
            self.tools += [json_tool('check_interface','Check a proposed typed interface. JSON string has parameters [{name,type}], premises [{id,type}], conclusion_type, representation_notes.','interface_json'),
                           json_tool('submit_interface','Submit the same typed interface after checking.','interface_json')]
        elif mode == 'plan':
            self.tools += [json_tool('check_plan','Check an IR plan structurally and elaborate its Lean proposition types.','plan_json'),
                           json_tool('submit_plan','Submit a complete IR plan; same checks as check_plan.','plan_json')]
        else:
            self.tools += [json_tool('check_transition','Compile a tactic body for the fixed target; no leading by, declarations, or placeholders.','proof'),
                           json_tool('submit_transition','Submit and check the final tactic body for the same target.','proof')]
        if mode=='proof':
            self.tools += [carrier.tool('check_auxiliary','Compile one helper proposition and tactic body in exactly this local port context. This never accepts the final goal or adds a premise.',
                {'statement':{'type':'string'},'proof':{'type':'string'}},['statement','proof']),
                carrier.tool('read_lean_draft','Read only your own same-stage proof/helper attempts. kind=index lists attempts; proof/auxiliary returns the selected body lines and actual check. No other stage or file is accessible.',
                {'kind':{'type':'string','enum':['index','proof','auxiliary']},'candidate':{'type':'integer'},'start':{'type':'integer'},'end':{'type':'integer'}},['kind','candidate','start','end'])]
            if instruction_arm=='yui':
                self.tools.append(carrier.tool('report_proof_obstruction',
                    'Request diagnosis while retaining this author. Reference current packet pointers and at most six actual own attempts. A source allegation requires source_issue with a verbatim source_quote and the mathematical defect. Ordinary errors, resource exhaustion or inability do not authorize ending the task.',
                    {'layer':{'type':'string','enum':['local_proof','interface','source','unknown']},
                     'explanation':{'type':'string'},'locations':{'type':'array','items':{'type':'string'}},
                     'candidates':{'type':'array','items':{'type':'object','properties':{
                         'kind':{'type':'string','enum':['proof','auxiliary']},'candidate':{'type':'integer'}},
                         'required':['kind','candidate'],'additionalProperties':False}},
                     'source_issue':{'type':'object','properties':{k:{'type':'string'} for k in
                         ['kind','source_quote','hypotheses','claim','defect','why_not_lean_difficulty']},
                         'required':['kind','source_quote','hypotheses','claim','defect','why_not_lean_difficulty'],
                         'additionalProperties':False}},
                    ['layer','explanation','locations','candidates']))
                self.system+=(' If the fixed interface or source appears inconsistent, report_proof_obstruction '
                    'with located actual evidence instead of silently changing it or repeating a blocker. '
                    'Compiler/interface reports require a relevant failed own-context check; successful helpers or bare inability are insufficient. Rejected reports leave you active. Ordinary proof-body errors remain your local repair work. '
                    'The controller routes the reported issue; it does not change frozen endpoints or retire sibling work on an idle-turn counter.')
        self.background_note_policy = None
        if (mode == 'proof' and instruction_arm == 'yui'
                and ir.local_packet(self.cpath, plan, step).get('accepted_background_notes')):
            self.background_note_policy = BACKGROUND_NOTE_POLICY
            self.tools.append(carrier.tool('read_background_note',
                'Read one complete audited background note from this task index by its qualified ID. No other task, file or proof is accessible; this is guidance, not a checked Lean proof.',
                {'id':{'type':'string'}}, ['id']))
            self.system += (
                ' Use familiar interfaces directly; no background-note scan is required. '
                'For a relevant obstacle, select a matching local background_note_index entry and '
                'read_background_note if its details may help. Relate the actual Lean goal/context '
                'to its NL step: use the note grounds to identify a small missing application premise '
                'or transport, prove it from permitted inputs, then check the intended application. '
                'Verify actual types and conditions; a note is not a Lean proof or extra assumption. '
                'If it does not fit, continue ordinary allowed search or repair without insisting '
                'on that note or rebuilding a larger argument by default.')
        if bank_enabled:
            self.tools += [json_tool('find_strategies','Query the indexed bank using a JSON diagnostic. Fields: family, tags, facts, lean_version. Advice is not a premise.','query_json')]
        self.tool_names = {t['name'] for t in self.tools}
        self.accepted = None
        self.own_lean_drafts={'proof':{},'auxiliary':{}}
        self.local_helpers=[]
        self.diagnose_obstruction=None
        self.diagnosis_cache={}
        if mode=='proof':
            self.system += (' Successful check_auxiliary results register a same-node yui_aux_... theorem. '
                'Use its returned application in later helpers or the final proof instead of copying its body. '
                'All helper proofs remain in standalone assembly and use only the listed inputs. '
                'Unknown difficulty or repeated failure does not end this task. A source issue must locate '
                'a false implication or major missing mathematical justification; not missing Lean syntax or APIs.')
            self.continuation_prompt=('Continue the same proof from saved drafts, checked helpers and actual feedback. '
                'Repair the next concrete implementation error. Repeated failures or inability alone are not '
                'a source defect and do not end the task. Submit the complete unchanged target when checked.')
        self.stop_on_submission=True
        self.submission_closed=False
        self.api_calls = self.lean_calls = self.rpc_id = 0
        self.request_lock = threading.Lock()
        self.native_turn_generation = 0
        self.request_turns = {}
        self.last_response_success = None
        self.inbox = queue.Queue()
        self.started = None
        self.allowed_user_messages = set()
        self.proc = None
        self.model_calls, self.tool_history = {}, {}
        self.continuation_count = 0
        self.turn_results = []
        self.last_turn_event = self.active_turn_id = self.pending_turn_start_id = None
        self.initial_user_message = None
        self.last_diagnostic = ''

    def dispatch(self, name, args):
        if name in ('search_mathlib','read_mathlib'):
            result=super().dispatch(name,args)
            self.observe_proof_progress(name,args,result)
            return result
        begin = time.monotonic()
        record=None;record_path=None
        try:
            if self.accepted or self.repair_request:
                raise ir.Invalid('stage already closed; no overwrite')
            if self.mode=='proof' and self.instruction_arm=='yui' and name=='report_proof_obstruction':
                report=proof_repair.obstruction(self,args)
                result=self.request_proof_repair(report)
            elif name == 'find_strategies':
                c=ir.contract(self.cpath)
                if self.mode=='proof':
                    packet=ir.local_packet(self.cpath,self.plan,self.step)
                    goal=packet['target'];context='\n'.join(p['type'] for p in packet['inputs'])
                else:
                    goal=c['conclusion']['type'];context='\n'.join(p['type'] for p in c['premises'])
                query,receipt=strategy_bank.grounded_query(json.loads(args['query_json']),goal,context,
                    c['pins']['lean_version'],self.last_diagnostic)
                result = strategy_bank.search(query)
                result['routing_receipt']=receipt
            elif name == 'read_background_note':
                ir.need(self.background_note_policy == BACKGROUND_NOTE_POLICY,
                        'background note access is unavailable for this stage')
                packet = ir.local_packet(self.cpath, self.plan, self.step)
                notes = packet.get('accepted_background_notes', {})
                key = args['id']
                ir.need(isinstance(key, str) and key in notes,
                        'background note is outside this local task')
                result = {'id':key, 'note':notes[key],
                    'background_supplement_sha256':packet['background_supplement_sha256'],
                    'scope':('Audited local guidance only. Ground locations address the source NL packet, '
                             'not positional Lean binders; match their content to this local context. '
                             'Prove required Lean facts under the unchanged permitted inputs.')}
            elif self.mode == 'interface' and name in ('check_interface','submit_interface'):
                value = ir.load_json_text(args['interface_json']) if hasattr(ir,'load_json_text') else json.loads(args['interface_json'],object_pairs_hook=ir.unique)
                result = ir.check_interface(self.cpath,value,timeout=self.lean_timeout())
                self.lean_calls += 1
                if result['exit_code'] == 0 and name.startswith('submit'):
                    self.accepted = value
            elif self.mode == 'plan' and name in ('check_plan','submit_plan'):
                value = json.loads(args['plan_json'],object_pairs_hook=ir.unique)
                result = ir.check(self.cpath,value,types_only=True,timeout=self.lean_timeout())
                self.lean_calls += 1
                if result['exit_code'] == 0 and name.startswith('submit'):
                    self.accepted = value
            elif name in ('check_transition','submit_transition'):
                value = args['proof']
                import local_helpers
                packaged=local_helpers.package(self.cpath,self.plan,self.step,value,self.local_helpers)
                number=len(self.own_lean_drafts['proof'])+1
                record={'proof':value,'statement':self.plan['steps'][next(i for i,s in enumerate(self.plan['steps']) if s['id']==self.step)]['statement'],
                        'proof_package':packaged}
                self.own_lean_drafts['proof'][number]=record;record_path=self.logs/'lean-drafts'/f'proof-{number:04d}.json'
                result = ir.check(self.cpath,self.plan,{self.step:packaged},only=self.step,timeout=self.lean_timeout())
                self.lean_calls += 1
                if result['exit_code'] == 0 and name.startswith('submit'):
                    self.accepted = {'proof':packaged}
            elif self.mode=='proof' and name=='check_auxiliary':
                number=len(self.own_lean_drafts['auxiliary'])+1
                record={'statement':args['statement'],'proof':args['proof']}
                self.own_lean_drafts['auxiliary'][number]=record;record_path=self.logs/'lean-drafts'/f'auxiliary-{number:04d}.json'
                result=ir.check_auxiliary(self.cpath,self.plan,self.step,args['statement'],args['proof'],
                    out=self.logs/'auxiliary-checks'/f'{number:04d}',timeout=self.lean_timeout(),helpers=self.local_helpers)
                self.lean_calls+=1
                result['candidate']=number
                if result.get('auxiliary_valid') and result.get('lean_sha256'):
                    import local_helpers
                    helper=local_helpers.append(self.cpath,self.plan,self.step,self.local_helpers,
                        args['statement'],args['proof'],result)
                    self.local_helpers.append(helper)
                    ir.write(self.logs/'local-helpers.json',self.local_helpers)
                    result['helper']={'name':helper['name'],'statement':helper['statement'],
                        'application':'@'+helper['name']+' '+ ' '.join(
                            [p['name'] for p in ir.contract(self.cpath)['parameters']]+
                            [p['binder'] for p in ir.local_packet(self.cpath,self.plan,self.step)['inputs']]),
                        'scope':'Checked same-node theorem; available in later checks and the final body.'}
            elif self.mode=='proof' and name=='read_lean_draft':
                kind=args['kind']
                if kind=='index':
                    result={'local_helpers':[{'name':r['name'],'statement':r['statement']} for r in self.local_helpers],
                        'own_same_stage_attempts':{key:[{'candidate':n,'statement_preview':r['statement'][:300],
                        'actual_check':{k:r.get('check',{}).get(k) for k in ['status','exit_code','auxiliary_valid','error']}}
                        for n,r in rows.items()] for key,rows in self.own_lean_drafts.items()},
                        'scope':'Only actual own-stage attempts; no helper has been added as a premise.'}
                else:
                    ir.need(kind in self.own_lean_drafts,'unknown draft kind')
                    number=args['candidate'];ir.need(type(number) is int and number in self.own_lean_drafts[kind],'unknown own-stage draft')
                    start,end=args['start'],args['end'];ir.need(type(start) is int and type(end) is int and 1<=start<=end and end-start<250,'Read at most 250 positive body lines')
                    row=self.own_lean_drafts[kind][number];lines=row['proof'].splitlines()
                    result={'statement':row['statement'],'proof':'\n'.join(lines[start-1:end]),'total_lines':len(lines),'actual_check':row.get('check')}
            else:
                raise PermissionError('tool not allowed for this stage')
            if 'exit_code' in result:
                result['accepted'] = result['exit_code']==0
                result['stage_complete'] = bool(self.accepted)
                self.last_diagnostic = (result.get('stdout','')+'\n'+result.get('stderr',''))[:14000] if result['exit_code'] else ''
                if (self.mode=='proof' and self.instruction_arm=='yui'
                        and name in {'check_transition','submit_transition','check_auxiliary'}):
                    advice=strategy_bank.native_timeout_feedback(result,
                        self.native_timeout_lean_version,self.native_timeout_snapshot)
                    if advice is not None:result['repair_advice']=advice
        except (ir.Invalid, KeyError, ValueError, TypeError, IndexError) as e:
            result = {'accepted':False,'error':str(e),'feedback_kind':'candidate_rejected'}
            self.last_diagnostic=str(e)[:14000]
        if record is not None:
            record['check']=dict(result);ir.write(record_path,record)
        self.observe_proof_progress(name,args,result)
        carrier.append(self.logs/'tools.jsonl',{'tool':name,'arguments':args,'result':result,
                                               'wall_seconds':time.monotonic()-begin})
        # Keep owner oracle signatures out of compiler feedback for interface work.
        if self.mode == 'interface' and result.get('exit_code',0) != 0:
            return {'accepted':False,'status':result['status'],
                    'feedback':'Interface did not match the original premise/target ports. Re-read the supplied NL input; do not change assumptions or equality/range conventions.'}
        if 'stdout' in result:
            return {**result,'stdout':result['stdout'][:14000],'stderr':result.get('stderr','')[:2000]}
        return result

    def observe_proof_progress(self,name,args,result):
        progress=getattr(self,'proof_progress',None)
        if progress is None:return
        progress.observe(name,args,result,carrier.now())
        ir.write(self.logs/'proof-progress.json',progress.metadata())
        ir.write(self.logs/'proof-progress-actions.json',{'actions':sorted(progress.seen)})
        recorder=getattr(self,'execution',None)
        if recorder:recorder.task(self.execution_task,proof_progress=progress.metadata())

    def request_proof_repair(self,report):
        key=report['evidence_key']
        out=self.logs/'diagnosis-requests'/key
        ir.write(out/'request.json',report)
        recorder=getattr(self,'execution',None)
        failed=[self.own_lean_drafts[x['kind']][x['candidate']]['check'] for x in report['candidates']
                if self.own_lean_drafts[x['kind']][x['candidate']]['check'].get('exit_code',0)!=0]
        if report['layer']!='source' and failed and all(proof_repair.resource_only(r) for r in failed):
            result={'accepted':False,'stage_complete':False,'repair_requested':False,
                'next_action':'Resource exhaustion alone is not an interface/source defect. Continue the same author using ST020 and checked helpers.',
                'diagnosis':{'route':'LOCAL_PROOF_REPAIR','basis':'RECORDED_RESOURCE_LIMIT_ONLY'}}
            ir.write(out/'diagnosis.json',result['diagnosis'])
            return result
        if self.diagnose_obstruction is None:
            return {'accepted':False,'stage_complete':False,'repair_requested':False,
                    'next_action':'No qualified diagnosis is available. Retain your work and continue the unchanged local obligation.'}
        if key in self.diagnosis_cache:
            diagnosis=self.diagnosis_cache[key]
        else:
            if recorder:recorder.task(self.execution_task,activity='WAITING_FOR_DIAGNOSIS')
            try:
                with self.budget.suspended():
                    diagnosis=self.diagnose_obstruction(self,report,out)
            finally:
                if recorder:recorder.task(self.execution_task,activity='MODEL_RUNNING')
            self.diagnosis_cache[key]=diagnosis
        ir.write(out/'diagnosis.json',diagnosis)
        route=diagnosis['route']
        handoff=route in {'SOURCE_REVIEW_REQUIRED','INTERNAL_INTERFACE_REPAIR','INTERFACE_REPAIR_REQUIRED'}
        if handoff:
            self.repair_request={**report,'diagnosis':diagnosis}
            ir.write(self.logs/'proof-repair-request.json',self.repair_request)
            ir.write(self.logs/'proof-progress-actions.json',{'actions':sorted(self.proof_progress.seen)})
            self.submission_closed=True;self.stage_close_reason='QUALIFIED_PROOF_DEFECT'
            if recorder:recorder.task(self.execution_task,activity='REPAIR_REQUESTED',
                repair_request=str(self.logs/'proof-repair-request.json'),proof_progress=self.proof_progress.metadata())
        return {'accepted':False,'stage_complete':False,'repair_requested':handoff,
                'diagnosis':diagnosis,'same_author_retained':True,
                'next_action':('Hand off the qualified defect to the controller.' if handoff else
                    'Continue this same obligation using the diagnosis; preserve checked helpers. Difficulty is not a source defect.')}

    def after_unaccepted_turn(self):
        progress=getattr(self,'proof_progress',None)
        if progress is None:return False
        recorder=getattr(self,'execution',None)
        if recorder:recorder.check(self.execution_task)
        progress.completed_turn()
        ir.write(self.logs/'proof-progress.json',progress.metadata())
        if recorder:recorder.task(self.execution_task,proof_progress=progress.metadata())
        return False

    def check_runtime_state(self):
        super().check_runtime_state()
        if not getattr(self,'_stopping',False) and not getattr(self,'submission_closed',False):
            recorder=getattr(self,'execution',None)
            if recorder:
                recorder.check(self.execution_task)
                parent=getattr(self,'parent_execution_task',None)
                if parent:recorder.check(parent)

    def timeout_policy_metadata(self):
        snapshot=getattr(self,'native_timeout_snapshot',None)
        return {k:v for k,v in snapshot.items() if k not in {'bank_root','files'}} if snapshot else None

    def proof_packet(self):
        packet = ir.local_packet(self.cpath, self.plan, self.step)
        if self.background_note_policy:
            notes = packet.pop('accepted_background_notes')
            packet['background_note_index'] = [
                {'id':key, 'at':note['at'], 'kind':note['kind'], 'fact':note['fact'],
                 **({'declaration':note['source']['declaration']} if note.get('source') else {})}
                for key, note in notes.items()]
        return packet

    def prompt(self):
        c = ir.contract(self.cpath)
        if self.mode == 'interface':
            return json.dumps({'task':'Translate this NL fragment into typed Lean parameter, premise and output interfaces, without writing a proof. Preserve listed names and IDs/order.',
                'header':c['header'],'source':ir.load(self.cpath.parent/c['source']['path'])['mathematical_input'],
                'parameters':[{'name':p['name'],'binder_kind':p.get('binder_kind','explicit')} for p in c['parameters']],
                'premises':[{'id':p['id'],'statement':p['statement']} for p in c['premises']],
                'conclusion':c['conclusion']['statement'],'representation':c['representation'],
                'output_schema':{'parameters':[{'name':'supplied name','type':'Lean type','binder_kind':'preserve supplied explicit/implicit/instance kind'}],
                    'premises':[{'id':'supplied ID','type':'Lean Prop'}],
                    'conclusion_type':'Lean Prop','representation_notes':'explain choices'}},ensure_ascii=False)
        if self.mode == 'plan':
            public = {k:c[k] for k in ('header','parameters','premises','conclusion','representation','source_steps')}
            if c['source'].get('background_supplement'):
                public['background_supplement']=c['source']['background_supplement']
            if c['version'] == 2:
                public.update({k:c.get(k, []) for k in ('objects','shared_obligations')})
            return json.dumps({'task':'Construct a small typed transition plan following every supplied NL paragraph. Do not write proof bodies. Prefer a small number of useful closed obligations; each has only listed direct inputs. All retained steps must reach terminal.',
                'contract':public,'contract_sha256':ir.digest(self.cpath),
                'output_schema':{'version':c['version'],'contract_sha256':ir.digest(self.cpath),'representation_notes':'describe the actual ranges, equality modes and representation bridges',
                    'steps':[{'id':'T001','statement':'complete Lean Prop','inputs':['H001'],
                              'source_steps':['S001'],'explanation':'mathematical mechanism'}],'terminal':'last T ID'},
                'constraint':'Terminal statement must be exactly the supplied conclusion type; local premise proof names are h_H001 or h_T001. Cover all source paragraphs. When background notes are supplied, add background_notes:["Rnnn.BGnnn"] to each corresponding step; retain the checked facts and conditions, never add H. In version 2, mark shared_lemma only for an exact frozen shared_obligations entry. Never create or approve a new export.'},ensure_ascii=False)
        return json.dumps({'task':'Prove exactly this local conditional obligation using the supplied NL route. Return only the tactic body through submit_transition. All displayed parameter and input proof binders are already in context.',
                           'packet':self.proof_packet()},ensure_ascii=False)

    def execute(self):
        from role_sessions import current
        session=current()
        if session and not getattr(self,'_role_dispatching',False):
            return session[0].execute(self,session[1])
        self.execution=getattr(self.budget,'execution',None) or execution.current()[0]
        self.execution_task=execution.current()[1] or self.step or 'stage-'+hashlib.sha256(str(self.logs).encode()).hexdigest()[:12]
        recorder=self.execution
        if recorder and getattr(self,'role_session',None):
            recorder.task(self.execution_task,state='PENDING',finished_at_utc=None,stage_result=None,
                role_session=self.role_session)
        if recorder:recorder.task(self.execution_task,activity='WAITING_FOR_MODEL_SLOT',log_path=str(self.logs),stage=self.mode,
            role=getattr(self.budget,'role',None) or ('proof' if self.mode=='proof' else 'preparation_review'),model=self.model,
            model_selection=self.model_selection)
        queued = time.monotonic()
        limiter = self.budget or STAGE_LIMITER
        try:
            with execution.activate(recorder,self.execution_task):
                if recorder:recorder.check(self.execution_task)
                if limiter is None:
                    if recorder:self.timeout=recorder.remaining(self.timeout)
                    self.check_runtime_state()
                    return self._execute()
                with limiter:
                    self.queue_seconds = time.monotonic()-queued
                    if recorder:self.timeout=recorder.remaining(self.timeout)
                    self.check_runtime_state()
                    return self._execute()
        except proof_repair.RoundInterrupted as error:
            result={'status':'REPAIR_WAIT','task_outcome':'PROOF_ROUND_RETIRED',
                    'error':str(error),'api_calls':0,'acceptance':False}
            if recorder:recorder.retain_stage(self,'lean')
            ir.write(self.logs/'result.json',result)
            return result,None
        except execution.Cancelled as error:
            return self.cancel_before_start(error)
        except execution.CaseDeadlineExceeded as error:
            if not (self.logs/'result.json').is_file():
                from run_resources import retention
                result={'status':'UNFINISHED','stop_reason':'CASE_DEADLINE',
                    'task_outcome':'UNFINISHED_ATTRIBUTION_UNVERIFIED','error':str(error),
                    'execution_health':'UNVERIFIED','identity_and_input_boundary_verified':False,
                    'model_work_started':False,'temporary_workspace_removed':False,
                    'workspace_retention':retention(self.work,getattr(self,'workspace_owner_logs',self.logs))}
                ir.write(self.logs/'result.json',result)
                if recorder:
                    recorder.retain_stage(self,'nl0' if self.mode.startswith(('nl0-','audit-a')) else 'lean')
                    recorder.record_stage(self.execution_task,self.logs,result)
                    recorder.task(self.execution_task,state='UNFINISHED',activity='CASE_DEADLINE')
                    recorder.flush(force=True)
            raise
        except Exception as error:
            try:self.pause_error(error,resumable=False)
            except execution.Cancelled as cancelled:return self.cancel_before_start(cancelled)

    def cancel_before_start(self,error):
        result={'status':'CANCELLED','task_outcome':'EXTERNAL_CANCELLED','stop_reason':'EXTERNAL_CANCEL',
            'error':str(error),'api_calls':getattr(self,'api_calls',0),'lean_calls':getattr(self,'lean_calls',0),
            'remote_retries':getattr(self,'remote_retry_count',0),'measurement_valid':False,
            'execution_health':'FAULT' if getattr(self,'_fault_gate',None) else 'NO_RECORDED_FAULT'}
        if not getattr(self,'_resources_released',False):self.release_resources('USER_CANCELLED')
        ir.write(self.logs/'result.json',result)
        if self.execution:self.execution.task(self.execution_task,state='CANCELLED',finished_at_utc=execution.now())
        return result,None

    def release_resources(self, authorization):
        if authorization not in {'AUDIT_A_FINALIZED','WORKFLOW_FINALIZED','USER_CANCELLED','ROLE_COMPLETED'}:
            raise ValueError('Faults do not authorize process/workspace cleanup')
        if authorization=='ROLE_COMPLETED':
            from role_sessions import BOUNDARIES
            record=ir.load(self.logs/'role-completion.json')
            if record['boundary'] not in BOUNDARIES or not record['evidence']:
                raise ValueError('Missing successful role boundary')
            for row in [record['submission'],*record['evidence']]:
                if ir.digest(row['path'])!=row['sha256']:raise ValueError('Role completion evidence changed')
        if authorization=='AUDIT_A_FINALIZED' and not self.mode.startswith(('nl0-','audit-a')):
            raise ValueError('Audit A cannot authorize release of translation/proof resources before Audit B')
        if getattr(self,'_resources_released',False):return
        result={}
        if self.proc:
            if getattr(self,'execution',None):
                if not self.execution.stop_process(self.proc):result['execution_fault']='Model process cleanup unconfirmed'
            else:
                owner=getattr(self,'process_owner',None) or execution.capture_process(self.proc,private_group=True)
                if not execution.terminate_owned(self.proc,owner):result['execution_fault']='Model process group cleanup unconfirmed'
            if result.get('execution_fault'):raise RuntimeError(result['execution_fault'])
            reader=getattr(self,'reader_thread',None)
            if reader:reader.join(timeout=1)
            for stream in (self.proc.stdin,self.proc.stdout):
                if stream:stream.close()
        for name in ('auth.json','models_cache.json'):
            (self.work/'state'/name).unlink(missing_ok=True)
        if result.get('execution_fault'):raise RuntimeError(result['execution_fault'])
        retained=getattr(self,'workspace_retention',None)
        if self.work.exists():shutil.rmtree(self.work)
        if retained and (self.logs/'result.json').is_file():
            owner_logs=Path(retained['logs'])
            ir.write(owner_logs/'resources/release.json',{
                'authorization':authorization,'workspace_retention':retained,
                'result_sha256':sha256(owner_logs/'result.json'),'cleanup_confirmed':True,
                'at_utc':carrier.now()})
        self._resources_released=True

    def _execute(self):
        user = self.prompt()
        if not (self.logs/'execution-manifest.json').exists():
            files = []
            for path in [*ir.ROOT.glob('nl0/scripts/*.py'), *ir.HERE.glob('scripts/*.py'),
                         ir.ROOT/'toolchain/lock.json', ir.ROOT/'config.json']:
                target = self.logs/'harness-snapshot'/path.relative_to(ir.ROOT)
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(path,target)
                files.append({'path':str(path.relative_to(ir.ROOT)),'sha256':sha256(target)})
            if self.lean_writing_rules is not None:
                relative = 'nl02lean/references/lean-writing.md'
                target = self.logs/'harness-snapshot'/relative
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(self.lean_writing_rules,encoding='utf-8')
                files.append({'path':relative,'sha256':sha256(target)})
            if self.native_timeout_snapshot is not None:
                files.extend({'path':'nl02lean/bank/'+row['path'],'sha256':row['sha256']}
                             for row in self.native_timeout_snapshot['files'])
            ir.write(self.logs/'execution-manifest.json',{'model':self.model,'model_selection':self.model_selection,'effort':self.model_selection['reasoning_effort'],'speed':self.model_selection['speed'],
                'arm':self.instruction_arm,'phase':self.mode,'runtime_files':files,
                'native_timeout_policy':self.timeout_policy_metadata(),
                'background_note_policy':self.background_note_policy,
                'model_output_policy':OUTPUT_POLICY,
                'provider_wait_policy':PROVIDER_WAIT_POLICY,
                'remote_retry_policy':REMOTE_RETRY_POLICY,
                'proof_progress_policy':proof_repair.POLICY if self.proof_progress is not None else None,
                'resolved_environment':load_lock(),'scope':'Only the declared frozen obligation is model-visible.'})
        (self.logs/'prompt.txt').write_text(user+'\n')
        (self.logs/'system.txt').write_text(self.system+'\n')
        ir.write(self.logs/'tools.json',self.tools)
        result = {'mode':self.mode,'step':self.step,'model':self.model,'model_selection':self.model_selection,'effort':self.model_selection['reasoning_effort'],
                  'stage_log_path':str(self.logs.resolve()),
                  'native_timeout_policy':self.timeout_policy_metadata(),
                  'background_note_policy':self.background_note_policy,
                  'output_verbosity':getattr(self,'output_verbosity','low'),
                  'harness':self.harness_version,'time_budget_seconds':self.timeout,
                  'queue_seconds':getattr(self, 'queue_seconds', 0),
                  'model_output_policy':OUTPUT_POLICY,
                  'provider_wait_policy':PROVIDER_WAIT_POLICY,
                  'owner_reference_visible_to_worker':False,'started_at_utc':carrier.now()}
        result['acceptance_scope'] = (('NL0_STRUCTURE_ONLY' if self.artifact_kind=='nl0' else 'JSON_ARTIFACT_ONLY')
            if hasattr(self,'artifact_kind') else 'LEAN_LOCAL_OBLIGATION_OR_TYPED_INTERFACE')
        case_deadline = None
        try:
            if self.proc is None:
                self.start_process()
                inventory = self.rpc('skills/list',{'cwds':[str(self.work/'input')],'forceReload':True})
                ir.write(self.logs/'skills-inventory.json',inventory)
                thread = self.rpc('thread/start',__import__('native_client').thread_parameters(self))
                __import__('native_client').verify_thread(self,thread)
                self.thread_id = thread['thread']['id']
            elif self.proc.poll() is not None:
                raise RuntimeError('Retained role carrier exited; preserve its checkpoint, do not restart silently')
            result['role_session']=getattr(self,'role_session',None)
            result['native_thread_id']=self.thread_id
            if getattr(self,'execution',None):
                self.execution.task(self.execution_task,state='RUNNING',activity='MODEL_RUNNING',
                    model_started_at_utc=execution.now(),model_thread_id=self.thread_id)
            self.solve_turns(user)
            result['status'] = 'REPAIR_REQUESTED' if self.repair_request else 'ACCEPTED' if self.accepted else 'NO_ACCEPTED_ARTIFACT'
            if self.repair_request:
                result.update(task_outcome='PROOF_DIAGNOSIS_REQUIRED',repair_request=self.repair_request,
                              stop_reason='PROOF_REPAIR_ESCALATION')
            if self.accepted and self.accepted.get('status') in {'SUBSTANTIVE_GAP','SUSPECTED_GAP','SOURCE_UNAVAILABLE','MISSING_SOURCE_STATEMENT','INPUT_CONFLICT'}:
                result['status'] = 'BLOCKED'
                result['task_outcome'] = self.accepted['status']
            if self.accepted and self.accepted.get('status')=='REVIEW_BLOCKED_INCOMPLETE':
                result.update(status='BLOCKED',task_outcome='MATHEMATICAL_REVIEW_FAILED',review_coverage='INCOMPLETE')
        except proof_repair.RoundInterrupted as e:
            result.update(status='REPAIR_WAIT',task_outcome='PROOF_ROUND_RETIRED',error=str(e),stop_reason='CASE_LOCAL_REPAIR')
            try:self.interrupt_active_turn(reason='PROOF_ROUND_RETIRED')
            except Exception as error:result['execution_fault']='Proof-round retirement unconfirmed: '+str(error)
        except execution.Cancelled as e:
            result.update(status='CANCELLED',task_outcome='EXTERNAL_CANCELLED',stop_reason='EXTERNAL_CANCEL',error=str(e))
            try:self.interrupt_active_turn(reason='EXTERNAL_CANCEL')
            except Exception as error:result['interrupt_error']=str(error)
        except execution.CaseDeadlineExceeded as e:
            case_deadline=e;self.budget_exhausted=True
            result.update(status='UNFINISHED',stop_reason='CASE_DEADLINE',error=str(e))
            if self.pending_turn_start_id is not None or self.active_turn_id:
                try:
                    self.interrupt_active_turn(reason='CASE_DEADLINE')
                    result['deadline_interrupt_completed']=True
                except Exception as error:
                    result['execution_fault']='Whole-case interruption unconfirmed: '+str(error)
        except TimeoutError as e:
            result.update({'status':'UNFINISHED','stop_reason':'DEADLINE','error':str(e)})
            try:
                self.interrupt_active_turn()
                result['deadline_interrupt_completed'] = True
            except Exception as stop_error:
                result['interrupt_error'] = str(stop_error)
        except KeyboardInterrupt:
            result.update({'status':'CANCELLED','stop_reason':'EXTERNAL_CANCEL',
                           'task_outcome':'EXTERNAL_CANCELLED'})
            try:
                self.interrupt_active_turn()
            except Exception as stop_error:
                result['interrupt_error'] = str(stop_error)
        except Exception as e:
            result.update({'status':'UNFINISHED','execution_fault':type(e).__name__+': '+str(e)})
            result['traceback']=traceback.format_exc()
            if getattr(self,'tool_execution_fault',None):
                result.update(stop_reason='LOCAL_TOOL_EXECUTION_FAULT',
                              tool_execution_fault=self.tool_execution_fault)
        finally:
            if case_deadline is None and result.get('status') not in {'ACCEPTED','BLOCKED','REPAIR_REQUESTED','REPAIR_WAIT','CANCELLED'}:
                from fault_control import outcome_error
                error=outcome_error(result)
                try:self.pause_error(error,resumable=False)
                except execution.Cancelled:
                    result['paused_outcome']=dict(result)
                    result.update(status='CANCELLED',task_outcome='EXTERNAL_CANCELLED',stop_reason='EXTERNAL_CANCEL')
            if getattr(self,'local_protocol_fault',None):
                result['local_protocol_fault']=self.local_protocol_fault
            if getattr(self,'submission_completion',None):
                result['submission_completion']=self.submission_completion
                if case_deadline is None:result['stop_reason']=('REPORTED_OBSTACLE' if self.accepted and self.accepted.get('status') in
                    {'SUBSTANTIVE_GAP','SUSPECTED_GAP','SOURCE_UNAVAILABLE','MISSING_SOURCE_STATEMENT','INPUT_CONFLICT'} else
                    'LOCATED_REVIEW_BLOCKER' if self.accepted and self.accepted.get('status')=='REVIEW_BLOCKED_INCOMPLETE' else 'ACCEPTED_ARTIFACT')
            if getattr(self,'post_acceptance_closing_error',None):
                result['execution_fault']='Post-acceptance closing: '+self.post_acceptance_closing_error
            result['error_pauses']=getattr(getattr(self,'_fault_gate',None),'resumed',[])
            result.update({'wall_seconds':time.monotonic()-self.started if self.started else None,
                           'api_calls':self.api_calls,'lean_calls':self.lean_calls,
                           'continuations':self.continuation_count,'finished_at_utc':carrier.now(),
                           'remote_retry_policy':REMOTE_RETRY_POLICY,
                           'remote_retries':getattr(self,'remote_retry_count',0)})
            if self.proof_progress is not None:result['proof_progress']=self.proof_progress.metadata()
            violations = self.logs/'isolation-violations.jsonl'
            result['isolation_violation'] = violations.exists() and bool(violations.read_text().strip())
            from execution_health import inspect
            result['transport_health']=inspect(self.logs)
            result['execution_health'] = ('FAULT' if result.get('execution_fault') or
                result['isolation_violation'] else result['transport_health']['status'])
            if result['status']=='UNFINISHED' and result.get('stop_reason')=='DEADLINE':
                result['task_outcome'] = ('MODEL_BUDGET_EXHAUSTED' if result['execution_health']=='NO_RECORDED_FAULT'
                    else 'UNFINISHED_WITH_EXECUTION_FAULT' if result['execution_health']=='FAULT' else 'UNFINISHED_ATTRIBUTION_UNVERIFIED')
            from usage import summarize_stage
            result['usage'] = summarize_stage(self.logs, phase=self.mode)
            result['speed_policy'] = 'standard'
            result['instruction_arm'] = getattr(self, 'instruction_arm', 'yui')
            result['measurement_valid'] = False
            if (self.logs/'native-client.json').exists():
                try:
                    result['exposure']=__import__('native_client').audit(self.logs)
                    if result['exposure']['errors']:
                        initialization_only=(case_deadline is not None and not self.native_turn_generation
                            and set(result['exposure']['errors'])<={'no_native_work_dispatched','unbound_initial_prompt'})
                        if initialization_only:
                            if result['execution_health']!='FAULT':result['execution_health']='UNVERIFIED'
                        else:result['execution_health']='FAULT';result['execution_fault']='Native context readback failed'
                except (ValueError,KeyError,OSError) as error:
                    result['execution_health']='FAULT';result['execution_fault']='Native context readback error: '+str(error)
                result['transport']='native-codex-stdio-v1'
                result['native_turns']=self.api_calls
                result['api_calls']=None
            if result.get('task_outcome')=='MODEL_BUDGET_EXHAUSTED' and result['execution_health']=='FAULT':
                result['task_outcome']='UNFINISHED_WITH_EXECUTION_FAULT'
            result['transport']='native-codex-stdio-v1'
            result['native_turns']=self.api_calls
            result['api_calls']=None
            from execution_health import qualification
            result.update(qualification(result))
            if result.get('task_outcome')=='MODEL_BUDGET_EXHAUSTED' and not result['identity_and_input_boundary_verified']:
                result['task_outcome']='UNFINISHED_ATTRIBUTION_UNVERIFIED'
            if case_deadline is not None:
                from execution_health import budget_outcome
                result['task_outcome']=budget_outcome([result])
            from run_resources import retention
            self.workspace_retention=retention(self.work,getattr(self,'workspace_owner_logs',self.logs))
            result.update(temporary_workspace_removed=False,workspace_retention=self.workspace_retention)
            recorder=getattr(self,'execution',None)
            if recorder:
                group='nl0' if self.mode.startswith(('nl0-','audit-a')) else 'lean'
                recorder.retain_stage(self,group)
            ir.write(self.logs/'result.json',result)
            if self.accepted: ir.write(self.logs/'accepted.json',self.accepted)
            if getattr(self,'execution',None):
                self.execution.record_stage(self.execution_task,self.logs,result)
                values={'activity':'CASE_DEADLINE' if case_deadline is not None else 'STAGE_FINISHED',
                        'usage_ledger':str(self.logs/'usage.json')}
                if self.step is None:values.update(state='CANCELLED' if result['status']=='CANCELLED' else 'FINISHED',finished_at_utc=execution.now())
                if getattr(self,'role_session',None):
                    values['role_state']='WAITING_FOR_FEEDBACK' if result['status']=='ACCEPTED' else result['status']
                    if self.step is None and result['status']=='ACCEPTED':
                        values.update(state='WAITING_REVIEW',activity='ASSIGNMENT_SUBMITTED',finished_at_utc=None)
                self.execution.task(self.execution_task,**values);self.execution.flush(force=True)
            if result.get('status')=='CANCELLED':self.release_resources('USER_CANCELLED')
        if case_deadline is not None:raise case_deadline
        return result,self.accepted

