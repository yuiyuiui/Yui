"""Optional, trusted local-browser readback; no model-generated browser code."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess

from controller_common import bind


def installation():
    """Use existing tools only. Explicit invalid overrides never fall back."""
    root=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies'
    def choose(variable,candidates):
        explicit=os.environ.get(variable)
        for value in [explicit] if explicit else candidates:
            if value and Path(value).expanduser().is_file():return str(Path(value).expanduser().resolve())
        raise FileNotFoundError(variable+': no installed compatible source-browser tool; see source-retrieval.md')
    return {
        'node':choose('YUI_SOURCE_BROWSER_NODE',[shutil.which('node'),root/'node/bin/node']),
        'module':choose('YUI_SOURCE_BROWSER_MODULE',[root/'node/node_modules/playwright/index.mjs']),
        'executable':choose('YUI_SOURCE_BROWSER_EXECUTABLE',[
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            shutil.which('google-chrome'),shutil.which('chromium')])}


def capture(directory,url,stem):
    from source_access import public_url,LIMIT
    public_url(url)
    directory=Path(directory).resolve();runtime=installation()
    driver=Path(__file__).with_suffix('.mjs')
    request={'url':url,'directory':str(directory),'stem':stem,'limit':LIMIT,**runtime}
    # No shell or model-provided code. Own a separate process group so timeout
    # or cancellation also closes this call's Chrome children.
    process=subprocess.Popen([runtime['node'],str(driver)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:
        stdout,stderr=process.communicate(json.dumps(request),timeout=100)
    except (subprocess.TimeoutExpired,KeyboardInterrupt):
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.communicate()
        raise
    if process.returncode:raise ValueError('Source browser failed: '+stderr[-1200:])
    result=json.loads(stdout)
    result['browser_runtime']={'driver':bind(driver),'module':runtime['module'],
                               'executable':runtime['executable'],**result.pop('runtime',{})}
    # The helper writes only these controller-selected output names.
    for name,suffix in [('document','.browser-document'),('screenshot','.png')]:
        path=directory/(stem+suffix)
        if name=='document' and not path.is_file():raise ValueError('Missing browser document')
        if path.exists():
            if not path.resolve().is_relative_to(directory):raise ValueError('Browser artifact escaped its directory')
            if path.stat().st_size>LIMIT:raise ValueError('Browser artifact exceeds retrieval limit')
            result[name]=bind(path)
    result['raw']=Path(result['document']['path']).read_bytes()
    return result
