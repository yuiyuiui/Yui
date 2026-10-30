---
name: rigorous-proof-v2
description: Use when Yui V2 or its simplified mathematical-NL0 workflow is requested. This separate experimental variant performs concise independent Audit A and defers exact Mathlib bindings to nl02lean before source-faithful Audit B. The original rigorous-proof skill remains distinct. Supports NL0-only, accepted-NL0 translation and full workflows; schema checks never certify proof correctness.
---

# Yui V2: mathematical NL0 and Lean implementation

Use the smallest requested track. Preserve the original problem, hypotheses,
definitions and proof route. The two stages share one specification and explicit
invalidation rules; completing stage one does not require stage two.

The installed skill root is the directory containing this `SKILL.md`. Keep
`config.json`, `nl0/`, `nl02lean/` and `toolchain/` beside it; no enclosing
`rigorous-proof-v2/` subdirectory or particular checkout name is required.

## Select a stage

Before dispatch, follow [target selection](nl0/references/target-selection.md).
Resolve a clear intended theorem yourself without asking again; ask the user
only when the intended target remains ambiguous. Freeze the complete selected
statement(s), including standing assumptions, as an explicit job input.

The invoking agent owns request/configuration collection and dispatch. Follow
[installed operation](nl0/references/operation.md) to identify explicit proof inputs,
ask once for missing active-phase model/reasoning/speed settings and, for a
NL0, full or translation request, an explicit per-case worker count N, then call
`nl0/scripts/yui.py run` (or prepare/execute). Retain settings already supplied by
the user; do not call a separate intent-classification model. Do not silently
choose a worker count from defaults or `auto`; obtain a positive integer or
the user's explicit confirmation of a proposed number. N bounds local R-node
reviews and, in a separate phase, local Lean proofs. NL0/Audit A and
Lean preparation/proofs/assembly/Audit B have separate phase profiles. The user
does not prepare queues, task packets or controller jobs manually.
The invoking owner follows [foreground handoff and monitoring](nl0/references/owner-observation.md):
normally dispatch with `--detach`, verify the owned processes, and register one
host heartbeat for a bounded check every ten minutes. Record the actual schedule
ID, report that mathematical work is still pending, then end the current
foreground turn. Never keep the owner active through sleep/poll loops. Each
scheduled check ends its turn as well. `DISPATCHED` is not workflow completion.
If host scheduling is unavailable, disclose that and return manual status/cancel
commands; do not claim that a monitor was registered. Frozen author/proof/reviewer
stages perform only their assigned roles and never schedule owner monitoring or
redispatch the workflow.

For missing external originals, follow [ordered source retrieval](nl0/references/source-retrieval.md):
arXiv, Google full-text search, Google DOI discovery, then confirmed-DOI Sci-Hub
lookup with ordinary browser readback when needed. Reuse an already available
adequate primary source; retrieval alone does not establish theorem fidelity.
At invocation disclose the [conditional-source policy](nl0/references/conditional-sources.md):
inaccessible primary texts can permit continued work from complete explicit
secondary statements, but the final result remains conditional. Show each
actual warning and include warn.json/warn.md in the final report. Never label
unverified sources or a qualified workflow as an ordinary full PASS.

Default permanent output is `<problem-directory>/rigorous-proof-v2/<run-id>/`,
outside the installed skill. Multiple problems own separate outputs, contexts,
queues and ledgers. Use normal local repair unless a first-pass measurement is
explicitly requested. Runtime and software controls are fully inside this skill;
no repository example/support directory or old test result is required.
New jobs retain an allowlisted executable/rule/catalog snapshot in their owned
`runtime/` directory and launch from it. Installation updates cannot silently
change an active job's bound code; snapshot tampering still fails validation.
Historical jobs without snapshots retain their original binding checks.
Each native Lean call defaults to a five-minute wall limit. Yui proof workers
automatically receive frozen ST020 repair advice after a verified native
wall/heartbeat limit, through the same failed tool result. Keep the target and
inputs unchanged, repair in the same worker, and recheck. General strategy-bank
queries remain optional; this failure-triggered advice needs no extra model call.
Follow [fault treatment and authorized exit](nl0/references/error-lifecycle.md).
Local Python retries recognized temporary service/network faults every 60seconds,
at most 10 times in the same carrier/thread. Other faults and exhausted retries
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

Normal translation requires a separate independent semantic interface review
before freezing and proof dispatch. Normal final Audit B is machine-only: verify
that actual E/P, their defining environment and complete proof dependencies still
match that reviewed authority. Only a valid-proof/interface-drift exception opens
an actual independent B-final model review, with warning-qualified delivery.
Follow [proof diagnosis and reviewed repair](nl02lean/references/proof-repair.md).
Local compiler defects return to their own author; explicit global proof-connection
issues go to the serial connection author. It cannot change frozen E/P or their
meaning-determining definitions. No fixed idle-turn threshold retires a round or
cancels sibling jobs. Frozen-contract/source defects wait for the user.

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
   authority and exact source version first. V2 requires its audit-format-4
   authority; do not relabel a V1 receipt as V2. Do not reconstruct or re-audit an
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
N limits concurrent local R reviews and local Lean proof jobs in their separate phases.
Report executor termination separately from mathematical acceptance.

Read [isolation](nl0/references/isolation.md) and [measurement](nl0/references/measurement.md)
before any model test or benchmark. Run model authoring, planning, proof and
review stages through the isolated carrier. The interactive developer's memory,
other personal skills, expert packages, old task outputs and hidden reference
proofs are never an input source for these stages.

The Yui arm receives only the declared Yui rules and task material. The direct
arm receives a minimal task/tool contract and the same mathematical inputs,
without Yui planning, strategy or shared-proof guidance. Log actual transmitted
instructions, complete allowed inputs, tool schemas/results, model identity,
phase, usage and health. Never execute model-generated Python or shell text.

Collect the active phase profiles as described above. `config.json` supplies
defaults only when explicitly selected. The current isolated carrier supports
Standard speed and checks model/effort availability without fallback. Freeze
and record each stage's selected profile;
never silently substitute a stronger model or fallback.
Resolve the confirmed concurrency before dispatch and record its basis; do not
claim an unknown backend maximum. N limits local R-node reviews, then local
Lean proof jobs in a later phase. NL0 authoring, global Audit A, preparation,
interface work, assembly and Audit B use one serial lane per case.
Count root/controller, worker, review and retry calls. Cached/reasoning tokens
are subsets of input/output totals, not extra tokens. Missing usage is unknown.

Return the exact accepted scope, source/formal artifacts, unresolved citations
or gaps, actual execution health, time/token breakdown, and reproducible commands.
Do not claim a universal NL0 compiler, an unconditional proof of literature
inputs, completed Audit C, or acceleration from this prototype alone.
