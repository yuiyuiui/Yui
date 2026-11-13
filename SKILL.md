---
name: rigorous-proof
description: Use Yui to audit an existing proof as NL0/Audit A and optionally translate it through frozen interfaces into conditional Lean/Audit B. An explicit unconditional full track adds 2basis and checked b2lean dependency discharge. Structural checks and compilation alone do not establish source fidelity.
---

# Yui: mathematical NL0 and Lean implementation

Use the smallest requested track. Preserve the original problem, hypotheses,
definitions and active proof route. The two stages share one specification and explicit
invalidation rules; completing stage one does not require stage two.

Conditional formalization remains the default, including `--track full`.
For an explicit unconditional request, select `--track full --formalization
unconditional` and follow [2basis and b2lean](nl0/references/basis.md).
2basis may rewrite the original proof route before the one shared NL0/Audit A;
the original target/H remain immutable. Audit A receives both original task and
basis proof and replacements. Prepare used class 1/2/3 Lean proofs in 2basis.
An independent reviewer compares the printed Lean propositions with the source and
all intended uses. Remaining class 4 requires the user's
exact stop/continue/accept-conditional decision. After the shared Audit B, b2lean
must check the actual closed export and transitive trust. Never present an
approved conditional fallback or source-qualified result as unconditional.
These optional stages reuse the two existing model profiles and controllers.

The installed skill root is the directory containing this `SKILL.md`. Keep
`config.json`, `nl0/`, `nl02lean/` and `toolchain/` beside it; no enclosing
`rigorous-proof/` subdirectory or particular checkout name is required.

New public cases use the versioned [workflow definition](workflow/workflow.json) and the [operator and maintenance guide](workflow/SKILL.md). A basis request freezes the reviewed foundation inventory and supplies a structured graph seed. Direct NL0 builds its working graph from the original input. In both routes NL0 owns intermediate statements and dependency edges. Local authors may request a located graph repair. Independent Audit A reviews the selected complete revision before delivery or Lean. Retain `RUN/delivery/` and report the actual scope from `run.json`. Use `verify-delivery` before and after explicit cleanup.

## Select a stage

Before dispatch, follow [target selection](nl0/references/target-selection.md).
Resolve a clear intended theorem yourself without asking again; ask the user
only when the intended target remains ambiguous. Freeze the complete selected
statement(s), including standing assumptions, as an explicit job input.

The invoking agent owns request/configuration collection and dispatch. Follow
[installed operation](nl0/references/operation.md) to identify explicit proof inputs,
ask once for missing active-phase model/reasoning/speed settings, then call
`nl0/scripts/yui.py run` (or prepare/execute). Retain settings already supplied by
the user; do not call a separate intent-classification model. An omitted worker
count or `auto` uses the current phase's node count: R nodes for local Audit A
review/repair and T nodes for local Lean proofs, including shared lemmas and
representation conversions. Resolve each count when that phase is ready; do not
ask for a worker count or fall back to two. An explicit positive integer N caps
both separate phases. NL0/Audit A and
Lean preparation/proofs/assembly/Audit B have separate phase profiles. The user
does not prepare queues, task packets or controller jobs manually.
For formalization, follow [per-run Lean/Mathlib selection](nl0/references/lean-environments.md).
Use a verified unambiguous local pair, or retain the user's explicit paths or
version choice. Ask for matched paths or desired versions when discovery is
ambiguous, missing or incompatible. Install only the explicitly chosen versions.
Freeze the actual selected environment with the job; pure NL0 requires no Lean
selection. Parallel and nested private workers inherit the selected profiles
and environment while owning independent role conversations.
The invoking owner follows [foreground handoff and monitoring](nl0/references/owner-observation.md).
Dispatch with `--detach`, verify process identities and report the initial
phase. Prefer a host-permitted ten-minute scheduled wakeup and record its
actual ID before ending the owner turn. If scheduling is restricted,
unavailable or unsuccessful, continue the same run with interruptible
ten-minute waits in the owning turn, one observation and report per interval.
A scheduling failure selects this fallback. Continue the authorized run.
An entry's recorded owner and monitoring mode govern ongoing observation.
Frozen workers perform only their assigned roles.

