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

The repository root is the complete `rigorous-proof` skill: `SKILL.md` sits
beside `config.json`, `nl0/`, `nl02lean/` and `toolchain/`. Install/copy this root
directory together with those resources. There is no inner `rigorous-proof/`
directory to extract, and the checkout or installation directory may be renamed.
Then ask, for example:

- “Use rigorous-proof on this paper's existing proof, through NL0 and Audit A.”
- “Use rigorous-proof on this proof, including Lean and Audit B.”
- “Use rigorous-proof on these supplied proofs concurrently.”
- “Continue from this accepted NL0 into Lean.”

The invoking agent asks once for all missing settings, retaining already
specified choices. A phase profile includes the model, reasoning effort and speed.

| Requested track | Settings to supply or confirm |
| --- | --- |
| NL0 and Audit A only | NL0 phase profile and R-review worker count N |
| Accepted NL0 to Lean and Audit B | Lean phase profile and local Lean proof-worker count N |
| Complete workflow | Both phase profiles and one worker count N, used for R reviews and later Lean proofs in separate phases |

N must be an explicitly supplied or confirmed positive integer, including 1
for serial local work. Authors, global review, preparation, assembly and Audit B
remain serial within each case.
The harness then stages inputs, schedules independent
roles, handles located local repairs and records actual results. It does not
require the user to create task packets or dispatch reviewers manually.

Results go beside each problem, under `rigorous-proof/<run-id>/`. The skill
installation contains code and rules, never a global scientific output tree.
Here `rigorous-proof/` is the generated output-folder name, not a required
installation directory. Supply your own proof or paper outside the installed
skill. Mathematical example runs and paper benchmarks are kept separately from
this software checkout. Read each run's `case-result.json` and gate reports for
its actual acceptance scope.

## Runtime

The root directory contains the four mathematical responsibilities, their shared
Python controllers, software tests, and one skill entry. The optional
`library/` catalog and `tests/` software suite are not required for ordinary
proof execution. Keep the runtime directories beside `SKILL.md` when installing.
[Operator instructions](nl0/references/operation.md)
cover commands, profile selection, local output, repair, status and cleanup.
The commands below assume the repository or installed skill root is the working
directory. From another directory, invoke `nl0/scripts/yui.py` using its actual
installation path; bundled resources are resolved from the script location.

```sh
python3 -B nl0/scripts/yui.py doctor
python3 -B nl0/scripts/yui.py selftest
```

The current isolated carrier requires macOS `sandbox-exec`, Python, ripgrep,
an authenticated compatible Codex installation and Lean 4.32.2 with Mathlib
commit `905b95818eb32af7874a58b427f50c1711a5e96c`. Lean and Mathlib must be
installed separately; they are not bundled with the skill. Configure
`YUI_CODEX_BINARY`, `YUI_RG_BINARY` or `YUI_CODEX_HOME` when the other host tools
or authentication home are outside their usual locations. Credentials are
never committed. The current carrier supports Standard speed; unavailable
models, reasoning levels or speeds fail explicitly, without fallback.

### PDF text extraction

Reading PDF inputs or downloaded PDF sources requires at least one existing
text-extraction backend:

- `pdftotext` on PATH (provided by Poppler); Yui tries this first.
- The `pypdf` package installed in the Python interpreter running Yui, used
  when `pdftotext` is absent.

For example, create a virtual environment for the Python alternative:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install pypdf
.venv/bin/python -B nl0/scripts/yui.py doctor
```

Use that same `.venv/bin/python` for subsequent Yui commands. Yui does not
install extraction packages automatically. `doctor` checks the main runtime
and toolchain; PDF extraction is checked when a PDF is actually read.
Markdown, text and LaTeX inputs need neither PDF backend unless an external PDF
must also be read. Scanned/image-only PDFs need OCR or a checked transcription
before use; Yui has no automatic OCR step. Check extracted mathematical notation,
especially subscripts and fractions, before freezing it as proof input.

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
python3 -B nl0/scripts/yui.py doctor
```

The `doctor` command checks the environment and prints the resolved paths under
`resolved_environment`. Location overrides do not override version requirements:
[`toolchain/lock.json`](toolchain/lock.json) pins the Mathlib
commit, dependency revisions, dependency manifest and Lean version. Startup
checks reject incompatible versions or tracked source changes in Mathlib and
its pinned dependencies. The resolved Mathlib location is then used both for
source search/read tools and for Lean's compiled-library search paths.
See [`runtime_config.py`](nl0/scripts/runtime_config.py) for path
selection and checks, and [`pilot_common.py`](nl0/scripts/pilot_common.py)
for the Lean environment.

