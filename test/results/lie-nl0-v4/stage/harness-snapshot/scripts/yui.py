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
    commands.add_parser('doctor')
    commands.add_parser('selftest')
    stage = commands.add_parser('stage')
    stage.add_argument('prompt', type=Path)
    stage.add_argument('--phase', required=True)
    stage.add_argument('--arm', choices=['direct', 'yui'], default='yui')
    stage.add_argument('--out', type=Path, required=True)
    stage.add_argument('--timeout-seconds', type=int, default=600)
    stage.add_argument('--inputs', type=Path, help='Frozen explicit task-document manifest')
    stage.add_argument('--kind', choices=['json','nl0'], default='json', help='Built-in structural contract; no automatic semantic certification')
    stage.add_argument('--case-id', help='Required case identity for NL0 authoring')
    tokens = commands.add_parser('usage')
    tokens.add_argument('directory', type=Path)
    exposure = commands.add_parser('exposure')
    exposure.add_argument('directory', type=Path)
    args = parser.parse_args()
    if args.command == 'doctor':
        print(json.dumps({'status': 'ENVIRONMENT-CHECKED', 'resolved_environment': verify()}, indent=2))
    elif args.command == 'selftest':
        for directory in [CORE / 'tests', CORE / 'translation/tests']:
            result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(directory), '-v'])
            if result.returncode:
                return result.returncode
    elif args.command == 'usage':
        from usage import aggregate
        print(json.dumps(aggregate(args.directory), indent=2))
    elif args.command == 'exposure':
        from exposure import audit_run
        result = audit_run(args.directory)
        print(json.dumps(result,indent=2))
        return 0 if result and all(x['status']=='TRANSMITTED-EXPOSURE-CHECK-PASSED' for x in result) else 1
    else:
        verify()
        from clean_stage import ArtifactStage
        sys.path.insert(0, str(CORE / 'translation/scripts'))
        import concurrency
        budget = concurrency.Budget(concurrency.resolve())
        print(json.dumps({'model_concurrency': budget.configuration}), flush=True)
        worker = ArtifactStage(args.out, args.prompt.read_text(), phase=args.phase, arm=args.arm,
                               timeout=args.timeout_seconds, budget=budget, inputs=args.inputs,
                               kind=args.kind, case_id=args.case_id)
        result, artifact = worker.execute()
        print(json.dumps({'stage': result, 'concurrency': budget.report()}, indent=2))
        blocked = {'SUBSTANTIVE_GAP','SUSPECTED_GAP','SOURCE_UNAVAILABLE','INPUT_CONFLICT'}
        return 0 if artifact is not None and artifact.get('status') not in blocked else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