For missing external originals, follow [ordered source retrieval](nl0/references/source-retrieval.md):
arXiv, Google full-text search, Google DOI discovery, then confirmed-DOI Sci-Hub
lookup with ordinary browser readback when needed. Reuse an already available
adequate primary source; retrieval alone does not establish theorem fidelity.
At invocation disclose the [conditional-source policy](nl0/references/conditional-sources.md):
inaccessible primary texts can permit continued work from complete explicit
secondary statements, but the final result remains conditional. Show each
actual warning and include warn.json/warn.md in the final report. Never label
unverified sources or a qualified workflow as an ordinary full PASS.

Default permanent output is `<problem-directory>/rigorous-proof/<run-id>/`,
outside the installed skill. Multiple problems own separate outputs, contexts,
queues and ledgers. Use normal local repair unless a first-pass measurement is
explicitly requested. Runtime and software controls are fully inside this skill;
no repository example/support directory or old test result is required.
New jobs retain an allowlisted executable/rule/catalog snapshot in their owned
`runtime/` directory and launch from it. Installation updates cannot silently
change an active job's bound code; snapshot tampering still fails validation.
Historical jobs without snapshots retain their original binding checks.
Local proof and helper checks start at six minutes; a workload-only diagnosis
raises the next allowance by six minutes, up to thirty. Complete-file nl02lean
assembly/export/inspection and final b2lean checks start at thirty minutes;
a workload-only diagnosis raises that allowance by fifteen minutes, up to sixty.
Each native wall timeout receives a source-located diagnosis. A code defect
returns for repair at the current allowance; an incomplete diagnosis grants no
increase. Timed-out checks remain unaccepted even if partial output looks valid.
Whole-case and stage deadlines remain binding. Workers check helpers
individually and submit the complete composition to Lean. Failed wall/heartbeat
checks also receive the locally stored ST020 repair advice.
Foundation and Lean authors can browse their respective strategy banks on demand
or proceed directly to submission. See [strategy lookup](nl02lean/references/obstacle-routing.md).
Follow [fault treatment and authorized exit](nl0/references/error-lifecycle.md).
Local Python retries recognized temporary service/network faults every 60seconds,
at most 30 times in the same carrier/thread. Other faults and exhausted retries
enter a retained `PAUSED_ERROR`, notify the owner through local `codex queue`,
and wait for an exact-incident operator action. An error never authorizes task
termination or workspace deletion. Release only the completed roles at the
specified global-pass, all-local-pass, interface-freeze and final-delivery
boundaries, after their bound handoffs are saved. Explicit user cancellation or
a selected B-final user decision is a separate authority. Keep
scientific evidence and the selected profile. A pause is nonterminal: never
restart it or delete its monitor. Existing exited-run recovery is historical,
not a substitute for live `resume-error` controls.
An explicitly authorized `--after-access-restored` continuation separately
supports a verified provider HTTP403 stop at the NL0/Audit A boundary. It checks
authenticated model metadata without inference before preparation and launch;
403 stays excluded from automatic retries. Preserve old faults/costs and disclose
the new runtime and unreleased-author scope in that operation reference.
For a previously stopped inherited probe-directory collision, the same operation
reference documents a separate guarded `--repair-local-tool` continuation after
verified software repair and explicit owner authorization; it restores the saved
located author repair rather than restarting the original proof.
The separate guarded `--repair-native-cleanup` route supports an actually exited
frozen proof queue stopped only by verified native-process cleanup faults. It
preserves the exact source/A/interface, rechecks completed local bodies and
restores only the failed worker's own bound drafts; never use it to resample a
mathematical nonpass or replace live work.

