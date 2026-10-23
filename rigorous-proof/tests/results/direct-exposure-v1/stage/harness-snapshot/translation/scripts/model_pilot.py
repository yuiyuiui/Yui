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
from shared_lemmas import Store

sys.path.insert(0, str(ir.ROOT/'scripts'))
import run_pilot as carrier
from pilot_common import sha256, load_lock as runtime_lock


def load_lock():
    return runtime_lock()


carrier.load_lock = load_lock

HARNESS = 'yui-0.1.0'
STAGE_LIMITER = None
carrier.CONTINUE_PROMPT = ('The requested artifact has not passed submission and time remains. '
                          'Continue with the same inputs and tools; preserve the fixed specification.')
SYSTEM = ('You translate the supplied natural-language proof faithfully into Lean 4. '
          'Use only the explicit task inputs and pinned mathlib through the available tools. '
          'Preserve all assumptions, conclusions, equality modes and the supplied proof route. '
          'No reference answers, personal context, other tasks, shell or external services are available. '
          'Use the submit tool when the requested artifact is complete; if rejected, repair it. '
          'A strategy is advice, never an additional theorem or assumption.')


def json_tool(name, description, field):
    return carrier.tool(name, description, {field:{'type':'string'}}, [field])


class Stage(carrier.Trial):
    def __init__(self, logs, cpath, mode, timeout, plan=None, step=None, bank_enabled=False, budget=None, instruction_arm='yui'):
        self.logs = Path(logs)
        self.logs.mkdir(parents=True, exist_ok=False)
        self.work = Path(tempfile.mkdtemp(prefix='nl0-ir-model-')).resolve()
        for n in ('input','output','tmp','home','state'):
            (self.work/n).mkdir(mode=0o700)
        self.cpath = Path(cpath)
        self.mode, self.plan, self.step = mode, plan, step
        self.budget = budget
        self.timeout = timeout
        self.harness_version = HARNESS
        self.strict = True
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
        if bank_enabled:
            self.tools += [json_tool('find_strategies','Query the indexed bank using a JSON diagnostic. Fields: family, tags, facts, lean_version. Advice is not a premise.','query_json')]
        self.tool_names = {t['name'] for t in self.tools}
        self.accepted = None
        self.api_calls = self.lean_calls = self.rpc_id = 0
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
                result = ir.check(self.cpath,self.plan,{self.step:value},only=self.step,timeout=self.lean_timeout())
                self.lean_calls += 1
                if result['exit_code'] == 0 and name.startswith('submit'):
                    self.accepted = {'proof':value}
            else:
                raise PermissionError('tool not allowed for this stage')
            if 'exit_code' in result:
                result['accepted'] = result['exit_code']==0
                result['stage_complete'] = bool(self.accepted)
                self.last_diagnostic = result.get('stdout','')[:14000] if result['exit_code'] else ''
        except (ir.Invalid, KeyError, ValueError, TypeError) as e:
            result = {'accepted':False,'error':str(e),'feedback_kind':'candidate_rejected'}
        carrier.append(self.logs/'tools.jsonl',{'tool':name,'arguments':args,'result':result,
                                               'wall_seconds':time.monotonic()-begin})
        # Keep owner oracle signatures out of compiler feedback for interface work.
        if self.mode == 'interface' and result.get('exit_code',0) != 0:
            return {'accepted':False,'status':result['status'],
                    'feedback':'Interface did not match the original premise/target ports. Re-read the supplied NL input; do not change assumptions or equality/range conventions.'}
        if 'stdout' in result:
            return {**result,'stdout':result['stdout'][:14000],'stderr':result.get('stderr','')[:2000]}
        return result

    def prompt(self):
        c = ir.contract(self.cpath)
        if self.mode == 'interface':
            return json.dumps({'task':'Translate this NL fragment into typed Lean parameter, premise and output interfaces, without writing a proof. Preserve listed names and IDs/order.',
                'header':c['header'],'source':ir.load(self.cpath.parent/c['source']['path'])['mathematical_input'],
                'parameters':[p['name'] for p in c['parameters']],
                'premises':[{'id':p['id'],'statement':p['statement']} for p in c['premises']],
                'conclusion':c['conclusion']['statement'],'representation':c['representation'],
                'output_schema':{'parameters':[{'name':'supplied name','type':'Lean type'}],
                    'premises':[{'id':'supplied ID','type':'Lean Prop'}],
                    'conclusion_type':'Lean Prop','representation_notes':'explain choices'}},ensure_ascii=False)
        if self.mode == 'plan':
            public = {k:c[k] for k in ('header','parameters','premises','conclusion','representation','source_steps')}
            if c['version'] == 2:
                public.update({k:c.get(k, []) for k in ('objects','shared_obligations')})
            return json.dumps({'task':'Construct a small typed transition plan following every supplied NL paragraph. Do not write proof bodies. Prefer a small number of useful closed obligations; each has only listed direct inputs. All retained steps must reach terminal.',
                'contract':public,'contract_sha256':ir.digest(self.cpath),
                'output_schema':{'version':c['version'],'contract_sha256':ir.digest(self.cpath),'representation_notes':'describe the actual ranges, equality modes and representation bridges',
                    'steps':[{'id':'T001','statement':'complete Lean Prop','inputs':['H001'],
                              'source_steps':['S001'],'explanation':'mathematical mechanism'}],'terminal':'last T ID'},
                'constraint':'Terminal statement must be exactly the supplied conclusion type; local premise proof names are h_H001 or h_T001. Cover all source paragraphs. In version 2, mark a step with shared_lemma only when it exactly matches a frozen shared_obligations entry. Never create or approve a new export.'},ensure_ascii=False)
        return json.dumps({'task':'Prove exactly this local conditional obligation using the supplied NL route. Return only the tactic body through submit_transition. All displayed parameter and input proof binders are already in context.',
                           'packet':ir.local_packet(self.cpath,self.plan,self.step)},ensure_ascii=False)

    def execute(self):
        queued = time.monotonic()
        limiter = self.budget or STAGE_LIMITER
        if limiter is None:
            return self._execute()
        with limiter:
            self.queue_seconds = time.monotonic()-queued
            return self._execute()

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
            ir.write(self.logs/'execution-manifest.json',{'model':carrier.MODEL,'effort':'high','speed':'standard',
                'arm':self.instruction_arm,'phase':self.mode,'runtime_files':files,
                'resolved_environment':load_lock(),'scope':'Only the declared frozen obligation is model-visible.'})
        (self.logs/'prompt.txt').write_text(user+'\n')
        (self.logs/'system.txt').write_text(self.system+'\n')
        ir.write(self.logs/'tools.json',self.tools)
        result = {'mode':self.mode,'step':self.step,'model':carrier.MODEL,'effort':'high',
                  'harness':self.harness_version,'time_budget_seconds':self.timeout,
                  'queue_seconds':getattr(self, 'queue_seconds', 0),
                  'owner_reference_visible_to_worker':False,'started_at_utc':carrier.now()}
        result['acceptance_scope'] = (('NL0_STRUCTURE_ONLY' if self.artifact_kind=='nl0' else 'JSON_ARTIFACT_ONLY')
            if hasattr(self,'artifact_kind') else 'LEAN_LOCAL_OBLIGATION_OR_TYPED_INTERFACE')
        try:
            self.start_process()
            inventory = self.rpc('skills/list',{'cwds':[str(self.work/'input')],'forceReload':True})
            ir.write(self.logs/'skills-inventory.json',inventory)
            thread = self.rpc('thread/start',{'model':carrier.MODEL,'modelProvider':'pilot-relay',
                'allowProviderModelFallback':False,'ephemeral':True,'cwd':str(self.work/'input'),
                'approvalPolicy':'never','sandbox':'read-only','baseInstructions':self.system,
                'developerInstructions':'','dynamicTools':self.tools,'environments':[],
                'experimentalRawEvents':True})
            self.thread_id = thread['thread']['id']
            self.solve_turns(user)
            result['status'] = 'ACCEPTED' if self.accepted else 'NO_ACCEPTED_ARTIFACT'
            if self.accepted and self.accepted.get('status') in {'SUBSTANTIVE_GAP','SUSPECTED_GAP','SOURCE_UNAVAILABLE','INPUT_CONFLICT'}:
                result['status'] = 'BLOCKED'
                result['task_outcome'] = self.accepted['status']
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
            result.update({'wall_seconds':time.monotonic()-self.started if self.started else None,
                           'api_calls':self.api_calls,'lean_calls':self.lean_calls,
                           'continuations':self.continuation_count,'finished_at_utc':carrier.now()})
            if self.proc:
                self.proc.terminate()
                try: self.proc.wait(timeout=5)
                except Exception: self.proc.kill();self.proc.wait()
            if self.relay: self.relay.shutdown()
            for name in ('auth.json','models_cache.json'):
                (self.work/'state'/name).unlink(missing_ok=True)
            violations = self.logs/'isolation-violations.jsonl'
            faults = self.logs/'relay-errors.jsonl'
            result['isolation_violation'] = violations.exists() and bool(violations.read_text().strip())
            result['relay_fault'] = faults.exists() and bool(faults.read_text().strip())
            result['execution_health'] = ('FAULT' if result.get('execution_fault') or result['relay_fault'] or
                result['isolation_violation'] else 'NO_RECORDED_FAULT')
            if result['status']=='UNFINISHED' and result.get('stop_reason')=='DEADLINE':
                result['task_outcome'] = 'MODEL_BUDGET_EXHAUSTED' if result['execution_health']=='NO_RECORDED_FAULT' else 'UNFINISHED_WITH_EXECUTION_FAULT'
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
                        and result['exposure']['actual_model_ids']==[carrier.MODEL]
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
            try:
                shutil.rmtree(self.work)
                result['temporary_workspace_removed']=True
            except OSError as cleanup_error:
                result['temporary_workspace_removed']=False
                result['cleanup_error']=str(cleanup_error)
            ir.write(self.logs/'result.json',result)
            if self.accepted: ir.write(self.logs/'accepted.json',self.accepted)
        return result,self.accepted

