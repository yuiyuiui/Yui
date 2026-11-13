# Local setup

Yui currently runs on **macOS** with `sandbox-exec`. The recorded environment used Python **3.13** and Codex CLI **0.166.0-alpha.5.1**. Formalization uses a Lean/Mathlib pair selected for each run. The [toolchain lock](../toolchain/lock.json) retains the historical 4.32.2 baseline for old jobs. Linux and Windows are not supported by the current isolation layer.

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

## Lean and Mathlib for each run

Reuse a compatible shared environment. Install [Elan](https://github.com/leanprover/elan#installation) if it is missing, then inspect Yui's verified choices:

```sh
python3 -B nl0/scripts/yui.py lean-environments
```

One compatible pair can be selected automatically. If there are multiple choices, pass `--lean-root /path/to/lean --mathlib-root /path/to/mathlib` or the exact `--lean-version` and `--mathlib-version` to `prepare` or `run`. Missing or incompatible installations return an explicit selection request before proof work.

To install a user-selected pair into a new shared directory, for example:

```sh
python3 -B nl0/scripts/yui.py lean-environments --install \
  --lean-version 4.35.0 --mathlib-version v4.35.0
```

The installer obtains official Lean, the exact Mathlib checkout, its locked dependencies and compiled cache. It refuses to overwrite existing installations. **Do not run `lake update`** in an existing pinned project. Do not clone Mathlib separately for each proof project. Pure NL0 work needs no Lean selection. See [the selection and reproducibility contract](../nl0/references/lean-environments.md).

`YUI_LEAN_ROOT` (containing `bin/lean`), `YUI_MATHLIB_ROOT` (the checkout itself), `YUI_LEAN_VERSION` and `YUI_MATHLIB_VERSION` can explicitly select a pair for low-level tools and doctor. Frozen jobs keep their own choice even if these variables later change.

## Check before starting a proof

```sh
python3 -B "${YUI_SKILL_ROOT:-$HOME/.agents/skills/rigorous-proof}/nl0/scripts/yui.py" doctor
```

Proceed when the command reports `ENVIRONMENT-CHECKED`. It checks local dependencies without starting a model or proof job. A missing helper or a toolchain mismatch must be fixed first. This is a dependency check, not a full new-machine workflow test.
For pure NL0, use `doctor --no-lean`; the host check and NL0 entry do not require a Lean installation or a version choice.

Then follow [Use](../README.md#use), or the [test and benchmark reproduction prompts](https://github.com/yuiyuiui/Yui-results#local-setup). Keep generated results outside the installed skill.
