#!/usr/bin/env python3
"""Bounded independent conditional proof jobs and exact shared-job deduplication."""
from __future__ import annotations

import concurrent.futures
import time
import threading

import execution_state

import ir
import shared_lemmas
import proof_repair
import proof_round_policy as proof_rounds


def prove_graph(cpath, plan, worker, *, max_workers=None, store=None, out=None, execution=None):
    """worker(sid, packet) -> {proof: tactic body, ...disclosed metadata}.

    All proof ports must already be frozen. Dependency edges are discharged
    during assembly, not replaced by axiom stubs during worker execution.
    """
    start = time.monotonic()
    slots = {}; slot_lock = threading.Lock()
    _, nodes, order = ir.validate(cpath, plan)
    max_workers = len(nodes) if max_workers is None else max_workers
    ir.need(type(max_workers) is int and max_workers >= 1, 'worker bound must be positive')
    typecheck = ir.check(cpath, plan, types_only=True)
    ir.need(typecheck['exit_code'] == 0, 'frozen interface/representation expressions failed Lean: '
            + ', '.join(typecheck.get('failed_input_uses',[])))
    initial_contract = ir.digest(cpath)
    initial_plan = shared_lemmas.hashed(plan)
    initial_store = store.snapshot() if store else None
    groups = {}
    requests = {}
    for sid in order:
        if store is not None and 'shared_lemma' in nodes[sid]:
            value = shared_lemmas.obligation(cpath, plan, sid)
            requests[sid] = value
            key = 'shared:' + shared_lemmas.signature_key(value)
        else:
            key = 'node:' + sid
        groups.setdefault(key, []).append(sid)
    proofs, jobs = {}, []
    if out:
        ir.write(out/'schedule.json', {'max_workers': max_workers, 'contract_sha256': initial_contract,
                 'jobs': [{'key': key, 'steps': group, 'status': 'PENDING'} for key, group in groups.items()]})

    if execution:
        for group in groups.values():
            sid=group[0]
            attempt=execution.state['run_id']+':'+shared_lemmas.hashed(str(out.resolve()) if out else str(time.monotonic()))[:12]+':'+sid
            execution.task(sid,state='PENDING',activity='QUEUED',queued_at_utc=execution_state.now(),
                attempt_id=attempt,claimed_at_utc=None,worker_id=None,finished_at_utc=None,
                role='proof',consumers=group,inputs=nodes[sid]['inputs'],
                contract_sha256=initial_contract,plan_digest=initial_plan,
                result_path=str(out/'jobs'/f'{sid}.json') if out else None)
        execution.update(proof_total=len(nodes),proof_group_sizes={g[0]:len(g) for g in groups.values()})
        execution.flush(force=True)

    def run(group):
        with execution_state.activate(execution,group[0]):
            return execute(group)

    def execute(group):
        sid = group[0]
        packet = ir.local_packet(cpath, plan, sid)
        job_start = time.monotonic()
        job = {'step': sid, 'consumers': group, 'started_offset_seconds': job_start-start,
               'status': 'RUNNING', 'model_worker_called': False}
        if out:
            ir.write(out/'jobs'/f'{sid}.json', job)
        with slot_lock:
            slot=slots.setdefault(threading.get_ident(),'W'+str(len(slots)+1).zfill(2))
        job['worker_id']=slot
        if execution:
            execution.task(sid,state='RUNNING',activity='CLAIMED',worker_id=slot,
                claimed_at_utc=execution_state.now(),packet_sha256=shared_lemmas.hashed(packet),
                queue_seconds=job_start-start)
        entry = None
        try:
            if execution:execution.check(sid)
            if sid in requests:
                entry, job['lookup'] = store.lookup(requests[sid])
            if entry:
                proof = shared_lemmas.reuse_body(entry, requests[sid])
                job['source'] = 'VERIFIED_SOURCE_CACHE'
            else:
                job['model_worker_called'] = True
                result = worker(sid, packet)
                job['model_worker_called']=result.get('model_worker_called',True)
                job['worker'] = {k: v for k, v in result.items() if k != 'proof'}
                if execution:execution.check(sid)
                request=result.get('stage',{}).get('repair_request')
                if request:
                    ir.need(request.get('step')==sid and request.get('acceptance') is False,
                            'Malformed proof repair request')
                    job['status']='REPAIR_REQUESTED';job['repair_request']=request
                    return {},job
                if result.get('stage',{}).get('status')=='REPAIR_WAIT':
                    raise proof_repair.RoundInterrupted('Worker retired for case-local serial repair')
                proof = result.get('proof')
                ir.need(proof is not None, 'worker returned no accepted proof')
                job['source'] = 'WORKER'
            checked = ir.check(cpath, plan, {sid: proof}, only=sid)
            job['verification'] = checked
            ir.need(checked['exit_code'] == 0, 'local proof rejected')
            if sid in requests and entry is None:
                if job['lookup']['reason'] == 'INVALIDATED_ARTIFACT':
                    job['admission'] = {'status': 'SKIPPED_INVALIDATED_ARTIFACT_PRESERVED'}
                else:
                    job['admission'] = store.admit(cpath, plan, sid, proof, checked)
                # Also permits safe local fanout after an invalid cache miss.
                entry = {'obligation': requests[sid], 'proof': proof}
            produced = {sid: proof}
            for alias in group[1:]:
                adapted = shared_lemmas.reuse_body(entry, requests[alias])
                alias_check = ir.check(cpath, plan, {alias: adapted}, only=alias)
                ir.need(alias_check['exit_code'] == 0, 'shared alias failed Lean instantiation')
                produced[alias] = adapted
                job.setdefault('alias_verification', {})[alias] = alias_check
            job['status'] = 'LOCAL_PROOFS_CHECKED'
            return produced, job
        except Exception as error:
            job['status'] = ('CANCELLED' if isinstance(error,execution_state.Cancelled) else
                             'REPAIR_WAIT' if isinstance(error,proof_repair.RoundInterrupted) else 'LOCAL_UNFINISHED')
            job['error'] = type(error).__name__ + ': ' + str(error)
            return {}, job
        finally:
            job['wall_seconds'] = time.monotonic()-job_start
            job['finished_offset_seconds'] = time.monotonic()-start
            if execution:
                execution.task(sid,state='LOCAL_CHECKED' if job['status']=='LOCAL_PROOFS_CHECKED' else 'CANCELLED' if job['status']=='CANCELLED' else 'REPAIR_WAIT' if job['status'] in {'REPAIR_WAIT','REPAIR_REQUESTED'} else 'UNFINISHED',
                    activity='FINISHED',finished_at_utc=execution_state.now(),outcome=job.get('error'),wall_seconds=job['wall_seconds'])
            if out:
                ir.write(out/'jobs'/f'{sid}.json', job)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        # Case-local profile/recording context must survive the thread boundary.
        from contextvars import copy_context
        pending = {pool.submit(copy_context().run, run, group):group for group in groups.values()}
        while pending:
            if execution and execution.cancelled():
                for future in pending:future.cancel()
            done,_ = concurrent.futures.wait(pending,timeout=.1,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                group=pending.pop(future)
                if future.cancelled():
                    state='CANCELLED' if execution and execution.cancelled() else 'REPAIR_WAIT'
                    result={};job={'step':group[0],'consumers':group,'status':state,'model_worker_called':False}
                    if execution:execution.task(group[0],state=state,activity='NOT_STARTED',finished_at_utc=execution_state.now())
                    if out:ir.write(out/'jobs'/f'{group[0]}.json',job)
                else:result,job=future.result()
                proofs.update(result);jobs.append(job)
                if out:ir.write(out/'progress.json', {'jobs': jobs, 'completed': sorted(proofs)})
    ir.need(ir.digest(cpath) == initial_contract and shared_lemmas.hashed(plan) == initial_plan,
            'interface changed while workers were running')
    complete = set(proofs) == set(nodes)
    if execution and execution.cancelled():complete=False
    case_deadline=None
    if execution and not execution.cancelled():
        try:execution.remaining()
        except execution_state.CaseDeadlineExceeded as error:
            case_deadline=error;complete=False
    requests={j['step']:j['repair_request'] for j in jobs if j.get('repair_request')}
    if requests:complete=False
    if execution:execution.update(phase='assembly' if complete else 'proof-diagnosis' if requests else 'proof-unfinished')
    assembly = ir.check(cpath, plan, proofs, out=out/'assembly' if out else None) if complete else None
    fresh = ir.check(cpath, plan, proofs, out=out/'fresh-verifier' if out else None) if complete else None
    accepted = complete and assembly['exit_code'] == fresh['exit_code'] == 0
    report = {'status': proof_rounds.state_for(complete=complete, accepted=accepted, repair_requested=bool(requests)),
              'repair_requests':requests,
              'contract_sha256': initial_contract, 'plan_digest': initial_plan,
              'max_workers': max_workers, 'mathematical_nodes': len(nodes),
              'unique_jobs': len(groups), 'deduplicated_jobs': len(nodes)-len(groups),
              'worker_calls': sum(j['model_worker_called'] for j in jobs),
              'interface_typecheck': typecheck,
              'cache_hits': sum(j.get('lookup', {}).get('status') == 'HIT' for j in jobs),
              'wall_seconds': time.monotonic()-start, 'jobs': jobs,
              'initial_shared_input': initial_store, 'assembly': assembly, 'fresh_verifier': fresh,
              'proofs': proofs, 'full_audit_b': False, 'speedup_established': False}
    if out:
        ir.write(out/'scheduler-report.json', report)
        ir.write(out/'proofs.json', {'contract_sha256': initial_contract,
                                   'plan_digest': initial_plan, 'proofs': proofs})
    if case_deadline is not None:raise case_deadline
    return report
