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


def run(cpath, ppath, out, *, shared_store=None, max_concurrency='auto', timeout_seconds=180, bank=False, budget=None, arm='yui'):
    ir.need(timeout_seconds >= 1, 'positive time limit required')
    ir.need(arm in {'yui','direct'}, 'unknown instruction arm')
    ir.need(arm != 'direct' or (not bank and shared_store is None), 'direct arm cannot use Yui strategy or proof stores')
    budget = budget or concurrency.Budget(concurrency.resolve(max_concurrency), role='proof')
    ir.need(budget.role != 'preparation_review', 'Proof execution requires its own proof budget')
    budget.role = 'proof'
    configuration = budget.configuration
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
    recorder.update(phase='proof',bindings={'contract_sha256':ir.digest(cpath),'plan_sha256':ir.digest(out/'inputs/plan.json')})
    try:
        with execution_state.activate(recorder),recorder.signals() if owns_recorder else contextlib.nullcontext():
            return _run_frozen(cpath,plan,out,shared_store,configuration,worker_budget=budget,
                timeout_seconds=timeout_seconds,bank=bank,arm=arm,lock=lock,started=started,recorder=recorder)
    finally:
        if owns_recorder:
            status=recorder.state.get('proof_result','EXECUTION_FAULT')
            recorder.close('CANCELLED' if recorder.cancelled() else status)


def _run_frozen(cpath,plan,out,shared_store,configuration,*,worker_budget,timeout_seconds,bank,arm,lock,started,recorder):
    budget=worker_budget
    store = Store(shared_store) if shared_store else None
    files = [Path(__file__),Path(ir.__file__),Path(pilot.__file__),Path(scheduler.__file__),
             Path(__file__).with_name('shared_lemmas.py'),Path(__file__).with_name('strategy_bank.py'),Path(concurrency.__file__),
             ir.ROOT/'scripts/run_pilot.py',ir.ROOT/'scripts/pilot_common.py',
             ir.ROOT/'scripts/runtime_config.py',ir.ROOT/'scripts/usage.py',ir.ROOT/'scripts/exposure.py',
             ir.ROOT/'scripts/execution_health.py']
    files.append(ir.ROOT/'scripts/execution_state.py')
    snapshot = out/'harness-snapshot'
    snapshot.mkdir()
    for path in files: shutil.copyfile(path,snapshot/path.name)
    ir.write(out/'decomposition.json',ir.decomposition(cpath,plan,configuration['effective']))
    ir.write(out/'configuration.json',{'harness':pilot.HARNESS,'model':pilot.carrier.MODEL,
             'reasoning':'high','speed':'standard','arm':arm,'lock':lock,'workers':configuration['effective'],'concurrency':configuration,'timeout_seconds':timeout_seconds,
             'background_note_policy':pilot.BACKGROUND_NOTE_POLICY if arm == 'yui' else None,
             'bank_enabled':bank,'initial_shared_input':store.snapshot() if store else None,
             'script_sha256':{p.name:ir.digest(p) for p in files},
             'contract_sha256':ir.digest(cpath),'plan_sha256':ir.digest(out/'inputs/plan.json'),
             'scope':'Frozen-port proof phase, not automatic NL0 semantic verification or full Audit B.'})
    def worker(sid, packet):
        stage = pilot.Stage(out/'workers'/sid,cpath,'proof',timeout_seconds,plan,sid,bank,budget=budget,instruction_arm=arm)
        stage.harness_version = pilot.HARNESS
        result, proof = stage.execute()
        return {'proof':proof['proof'] if proof else None,'stage':result}
    result = scheduler.prove_graph(cpath,plan,worker,max_workers=configuration['effective'],store=store,out=out/'graph',execution=recorder)
    result['runner_wall_seconds'] = time.monotonic()-started
    result['concurrency'] = budget.report()
    if result['status'] == 'FRAGMENT_ASSEMBLED':
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
    ap.add_argument('--timeout-seconds',type=int,default=180)
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
