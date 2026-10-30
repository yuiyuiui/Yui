#!/usr/bin/env python3
"""Yui runtime entry: environment checks, regressions, clean artifact stages and accounting."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from runtime_config import CORE, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    import entrypoint
    entrypoint.parsers(commands)
    commands.add_parser('doctor')
    commands.add_parser('selftest').add_argument('--verbose',action='store_true')
    stage = commands.add_parser('stage')
    stage.add_argument('prompt', type=Path)
    stage.add_argument('--phase', required=True)
    stage.add_argument('--arm', choices=['direct', 'yui'], default='yui')
    stage.add_argument('--out', type=Path, required=True)
    stage.add_argument('--timeout-seconds', type=int, default=None, help='Optional wall limit in seconds; omitted means unlimited')
    stage.add_argument('--inputs', type=Path, help='Frozen explicit task-document manifest')
    stage.add_argument('--kind', choices=['json','nl0'], default='json', help='Built-in structural contract; no automatic semantic certification')
    stage.add_argument('--case-id', help='Required case identity for NL0 authoring')
    stage.add_argument('--no-library', action='store_true',
                       help='Disable library search/read/probe tools, including for packet-only replay')
    tokens = commands.add_parser('usage')
    tokens.add_argument('directory', type=Path)
    commands.add_parser('metrics',help='Read recorded phase/tool/request costs; no model calls').add_argument('directory',type=Path)
    exposure = commands.add_parser('exposure')
    exposure.add_argument('directory', type=Path)
    status=commands.add_parser('case-status',help='Read artifact-scoped progress without running a model')
    status.add_argument('source',type=Path)
    for name in ['interface','interface-review','workflow']:status.add_argument('--'+name,type=Path)
    args = parser.parse_args()
    if args.command in {'prepare','run','execute','resume','status','observe','cancel','cleanup','targets','errors','resume-error','final-decision'}:
        try:
            result=entrypoint.dispatch(args)
            print(json.dumps(result,indent=2))
            if result.get('status') in {'BLOCKED','VALIDATION_FAILED'}:return 1
            if args.command in {'run','execute','resume'} and result.get('outcomes'):
                return 0 if all(r.get('completion',{}).get('workflow_completed',r.get('completion',{}).get('acceptance_target_satisfied')) for r in result['outcomes'].values()) else 1
            return 0
        except (OSError,ValueError,KeyError) as error:
            print(json.dumps({'status':'REQUEST_NOT_STARTED_OR_BLOCKED','error':str(error)},indent=2));return 1
    elif args.command == 'doctor':
        print(json.dumps({'status': 'ENVIRONMENT-CHECKED', 'resolved_environment': verify()}, indent=2))
    elif args.command == 'selftest':
        directory = CORE / 'tests'
        result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(directory), '-v'],
                                capture_output=True,text=True)
        if args.verbose or result.returncode:
            print(result.stdout,end='')
            print(result.stderr,end='')
        else:
            summary=[s for s in result.stderr.splitlines() if s.startswith('Ran ') or s=='OK']
            print('tests: '+'; '.join(summary),flush=True)
        return result.returncode
    elif args.command == 'usage':
        from usage import aggregate
        print(json.dumps(aggregate(args.directory), indent=2))
    elif args.command=='metrics':
        from phase_metrics import summarize
        print(json.dumps(summarize(args.directory),indent=2))
    elif args.command == 'exposure':
        from exposure import audit_run
        result = audit_run(args.directory)
        print(json.dumps(result,indent=2))
        return 0 if result and all(x['status'] in {'TRANSMITTED-EXPOSURE-CHECK-PASSED','NATIVE-CODEX-CONTEXT-CHECK-PASSED'} for x in result) else 1
    elif args.command=='case-status':
        from case_status import project
        print(json.dumps(project(args.source,interface=args.interface,interface_review=args.interface_review,workflow=args.workflow),indent=2))
    else:
        if args.kind=='nl0' and not args.case_id:
            parser.error('--kind nl0 requires an explicit --case-id')
        verify()
        from clean_stage import ArtifactStage
        sys.path.insert(0, str(CORE / 'nl02lean/scripts'))
        import concurrency
        budget = concurrency.serial_budget()
        print(json.dumps({'model_concurrency': budget.configuration}), flush=True)
        worker = ArtifactStage(args.out, args.prompt.read_text(), phase=args.phase, arm=args.arm,
                               timeout=args.timeout_seconds, budget=budget, inputs=args.inputs,
                               kind=args.kind, case_id=args.case_id, library=not args.no_library)
        result, artifact = worker.execute()
        print(json.dumps({'stage': result, 'concurrency': budget.report()}, indent=2))
        blocked = {'SUBSTANTIVE_GAP','SUSPECTED_GAP','SOURCE_UNAVAILABLE','MISSING_SOURCE_STATEMENT','INPUT_CONFLICT'}
        return 0 if artifact is not None and artifact.get('status') not in blocked and result.get('measurement_valid') else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
