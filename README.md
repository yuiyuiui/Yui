# Yui

Yui is a harness for making an existing mathematical proof explicit, auditable,
and ready for Lean. Its single entry is the `rigorous-proof` skill:

1. Write structured natural-language proof `NL0` and perform independent Audit A.
2. Optionally translate the accepted proof through local Lean obligations,
   assemble the checked proofs, and perform independent Audit B.

Audit B checks every external theorem and the complete target, including all
hypotheses, against the actual Lean statements. The pinned Mathlib environment
is available freely. Literature theorems not proved in Lean remain explicit
external premises. An LLM review is not a kernel proof of natural-language
mathematics, and a successful compilation alone is not source-fidelity approval.

## Use

Install/copy the complete `rigorous-proof/` directory as a skill. Then ask, for
example:

- “Use rigorous-proof on this paper's existing proof, through NL0 and Audit A.”
- “Use rigorous-proof on this proof, including Lean and Audit B.”
- “Use rigorous-proof on these three supplied problems concurrently.”
- “Continue from this accepted NL0 into Lean.”

The invoking agent asks once for all missing settings, retaining already
specified choices. NL0-only needs its model/reasoning/speed profile. Translation
from accepted NL0 needs the Lean profile and an explicit per-case proof-worker
count. A full workflow needs both phase profiles and that worker count.
The harness then stages inputs, schedules independent
roles, handles located local repairs and records actual results. It does not
require the user to create task packets or dispatch reviewers manually.

Results go beside each problem, under `rigorous-proof/<run-id>/`. The skill
installation contains code and rules, never a global scientific output tree.
Three supplied examples are ordinary inputs to the same runtime:

| Example | Original problem and supplied natural-language proof |
| --- | --- |
| Geometry and measure | [Hausdorff product dimension](test/geometry-product-dimension/problem.md) |
| Lie algebras and representations | [Admissible lattice reduction](test/lie-module-irreducibility/problem.md) |
| PDE | [Sphere-valued wave-map energy](test/wave-map-energy/problem.md) |

Each example also includes its latest completed `rigorous-proof/` result. The
runs below contain the final standalone Lean file, actual Audit A/B reports,
execution records and the result reported by the workflow:

| Example | Completed run | Standalone Lean file |
| --- | --- | --- |
| Geometry and measure | [Result](test/geometry-product-dimension/rigorous-proof/20261026T133531Z-7b8941cddb/case-result.json) | [Proof.lean](test/geometry-product-dimension/rigorous-proof/20261026T133531Z-7b8941cddb/nl0-to-lean/0001/workflow/audit-b/Proof.lean) |
| Lie algebras and representations | [Result](test/lie-module-irreducibility/rigorous-proof/20261026T100241Z-0a0dbbcb5b/case-result.json) | [Proof.lean](test/lie-module-irreducibility/rigorous-proof/20261026T100241Z-0a0dbbcb5b/nl0-to-lean/0001/workflow/audit-b/Proof.lean) |
| PDE | [Result](test/wave-map-energy/rigorous-proof/20261026T100247Z-61293f4243/case-result.json) | [Proof.lean](test/wave-map-energy/rigorous-proof/20261026T100247Z-61293f4243/nl0-to-lean/0001/workflow/audit-b/Proof.lean) |

Only the latest completed run is kept for each example; earlier attempts remain
in Git history. Consult each run's actual result and gate reports for its
acceptance scope. These historical archives contain machine-specific paths and
runtime bindings. Preserved evidence, dependency copies and relocation notes
retain the completed run's provenance without rewriting the original receipts.

## Runtime

The only directory you need to copy from this repository is `rigorous-proof/`.
It contains the four mathematical responsibilities, their shared Python
controllers, software tests, and one skill entry.
[Operator instructions](rigorous-proof/nl0/references/operation.md)
cover commands, profile selection, local output, repair, status and cleanup.

```sh
python3 -B rigorous-proof/nl0/scripts/yui.py doctor
python3 -B rigorous-proof/nl0/scripts/yui.py selftest
```

The current isolated carrier requires macOS `sandbox-exec`, Python, ripgrep,
an authenticated compatible Codex installation and Lean 4.32.2 with Mathlib
commit `905b95818eb32af7874a58b427f50c1711a5e96c`. Lean and Mathlib must be
installed separately; they are not bundled with the skill. Configure
`YUI_CODEX_BINARY`, `YUI_RG_BINARY` or `YUI_CODEX_HOME` when the other host tools
or authentication home are outside their usual locations. Credentials are
never committed. The current carrier supports Standard speed; unavailable
models, reasoning levels or speeds fail explicitly, without fallback.