### What `toolchain/` contains

[`toolchain/`](toolchain/) stores environment
reproducibility records, not the Lean executable, Mathlib source or compiled
library cache:

- [`lock.json`](toolchain/lock.json) pins the Lean version,
  Mathlib commit, dependency revisions and dependency-manifest hash. Startup
  checks compare the installed environment against these requirements and
  reject tracked source changes. Local installation paths are resolved by
  `nl0/scripts/runtime_config.py`, using the defaults and overrides above.
  Historical model observations in this record do not select a run's model;
  phase defaults and explicit job profiles do that.
- [`migration.json`](toolchain/migration.json) records which
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

For an old author-repair run stopped by the inherited probe-directory allocator
defect, the verified runtime supports an explicitly authorized
`resume OLD_RUN --repair-local-tool --prepare-only`. It preserves the released
baseline, exact recorded repair obligations, prior evidence and costs; it rejects
live processes, changed evidence and unsupported partial checkpoints. See
[guarded local-tool recovery](nl0/references/operation.md#inherited-probe-directory-collisions).

### Foreground turn and ten-minute checks

The invoking owner normally uses detached execution. After dispatch and process
verification, it registers one host heartbeat covering the exact current runs,
records the returned automation ID and ends the foreground turn. Each heartbeat
performs one bounded check every ten minutes, then ends its turn. It reports
meaningful changes; routine unchanged checks stay quiet unless the user asks
for a report every time. No foreground sleep/poll loop is used.

`config.json` records this under `owner_observation`. A detached launch returns
a pending handoff with the observation command and scheduler prompt; it does
not claim that a schedule exists. The host must register the heartbeat. A host
without scheduling reports that limitation and returns manual commands instead
of silently keeping an observer model running. After actual terminal results
and verified process exits, the owner preserves the report and deletes the
completed heartbeat. See [the owner protocol](nl0/references/owner-observation.md).

## Optional personal Mathlib library

After completing a rigorous-proof workflow, users may choose to add useful
Mathlib theorems from its retained native-query receipts to the separate
[`library/`](library/README.md). Over time, this can form a convenient theorem
search catalog for their own fields, with reusable verified signature metadata.
The repository provides only three demonstration entries, not a comprehensive
Mathlib index or a source of preapproved mathematical answers.

The catalog is optional: normal Mathlib search, source reading and native
queries work without it. Yui looks in `library/` inside the installed skill root
by default; `YUI_LIBRARY_ROOT` can select another catalog directory.
Runs never update it automatically. See the [maintenance guide](library/README.md)
for finding a run's source receipts, explicitly importing selected declarations,
adding search tags, validating evidence and preserving version bindings.

## Optional reusable Lean strategies

After a rigorous-proof workflow, users may also choose to extract generalizable
Lean implementation strategies from its work records and maintain
[`nl02lean/bank/`](nl02lean/bank/rule.md).
Follow its [`rule.md`](nl02lean/bank/rule.md): record prerequisites,
failure conditions and verification, remove case-specific names and proof
material, and retain only general procedures or broad-field strategies.
The live bank supplies advice, not theorem permissions or accepted proofs.
Its current entries are generalized guidance with no claimed performance
validation. This maintenance is optional and never automatic; normal full
workflows keep strategy lookup disabled.

## Repository and evidence

| Path | Contents |
| --- | --- |
| `SKILL.md` | Skill entry and links to the two stages |
| `config.json` | Default profiles and execution configuration |
| `nl0/` | Stage one: NL0/Audit A rules (`references/`), programs (`scripts/`) and templates (`templates/`) |
| `nl02lean/` | Stage two: Lean/Audit B rules, programs, templates and optional strategy bank |
| `tests/` | One harness-wide software suite covering shared runtime, NL0, Lean and cross-stage behavior; see the [test guide](tests/README.md) |
| `toolchain/` | Version lock and historical source-migration records; actual tools are installed separately |
| `library/` | Optional user-maintained Mathlib catalog, three demonstrations and maintenance guide |

The [`nl0-audit-a-2026-10-25`](NL0_AUDIT_A_FREEZE.json) file records
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
targets require clarification. The [target-selection contract](nl0/references/target-selection.md)
binds the selected statements to the supplied document before model dispatch.

Missing external originals follow the [ordered source procedure](nl0/references/source-retrieval.md):
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
secondary statement exists, the [conditional-source route](nl0/references/conditional-sources.md)
can continue with warn.json/warn.md. Such completion is WORKFLOW-CONDITIONAL,
never ordinary full PASS; actual mathematical failures remain blocking.
