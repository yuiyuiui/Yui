# Local setup

Yui currently runs on **macOS** with `sandbox-exec`. The recorded environment used Python **3.13**, Codex CLI **0.166.0-alpha.5.1**, Lean **4.32.2** and the Mathlib revision in [the toolchain lock](../toolchain/lock.json). Linux and Windows are not supported by the current isolation layer.

Install Git, Python 3, [ripgrep](https://github.com/BurntSushi/ripgrep#installation), and either `pdftotext` from [Poppler](https://poppler.freedesktop.org/) or Python's `pypdf` package for PDF input. Keep the complete Yui repository together as described in the [main README](../README.md#4-installation-and-requirements).

## Codex and authentication

Use an authenticated [Codex CLI installation](https://learn.chatgpt.com/docs/codex/cli) that includes its matching `codex-code-mode-host`. Yui binds both components from the same installation. A CLI version number alone does not establish compatibility.

For a packaged desktop or standalone installation, set `YUI_CODEX_BINARY` to its native `codex` executable if Yui does not select it automatically. For example, some Codex desktop installations provide `/Applications/Codex.app/Contents/Resources/codex`. The helper must either sit beside that executable or be described by the same installation's `codex-package.json`. Do not copy a helper from a different release.

If using npm, the recorded CLI version is published as `@openai/codex@0.166.0-alpha.5.1`. Its macOS platform package includes both native components. The npm `codex` command is a JavaScript launcher, so select the native executable explicitly:

```sh
npm install -g @openai/codex@0.166.0-alpha.5.1
export YUI_CODEX_BINARY="$(python3 - "$(npm root -g)" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1]) / '@openai'
candidates = [p for p in root.rglob('bin/codex')
              if p.is_file() and (p.parent / 'codex-code-mode-host').is_file()]
if len(candidates) != 1:
    raise SystemExit('Select your matching native Codex executable manually with YUI_CODEX_BINARY.')
print(candidates[0])
PY
)"
"$YUI_CODEX_BINARY" --version
"$YUI_CODEX_BINARY" login
```

Skip login if this installation is already authenticated. By default, Yui reads authentication from `~/.codex`; use `YUI_CODEX_HOME` if your authenticated home is elsewhere. Keep that directory and its credentials outside published results. The requested benchmark model must be available to your account; Yui does not silently substitute another model.

## Pinned Lean and Mathlib

Reuse an existing compatible shared environment if you have one. Otherwise, install [Elan](https://github.com/leanprover/elan#installation) first:

```sh
curl -sSf https://elan.lean-lang.org/elan-init.sh | sh -s -- -y --default-toolchain none
. "$HOME/.elan/env"
```

The following reads Yui's pins, installs the matching Lean toolchain and prepares one shared Mathlib checkout. It refuses to change an existing checkout with a different revision or modified tracked sources. Set `YUI_SKILL_ROOT` to your actual Yui installation if different.

```sh
export YUI_SKILL_ROOT="$HOME/.agents/skills/rigorous-proof"
export YUI_MATHLIB_ROOT="$HOME/formalization-tools/lean-mathlib-v4.32.2/mathlib"
python3 - <<'PY'
import json
import os
from pathlib import Path
import subprocess

lock = json.loads((Path(os.environ['YUI_SKILL_ROOT']) / 'toolchain/lock.json').read_text())
root = Path(os.environ['YUI_MATHLIB_ROOT']).expanduser()
subprocess.run(['elan', 'toolchain', 'install', lock['lean']['toolchain']], check=True)
if not root.exists():
    root.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'clone', '--filter=blob:none', lock['mathlib']['url'], str(root)], check=True)
    subprocess.run(['git', '-C', str(root), 'checkout', '--detach', lock['mathlib']['rev']], check=True)
actual = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
if actual != lock['mathlib']['rev']:
    raise SystemExit('Existing Mathlib has a different revision; choose another shared directory.')
subprocess.run(['git', '-C', str(root), 'diff', '--quiet', 'HEAD', '--'], check=True)
subprocess.run(['elan', 'run', lock['lean']['toolchain'], 'lake', 'exe', 'cache', 'get'], cwd=root, check=True)
PY
```

[`lake exe cache get`](https://leanprover-community.github.io/install/project.html) retrieves compiled Mathlib artifacts using the checkout's existing dependency manifest. **Do not run `lake update`**: that changes the dependency selection. Do not clone Mathlib for every proof project. Yui's doctor checks the pinned manifest and dependency revisions as well as Mathlib itself.

With Elan's default installation, Yui finds Lean automatically. For a custom installation, set `YUI_LEAN_ROOT` to the directory containing `bin/lean` and `bin/lake`. `YUI_MATHLIB_ROOT` must point to the Mathlib checkout, not its parent directory. Preserve the environment overrides you need in the shell that starts Codex.

## Check before starting a proof

```sh
python3 -B "${YUI_SKILL_ROOT:-$HOME/.agents/skills/rigorous-proof}/nl0/scripts/yui.py" doctor
```

Proceed when the command reports `ENVIRONMENT-CHECKED`. It checks local dependencies without starting a model or proof job. A missing helper or a toolchain mismatch must be fixed first. This is a dependency check, not a full new-machine workflow test.

Then follow [Use](../README.md#use), or the [test and benchmark reproduction prompts](https://github.com/yuiyuiui/Yui-results#local-setup). Keep generated results outside the installed skill.
