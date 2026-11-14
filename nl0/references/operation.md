# Installed skill operation

For a new public case, the job snapshot pins the route in [workflow.json](../../workflow/workflow.json). See the [workflow guide](../../workflow/SKILL.md) for the native CLI, final directory tree, explicit verification, optional stage breakpoints and operator attachments. After complete cleanup the four artifacts remain in `RUN/delivery`. For a stopped or interrupted case, read its actual phase and scope in `run.json`. Historical cases use their own frozen runtime and recovery instructions.

This reference is for the invoking agent/operator, not an additional proof step.
All executable paths are relative to the installed skill, independent of the
Yui repository. Keep case materials and outputs outside the installation.

## Request and configuration

Formalization goal is separate from the stage track. Keep `conditional` as the
default, including `--track full`. For an explicit complete/unconditional request
use `--track full --formalization unconditional` and follow
[basis preparation and discharge](basis.md). It reuses the existing NL0/Lean
profiles and worker settings. Do not repeat configuration collection.
Class-4 choices use `yui.py basis-decision RUN --incident ID --action
stop|continue|accept-conditional`, only after the actual user selects an action.
Show exact residuals and their retained source evidence. This choice is separate
from B-final decisions and never silently downgrades an unconditional goal.
Supported operational continuations preserve the original goal and prepared
basis; they do not rerun 2basis or ask for residual approval again.
For unconditional delivery include `b2lean/Proof.lean`, export `YuiClosed.P`,
the final `check.json`/`report.json`, and any `b2lean/warn.json`/`warn.md`.
The conditional intermediate receipt alone cannot close this goal.

The invoking agent identifies the explicit proof files and requested track:
`nl0` (NL0 + Audit A), `full`, `translate` (accepted NL0 onward), or `audit-b`
(existing native build, fresh semantic review only). Ask about genuinely ambiguous
scope; never add Lean work to an explicitly NL0-only request. Read only explicitly
provided files and relevant rules. A directory input selects its `problem.md`,
not all neighboring documents. Extra sources are explicit `--material` inputs.
Text/TeX/Markdown is copied exactly; PDF extraction uses `pdftotext -layout` or a disclosed pypdf fallback and
binds both original bytes and extracted text. An unreadable/scanned PDF needs an
explicitly checked text transcription before model execution.
The invoking agent checks that mathematical notation survives extraction before
freezing it as the supplied proof; a successful pdftotext exit is not a fidelity
judgment. Use an explicitly checked text source when the extraction is ambiguous.

Reuse profiles selected during local adaptation unless the user overrides them.
Ask once for each active phase whose model, reasoning effort or speed remains
missing. Retain choices supplied in the current request or already authorized
in the conversation. NL0 authors and Audit A share the NL0 profile. Source preparation,
local source review, interface authoring, all Lean proof jobs, assembly and Audit B
share the Lean profile. Do not ask about an unused phase. Do not invoke a separate
intent-classification model. Defaults in config.json require an explicit choice
(`--use-config-profiles`); installation defaults are not permission to bypass the
configuration question. The current isolated subscription carrier supports
Standard speed only. Unknown models/efforts/speeds are rejected explicitly;
model/effort availability is checked against local backend metadata and actual
transmitted/observed settings are recorded. No fallback or automatic upgrade.

Collect the following settings before preparing or dispatching a new run.
A phase profile means model, reasoning effort and speed:

Formal tracks also use [per-run Lean/Mathlib selection](lean-environments.md).
Discover and verify local pairs, preserve explicit user paths/versions and ask
once when the choice is missing, incompatible or ambiguous. Pure NL0 needs no
Lean selection. Every private worker inherits its run's profiles and scientific
environment while owning a separate role conversation.

| Requested track | Required user settings |
| --- | --- |
| NL0 and Audit A only (`nl0`) | NL0 phase profile; optional worker cap N |
| Accepted NL0/Audit A to Lean (`translate`) | Lean phase profile; optional worker cap N |
| Complete workflow (`full`) | NL0 phase profile and Lean phase profile; optional worker cap N |

Ask for all missing phase-profile settings together and retain supplied values.
Do not ask for an omitted worker count: the default `auto` uses the current
phase's full node count, R for local Audit A review/repair and T for local Lean
proofs, including shared lemmas and representation conversions. Resolve R after
global acceptance and T from the frozen Lean plan; recompute auto if a reviewed
revision changes either graph. Before a graph exists, report the effective
count as pending rather than guessing a number. There is no fixed fallback.
An explicit N must be a positive integer, including 1 for serial local work,
and caps each separate phase. For several cases, N applies independently to each
case unless different per-case settings were requested.

