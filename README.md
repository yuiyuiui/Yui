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

Current status: development candidate. The runtime and its regression controls
are executable; the three new exercise tests have **not** passed the complete
NL0/Audit A/Lean/Audit B workflow. The test inputs have been reset to three
fixed problem-and-proof files; previous generated runs have been cleared. See
the [test protocol](test/README.md) and
[software maintenance record](test/support/MAINTENANCE.md).

## Layout

| Directory | Purpose |
| --- | --- |
| [`rigorous-proof/`](rigorous-proof/SKILL.md) | Complete runtime and the single `rigorous-proof` skill entry; internal regression tests are kept here |
| [`test/`](test/README.md) | Three fixed exercise/proof inputs and clean-run test tools |
| [`benchmark/`](benchmark/README.md) | Protocol, parameters and eventual paper-scale direct/sequential/parallel comparisons |

Only `rigorous-proof/` is needed to carry the runtime to another location.
This repository does not depend on an NL2Lean checkout, a personal skill
installation, previous chats or a historical proof store.

## Execution profile

The selected profile is `gpt-6.1-sol`, reasoning `high`, Standard speed, through
an existing authenticated Codex subscription. There is no automatic model
fallback. Default concurrency is `auto`; when a backend hard limit is unknown,
the runtime discloses its conservative fallback and records observed concurrency.
This limit applies to Lean proof jobs per case. NL0 authoring, preparation,
Audit A, interface work and Audit B use a separate serial lane. Both lanes share
one all-stage cost ledger. The test batch has a separate concurrent-case limit.
Each case writes `nl0-to-lean/execution-status.json`, with coalesced one-second
updates and a five-second heartbeat. Recording makes no model calls. See the
[execution protocol](rigorous-proof/translation/references/execution-protocol.md)
for queues, scoped cancellation and the desktop main-chat Stop limitation.

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

Inspect supplied artifacts or recorded costs without starting a model:

```sh
python3 rigorous-proof/scripts/yui.py case-status /absolute/source-case
python3 rigorous-proof/scripts/yui.py metrics /absolute/run
```

Lean 4.32.2 and mathlib commit
`905b95818eb32af7874a58b427f50c1711a5e96c` are pinned. Use an existing compatible
installation, or configure `YUI_LEAN_ROOT`, `YUI_MATHLIB_ROOT`,
`YUI_CODEX_BINARY`, and `YUI_RG_BINARY`. `YUI_CODEX_HOME` selects the existing
subscription authentication directory; credentials are never committed.
See the skill for the staged author/review/translation commands.

For a clean text stage, explicitly stage its inputs and prompt:

```sh
python3 rigorous-proof/scripts/yui.py stage /absolute/prompt.txt \
  --phase nl0-authoring --kind nl0 --case-id selected-case \
  --inputs /absolute/inputs.json --out /absolute/new-run
python3 rigorous-proof/scripts/yui.py exposure /absolute/new-run
python3 rigorous-proof/scripts/yui.py usage /absolute/new-run
```

The input manifest lists `{id,path,sha256}` documents under its own directory.
`--kind nl0` checks structural source artifacts; it does not issue Audit A.
The default JSON stage is suitable for candidate drafts and actual review
records, which still pass through the dedicated A/B gates. There is no claimed
universal automatic paper-to-Lean compiler behind this command.

## Test and benchmark status

The three supplied exercises are fixed under `test/`, each in a single
`problem.md` containing the original statement, approved target interpretation
and detailed natural-language proof. They cover Hausdorff dimension, arbitrary
admissible sl2 lattices, and sphere-valued wave-map energy. Old NL0s, audit
receipts and test logs have been cleared to prepare a fresh run; the current
checkout contains no accepted mathematical test result. Supplied proofs do not
confer acceptance.

Preview or perform a scoped test cleanup without calling a model:

```sh
python3 -B test/support/cleanup_tests.py
python3 -B test/support/cleanup_tests.py --apply
```

The cleanup confirms owned process termination before deleting generated test
outputs and registered temporary workspaces. It preserves the fixed problem
files, runtime, test code, benchmarks and shared toolchain. See
[the test protocol](test/README.md) for ownership checks and the cancellation
boundary. Generated runs are ignored by Git; curated future results should be
published deliberately after review.

No paper-scale benchmark has run in this repository. Future results must report
acceptance, end-to-end and phase time, all-agent token usage, failures, execution
health, model/prompt/toolchain versions, and requested/observed concurrency.
Development controls and historical NL2Lean observations are not benchmark scores.
Review completion, bounded repairs and conservative inherited evidence are
described in [the execution contract](rigorous-proof/references/review-execution.md).
The small [source catalog](rigorous-proof/library/foundations.json) contains
eight natively checked pinned declarations, with complete signatures and original
query cost. It grants no source/application review or blanket Mathlib permission.