The explicit `--repair-proof-io` continuation supports an exited, unfinalized
full/unconditional frozen proof queue with actual ENOSPC diagnostics. It keeps
the old run read-only, inherits the checked basis/A authority, independently
reviews the unchanged interface again, and rechecks saved local bodies. Only
intact own-node drafts and local diagnostic advice reach the unfinished authors
in fresh isolated contexts. It never fabricates a missing queue/result receipt,
overrides a protected/source diagnostic, or silently edits a frozen runtime.
See [I/O interruption recovery](nl0/references/operation.md#exited-proof-queue-after-enospc).

After verified software repair, the explicit `--repair-basis-closure` route
repeats only final native closure from accepted basis and Audit B artifacts.
It requires an unlimited normal unconditional job, explicit cancellation and
verified process exits, and unchanged bound evidence. It writes a fresh owned
run, repeats no proof authoring or semantic audit, and preserves all residual assumptions and source
qualifications. See [final closure recovery](README.md#final-closure-and-recovery).
An actual native wall timeout can invoke the source-located diagnostic role
before a bounded retry; its model usage is recorded separately from semantic review.

Normal translation requires a separate independent semantic interface review
before freezing and proof dispatch. Normal final Audit B is machine-only: verify
that actual E/P, their defining environment and complete proof dependencies still
match that reviewed authority. Only a valid-proof/interface-drift exception opens
an actual independent B-final model review, with warning-qualified delivery.
Follow [proof diagnosis and reviewed repair](nl02lean/references/proof-repair.md).
Local compiler defects return to their own author; explicit global proof-connection
issues go to the serial connection author. It cannot change frozen E/P or their
meaning-determining definitions. No fixed idle-turn threshold retires a round or
cancels sibling jobs. Located internal T-plan defects return to preprocessing
after the current round's handoffs. Strict declaration checks and an independent
delta review precede a new frozen revision; reuse own bodies only after current
Lean checks. Original source, H/E/P and the public header remain fixed.
Protected public-contract/source defects wait for the user.

1. **NL0 and Audit A.** Use [Audit A's shared acceptance requirements](nl0/references/audit-a.md#shared-mathematical-acceptance-requirements)
   as the single mathematical standard for both author and auditor. Prefer concise grouped
   review and batch completion; ordinary background facts require mathematical
   conditions and justification, not a pre-translation native probe.
   Read [the NL0 stage](nl0/references/nl0-stage.md),
   [format](nl0/references/nl0-format.md), [self-containment](nl0/references/self-containment.md),
   [authoring](nl0/references/nl0-authoring.md), and Audit A's role-specific execution protocol.
   Read [external-source review](nl0/references/external-theorems.md) for citations
   and [logical packaging](nl0/references/logical-rules.md) for local assumptions.
   Use `nl0/scripts/nl0.py`; its explicit accounting is not a mathematical prover.
   Controllers and reviewers follow [completion and local repair](nl0/references/review-execution.md)
   for global-first parallel R coverage, exact evidence inheritance and stage boundaries.
2. **Translate an accepted NL0 and run Audit B.** Verify the supplied Audit A
   authority and exact source version first. This workflow requires audit-format-4
   authority; do not relabel a detailed-NL0 format-3 receipt. Do not reconstruct or re-audit an
   unchanged proof. Start with [minimal translation](nl02lean/references/minimal-translation.md).
   Read [translation](nl02lean/references/stage.md),
   [the working sequence](nl02lean/references/integrated-workflow.md), and
   [Audit B](nl02lean/references/audit-b.md). Operators use
   [execution and file-based control](nl02lean/references/execution-protocol.md)
   for parallel queues, status and stops; workers need only their frozen packet.
   After local proofs complete, the controller first attempts mechanical
   [assembly and source-facing export](nl02lean/references/assembly.md).
   Use the serial connection author only for actual connection/library-discharge
   repair. Normal final machine Audit B inherits the frozen semantic review;
   B-final is reserved for proof-valid interface deviation.
   Use
   `nl02lean/scripts/source_preparation.py` for bounded shared extraction,
   then `workflow.py` for source/IR freeze, proof work and final gates.
3. **Full workflow.** Complete track one, then track two. A changed mathematical
   statement or new theorem returns to the affected NL0/Audit A boundary.
   With the explicit unconditional goal, run 2basis first and b2lean last.
   Report the requested goal and achieved scope separately, with the final
   `YuiClosed.P` artifact and any residual class-4/source warnings.

## Mathematical invariants

- Accepted NL0 is a complete natural-language proof relative to explicit H/E/M,
  fixed logic and its hash-bound mathematically reviewed background supplement. Important
  tools remain explicit; ordinary correct elementary reasoning needs no
  exhaustive calculation chain. See [background notes](nl0/references/background-notes.md).
- Within NL0, each inference uses only its direct inputs, global definitions and explicitly
  established in-scope local facts or mathematically checked node-local background
  notes. Exact routine Mathlib declarations are resolved during translation.
  Notes never add H or repair a substantive gap. Source papers and producer proof bodies do
  not fill gaps in a task packet.
- Preserve one global mathematical identity while allowing local Lean views.
  Actual cross-view conversions need checked proofs. In stage two, the pinned
  Mathlib environment is freely available without NL0 M registration.
- Shared mathematical extraction is a bounded local change at translation entry.
  Review its new producer and substitution cuts; inherit unchanged evidence.
  Freeze the revised NL0 before final IR and worker packets.
- Local conditional bodies may run concurrently. Assembly must discharge every
  internal dependency with an actual checked proof; conditional checks alone
  are not a final result.
- The independent pre-freeze review checks every E and complete P, including
  hypotheses, quantifiers and relevant definitions. Final machine Audit B checks
  actual exported full types and complete closure against that frozen authority.
  Supply short direct/equivalent correspondence explanations. Check actual Lean
  closure and trust, without a Mathlib-to-NL0 use ledger.
  Neither author notes nor a compiler pass are semantic approval.
- Stop on a judged substantive mathematical gap. Ordinary expansion and local
  verifiable corrections remain allowed. Difficulty or elapsed time does not
  establish that a mathematical claim is false.

## Clean execution and accounting

Operators use [execution terminology](nl0/references/terminology.md) to distinguish
Codex conversations, native subagents, Yui jobs, worker slots and controllers.
Use the logical phase names **NL0 worker**, **preprocessing worker**,
**formalization workers (N slots)** and **postprocessing worker**. A logical
worker may contain several separate author/reviewer threads and program steps;
The local slot limit is the current R/T node count by default, or the user's
explicit N in both separate phases.
Report executor termination separately from mathematical acceptance.

Read [isolation](nl0/references/isolation.md) and [measurement](nl0/references/measurement.md)
before any model test or benchmark. Run model authoring, planning, proof and
review stages through the isolated carrier. The interactive developer's memory,
other personal skills, expert packages, old task outputs and hidden reference
proofs are never an input source for these stages.

The Yui arm receives only the declared Yui rules and task material. The direct
arm receives a minimal task/tool contract and the same mathematical inputs,
without Yui planning, strategy or shared-proof guidance. Log controller-supplied instructions, frozen inputs, native configuration,
tool schemas/results, reported model identity, phase, usage and health. Native
Codex manages model networking and context; Yui does not intercept HTTP payloads.
Actual tier and per-response usage coverage remain unknown when not exposed. Never execute model-generated Python or shell text.

Collect the active phase profiles as described above. `config.json` supplies
defaults only when explicitly selected. The current isolated native Codex carrier requests
Standard speed and checks model/effort availability without fallback. Freeze
and record each stage's selected profile;
never silently substitute a stronger model or fallback.
Resolve automatic concurrency from each frozen phase's nodes before local
dispatch and record its basis; do not claim an unknown backend maximum. Explicit
N limits local R-node reviews, then local Lean proof jobs in a later phase.
Recompute auto after a reviewed revision changes the phase graph. NL0 authoring, global Audit A, preparation,
interface work, assembly and Audit B use one serial lane per case.
Count root/controller, worker, review and retry calls. Cached/reasoning tokens
are subsets of input/output totals, not extra tokens. Missing usage is unknown.

Return the exact accepted scope, source/formal artifacts, unresolved citations
or gaps, actual execution health, time/token breakdown, and reproducible commands.
Do not claim a universal NL0 compiler, an unconditional proof of literature
inputs, completed Audit C, or acceleration from this prototype alone.