An `audit-b`-only continuation has no proof queue and needs only its Lean phase
profile, not N. `execute` and supported `resume` reuse an existing job's frozen
settings; they do not recollect values or change a historical worker count.
These configuration questions do not change the scheduling architecture:
Initial/global NL0 authors, global Audit A, preparation, assembly and final acceptance
remain serial. Local R reviewers and their repair authors share N active slots.
Later Lean proofs use their own phase-sized or explicitly capped lane; waiting roles use no slot.

## Entry commands

The user need not type commands or prepare intermediate files. After [resolving the target](target-selection.md) and collecting
configuration, the invoking agent calls the installed entry. For example:

```sh
python3 -B /path/to/Yui/nl0/scripts/yui.py run /papers/example/proof.md \
  --track full \
  --nl0-model gpt-6.1-sol --nl0-effort high --nl0-speed standard \
  --lean-model gpt-6-luna --lean-effort high --lean-speed standard \
  --max-concurrency 5 --target-file /papers/example/target-selection.json --detach
```

Supply several problem paths to run independent cases together. For different
per-case sources, materials or profiles, `prepare` each separately, then use
`execute RUN_A RUN_B`. `prepare` makes no model calls; formal tracks perform an
isolated native environment-compatibility check before freezing the job. `--detach` starts
owned background case processes and returns their exact run paths; a parent
chat Stop is not a verified cancellation of these processes.

Follow the [owner monitoring procedure](owner-observation.md). Verify the
detached process identities and prefer a host-permitted ten-minute scheduled
wakeup. Record its actual ID before ending the owner turn. If scheduling is
restricted, unavailable or unsuccessful, continue the same run with ten-minute
waits in the owning turn and one bounded observation per interval. The entry
records the selected mode for subsequent observation.

For translation pass `--track translate --source /accepted/nl0-case` and the Lean
profile. Optionally pass `--max-concurrency N` to cap local work. For audit-only pass
`--track audit-b --audit /checked/native-audit-dir`.
An audit-only continuation discloses inherited native evidence and does not
claim a new proof, compilation or cold workflow result.

The public `run`/`prepare` entry defaults to `--max-concurrency auto` for NL0,
full and translation tracks. Auto resolves independently to the current R/T
node count. An optional positive N limits both separate local phases, not all
model stages. Existing frozen jobs retain their bound settings/runtime.
`--case-concurrency K` separately limits independent cases;
by default the explicitly requested cases may run concurrently. The author, global review, preparation, assembly and Audit B
remain serial within each case. Python controllers occupy no model slot.
Backend/account limits may lower observed concurrency; retain actual outcomes.

## Local output ownership

Default permanent output is `<problem-directory>/rigorous-proof/<run-id>/`:

```text
inputs/                  exact declared documents and extraction provenance
job.json                 immutable request, profiles, runtime/input bindings
runtime/                 owned allowlisted executable/rules/strategy snapshot
runtime-manifest.json    original-to-snapshot hashes, no credentials/memories
.yui-run.json            cleanup ownership marker
execution-status.json    coalesced status/usage/owned-process record
nl0/0001/                first author; later numbers are actual local repairs
audit-a/0001/            corresponding independent actual assessments
nl0-to-lean/preparation/  bounded shared-source decision and any local reviews
nl0-to-lean/0001/         interface, workflow/proof-run, optional assembly repair, optional audit-b-final
audit-b/                 final-review index, or audit-only continuation evidence
repairs/                 actual located diagnostic routing
logs/                    controller lifecycle output
case-result.json         actual acceptance scope and execution qualification
```

New v5/v6 jobs and v3 runtime snapshots do not contain a personal theorem catalog.
Native Mathlib queries save their selected-environment evidence inside the
owning stage; that evidence is not a cross-task theorem directory. Old frozen
jobs retain read-only format compatibility, including the hashes of any old
catalog files. Only their old executable snapshot receives the retired catalog
setting. New stages never discover or consult it.

Only applicable stages are created. Multiple attempts are retained, not
silently overwritten. An explicit `--output` chooses another new directory;
it cannot overwrite an input or write inside the skill. Never create a global
repository results directory, scan parent folders for proof caches or read other
cases. OS temporary sandboxes are registered and retained until their specified successful role handoff or explicit user cancellation; they
are not persistent scientific output. Running several cases adds no files to
their common parent or the example root. Batch summaries are per-run metadata,
never worker-visible mathematical inputs.

Prepared jobs launch their queue/case scripts from the retained `runtime/`, not
the mutable installed checkout. Updates to the installation affect new jobs;
they do not rewrite active snapshot bindings. Keep runtime dependencies with
the evidence. Older jobs lacking snapshots retain their original validation.
Proof round diagnostics and selected retained rounds are documented in
[proof repair](../../nl02lean/references/proof-repair.md).

## Completion and repair

