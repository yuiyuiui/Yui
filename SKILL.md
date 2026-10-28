---
name: rigorous-proof
description: Use Yui to make an existing mathematical proof self-contained as structured NL0 with Audit A, then optionally translate it through typed interfaces into Lean with source-faithful Audit B. Supports NL0-only, translation from an accepted NL0, and full workflows. Do not infer proof correctness from schema checks or introduce unproved assumptions to close a goal.
---

# Yui: rigorous proof development

Use the smallest requested track. Preserve the original problem, hypotheses,
definitions and proof route. The two stages share one specification and explicit
invalidation rules; completing stage one does not require stage two.

The installed skill root is the directory containing this `SKILL.md`. Keep
`config.json`, `nl0/`, `nl02lean/` and `toolchain/` beside it; no enclosing
`rigorous-proof/` subdirectory or particular checkout name is required.

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

Default permanent output is `<problem-directory>/rigorous-proof/<run-id>/`,
outside the installed skill. Multiple problems own separate outputs, contexts,
queues and ledgers. Use normal local repair unless a first-pass measurement is
explicitly requested. Runtime and software controls are fully inside this skill;
no repository example/support directory or old test result is required.
Positively identified temporary remote-service failures retry within the same
isolated thread, preserving its drafts and tool receipts. Keep the selected
profile and record every fault/wait; use [operational recovery](nl0/references/operation.md#remote-service-recovery)
for backoff, cancellation and explicit continuation of an already exited run.
For a previously stopped inherited probe-directory collision, the same operation
reference documents a separate guarded `--repair-local-tool` continuation after
verified software repair and explicit owner authorization; it restores the saved
located author repair rather than restarting the original proof.

1. **NL0 and Audit A.** Use [Audit A's shared acceptance requirements](nl0/references/audit-a.md#shared-mathematical-acceptance-requirements)
   as the single mathematical standard for both author and auditor.
   Read [the NL0 stage](nl0/references/nl0-stage.md),
   [format](nl0/references/nl0-format.md), [self-containment](nl0/references/self-containment.md),
   [authoring](nl0/references/nl0-authoring.md), and Audit A's role-specific execution protocol.
   Read [external-source review](nl0/references/external-theorems.md) for citations
   and [logical packaging](nl0/references/logical-rules.md) for local assumptions.
   Use `nl0/scripts/nl0.py`; its explicit accounting is not a mathematical prover.
   Controllers and reviewers follow [completion and local repair](nl0/references/review-execution.md)
   for global-first parallel R coverage, exact evidence inheritance and stage boundaries.
2. **Translate an accepted NL0 and run Audit B.** Verify the supplied Audit A
   authority and exact source version first; do not reconstruct or re-audit an
   unchanged proof. Start with [minimal translation](nl02lean/references/minimal-translation.md).
   Read [translation](nl02lean/references/stage.md),
   [the working sequence](nl02lean/references/integrated-workflow.md), and
   [Audit B](nl02lean/references/audit-b.md). Operators use
   [execution and file-based control](nl02lean/references/execution-protocol.md)
   for parallel queues, status and stops; workers need only their frozen packet.
   After local proofs complete, the serial postprocessing author follows
   [assembly and source-facing export](nl02lean/references/assembly.md),
   then hands actual checked evidence to a separate independent Audit B reviewer.
   Use
   `nl02lean/scripts/source_preparation.py` for bounded shared extraction,
   then `workflow.py` for source/IR freeze, proof work and final gates.
3. **Full workflow.** Complete track one, then track two. A changed mathematical
   statement or new theorem returns to the affected NL0/Audit A boundary.

## Mathematical invariants

- Accepted NL0 is a complete natural-language proof relative to explicit H/E/M,
  fixed logic and its hash-bound verified background supplement. Important
  tools remain explicit; ordinary correct elementary reasoning needs no
  exhaustive calculation chain. See [background notes](nl0/references/background-notes.md).
- Within NL0, each inference uses only its direct inputs, global definitions and explicitly
  established in-scope local facts or positively checked node-local background
  notes. Notes never add H or repair a substantive gap. Source papers and producer proof bodies do
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
- Audit B checks every external E and the complete target P, including its
  hypotheses, against actual Lean types and relevant definitions. Supply short
  direct/equivalent correspondence explanations; an independent reviewer verifies
  them. Check fresh Lean closure and trust, without a Mathlib-to-NL0 use ledger.
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
