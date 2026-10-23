# Yui

Yui is a harness for making existing mathematical proofs explicit, auditable,
and ready for Lean formalization. It has two stages:

1. Build a self-contained structured natural-language proof (`NL0`) and run
   Audit A over its statements, dependencies, local arguments and citations.
2. Translate the accepted proof through typed local interfaces into Lean,
   assemble checked local proofs, and run Audit B over source fidelity and
   actual kernel types/dependencies.

Literature results that have not been proved in Lean remain explicitly listed
external premises. Checking a citation and proving that cited theorem in Lean
are separate tasks. Neither a schema check nor an LLM review is an automatic
proof of natural-language mathematics. No speed advantage is claimed yet.

## Layout

| Directory | Purpose |
| --- | --- |
| [`rigorous-proof/`](rigorous-proof/SKILL.md) | Complete runtime and the single `rigorous-proof` skill entry; internal regression tests are kept here |
| [`test/`](test/README.md) | Three user-selected mathematical exercises and clean full-workflow test records |
| [`benchmark/`](benchmark/README.md) | Protocol, parameters and eventual paper-scale direct/sequential/parallel comparisons |

Only `rigorous-proof/` is needed to carry the runtime to another location.
This repository does not depend on an NL2Lean checkout, a personal skill
installation, previous chats or a historical proof store.

## Execution profile

The selected profile is `gpt-6-luna`, reasoning `high`, Standard speed, through
an existing authenticated Codex subscription. There is no automatic model
fallback. Default concurrency is `auto`; when a backend hard limit is unknown,
the runtime discloses its conservative fallback and records observed concurrency.

The current strong local boundary uses macOS `sandbox-exec`, a fresh carrier
home/state/working directory, an upstream request allowlist, and offline Lean
checking. Unsupported execution boundaries fail visibly. Read
[`isolation.md`](rigorous-proof/references/isolation.md) before interpreting a
clean-run claim. The subscription carrier necessarily makes network model
requests; it does not grant model-visible access to personal files or tools.

## Quick start

```sh
python3 rigorous-proof/scripts/yui.py doctor
python3 rigorous-proof/scripts/yui.py selftest
```

Lean 4.32.2 and mathlib commit
`905b95818eb32af7874a58b427f50c1711a5e96c` are pinned. Use an existing compatible
installation, or configure `YUI_LEAN_ROOT`, `YUI_MATHLIB_ROOT`,
`YUI_CODEX_BINARY`, and `YUI_RG_BINARY`. `YUI_CODEX_HOME` selects the existing
subscription authentication directory; credentials are never committed.
See the skill for the staged author/review/translation commands.

## Test and benchmark status

The three supplied exercise screenshots are registered under `test/`. Their
missing textbook definitions and conventions must be resolved before mathematical
targets are frozen. A registered input is not a passing test.

No paper-scale benchmark has run in this repository. Future results must report
acceptance, end-to-end and phase time, all-agent token usage, failures, execution
health, model/prompt/toolchain versions, and requested/observed concurrency.
Development controls and historical NL2Lean observations are not benchmark scores.