Ordinary `normal` policy organizes authoring, actual Audit A, optional bounded
factoring, interface freeze, the existing proof queue, actual standalone assembly,
native inspection and machine final acceptance against independently reviewed frozen semantics. It never turns a type/schema check
into a mathematical PASS. Unchanged valid Audit A is checked and reused rather
than repeated. A factoring no-op is normal. The existing narrow delta route
leaves consumers with accepted background notes unchanged; it never drops notes
or bypasses their scoped-review requirement to extract a lemma.

Follow the retained global/local roles in review-execution.md. Return complete
global findings to the same author before local dispatch; node-local repair uses
its own separate author. Inherit only exact qualified scopes. Restore global roles
for genuine public-context changes, draining active local work before repair.
A failed global or local Audit A review is bound to the rejected material.
Submitting that material again pauses with `REPAIR_UNCHANGED` or `REPAIR_CYCLE`
and retains the original findings. A change to the relevant proof or evidence
permits a fresh review. For a located objection to a protected basis field, see
the explicit `resume RUN --repair-basis` procedure in [the basis workflow](basis.md).

A pre-freeze interface defect returns to the same preprocessing author/reviewer.
After freeze, E/P and their defining meanings cannot be rewritten by local or
connection authors; a genuine frozen-contract defect waits for the user. Native implementation feedback remains inside its current author/proof
stage. A revised target/hypothesis requires the source boundary, never a hidden
change to the accepted task. Supported mathematical obstacles, unresolved source
access/disagreement and execution faults remain visible. Retain the same assigned
author/reviewer through revisions; do not create fresh reviewers just to reroll a
verdict. Unchanged content or repeated evidence alone does not authorize a pause.
Execution has no imposed time,
token or call quota unless the user explicitly requests one.

Explicit `first-pass` policy stops on the first actual nonpass for measurement;
it is not the default user workflow. Developer reviewer calibration is separate
from a case's mathematical review. Calibration tests live in tests/tooling and
do not supply missing mathematical judgments or force every ordinary paper to
run a development exercise campaign first. Calibration status, when measured,
is reported separately; it is not fabricated as a prerequisite receipt.

## Recoverable controller faults

Normal policy repairs ordinary mathematical feedback in its assigned author or
proof stage; an Audit A/B nonpass is not by itself a first-pass stop. Classify
execution failures separately. A verified bookkeeping defect must not force
the proof and all completed independent reviews to be repeated.

Inherited evidence is checked before any remaining review model is called.
If a legacy path-to-key index is wrong but the original judgment and matching
source bytes are intact and hash-bound, collection reconstructs a new index,
validates it with the unchanged full checks, and proceeds. It records the old
and new bindings in bookkeeping-repairs.json. This operation changes no theorem,
judgment, source content or acceptance rule and makes no model/native calls.
Missing/tampered evidence, changed context, unqualified execution or a nonpassing
judgment cannot be repaired into a PASS by this route.

After repairing this known defect in an already stopped run, use
`yui.py resume OLD_RUN --repair-evidence --detach`. The guarded entry requires
the recorded index error to be reproducible and all required actual reviews
to be complete and qualified. It restores the unchanged released source through
its bound lineage and inherits completed scopes instead of asking models again.
An unknown program defect preserves the current phase/artifact checkpoint and
requires a verified software fix; it is not a mathematical rejection, permission
to rewrite proof rules, or a reason to replay the whole problem from scratch.

### Inherited probe-directory collisions

Library probes reserve a fresh numbered evidence directory atomically. Existing
normal directories, including inherited receipts and failed probes, are retained
and skipped. A new query returns its actual newly reserved receipt path and hash;
an occupied directory never supplies implicit source approval. Unsafe occupied
paths and unrelated I/O failures remain explicit execution faults, not failed
mathematical judgments. The stage log retains the failing tool and original
exception before cleanup, and the case result preserves that execution cause.

For an old run stopped by the former inherited-directory allocator defect, after
installing and verifying the software repair, an explicitly authorized owner can
prepare a guarded continuation:

```sh
python3 -B /path/to/Yui/nl0/scripts/yui.py resume /paper/rigorous-proof/OLD_RUN --repair-local-tool --prepare-only
```

This narrowly supports a normal-policy NL0 author-repair stage that stopped on
an actual `probe_library` directory collision before any new draft was submitted.
It verifies complete owned PID/start/PGID and group exits, the actual terminal
tool call, the unchanged inherited receipt, the released baseline, frozen input
manifest and exact located review obligations. Unknown faults, live groups,
changed evidence, a partial repair draft or changed configuration are rejected.
The new job starts at the located author-repair boundary; it does not replay
initial authoring, grant Audit A, revive the exited model thread or discard the
old run and costs. Changed contexts require fresh independent review under the
existing exact-scope reuse rules. Inspect the prepared job, then use `execute
NEW_RUN --detach` and the normal host-monitor handoff. The same guarded resume
can dispatch directly with `--detach` when prepare-only inspection is not needed.

