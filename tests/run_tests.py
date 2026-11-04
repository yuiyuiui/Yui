#!/usr/bin/env python3
"""Run unittest with cleanup on success, failure and catchable interruption.

All scratch, hidden state and compilation output live in a private temporary
root. Only exact child identities observed by this test run may be stopped.
Unconfirmed shutdown retains its directory/evidence and makes the run fail.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

TESTS=Path(__file__).resolve().parent
CORE=TESTS.parent
sys.path.insert(0,str(CORE/'nl0/scripts'))
from cleanup import process_table, matching, signal_owned


def owner_identity():
    row=process_table()[os.getpid()]
    return {k:row[k] for k in ('pid','pgid','started')}


def observe(records, leader, root):
    table=process_table()
    ledger=root/'processes.jsonl'
    if ledger.is_file():
        for line in ledger.read_text().splitlines():
            try:row=json.loads(line)
            except ValueError:continue
            if matching(row,table):records[(row['pid'],row['started'])]=row
    owned={r['pid'] for r in records.values() if matching(r,table)}
    while True:
        added={pid for pid,row in table.items() if row['ppid'] in owned and pid not in owned}
        if not added:break
        owned.update(added)
    for pid in owned:
        row=table[pid];records[(pid,row['started'])]=row
    return {r['pid']:table[r['pid']] for r in records.values() if matching(r,table)}


def cleanup(root, records, leader=None):
    root=Path(root)
    if not root.exists():return {'status':'CLEANED','residual_pids':[]}
    marker=root/'.test-owner.json'
    if root.is_symlink() or marker.is_symlink() or not marker.is_file():raise ValueError('Unmarked or symlink test cleanup root')
    value=json.loads(marker.read_text())
    if value.get('owner')!=owner_identity() or value.get('root')!=str(root.resolve()):raise ValueError('Foreign test cleanup root')
    try:
        live=observe(records,leader,root)
        signal_owned(live,signal.SIGTERM)
        until=time.monotonic()+1
        while live and time.monotonic()<until:
            time.sleep(.05);live=observe(records,leader,root)
        signal_owned(live,signal.SIGKILL)
        until=time.monotonic()+3
        while live and time.monotonic()<until:
            time.sleep(.05);live=observe(records,leader,root)
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        report={'status':'CLEANUP_FAILED','residual_pids':None,'retained_root':str(root),
            'error':type(error).__name__+': '+str(error)}
        (root/'cleanup-failure.json').write_text(json.dumps(report));return report
    if live:
        report={'status':'CLEANUP_FAILED','residual_pids':sorted(live),'retained_root':str(root)}
        (root/'cleanup-failure.json').write_text(json.dumps(report));return report
    shutil.rmtree(root)
    return {'status':'CLEANED','residual_pids':[]}


def run(arguments=(), *, command=None):
    root=Path(tempfile.mkdtemp(prefix='yui-tests-')).resolve()
    try:
        (root/'.test-owner.json').write_text(json.dumps({'owner':owner_identity(),'root':str(root)}))
        scratch=root/'tmp';scratch.mkdir()
    except BaseException:
        shutil.rmtree(root)  # Setup has not started a child or accepted user data.
        raise
    env=dict(os.environ,TMPDIR=str(scratch),TMP=str(scratch),TEMP=str(scratch),
        PYTHONDONTWRITEBYTECODE='1',YUI_TEST_CLEANUP_ROOT=str(root))
    # Child imports instrumentation before harness_support captures Popen for its
    # offline model guard. Ordinary direct unittest remains supported as well.
    bootstrap=("import sys;sys.path.insert(0,"+repr(str(TESTS))+");import test_resources;"
        "import unittest;unittest.main(module=None)")
    command=command or [sys.executable,'-B','-c',bootstrap,*arguments]
    previous={};records={};process=None;interrupted=None;report=None
    def stop(signum,frame):
        nonlocal interrupted
        interrupted=signum
    for sig in (signal.SIGINT,signal.SIGTERM):previous[sig]=signal.signal(sig,stop)
    try:
        process=subprocess.Popen(command,env=env,cwd=CORE,start_new_session=True)
        table=process_table();row=table.get(process.pid)
        if row and row['ppid']==os.getpid() and process.poll() is None:
            records[(row['pid'],row['started'])]=row
        while process.poll() is None:
            observe(records,process.pid,root)
            if interrupted:break
            time.sleep(.1)
        returncode=128+interrupted if interrupted else process.wait()
    finally:
        try:
            report=cleanup(root,records,process.pid if process else None)
            if process:
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:pass
        finally:
            for sig,handler in previous.items():signal.signal(sig,handler)
    print('test cleanup: '+report['status']+((' '+report['retained_root']) if report.get('retained_root') else ''),flush=True)
    return (128+interrupted if interrupted else returncode) if report['status']=='CLEANED' else 1


if __name__=='__main__':
    args=sys.argv[1:] or ['discover','-s',str(TESTS),'-v']
    raise SystemExit(run(args))
