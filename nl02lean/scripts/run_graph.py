#!/usr/bin/env python3
"""Run an arbitrary frozen contract/plan with isolated subscription proof workers."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import time
import contextlib

import ir
import model_pilot as pilot
import scheduler
import concurrency
import execution_state
import proof_repair
from shared_lemmas import Store


def package(cpath, ppath, out):
    c = ir.contract(cpath)
    plan = ir.load(ppath)
    ir.validate(cpath, plan)
    relative = Path(c['source']['path'])
    ir.need(not relative.is_absolute() and '..' not in relative.parts,
            'stage the source under the contract directory before packaging')
    inputs = out/'inputs'
    inputs.mkdir(parents=True, exist_ok=False)
    destination = inputs/relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    ir.need(relative not in {Path('contract.json'), Path('plan.json')}, 'source filename collides with interface artifact')
    shutil.copyfile(cpath.parent/relative, destination)
    shutil.copyfile(cpath, inputs/'contract.json')
    shutil.copyfile(ppath, inputs/'plan.json')
    return inputs/'contract.json', ir.load(inputs/'plan.json')


def run(cpath, ppath, out, *, shared_store=None, max_concurrency='auto', timeout_seconds=None, bank=False, budget=None, arm='yui', prior_run=None, repair_guidance=None, reviewed_interface=None,sessions=None,diagnostic_interface=None):
    timeout_seconds = __import__('runtime_config').time_limit(timeout_seconds)
    ir.need(arm in {'yui','direct'}, 'unknown instruction arm')
    ir.need(arm != 'direct' or (not bank and shared_store is None), 'direct arm cannot use Yui strategy or proof stores')
    budget = budget or concurrency.Budget(concurrency.resolve(max_concurrency), role='proof')
    ir.need(budget.role != 'preparation_review', 'Proof execution requires its own proof budget')
    budget.role = 'proof'
    _, nodes, _ = ir.validate(Path(cpath).resolve(), ir.load(Path(ppath).resolve()))
    configuration = budget.configure(len(nodes))
    print(__import__('json').dumps({'model_concurrency': configuration}, ensure_ascii=False), flush=True)
    lock = pilot.load_lock()
    for path, expected in [(Path(lock['codex']['binary_path']),lock['codex']['sha256']),
                           (Path(lock['lean']['local_path'])/'bin/lean',lock['lean']['binary_sha256']),
                           (Path(lock['tools']['ripgrep']['binary_path']),lock['tools']['ripgrep']['sha256'])]:
        ir.need(ir.digest(path) == expected,'pinned binary changed: '+str(path))
    out = Path(out).resolve()
    out.mkdir(parents=True,exist_ok=False)
    started = time.monotonic()
    cpath, plan = package(Path(cpath).resolve(),Path(ppath).resolve(),out)
    recorder=getattr(budget,'execution',None)
    owns_recorder=recorder is None
    if owns_recorder:
        recorder=execution_state.Recorder(out,ir.contract(cpath)['id'],configuration)
        budget.execution=recorder
    recorder.model_configuration('proof', configuration)
    recorder.update(phase='proof',bindings={'contract_sha256':ir.digest(cpath),'plan_sha256':ir.digest(out/'inputs/plan.json')})
    try:
        with execution_state.activate(recorder),recorder.signals() if owns_recorder else contextlib.nullcontext():
            return _run_frozen(cpath,plan,out,shared_store,configuration,worker_budget=budget,
                timeout_seconds=timeout_seconds,bank=bank,arm=arm,lock=lock,started=started,recorder=recorder,prior_run=prior_run,
                repair_guidance=repair_guidance,reviewed_interface=reviewed_interface,sessions=sessions,
                diagnostic_interface=diagnostic_interface)
    finally:
        if owns_recorder:
            status=recorder.state.get('proof_result','EXECUTION_FAULT')
            try:recorder.close('CANCELLED' if recorder.cancelled() else status)
            except Exception as error:
                from fault_control import Gate
                try:
                    with recorder.signals():
                        Gate(out/'logs/controller-errors',recorder=recorder,stage='standalone-proof-queue').pause(
                            error,resumable=False,checkpoint={'preserve_checked_bodies':True,'no_automatic_restart':True})
                except execution_state.Cancelled:recorder.close('CANCELLED')


def _run_frozen(cpath,plan,out,shared_store,configuration,*,worker_budget,timeout_seconds,bank,arm,lock,started,recorder,prior_run=None,repair_guidance=None,reviewed_interface=None,sessions=None,diagnostic_interface=None):
    import basis_defect
    basis_revision=basis_defect.is_revision_program(out,prior_run)
    budget=worker_budget
    store = Store(shared_store) if shared_store else None
    files = [Path(__file__),Path(ir.__file__),Path(__file__).with_name('dependency_instances.py'),Path(pilot.__file__),Path(scheduler.__file__),
             Path(__file__).with_name('shared_lemmas.py'),Path(__file__).with_name('strategy_bank.py'),Path(concurrency.__file__),
             ir.ROOT/'nl0/scripts/run_pilot.py',ir.ROOT/'nl0/scripts/pilot_common.py',
             ir.ROOT/'nl0/scripts/runtime_config.py',ir.ROOT/'nl0/scripts/usage.py',ir.ROOT/'nl0/scripts/exposure.py',
             ir.ROOT/'nl0/scripts/execution_health.py']
    files.extend([ir.ROOT/'nl0/scripts/execution_state.py',Path(proof_repair.__file__),
                  Path(__file__).with_name('local_helpers.py'),Path(__file__).with_name('proof_diagnosis.py')])
    snapshot = out/'harness-snapshot'
    snapshot.mkdir()
    for path in files: shutil.copyfile(path,snapshot/path.name)
    timeout_policy=pilot.strategy_bank.freeze_native_timeout_policy(
        snapshot/'nl02lean/bank') if arm=='yui' else None
    ir.write(out/'decomposition.json',ir.decomposition(cpath,plan,configuration['effective']))
    ir.write(out/'configuration.json',{'harness':pilot.HARNESS,'model':pilot.carrier.model_profile('proof')['id'],'model_selection':pilot.carrier.model_profile('proof'),
             'reasoning':pilot.carrier.model_profile('proof')['reasoning_effort'],'speed':pilot.carrier.model_profile('proof')['speed'],'arm':arm,'lock':lock,'workers':configuration['effective'],'concurrency':configuration,'timeout_seconds':timeout_seconds,
             'background_note_policy':pilot.BACKGROUND_NOTE_POLICY if arm == 'yui' else None,
             'native_timeout_policy':{k:v for k,v in timeout_policy.items() if k!='bank_root'} if timeout_policy else None,
             'bank_enabled':bank,'initial_shared_input':store.snapshot() if store else None,
             'script_sha256':{p.name:ir.digest(p) for p in files},
             'contract_sha256':ir.digest(cpath),'plan_sha256':ir.digest(out/'inputs/plan.json'),
             'scope':'Frozen-port proof phase, not automatic NL0 semantic verification or full Audit B.'})
    # An explicit node obstruction does not cancel its siblings or queued jobs.
    def worker(sid, packet):
        cached=None;checked=None
        if prior_run is not None:
            import proof_reuse
            cached=proof_reuse.candidate(prior_run,cpath,plan,sid,reviewed_interface=reviewed_interface,basis_revision=basis_revision)
            if cached:
                checked=ir.check(cpath,plan,{sid:cached['body']},only=sid,out=out/'reused'/sid)
                ir.write(out/'reused'/sid/'origin.json',{k:v for k,v in cached.items() if k!='body'})
                if checked['exit_code']==0:
                    return {'proof':cached['body'],'model_worker_called':False,
                            'stage':{'status':'SAME_CASE_NATIVE_RECHECKED','previous_run':str(prior_run)}}
        stage = pilot.Stage(out/'workers'/sid,cpath,'proof',timeout_seconds,plan,sid,bank,budget=budget,instruction_arm=arm,
                            timeout_policy=timeout_policy)
        if arm=='yui' and diagnostic_interface is not None:
            def diagnose(author,request,root):
                import proof_diagnosis
                # This nested role uses the suspended author's proof lane and
                # never waits for sibling nodes to finish.
                role=sessions.use('proof-diagnosis:'+sid) if sessions else contextlib.nullcontext()
                with role, execution_state.activate(recorder,'diagnosis-'+sid+'-'+request['evidence_key'][:12]):
                    return proof_diagnosis.run_live(author,request,diagnostic_interface,root/'review',
                        budget=budget,timeout=timeout_seconds)
            stage.diagnose_obstruction=diagnose
        if prior_run is not None:
            import proof_reuse
            if not basis_revision:
                proof_reuse.restore_cleanup_drafts(stage,prior_run)
                proof_reuse.restore_repair_drafts(stage,prior_run,reviewed_interface=reviewed_interface)
            if arm=='yui' and cached and checked['exit_code']!=0:
                advice=pilot.strategy_bank.native_timeout_feedback(checked,
                    stage.native_timeout_lean_version,stage.native_timeout_snapshot)
                proof_reuse.retain_recheck_failure(stage,cached,{**checked,**({'repair_advice':advice} if advice else {})})
        if repair_guidance and sid in repair_guidance:
            guidance=repair_guidance[sid]
            stage.system+='\nSerial diagnostic handoff for this own obligation (advice, never a premise):\n'+__import__('json').dumps(guidance,ensure_ascii=False)
            ir.write(stage.logs/'repair-guidance.json',guidance)
        stage.harness_version = pilot.HARNESS
        if sessions:
            with sessions.use('lean:'+sid):result,proof=stage.execute()
        else:result, proof = stage.execute()
        return {'proof':proof['proof'] if proof else None,'stage':result}
    result = scheduler.prove_graph(cpath,plan,worker,max_workers=configuration['effective'],store=store,out=out/'graph',execution=recorder)
    result['runner_wall_seconds'] = time.monotonic()-started
    result['concurrency'] = budget.report()
    if result['status'] in {'FRAGMENT_ASSEMBLED','GRAPH_ASSEMBLY_REPAIR_REQUIRED'}:
        ir.write(out/'proofs.json', {'contract_sha256': ir.digest(cpath), 'plan_sha256': ir.digest(out/'inputs/plan.json'), 'proofs': result['proofs']})
    ir.write(out/'report.json',result)
    from usage import aggregate
    from exposure import audit_run
    ir.write(out/'usage-summary.json',aggregate(out))
    ir.write(out/'exposure-summary.json',audit_run(out))
    recorder.update(proof_result=result['status'])
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('contract',type=Path)
    ap.add_argument('plan',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--shared-store',type=Path)
    ap.add_argument('--max-concurrency', default='auto')
    ap.add_argument('--workers',type=int, help='Compatibility alias for --max-concurrency; explicit integers only.')
    ap.add_argument('--timeout-seconds',type=int,default=None)
    ap.add_argument('--bank',action='store_true')
    ap.add_argument('--arm',choices=['direct','yui'],default='yui')
    args = ap.parse_args()
    ir.need(args.workers is None or args.max_concurrency == 'auto', 'choose --workers or --max-concurrency')
    result = run(args.contract, args.plan, args.out, shared_store=args.shared_store,
                 max_concurrency=args.workers if args.workers is not None else args.max_concurrency,
                 timeout_seconds=args.timeout_seconds, bank=args.bank, arm=args.arm)
    print(result['status'])
    return 0 if result['status'] == 'FRAGMENT_ASSEMBLED' else 1


if __name__ == '__main__': raise SystemExit(main())
