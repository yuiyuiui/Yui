#!/usr/bin/env python3
"""Bounded independent conditional proof jobs and exact shared-job deduplication."""
from __future__ import annotations

import concurrent.futures
import time

import ir
import shared_lemmas


def prove_graph(cpath, plan, worker, *, max_workers=2, store=None, out=None):
    """worker(sid, packet) -> {proof: tactic body, ...disclosed metadata}.

    All proof ports must already be frozen. Dependency edges are discharged
    during assembly, not replaced by axiom stubs during worker execution.
    """
    start = time.monotonic()
    ir.need(max_workers >= 1, 'worker bound must be positive')
    _, nodes, order = ir.validate(cpath, plan)
    typecheck = ir.check(cpath, plan, types_only=True)
    ir.need(typecheck['exit_code'] == 0, 'frozen interface/representation expressions failed Lean')
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

    def run(group):
        sid = group[0]
        packet = ir.local_packet(cpath, plan, sid)
        job_start = time.monotonic()
        job = {'step': sid, 'consumers': group, 'started_offset_seconds': job_start-start,
               'status': 'RUNNING', 'model_worker_called': False}
        if out:
            ir.write(out/'jobs'/f'{sid}.json', job)
        entry = None
        if sid in requests:
            entry, job['lookup'] = store.lookup(requests[sid])
        try:
            if entry:
                proof = shared_lemmas.reuse_body(entry, requests[sid])
                job['source'] = 'VERIFIED_SOURCE_CACHE'
            else:
                job['model_worker_called'] = True
                result = worker(sid, packet)
                job['worker'] = {k: v for k, v in result.items() if k != 'proof'}
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
            job['status'] = 'LOCAL_UNFINISHED'
            job['error'] = type(error).__name__ + ': ' + str(error)
            return {}, job
        finally:
            job['wall_seconds'] = time.monotonic()-job_start
            job['finished_offset_seconds'] = time.monotonic()-start
            if out:
                ir.write(out/'jobs'/f'{sid}.json', job)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(run, group) for group in groups.values()]
        for future in concurrent.futures.as_completed(futures):
            result, job = future.result()
            proofs.update(result)
            jobs.append(job)
            if out:
                ir.write(out/'progress.json', {'jobs': jobs, 'completed': sorted(proofs)})
    ir.need(ir.digest(cpath) == initial_contract and shared_lemmas.hashed(plan) == initial_plan,
            'interface changed while workers were running')
    complete = set(proofs) == set(nodes)
    assembly = ir.check(cpath, plan, proofs, out=out/'assembly' if out else None) if complete else None
    fresh = ir.check(cpath, plan, proofs, out=out/'fresh-verifier' if out else None) if complete else None
    accepted = complete and assembly['exit_code'] == fresh['exit_code'] == 0
    report = {'status': 'FRAGMENT_ASSEMBLED' if accepted else 'GRAPH_UNFINISHED',
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
    return report
