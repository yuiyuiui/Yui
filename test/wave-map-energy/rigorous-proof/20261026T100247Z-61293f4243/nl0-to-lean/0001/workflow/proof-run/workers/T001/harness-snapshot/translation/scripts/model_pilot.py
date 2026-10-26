#!/usr/bin/env python3
"""Fresh subscription-carried Yui model stages for typed Lean obligations.

Uses the existing request-normalizing relay; exposes neither owner references
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
import uuid

import ir
import strategy_bank
import scheduler
import concurrency
import execution_state as execution
from shared_lemmas import Store

sys.path.insert(0, str(ir.ROOT/'scripts'))
import run_pilot as carrier
from runtime_config import model_profile
from output_guard import (ArgumentGuard, ModelOutputLimit, ModelOutputStalled, POLICY as OUTPUT_POLICY,
                          ProviderTerminalWaitExceeded, PROVIDER_WAIT_POLICY)
from pilot_common import sha256, load_lock as runtime_lock

REMOTE_RETRY_POLICY = carrier.REMOTE_RETRY_POLICY


def load_lock():
    return runtime_lock()


carrier.load_lock = load_lock

HARNESS = 'yui-0.1.3'
BACKGROUND_NOTE_POLICY = 'local-background-on-demand-1'
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
    def __init__(self, logs, cpath, mode, timeout, plan=None, step=None, bank_enabled=False, budget=None, instruction_arm='yui'):
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
        self.argument_guard = ArgumentGuard()
        self.system = SYSTEM
        if instruction_arm not in {'yui','direct'}:
            raise ValueError('Unknown instruction arm')
        self.instruction_arm = instruction_arm
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
        self.stop_on_submission=True
        self.submission_closed=False
        self.api_calls = self.lean_calls = self.rpc_id = 0
        self.request_lock = threading.Lock()
        self.inbox = queue.Queue()
        self.started = None
        self.allowed_user_messages = set()
        self.proc = self.relay = None
        self.model_history, self.model_calls, self.tool_history = {}, {}, {}
        self.prompt_cache_key = 'nl0-ir-'+str(uuid.uuid4())
        self.continuation_count = 0
        self.turn_results = []
        self.last_turn_event = self.active_turn_id = self.pending_turn_start_id = None
        self.cancelled_requests = {}
        self.initial_user_message = None
        self.last_diagnostic = ''

    def dispatch(self, name, args):
        if name in ('search_mathlib','read_mathlib'):
            return super().dispatch(name,args)
        begin = time.monotonic()
        record=None;record_path=None
        try:
            if self.accepted:
                raise ir.Invalid('stage already accepted; no overwrite')
            if name == 'find_strategies':
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
                number=len(self.own_lean_drafts['proof'])+1
                record={'proof':value,'statement':self.plan['steps'][next(i for i,s in enumerate(self.plan['steps']) if s['id']==self.step)]['statement']}
                self.own_lean_drafts['proof'][number]=record;record_path=self.logs/'lean-drafts'/f'proof-{number:04d}.json'
                result = ir.check(self.cpath,self.plan,{self.step:value},only=self.step,timeout=self.lean_timeout())
                self.lean_calls += 1
                if result['exit_code'] == 0 and name.startswith('submit'):
                    self.accepted = {'proof':value}
            elif self.mode=='proof' and name=='check_auxiliary':
                number=len(self.own_lean_drafts['auxiliary'])+1
                record={'statement':args['statement'],'proof':args['proof']}
                self.own_lean_drafts['auxiliary'][number]=record;record_path=self.logs/'lean-drafts'/f'auxiliary-{number:04d}.json'
                result=ir.check_auxiliary(self.cpath,self.plan,self.step,args['statement'],args['proof'],
                    out=self.logs/'auxiliary-checks'/f'{number:04d}',timeout=self.lean_timeout())
                self.lean_calls+=1
                result['candidate']=number
            elif self.mode=='proof' and name=='read_lean_draft':
                kind=args['kind']
                if kind=='index':
                    result={'own_same_stage_attempts':{key:[{'candidate':n,'statement_preview':r['statement'][:300],
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
        except (ir.Invalid, KeyError, ValueError, TypeError, IndexError) as e:
            result = {'accepted':False,'error':str(e),'feedback_kind':'candidate_rejected'}
            self.last_diagnostic=str(e)[:14000]
        if record is not None:
            record['check']=dict(result);ir.write(record_path,record)
        carrier.append(self.logs/'tools.jsonl',{'tool':name,'arguments':args,'result':result,
                                               'wall_seconds':time.monotonic()-begin})
        # Keep owner oracle signatures out of compiler feedback for interface work.
        if self.mode == 'interface' and result.get('exit_code',0) != 0:
            return {'accepted':False,'status':result['status'],
                    'feedback':'Interface did not match the original premise/target ports. Re-read the supplied NL input; do not change assumptions or equality/range conventions.'}
        if 'stdout' in result:
            return {**result,'stdout':result['stdout'][:14000],'stderr':result.get('stderr','')[:2000]}
        return result

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
        self.execution=getattr(self.budget,'execution',None) or execution.current()[0]
        self.execution_task=execution.current()[1] or self.step or 'stage-'+hashlib.sha256(str(self.logs).encode()).hexdigest()[:12]
        recorder=self.execution
        if recorder:recorder.task(self.execution_task,activity='WAITING_FOR_MODEL_SLOT',log_path=str(self.logs),stage=self.mode,
            role='proof' if self.mode=='proof' else 'preparation_review',model=self.model,
            model_selection=self.model_selection)
        queued = time.monotonic()
        limiter = self.budget or STAGE_LIMITER
        try:
            with execution.activate(recorder,self.execution_task):
                if recorder:recorder.check(self.execution_task)
                if limiter is None:
                    if recorder:self.timeout=recorder.remaining(self.timeout)
                    return self._execute()
                with limiter:
                    self.queue_seconds = time.monotonic()-queued
                    if recorder:self.timeout=recorder.remaining(self.timeout)
                    return self._execute()
        except execution.CaseDeadlineExceeded as error:
            result={'status':'UNFINISHED','task_outcome':'MODEL_BUDGET_EXHAUSTED','stop_reason':'CASE_DEADLINE',
                'error':str(error),'api_calls':0,'measurement_valid':False,'execution_health':'NO_RECORDED_FAULT',
                'scope':'No new model session started after the shared case budget expired.'}
            shutil.rmtree(self.work)
            ir.write(self.logs/'result.json',result)
            if recorder:recorder.task(self.execution_task,state='FINISHED',stage_result=result,finished_at_utc=execution.now())
            return result,None
        except execution.Cancelled as error:
            result={'status':'CANCELLED','task_outcome':'EXTERNAL_CANCELLED','stop_reason':'EXTERNAL_CANCEL',
                'error':str(error),'api_calls':0,'measurement_valid':False,'execution_health':'NO_RECORDED_FAULT'}
            shutil.rmtree(self.work)
            ir.write(self.logs/'result.json',result)
            if recorder:recorder.task(self.execution_task,state='CANCELLED',finished_at_utc=execution.now())
            return result,None

    def _execute(self):
        user = self.prompt()
        if not (self.logs/'execution-manifest.json').exists():
            files = []
            for path in [*ir.ROOT.glob('scripts/*.py'), *ir.HERE.glob('scripts/*.py'),
                         ir.ROOT/'toolchain/lock.json', ir.ROOT/'config.json']:
                target = self.logs/'harness-snapshot'/path.relative_to(ir.ROOT)
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(path,target)
                files.append({'path':str(path.relative_to(ir.ROOT)),'sha256':sha256(target)})
            ir.write(self.logs/'execution-manifest.json',{'model':self.model,'model_selection':self.model_selection,'effort':self.model_selection['reasoning_effort'],'speed':self.model_selection['speed'],
                'arm':self.instruction_arm,'phase':self.mode,'runtime_files':files,
                'background_note_policy':self.background_note_policy,
                'model_output_policy':OUTPUT_POLICY,
                'provider_wait_policy':PROVIDER_WAIT_POLICY,
                'remote_retry_policy':REMOTE_RETRY_POLICY,
                'resolved_environment':load_lock(),'scope':'Only the declared frozen obligation is model-visible.'})
        (self.logs/'prompt.txt').write_text(user+'\n')
        (self.logs/'system.txt').write_text(self.system+'\n')
        ir.write(self.logs/'tools.json',self.tools)
        result = {'mode':self.mode,'step':self.step,'model':self.model,'model_selection':self.model_selection,'effort':self.model_selection['reasoning_effort'],
                  'background_note_policy':self.background_note_policy,
                  'output_verbosity':getattr(self,'output_verbosity','low'),
                  'harness':self.harness_version,'time_budget_seconds':self.timeout,
                  'queue_seconds':getattr(self, 'queue_seconds', 0),
                  'model_output_policy':OUTPUT_POLICY,
                  'provider_wait_policy':PROVIDER_WAIT_POLICY,
                  'owner_reference_visible_to_worker':False,'started_at_utc':carrier.now()}
        result['acceptance_scope'] = (('NL0_STRUCTURE_ONLY' if self.artifact_kind=='nl0' else 'JSON_ARTIFACT_ONLY')
            if hasattr(self,'artifact_kind') else 'LEAN_LOCAL_OBLIGATION_OR_TYPED_INTERFACE')
        try:
            self.start_process()
            inventory = self.rpc('skills/list',{'cwds':[str(self.work/'input')],'forceReload':True})
            ir.write(self.logs/'skills-inventory.json',inventory)
            thread = self.rpc('thread/start',{'model':self.model,'modelProvider':'pilot-relay',
                'allowProviderModelFallback':False,'ephemeral':True,'cwd':str(self.work/'input'),
                'approvalPolicy':'never','sandbox':'read-only','baseInstructions':self.system,
                'developerInstructions':'','dynamicTools':self.tools,'environments':[],
                'experimentalRawEvents':True})
            self.thread_id = thread['thread']['id']
            if getattr(self,'execution',None):
                self.execution.task(self.execution_task,state='RUNNING',activity='MODEL_RUNNING',
                    model_started_at_utc=execution.now(),model_thread_id=self.thread_id)
            self.solve_turns(user)
            result['status'] = 'ACCEPTED' if self.accepted else 'NO_ACCEPTED_ARTIFACT'
            if self.accepted and self.accepted.get('status') in {'SUBSTANTIVE_GAP','SUSPECTED_GAP','SOURCE_UNAVAILABLE','INPUT_CONFLICT'}:
                result['status'] = 'BLOCKED'
                result['task_outcome'] = self.accepted['status']
            if self.accepted and self.accepted.get('status')=='REVIEW_BLOCKED_INCOMPLETE':
                result.update(status='BLOCKED',task_outcome='MATHEMATICAL_REVIEW_FAILED',review_coverage='INCOMPLETE')
        except execution.Cancelled as e:
            result.update(status='CANCELLED',task_outcome='EXTERNAL_CANCELLED',stop_reason='EXTERNAL_CANCEL',error=str(e))
            try:self.interrupt_active_turn(reason='EXTERNAL_CANCEL')
            except Exception as error:result['interrupt_error']=str(error)
        except ProviderTerminalWaitExceeded as e:
            result.update(status='UNFINISHED',task_outcome='PROVIDER_TERMINAL_WAIT_EXCEEDED',
                stop_reason='PROTOCOL_WAIT_GUARD',attribution='UNVERIFIED',error=str(e),
                provider_wait_evidence=e.evidence)
            try:
                self.interrupt_active_turn(reason='PROVIDER_TERMINAL_WAIT_EXCEEDED')
                result['protocol_wait_stop_confirmed']=True
            except Exception as error:
                result['execution_fault']='Protocol-wait stop could not be confirmed: '+str(error)
        except (ModelOutputStalled, ModelOutputLimit) as e:
            outcome = 'MODEL_OUTPUT_STALLED' if isinstance(e, ModelOutputStalled) else 'MODEL_OUTPUT_LIMIT'
            result.update(status='UNFINISHED', task_outcome=outcome,
                          stop_reason='OUTPUT_SERIALIZATION_GUARD' if isinstance(e, ModelOutputStalled) else 'OUTPUT_TOKEN_LIMIT',
                          error=str(e), model_output_evidence=e.evidence)
            try:
                self.interrupt_active_turn(reason=outcome)
                result['model_output_stop_confirmed'] = True
            except Exception as error:
                result['execution_fault'] = 'Model-output stop could not be confirmed: '+str(error)
        except TimeoutError as e:
            result.update({'status':'UNFINISHED','stop_reason':'DEADLINE','error':str(e)})
            try:
                self.interrupt_active_turn()
                result['deadline_interrupt_completed'] = True
            except Exception as stop_error:
                result['interrupt_error'] = str(stop_error)
        except KeyboardInterrupt:
            result.update({'status':'UNFINISHED','stop_reason':'EXTERNAL_EARLY_STOP',
                           'task_outcome':'UNFINISHED_EXTERNAL_STOP'})
            try:
                self.interrupt_active_turn()
            except Exception as stop_error:
                result['interrupt_error'] = str(stop_error)
        except Exception as e:
            result.update({'status':'UNFINISHED','execution_fault':type(e).__name__+': '+str(e)})
        finally:
            if getattr(self,'local_protocol_fault',None):
                result['local_protocol_fault']=self.local_protocol_fault
            if getattr(self,'submission_completion',None):
                result['submission_completion']=self.submission_completion
                result['stop_reason']=('REPORTED_OBSTACLE' if self.accepted and self.accepted.get('status') in
                    {'SUBSTANTIVE_GAP','SUSPECTED_GAP','SOURCE_UNAVAILABLE','INPUT_CONFLICT'} else
                    'LOCATED_REVIEW_BLOCKER' if self.accepted and self.accepted.get('status')=='REVIEW_BLOCKED_INCOMPLETE' else 'ACCEPTED_ARTIFACT')
            if getattr(self,'post_acceptance_closing_error',None):
                result['execution_fault']='Post-acceptance closing: '+self.post_acceptance_closing_error
            result.update({'wall_seconds':time.monotonic()-self.started if self.started else None,
                           'api_calls':self.api_calls,'lean_calls':self.lean_calls,
                           'continuations':self.continuation_count,'finished_at_utc':carrier.now(),
                           'remote_retry_policy':REMOTE_RETRY_POLICY,
                           'remote_retries':getattr(self,'remote_retry_count',0)})
            if self.proc:
                if getattr(self,'execution',None):
                    if not self.execution.stop_process(self.proc):result['execution_fault']='Model process cleanup unconfirmed'
                else:
                    self.proc.terminate()
                    try: self.proc.wait(timeout=5)
                    except Exception: self.proc.kill();self.proc.wait()
                reader=getattr(self,'reader_thread',None)
                if reader:reader.join(timeout=1)
                for stream in (self.proc.stdin,self.proc.stdout):
                    if stream:stream.close()
            if self.relay:
                self.relay.shutdown()
                try:self.drain_relay_streams()
                except RuntimeError as error:result['execution_fault']='Response finalization: '+str(error)
                self.relay.server_close()
            for name in ('auth.json','models_cache.json'):
                (self.work/'state'/name).unlink(missing_ok=True)
            violations = self.logs/'isolation-violations.jsonl'
            faults = self.logs/'relay-errors.jsonl'
            result['isolation_violation'] = violations.exists() and bool(violations.read_text().strip())
            result['relay_fault'] = faults.exists() and bool(faults.read_text().strip())
            from execution_health import inspect
            result['transport_health']=inspect(self.logs)
            result['execution_health'] = ('FAULT' if result.get('execution_fault') or result['relay_fault'] or
                result['isolation_violation'] else result['transport_health']['status'])
            if result['status']=='UNFINISHED' and result.get('stop_reason')=='DEADLINE':
                result['task_outcome'] = ('MODEL_BUDGET_EXHAUSTED' if result['execution_health']=='NO_RECORDED_FAULT'
                    else 'UNFINISHED_WITH_EXECUTION_FAULT' if result['execution_health']=='FAULT' else 'UNFINISHED_ATTRIBUTION_UNVERIFIED')
            from usage import summarize_stage
            result['usage'] = summarize_stage(self.logs, phase=self.mode)
            result['speed_policy'] = 'standard'
            result['instruction_arm'] = getattr(self, 'instruction_arm', 'yui')
            result['measurement_valid'] = False
            if (self.logs/'requests.jsonl').exists():
                from exposure import audit_stage
                try:
                    result['exposure'] = audit_stage(self.logs)
                    result['measurement_valid'] = (result['exposure']['status']=='TRANSMITTED-EXPOSURE-CHECK-PASSED'
                        and result['exposure']['actual_model_ids']==[self.model]
                        and result['exposure']['standard_tier_verified'] and result['usage']['complete']
                        and result['execution_health']=='NO_RECORDED_FAULT')
                    if result['exposure']['errors']:
                        result['execution_health']='FAULT'
                        result['execution_fault']='Transmitted exposure readback failed'
                except (ValueError,KeyError,OSError) as error:
                    result['execution_health']='FAULT'
                    result['execution_fault']='Exposure readback error: '+str(error)
            if result.get('task_outcome')=='MODEL_BUDGET_EXHAUSTED' and result['execution_health']=='FAULT':
                result['task_outcome']='UNFINISHED_WITH_EXECUTION_FAULT'
            from execution_health import qualification
            result.update(qualification(result))
            if result.get('task_outcome')=='MODEL_BUDGET_EXHAUSTED' and not result['identity_and_input_boundary_verified']:
                result['task_outcome']='UNFINISHED_ATTRIBUTION_UNVERIFIED'
            try:
                shutil.rmtree(self.work)
                result['temporary_workspace_removed']=True
            except OSError as cleanup_error:
                result['temporary_workspace_removed']=False
                result['cleanup_error']=str(cleanup_error)
            ir.write(self.logs/'result.json',result)
            if self.accepted: ir.write(self.logs/'accepted.json',self.accepted)
            if getattr(self,'execution',None):
                values={'activity':'STAGE_FINISHED','stage_result':{k:result.get(k) for k in
                    ['status','task_outcome','execution_health','acceptance_scope']},'usage_ledger':str(self.logs/'usage.json')}
                if self.step is None:values.update(state='CANCELLED' if result['status']=='CANCELLED' else 'FINISHED',finished_at_utc=execution.now())
                self.execution.task(self.execution_task,**values);self.execution.flush(force=True)
        return result,self.accepted

