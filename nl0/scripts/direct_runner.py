#!/usr/bin/env python3
"""One persistent native session; normal turn completion is not task completion.

This runner checks artifact completeness and native compilation. It does not
certify natural-language/Lean correspondence or primary-source authenticity.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import subprocess
import threading
import time

MODEL='gpt-6.1-sol'


def write(path,value):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


def proof_tokens(text):
    """Ignore Lean comments and string literals when rejecting placeholders."""
    output=[];i=0;depth=0;string=False
    while i<len(text):
        if depth:
            if text.startswith('/-',i):depth+=1;i+=2
            elif text.startswith('-/',i):depth-=1;i+=2
            else:i+=1
        elif string:
            if text[i]=='\\':i+=2
            elif text[i]=='"':string=False;i+=1
            else:i+=1
        elif text.startswith('/-',i):depth=1;i+=2
        elif text.startswith('--',i):
            end=text.find('\n',i);i=len(text) if end<0 else end
        elif text[i]=='"':string=True;i+=1
        else:output.append(text[i]);i+=1
    if depth or string:raise ValueError('Unterminated comment or string')
    return ''.join(output)


def compile_process(command,*,cwd,env,capture_output=True,text=True,cancelled=lambda:False):
    proc=subprocess.Popen(command,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=text,start_new_session=True)
    while True:
        try:
            stdout,stderr=proc.communicate(timeout=.2)
            return subprocess.CompletedProcess(command,proc.returncode,stdout,stderr)
        except subprocess.TimeoutExpired:
            if cancelled() and proc.poll() is None:
                if os.getpgid(proc.pid)==proc.pid:os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if proc.poll() is None and os.getpgid(proc.pid)==proc.pid:os.killpg(proc.pid,signal.SIGKILL)


def verify(work,lean,mathlib,*,compile_call=compile_process):
    report=work/'result.json';proof=work/'Proof.lean';mapping=work/'correspondence.md'
    if not report.is_file():return {'ready':False,'reason':'Save result.json and continue the complete target.'}
    value=json.loads(report.read_text())
    if not isinstance(value,dict):return {'ready':False,'reason':'Save a result.json object with the actual completion state.'}
    if value.get('status')!='complete' or value.get('remaining_obligations')!=[]:
        return {'ready':False,'reason':'The target still has unfinished obligations. Continue from the saved checkpoint.'}
    if value.get('root_declaration')!='theorem_1' or value.get('target_label')!='Theorem 1':
        return {'ready':False,'reason':'Export theorem_1 for the original Theorem 1; preserve the original target.'}
    if not proof.is_file() or not mapping.is_file() or not mapping.read_text().strip():
        return {'ready':False,'reason':'A complete Proof.lean and correspondence.md are required.'}
    code=proof_tokens(proof.read_text())
    if re.search(r'\b(?:sorry|admit|axiom|unsafe)\b',code):
        return {'ready':False,'reason':'The Lean artifact still contains an unproved or unsafe declaration.'}
    env=os.environ.copy();roots=[work,mathlib/'.lake/build/lib/lean']
    roots.extend(p for p in (mathlib/'.lake/packages').glob('*/.lake/build/lib/lean') if p.is_dir())
    env['LEAN_PATH']=os.pathsep.join(str(p) for p in roots)
    built=compile_call([str(lean),'-o',str(work/'Proof.olean'),str(proof)],cwd=work,env=env,capture_output=True,text=True)
    (work/'build.log').write_text(built.stdout+built.stderr)
    if built.returncode:return {'ready':False,'reason':'Full-file Lean compilation failed. Repair the actual diagnostics.','diagnostic':(built.stdout+built.stderr)[-18000:]}
    probe=work/'Verify.lean';probe.write_text('import Proof\n#check theorem_1\n#print axioms theorem_1\n')
    checked=compile_call([str(lean),str(probe)],cwd=work,env=env,capture_output=True,text=True)
    (work/'verification.log').write_text(checked.stdout+checked.stderr)
    if checked.returncode or 'sorryAx' in checked.stdout+checked.stderr:
        return {'ready':False,'reason':'The exported target or its native trust inspection failed.','diagnostic':(checked.stdout+checked.stderr)[-18000:]}
    found=re.search(r'depends on axioms:\s*\[([^]]*)\]',checked.stdout)
    axioms={s.strip().strip("'") for s in found.group(1).split(',') if s.strip()} if found else set()
    if (not found and 'does not depend on any axioms' not in checked.stdout) or axioms-{'propext','Classical.choice','Quot.sound'}:
        return {'ready':False,'reason':'Native trust report is absent or contains an undeclared axiom.'}
    return {'ready':True,'status':'CANDIDATE_READY','proof_sha256':hashlib.sha256(proof.read_bytes()).hexdigest(),
            'whole_file_compiled':True,'independent_semantic_acceptance':'UNVERIFIED',
            'scope':'Native compilation and declared completion only; independent target/source correspondence review remains required.'}


def command(binary,work,session=None):
    result=[str(binary),'exec','--ignore-user-config','--ignore-rules','--json','--skip-git-repo-check',
        '-C',str(work),'-s','workspace-write','-m',MODEL,'-c','model_reasoning_effort="high"',
        '-c','service_tier="default"','-c','project_doc_max_bytes=0',
        '--disable','memories','--disable','multi_agent','--disable','plugins','--disable','apps']
    return result+(['resume',session,'-'] if session else ['-'])


def turn(binary,work,prompt,session,number,env,cancelled):
    proc=subprocess.Popen(command(binary,work,session),cwd=work,env=env,stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    proc.stdin.write(prompt);proc.stdin.close()
    events=queue.Queue()
    def consume(stream,kind):
        for line in stream:events.put((kind,line))
        events.put((kind,None))
    readers=[threading.Thread(target=consume,args=(stream,kind),daemon=True)
             for stream,kind in [(proc.stdout,'stdout'),(proc.stderr,'stderr')]]
    for thread in readers:thread.start()
    closed=set();found=session;usage=[]
    with (work/f'turn-{number:04d}.jsonl').open('w') as out, (work/f'turn-{number:04d}.stderr').open('w') as err:
        while proc.poll() is None or len(closed)<2:
            if cancelled() and proc.poll() is None:
                if os.getpgid(proc.pid)==proc.pid:os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if proc.poll() is None and os.getpgid(proc.pid)==proc.pid:os.killpg(proc.pid,signal.SIGKILL)
            try:kind,line=events.get(timeout=.2)
            except queue.Empty:continue
            if line is None:closed.add(kind);continue
            (out if kind=='stdout' else err).write(line)
            if kind=='stdout':
                try:row=json.loads(line)
                except ValueError:continue
                if row.get('type')=='thread.started':found=row.get('thread_id')
                if row.get('type')=='turn.completed' and isinstance(row.get('usage'),dict):usage.append(row['usage'])
    for thread in readers:thread.join()
    proc.stdout.close();proc.stderr.close()
    return proc.wait(),found,usage


def run(work,binary,lean,mathlib,*,turn_call=turn,verify_call=verify):
    work=Path(work).resolve();work.mkdir(parents=True,exist_ok=True)
    status=work/'execution-status.json'
    if status.exists():raise ValueError('Existing run metadata must be preserved; choose a fresh output directory')
    prompt=(work/'prompt.md').read_text();session=None;number=0;costs=[];started=time.monotonic();stopped=False
    env=os.environ.copy();home=work/'.runtime-home';home.mkdir(mode=0o700)
    # Authentication is copied, never logged; no user config, history or memory.
    origin=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))
    for name in ['auth.json','models_cache.json']:
        if (origin/name).is_file():
            shutil.copyfile(origin/name,home/name);(home/name).chmod(0o600)
    env['CODEX_HOME']=str(home)
    previous={}
    def stop(signum,frame):
        nonlocal stopped
        stopped=True
    for sig in (signal.SIGINT,signal.SIGTERM):previous[sig]=signal.signal(sig,stop)
    cancelled=lambda:stopped or (work/'cancel.json').exists()
    try:
        while not cancelled():
            number+=1
            write(status,{'status':'RUNNING','turn':number,'session_id':session,
                'requested_model':MODEL,'reasoning_effort':'high','requested_service_tier':'default',
                'observed_service_tier':'UNVERIFIED','total_limits':None})
            code,observed,usage=turn_call(binary,work,prompt,session,number,env,cancelled)
            costs.extend(usage)
            if cancelled():break
            if session is not None and observed!=session:raise RuntimeError('Native continuation changed session identity')
            session=observed
            if code!=0:raise RuntimeError('Native CLI exited with code '+str(code)+'; preserve its actual fault and session')
            if not session:raise RuntimeError('Native CLI did not report its session identity')
            try:
                if verify_call is verify:
                    check=verify(work,lean,mathlib,compile_call=lambda *a,**kw:compile_process(*a,**kw,cancelled=cancelled))
                else:check=verify_call(work,lean,mathlib)
            except (ValueError,OSError) as error:check={'ready':False,'reason':str(error)}
            write(work/'completion-check.json',check)
            if check['ready']:
                result={**check,'session_id':session};break
            try:checkpoint=json.loads((work/'result.json').read_text()) if (work/'result.json').is_file() else {}
            except (ValueError,OSError):checkpoint={}
            if not isinstance(checkpoint,dict):checkpoint={}
            blocker=checkpoint.get('blocker')
            if checkpoint.get('status')=='blocked' and isinstance(blocker,dict) and blocker.get('kind') in {
                    'missing_input','essential_statement_unavailable','tool_environment'} and blocker.get('detail') and blocker.get('evidence'):
                result={'status':'HUMAN_INPUT_REQUIRED','blocker':blocker,'session_id':session};break
            prompt='Continue the same task from the existing files and checkpoint. A normal turn ending is not completion.\n'+json.dumps(check,ensure_ascii=False)
        else:result={'status':'CANCELLED','session_id':session}
        if cancelled():result={'status':'CANCELLED','session_id':session}
    except Exception as error:result={'status':'EXECUTION_FAULT','error':type(error).__name__+': '+str(error),'session_id':session}
    finally:
        for sig,handler in previous.items():signal.signal(sig,handler)
        (home/'auth.json').unlink(missing_ok=True)
    result.update(turns=number,elapsed_seconds=time.monotonic()-started,reported_usage=costs,
                  independent_semantic_acceptance='UNVERIFIED')
    write(work/'execution-result.json',result);write(status,result);return result


def prepare_prompt(work,paper,lean,mathlib,renderer):
    """Render selected input/tool paths without launching or overwriting a run."""
    work=Path(work).expanduser().resolve()
    if any((work/name).exists() for name in ('execution-status.json','execution-result.json')):
        raise ValueError('Existing run metadata must be preserved; choose a fresh output directory')
    paper,lean,mathlib=[Path(p).expanduser().resolve(strict=True) for p in (paper,lean,mathlib)]
    if not paper.is_file() or not lean.is_file() or not mathlib.is_dir():
        raise ValueError('Supply an existing paper, Lean executable and Mathlib directory')
    value=renderer(paper=paper,lean=lean,mathlib=mathlib)
    if not isinstance(value,str) or not value.strip():raise ValueError('Prompt renderer returned no text')
    prompt=work/'prompt.md'
    if prompt.is_symlink() or (prompt.exists() and prompt.read_text()!=value):
        raise ValueError('Existing prompt differs; preserve it and choose a fresh output directory')
    work.mkdir(parents=True,exist_ok=True)
    if not prompt.exists():
        with prompt.open('x') as out:out.write(value)
    return {'status':'PROMPT_PREPARED','work':str(work),'paper':str(paper),'lean':str(lean),
            'mathlib':str(mathlib),'prompt':str(prompt),
            'prompt_sha256':hashlib.sha256(prompt.read_bytes()).hexdigest()}


def main(default_work=None,*,prompt_factory=None,default_paper=None,argv=None):
    shared=Path.home()/'formalization-tools/lean-mathlib-v4.32.2'
    lean_root=Path(os.environ['YUI_LEAN_ROOT']).expanduser() if os.environ.get('YUI_LEAN_ROOT') else (
        shared/'lean' if (shared/'lean').exists() else Path.home()/'.elan/toolchains/leanprover--lean4---v4.32.2')
    codex=os.environ.get('YUI_CODEX_BINARY') or shutil.which('codex') or next((p for p in [
        '/Applications/Codex.app/Contents/Resources/codex',
        '/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex'] if Path(p).is_file()),
        '/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex')
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=Path,default=default_work or Path.cwd())
    ap.add_argument('--codex',type=Path,default=Path(codex))
    ap.add_argument('--lean',type=Path,default=lean_root/'bin/lean')
    ap.add_argument('--mathlib',type=Path,default=Path(os.environ.get('YUI_MATHLIB_ROOT') or str(shared/'mathlib')))
    if prompt_factory:
        ap.add_argument('--paper',type=Path,default=default_paper,required=default_paper is None)
        ap.add_argument('--prepare-only',action='store_true',help='Generate and display prompt paths without starting a model')
    args=ap.parse_args(argv)
    for key in ('work','codex','lean','mathlib'):setattr(args,key,getattr(args,key).expanduser().resolve())
    if prompt_factory:
        prepared=prepare_prompt(args.work,args.paper,args.lean,args.mathlib,prompt_factory)
        if args.prepare_only:
            print(json.dumps(prepared,indent=2));return prepared
    result=run(args.work,args.codex,args.lean,args.mathlib)
    print(json.dumps(result,indent=2));return result


if __name__=='__main__':main()
