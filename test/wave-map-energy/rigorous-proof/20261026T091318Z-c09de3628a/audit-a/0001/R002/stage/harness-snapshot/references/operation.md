# Installed skill operation

This reference is for the invoking agent/operator, not an additional proof step.
All executable paths are relative to the installed skill, independent of the
Yui repository. Keep case materials and outputs outside the installation.

## Request and configuration

The invoking agent identifies the explicit proof files and requested track:
`nl0` (NL0 + Audit A), `full`, `translate` (accepted NL0 onward), or `audit-b`
(existing native build, fresh semantic review only). Ask about genuinely ambiguous
scope; never add Lean work to an explicitly NL0-only request. Read only explicitly
provided files and relevant rules. A directory input selects its `problem.md`,
not all neighboring documents. Extra sources are explicit `--material` inputs.
Text/TeX/Markdown is copied exactly; PDF extraction uses `pdftotext -layout` and
binds both original bytes and extracted text. An unreadable/scanned PDF needs an
explicitly checked text transcription before model execution.
The invoking agent checks that mathematical notation survives extraction before
freezing it as the supplied proof; a successful pdftotext exit is not a fidelity
judgment. Use an explicitly checked text source when the extraction is ambiguous.

Ask once for each missing active phase's model, reasoning effort and speed.
Retain choices supplied in the current request or already authorized in the
conversation. NL0 authors and Audit A share the NL0 profile. Source preparation,
local source review, interface authoring, all Lean proof jobs, assembly and Audit B
share the Lean profile. Do not ask about an unused phase. Do not invoke a separate
intent-classification model. Defaults in config.json require an explicit choice
(`--use-config-profiles`); installation defaults are not permission to bypass the
configuration question. The current isolated subscription carrier supports
Standard speed only. Unknown models/efforts/speeds are rejected explicitly;
model/effort availability is checked against local backend metadata and actual
transmitted/observed settings are recorded. No fallback or automatic upgrade.

## Entry commands

The user need not type commands or prepare intermediate files. After collecting
configuration, the invoking agent calls the installed entry. For example:

```sh
python3 -B /path/to/rigorous-proof/scripts/yui.py run /papers/example/proof.md \
  --track full \
  --nl0-model gpt-6.1-sol --nl0-effort high --nl0-speed standard \
  --lean-model gpt-6-luna --lean-effort high --lean-speed standard
```

Supply several problem paths to run independent cases together. For different
per-case sources, materials or profiles, `prepare` each separately, then use
`execute RUN_A RUN_B`. `prepare` makes no model/Lean calls. `--detach` starts
owned background case processes and returns their exact run paths; a parent
chat Stop is not a verified cancellation of these processes.

For translation pass `--track translate --source /accepted/nl0-case` and the Lean
profile. For audit-only pass `--track audit-b --audit /checked/native-audit-dir`.
An audit-only continuation discloses inherited native evidence and does not
claim a new proof, compilation or cold workflow result.

`--max-concurrency auto|N` limits local Lean proof jobs per case, not all model
stages. The current unknown-backend fallback for auto is two and is disclosed,
not called a maximum. `--case-concurrency K` separately limits independent cases;
by default the explicitly requested cases may run concurrently. Preparation and
reviews remain serial within each case. Python controllers occupy no model slot.
Backend/account limits may lower observed concurrency; retain actual outcomes.

## Local output ownership

Default permanent output is `<problem-directory>/rigorous-proof/<run-id>/`:

```text
inputs/                  exact declared documents and extraction provenance
job.json                 immutable request, profiles, runtime/input bindings
.yui-run.json            cleanup ownership marker
execution-status.json    coalesced status/usage/owned-process record
nl0/0001/                first author; later numbers are actual local repairs
audit-a/0001/            corresponding independent actual assessments
nl0-to-lean/preparation/  bounded shared-source decision and any local reviews
nl0-to-lean/0001/         interface, workflow/proof-run, assembly, audit-b-review
audit-b/                 final-review index, or audit-only continuation evidence
repairs/                 actual located diagnostic routing
logs/                    controller lifecycle output
case-result.json         actual acceptance scope and execution qualification
```

Only applicable stages are created. Multiple attempts are retained, not
silently overwritten. An explicit `--output` chooses another new directory;
it cannot overwrite an input or write inside the skill. Never create a global
repository results directory, scan parent folders for proof caches or read other
cases. OS temporary sandboxes are registered and cleaned on stage exit; they
are not persistent scientific output. Running several cases adds no files to
their common parent or the example root. Batch summaries are per-run metadata,
never worker-visible mathematical inputs.

## Completion and repair

Ordinary `normal` policy organizes authoring, actual Audit A, optional bounded
factoring, interface freeze, the existing proof queue, actual standalone assembly,
native inspection and fresh semantic Audit B. It never turns a type/schema check
into a mathematical PASS. Unchanged valid Audit A is checked and reused rather
than repeated. A factoring no-op is normal. The existing narrow delta route
leaves consumers with accepted background notes unchanged; it never drops notes
or bypasses their scoped-review requirement to extract a lemma.