### Lean and Mathlib locations

The controller resolves these paths before model work starts. It does not ask
the LLM to locate Mathlib, scan the computer for repositories, or download a
missing installation. Path discovery is independent of the optional metadata
catalog in [`library/`](library/README.md).

| Dependency | Environment override | Default when no override is supplied |
| --- | --- | --- |
| Mathlib repository root, containing `Mathlib/` and `.lake/` | `YUI_MATHLIB_ROOT` | `~/formalization-tools/lean-mathlib-v4.32.2/mathlib` |
| Lean installation root, containing `bin/lean` | `YUI_LEAN_ROOT` | `~/formalization-tools/lean-mathlib-v4.32.2/lean`, then `~/.elan/toolchains/leanprover--lean4---v4.32.2` if the first path is absent |

Here `~` means the home directory of the user running Yui, not a fixed username.
Existing symbolic links are resolved to their targets. An explicit override
takes precedence: an invalid override fails instead of falling back to a
default. Missing default installations also fail.

For a compatible installation elsewhere, set the paths in the environment
used to launch Yui:

```sh
export YUI_MATHLIB_ROOT="/absolute/path/to/mathlib4"
export YUI_LEAN_ROOT="/absolute/path/to/lean-4.32.2"
python3 -B rigorous-proof/nl0/scripts/yui.py doctor
```

The `doctor` command checks the environment and prints the resolved paths under
`resolved_environment`. Location overrides do not override version requirements:
[`toolchain/lock.json`](rigorous-proof/toolchain/lock.json) pins the Mathlib
commit, dependency revisions, dependency manifest and Lean version. Startup
checks reject incompatible versions or tracked source changes in Mathlib and
its pinned dependencies. The resolved Mathlib location is then used both for
source search/read tools and for Lean's compiled-library search paths.
See [`runtime_config.py`](rigorous-proof/nl0/scripts/runtime_config.py) for path
selection and checks, and [`pilot_common.py`](rigorous-proof/nl0/scripts/pilot_common.py)
for the Lean environment.

### What `toolchain/` contains

[`rigorous-proof/toolchain/`](rigorous-proof/toolchain/) stores environment
reproducibility records, not the Lean executable, Mathlib source or compiled
library cache:

- [`lock.json`](rigorous-proof/toolchain/lock.json) pins the Lean version,
  Mathlib commit, dependency revisions and dependency-manifest hash. Startup
  checks compare the installed environment against these requirements and
  reject tracked source changes. Local installation paths are resolved by
  `nl0/scripts/runtime_config.py`, using the defaults and overrides above.
  Historical model observations in this record do not select a run's model;
  phase defaults and explicit job profiles do that.
- [`migration.json`](rigorous-proof/toolchain/migration.json) records which
  source repository/commit this harness was imported from and the original
  source checks and execution boundary. It is historical provenance, not an
  installer or an automatic toolchain-upgrade script.

Actual Lean/Mathlib installations remain outside Yui. Editing the lock does
not install the corresponding versions; a version upgrade requires preparing
and validating a matching environment separately.

### Execution and cleanup

NL0, full and translation requests require an explicitly supplied or confirmed
positive worker count N (`--max-concurrency N`). Missing counts and
`auto` cannot silently select a default at the public entry. N controls local
R-node reviews and local Lean proof work in separate phases. Independent-case
concurrency is separate. Authors, global review, preparation, assembly and
Audit B are serial within one case. There is no
default time/token/call budget. Explicit cancellation is supported; the parent
chat Stop button is not a verified cancellation of detached CLI processes.

Cleanup previews unless `--apply` is supplied. It targets only explicitly
selected owned run directories, confirms process exit and preserves original
inputs, the installed skill and the shared toolchain. See the operator instructions.

## Optional personal Mathlib library

After completing a rigorous-proof workflow, users may choose to add useful
Mathlib theorems from its retained native-query receipts to the separate
[`library/`](library/README.md). Over time, this can form a convenient theorem
search catalog for their own fields, with reusable verified signature metadata.
The repository provides only three demonstration entries, not a comprehensive
Mathlib index or a source of preapproved mathematical answers.

The catalog is optional: normal Mathlib search, source reading and native
queries work without it. Yui looks beside the installed `rigorous-proof/`
directory by default; `YUI_LIBRARY_ROOT` can select another catalog directory.
Runs never update it automatically. See the [maintenance guide](library/README.md)
for finding a run's source receipts, explicitly importing selected declarations,
adding search tags, validating evidence and preserving version bindings.

