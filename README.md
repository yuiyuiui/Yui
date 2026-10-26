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

Each example also includes its archived `rigorous-proof/` results. The completed
runs below contain the final standalone Lean file, actual Audit A/B reports,
execution records and the result reported by the workflow:

| Example | Completed run | Standalone Lean file |
| --- | --- | --- |
| Geometry and measure | [Result](test/geometry-product-dimension/rigorous-proof/20261026T133531Z-7b8941cddb/case-result.json) | [Proof.lean](test/geometry-product-dimension/rigorous-proof/20261026T133531Z-7b8941cddb/nl0-to-lean/0001/workflow/audit-b/Proof.lean) |
| Lie algebras and representations | [Result](test/lie-module-irreducibility/rigorous-proof/20261026T100241Z-0a0dbbcb5b/case-result.json) | [Proof.lean](test/lie-module-irreducibility/rigorous-proof/20261026T100241Z-0a0dbbcb5b/nl0-to-lean/0001/workflow/audit-b/Proof.lean) |
| PDE | [Result](test/wave-map-energy/rigorous-proof/20261026T100247Z-61293f4243/case-result.json) | [Proof.lean](test/wave-map-energy/rigorous-proof/20261026T100247Z-61293f4243/nl0-to-lean/0001/workflow/audit-b/Proof.lean) |

Earlier stopped attempts remain alongside the completed Lie/PDE runs for
provenance. A directory's presence or a supplied proof does not establish
acceptance; consult that run's actual result and gate reports. These are
historical archives with machine-specific paths and runtime bindings, not
portable run configurations. Preserved dependency copies and relocation notes
document earlier runtime moves without rewriting the original receipts.

## Runtime

Only `rigorous-proof/` is required for the workflow. It contains the four
mathematical responsibilities, their shared Python controllers, software tests,
and one skill entry. [Operator instructions](rigorous-proof/references/operation.md)
cover commands, profile selection, local output, repair, status and cleanup.

```sh
python3 -B rigorous-proof/scripts/yui.py doctor
python3 -B rigorous-proof/scripts/yui.py selftest
```

The current isolated carrier requires macOS `sandbox-exec`, Python, ripgrep,
an authenticated compatible Codex installation and Lean 4.32.2 with Mathlib
commit `905b95818eb32af7874a58b427f50c1711a5e96c`. Configure `YUI_LEAN_ROOT`,
`YUI_MATHLIB_ROOT`, `YUI_CODEX_BINARY`, `YUI_RG_BINARY` or `YUI_CODEX_HOME` when
existing compatible installations are outside the usual locations. Credentials
are never committed. The current carrier supports Standard speed; unavailable
models, reasoning levels or speeds fail explicitly, without fallback.

Full and translation requests require an explicitly supplied or confirmed
positive proof-worker count N (`--max-concurrency N`). Missing counts and
`auto` cannot silently select a default at the public entry. NL0-only does not
ask for a proof-worker count. Independent-case concurrency is separate.
Preparation and reviews are serial within one case. There is no
default time/token/call budget. Explicit cancellation is supported; the parent
chat Stop button is not a verified cancellation of detached CLI processes.

Cleanup previews unless `--apply` is supplied. It targets only explicitly
selected owned run directories, confirms process exit and preserves original
inputs, the installed skill and the shared toolchain. See the operator instructions.

## Repository and evidence

| Path | Contents |
| --- | --- |
| `rigorous-proof/` | Complete skill, runtime, shared controllers and software controls |
| `test/` | Three mathematical examples and their archived proof/audit runs |
| `benchmark/` | Original paper input; temporary benchmark outputs have been removed |

The NL0/Audit A mathematical rules remain at the frozen
[`nl0-audit-a-2026-10-25`](rigorous-proof/NL0_AUDIT_A_FREEZE.json) baseline.
Its old paths/hashes describe that historical snapshot; current runs bind their
actual installed runtime separately. Operational integration does not relabel
historical reviews or manufacture new mathematical results.

No paper-scale benchmark or speed advantage is claimed. Future comparisons must
include preparation, audits, repairs, all-agent tokens, actual concurrency and
execution health, and distinguish original-proof direct baselines from
fixed-NL0 continuation experiments.