Return located ordinary A defects to the author with the prior draft; preserve
unaffected material and inherit only exact qualified passing review scopes.
Recheck graph structure. Do not send old judgments to independent new reviewers.
A real B endpoint defect returns to interface/implementation work, preserving the
accepted source. Revised interfaces and dependent proofs must pass their gates
again. Native implementation feedback remains inside its current author/proof
stage. A revised target/hypothesis requires the source boundary, never a hidden
change to the accepted task. Supported mathematical obstacles, unresolved source
access/disagreement and execution faults remain visible. Do not resample an
unchanged rejected artifact/review until PASS. Execution has no imposed time,
token or call quota unless the user explicitly requests one.

Explicit `first-pass` policy stops on the first actual nonpass for measurement;
it is not the default user workflow. Developer reviewer calibration is separate
from a case's mathematical review. Calibration tests live in tests/tooling and
do not supply missing mathematical judgments or force every ordinary paper to
run a development exercise campaign first. Calibration status, when measured,
is reported separately; it is not fabricated as a prerequisite receipt.

## Remote-service recovery

The common model carrier retries positively identified temporary remote errors
(capacity, service availability, transient rate limiting or connection failures)
inside the same isolated thread. It retains actual drafts, source probes and
immutable tool receipts and uses the stage's existing short continuation input.
It does not repeat the initial task or execute a repeated completed tool-call ID
twice. The selected model, reasoning effort, speed, inputs and acceptance gates
remain fixed. A mathematical nonpass continues through normal located repair;
it is not a remote error. Authentication, billing/quota, unsupported settings,
context/output limits, cancellation and local/provenance faults are not remote
retries. An unclassified failure remains visible rather than guessed transient.

Retry waits start near 15 seconds and increase exponentially to 300 seconds,
with small jitter; a recorded valid `Retry-After` is a lower bound. There is no
fixed retry-count cutoff. Waiting makes no model call, remains cancellable, and
respects an explicit user deadline. Status reports `REMOTE_RETRY_WAIT` on the
affected task. `remote-retries.jsonl` preserves each reason, delay and original
failed turn; stage results record the policy and retry count. Original transport
faults and missing usage remain visible after recovery. A complete qualified
submission can proceed through actual mathematical gates; recovered execution
is never relabeled fault-free timing or a cold first-pass success.

For a run that already exited before this in-session recovery was available,
the invoking agent can continue explicitly selected interrupted NL0/Audit A work:

```sh
python3 -B /path/to/rigorous-proof/scripts/yui.py resume /paper/rigorous-proof/OLD_RUN --detach
```

This prepares a new owned run, checks that the old processes exited, and binds
the exact original inputs/profiles, actual last remote failure and selected old
evidence. The old run is preserved. `--prepare-only` inspects this boundary before
`execute`. A definitive release-ready NL0 is restored byte-for-byte; only exact
qualified complete Audit A scopes are inherited. Incomplete reviews get fresh
isolated contexts without prior judgments. An interrupted unreleased author
uses its original declared inputs, including an own draft only if that draft
was already an explicit input. This is a disclosed warm continuation, not a
resurrected carrier or a new cold attempt. Previous usage stays in the old run.
This entry supports authoring/Audit A recovery only and rejects unknown faults,
live old owners, changed inputs, completed workflows or unsupported later phases.
A former explicit deadline cannot be reset: a finite-budget old run without a
retained absolute deadline is rejected. New stages then use the common carrier's
in-session remote retry throughout the remaining workflow.

## Observe, stop and clean

```sh
python3 -B /path/to/rigorous-proof/scripts/yui.py status /paper/rigorous-proof/RUN
python3 -B /path/to/rigorous-proof/scripts/yui.py cancel /paper/rigorous-proof/RUN
python3 -B /path/to/rigorous-proof/scripts/yui.py cancel /paper/rigorous-proof/RUN --task T003
python3 -B /path/to/rigorous-proof/scripts/yui.py cleanup /paper/rigorous-proof/RUN
python3 -B /path/to/rigorous-proof/scripts/yui.py cleanup /paper/rigorous-proof/RUN --apply
```

Status writes coalesce to at most once per second, with a five-second liveness
heartbeat; both are program operations, not model calls. Usage updates on actual
provider reports, not every heartbeat. In-flight/missing usage remains unknown.
Cleanup previews by default, requires exact marked run roots, verifies process
PID/start identity/PGID and registered workspaces, and refuses deletion if exit
is unconfirmed. A selected-case stop/cleanup must not kill sibling cases or the
desktop application. Original problem files, installed skill and shared toolchain
are preserved. Cleanup can remove scientific results only when explicitly requested.

## Installation verification

Use `yui.py doctor` and `yui.py selftest`. Software tests and neutral controls are
inside this skill; no examples checkout, test/support directory, old results,
personal skills or chat memory are required. The current strong isolation backend
requires macOS sandbox-exec, an authenticated compatible Codex carrier, Python,
ripgrep and the pinned Lean/Mathlib environment. Missing prerequisites fail
explicitly; no unrestricted execution fallback is silently used. Selftests use
neutral fixtures and controlled executors, not a new mathematical benchmark.