## Optional reusable Lean strategies

After a rigorous-proof workflow, users may also choose to extract generalizable
Lean implementation strategies from its work records and maintain
[`rigorous-proof/nl02lean/bank/`](rigorous-proof/nl02lean/bank/rule.md).
Follow its [`rule.md`](rigorous-proof/nl02lean/bank/rule.md): record prerequisites,
failure conditions and verification, remove case-specific names and proof
material, and retain only general procedures or broad-field strategies.
The live bank supplies advice, not theorem permissions or accepted proofs.
Its current entries are generalized guidance with no claimed performance
validation. This maintenance is optional and never automatic; normal full
workflows keep strategy lookup disabled.

## Repository and evidence

| Path | Contents |
| --- | --- |
| `rigorous-proof/` | Complete skill, runtime, shared controllers and software controls |
| `rigorous-proof/nl0/` | Stage one: NL0/Audit A rules (`references/`), programs (`scripts/`) and templates (`templates/`) |
| `rigorous-proof/nl02lean/` | Stage two: Lean/Audit B rules, programs, templates and optional strategy bank |
| `rigorous-proof/tests/` | One harness-wide software suite covering shared runtime, NL0, Lean and cross-stage behavior; see the [test guide](rigorous-proof/tests/README.md) |
| `rigorous-proof/toolchain/` | Version lock and historical source-migration records; actual tools are installed separately |
| `library/` | Optional user-maintained Mathlib catalog, three demonstrations and maintenance guide |
| `test/` | Three mathematical examples and their archived proof/audit runs |
| `benchmark/` | Original paper input; temporary benchmark outputs have been removed |

The [`nl0-audit-a-2026-10-25`](rigorous-proof/NL0_AUDIT_A_FREEZE.json) file records
a historical baseline, including its old paths and hashes. Current runs bind
their actual installed rules and runtime separately. The current elementary
profile keeps logic, finite calculations and core typed syntax; it no longer
contains a domain vocabulary. Each problem declares its own objects and notation.
Structural prechecks validate explicit records and references, while Audit A
checks mathematical meaning, hidden hypotheses and theorem applications across
all subjects. These changes do not relabel historical reviews or manufacture
new mathematical results.

No paper-scale benchmark or speed advantage is claimed. Future comparisons must
include preparation, audits, repairs, all-agent tokens, actual concurrency and
execution health, and distinguish original-proof direct baselines from
fixed-NL0 continuation experiments.

## Target selection and source qualifications

For a clear intended theorem, the invoking agent extracts its complete target
and proceeds without an extra user question. Multiple independent plausible
targets require clarification. The [target-selection contract](rigorous-proof/nl0/references/target-selection.md)
binds the selected statements to the supplied document before model dispatch.

Missing external originals follow the [ordered source procedure](rigorous-proof/nl0/references/source-retrieval.md):
arXiv full text first, Google full-text search, Google DOI discovery, then
Sci-Hub lookup with the confirmed DOI. Already supplied adequate originals are
reused. The author and global reviewer receive explicit engine selection and
an optional normal local-Chrome readback tool for JavaScript/verification pages.
This does not require controlling the user's visible in-app browser. It uses
an existing Node/Playwright/Chrome installation, a fresh browser profile and
ordinary site controls; the linked guide documents discovery and environment
overrides. No browser package or paid service is installed automatically.
Missing tools, unresolved verification, redirects and access failures are
retained as actual receipts. Downloads preserve original bytes, version and
hashes; the relevant theorem, definitions and hypotheses still require review.
When the full primary text is unavailable but a complete explicit
secondary statement exists, the [conditional-source route](rigorous-proof/nl0/references/conditional-sources.md)
can continue with warn.json/warn.md. Such completion is WORKFLOW-CONDITIONAL,
never ordinary full PASS; actual mathematical failures remain blocking.

The direct benchmark [prompt](benchmark/pure-model-result/prompt.md) and
[native continuation runner](benchmark/pure-model-result/runner.py) retain one
session across incomplete normal turns. The runner checks the complete Lean
file, exported declaration and trust report, and records CANDIDATE_READY only.
Independent semantic acceptance remains a separate required assessment.
The native CLI continuation uses the [documented exec/resume interface](https://learn.chatgpt.com/docs/non-interactive-mode)
and the locally checked CLI flags. No new benchmark is launched by these edits.