## Remote-service recovery

### Exited proof queue after ENOSPC

After the user explicitly requests recovery, use:

```sh
python3 -B /path/to/Yui/nl0/scripts/yui.py resume OLD_RUN --repair-proof-io --prepare-only
python3 -B /path/to/Yui/nl0/scripts/yui.py execute NEW_RUN --detach
```

This narrow route requires verified exits of all owned processes/groups, an
unlimited normal full/unconditional job, actual structured ENOSPC errors in the
frozen local proof phase, intact native input/profile readback and the unchanged
bound source/A/interface. It rejects existing terminal/queue result records,
unknown faults, provenance/isolation failures and protected or source-changing
diagnoses. The old run and all fault/cost records remain unchanged. No old
unverified source or completed review is relabeled.

The new job retains track=full and formalization=unconditional. It inherits the
checked 2basis and Audit A at their exact checkpoint, repeats independent review
of the unchanged interface, and passes saved local submissions to the current
native checker. A separate candidate view replaces no missing historical queue
report. Unfinished authors get only intact own-node drafts/helpers and completed
local diagnostic advice in fresh isolated contexts; historical checks do not
grant acceptance. Current local checks, assembly, machine Audit B and b2lean
remain mandatory. This is a disclosed warm continuation, with new runtime
bindings and separate usage, not resurrection of an exited native thread.

The preparation verifies an actual writable-storage operation. Current free
space does not establish the cause of historical ENOSPC or guarantee future
writes. A truncated input/profile/draft record prevents this exact recovery;
never patch the prior logs or create synthetic PASS/result records to qualify it.

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

Retry waits are exactly 60seconds, with at most 30 retries after the original
failure. Carrier-level provider retries are disabled. Waiting requires no model
call and remains cancellable. Nonretryable faults, unknown/local bugs and retry
exhaustion enter `PAUSED_ERROR`, retaining the same processes, context, drafts
and temporary workspace. They notify the owner with the local `codex queue`
command and wait for explicit handling; they never imply task completion or
permission to clean up. Inspect with `yui.py errors RUN`; resume a supported live
checkpoint with `yui.py resume-error RUN --incident ID`; cancel with `yui.py cancel RUN`.
The [error lifecycle](error-lifecycle.md) specifies categories, owner routing,
full diagnostic logs, control guards and the only authorized exit boundaries.
Original faults, qualifications and missing usage remain visible after recovery.
A qualified submission still needs the unchanged mathematical acceptance gates;
resumed work is never relabeled a fault-free or cold first-pass success.

For a run that already exited before this in-session recovery was available,
the invoking agent can continue explicitly selected interrupted NL0/Audit A work:

```sh
python3 -B /path/to/Yui/nl0/scripts/yui.py resume /paper/rigorous-proof/OLD_RUN --detach
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

Scheduled owners use the compact, read-only observation command once per wake:

```sh
python3 -B /path/to/Yui/nl0/scripts/yui.py observe /paper/rigorous-proof/RUN
```

This reports small metadata and exact process identities, without proof bodies
or new model/Lean calls. Full `status` remains available for located diagnosis.

```sh
python3 -B /path/to/Yui/nl0/scripts/yui.py status /paper/rigorous-proof/RUN
python3 -B /path/to/Yui/nl0/scripts/yui.py cancel /paper/rigorous-proof/RUN
python3 -B /path/to/Yui/nl0/scripts/yui.py cancel /paper/rigorous-proof/RUN --task T003
python3 -B /path/to/Yui/nl0/scripts/yui.py cleanup /paper/rigorous-proof/RUN
python3 -B /path/to/Yui/nl0/scripts/yui.py cleanup /paper/rigorous-proof/RUN --apply
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

At invocation and on actual source deferrals, display the [source qualification notice](conditional-sources.md). A conditional completion is not an ordinary PASS.

## Frozen proof recovery after a native-cleanup fault

After verified software repair and explicit user authorization, use
`yui.py resume OLD_RUN --repair-native-cleanup --prepare-only`, inspect the new
job, then execute it with `--detach` or omit `--prepare-only` for direct dispatch.
This route requires the old controller and all owned processes to have exited,
an actual `PROOF_UNFINISHED` result, an unchanged accepted source and frozen
interface, and only positively identified native-process cleanup faults among
the unfinished proof jobs. It refuses live work, changed profiles/worker counts,
mathematical nonpasses and unrelated execution failures.

The continuation skips NL0, Audit A and interface authoring. Previously checked
local bodies are candidates for fresh native rechecking, not a fabricated full
proof receipt. The stopped worker's own hash-bound drafts, including an
unaccepted helper interrupted during cleanup, may be restored only in the exact
same local packet. Record the fresh worker session and all old costs. Assembly,
native trust inspection and bound semantic authority remain required; their
normal located-repair boundaries are unchanged.
