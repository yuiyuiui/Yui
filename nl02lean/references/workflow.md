# Current working architecture

## Three semantic stages

1. Structured NL0/Audit A owns the source mathematics and project premises;
   stage two may freely use the pinned Mathlib environment.
2. Typed translation produces an actual Lean proof along that route.
3. Audit B checks source/formal concordance and real kernel closure.

Yui's NL0 module implements stage 1. Its translation module implements a typed
graph translation prototype and a review-bound Audit B adapter. Neither an
interface contract nor a local proof plan is itself a proved mathematical step.

## Two graph levels

The source graph has H/E/M/N/P proposition vertices and R inference vertices.
A particular R or prepared fragment may be implemented by several T obligations.
These T steps are implementation proof ports, not automatic new NL0 theorems.
Each carries its complete Lean type, direct inputs, source-paragraph mapping
and mechanism. A changed source claim or new external assumption returns to
the source graph/Audit A; direct use of pinned Mathlib does not.

The current runner consumes one frozen contract/plan. The legacy model pilot
can generate interfaces/plans for its three prepared development extracts, using
an owner-reviewed interface oracle. It is not a general semantic NL0 compiler.
A whole-paper controller that automatically discovers every representation,
converts all source R nodes and joins arbitrary dependent witness interfaces is
not implemented. Audit B can cover a whole structured graph only when the
provided actual assembly closes its obligations and the endpoint mapping
covers every E and complete P.

## Execution pipeline and responsibility

Shared mathematical extraction belongs to translation entry, not NL0-only
authoring. [The local revision protocol](source-refactoring.md) defines the
minimal patch, unchanged-content inheritance and new producer/substitution
review. Preserve the baseline and seal a separate revised source before final
IR/worker-packet generation. `source_preparation.py` validates ordinary or
incremental current Audit A authority without changing the parent standard.
`workflow.py` then gates frozen IR, model work and Audit B; its explicit commands
are in [the integrated guide](integrated-workflow.md). Authoring and mathematical
judgments remain real model/human work, not automatic semantic compilation.

| Stage | Responsibility | Main artifact/tool |
| --- | --- | --- |
| Translation-entry source preparation | Extract existing shared derivations through allowlisted local patches; review new producers and substitution cuts, preserving old evidence | source_preparation.py inventory/stage/check; ordinary or incremental Audit A authority |
| Source/IR freeze | Preserve baseline, accepted source, definitions, complete target/H/E, optional M ports, paragraph/output mapping and project input boundaries | workflow.py freeze; source/type checks, actual independent interface receipt in normal entry, immutable bindings; final Audit B still required |
| Interface authoring | Choose source-faithful Lean representations and complete input/output types | contract.json; actual type checks and separate independent pre-proof semantic review |
| Local planning | Define useful typed T ports, direct input IDs and source correspondence | plan.json; structural/type checks in ir.py |
| Explicit reuse | Match a reviewed common port against a supplied project source store | shared_lemmas.py, initial index, full conditional types |
| Local proof work | Fresh worker proves only its own conditional obligation; direct proof by default | Stage in model_pilot.py; fixed search/read/check/submit tools |
| Bounded execution | Launch independent conditional bodies; deduplicate compatible shared jobs within one graph | scheduler.py; pending/running/results and actual intervals |
| Located repair | Return compiler errors to the same node author; diagnose explicit global obstructions after active handoffs without canceling siblings | proof_repair.py, proof_diagnosis.py; internal connection repair only, frozen-contract/source defects wait for user |
| Assembly | Apply every real local proof and discharge internal T dependencies | Actual Translation.P and a fresh verifier |
| Audit B | Machine preservation of reviewed E/P meanings and complete native closure; exceptional B-final only for proof-valid drift | final_acceptance.py, audit_b.py, audit_probe.lean; inherited semantic receipt or warning-qualified exception |

Local R reviews and later Lean proof jobs default to their respective current
R/T node counts in separate phases, each with its own bounded lane. An explicit
positive N caps both. NL0 authoring, global Audit A,
preparation, interface work, assembly and Audit B use the serial lane. All
roles contribute to the same case cost ledger. Public and lower-level commands
use the same automatic phase-sizing policy; no fixed fallback or worker-count
confirmation is required.
Record requested/effective values, basis, proof/review peaks and queue intervals.
Independent cases own separate budgets/processes. Free executor slots claim
pending jobs without waiting for the entire group. See
[execution-protocol.md](execution-protocol.md) for ownership, file-based status,
scoped stops and the desktop Stop limitation. No dashboard is needed.
No-extraction uses the accepted original graph directly. Source changes after
freeze require a new revision, not continued mutation of dispatched packets.

Global mathematical identity does not force a global Lean representation. A
view record selects a local expression/type; explicit proved input relations
justify crossings. The current implementation keeps fixed cross-node parameters
within one contract and permits local views/definitions. It does not choose an
optimal view or generate an arbitrary bridge automatically.

Default execution has no total time/token/call deadline. Only an explicit user
deadline covers all preparation, proof work and acceptance; stages receive its
remaining budget. Each native Lean call separately uses the configured limit.
The controller occupies no model slot. See
[minimal translation](minimal-translation.md) for the current default.

## What a local worker sees

A packet contains the frozen definition header and typed parameters, only the
listed direct input statements/proof binders, the complete target, the matched
source argument paragraphs, and relevant local view/bridge records. It does not
contain sibling proof bodies, historical successful answers or a second task's
conversation. Pinned mathlib source search/read and local Lean checks remain
explicit tools. Strategy lookup is optional; a strategy card adds no premise.
Packets are generated only after the selected source and implementation ports
are frozen. Source-revision planning may inspect provisional interfaces, but
those are not final worker packets and must not be dispatched as such.

The source store is separate from the advice bank. It records actual checked
conditional proofs and their complete guards, source, pins and hashes. Matching
is conservative typed/route matching with binder alpha-renaming, not semantic
similarity. A hit is rechecked in the present context and skips a model call.
A miss takes the original worker path. Source is re-elaborated; there is no
compiled-module cache. Preserve natural source node boundaries and export one
common mathematical lemma rather than shredding every consumer.

## Conditional concurrency example

Source route: equal real norms -> equal extended norms -> equal suprema.

- T001 receives H001 and proves the pointwise extended-norm equality B.
- T002 receives B as the explicit local input h_T001 and proves the supremum
  equality P. It can run while T001 is still being proved.
- After both bodies pass, assembly applies the actual proof of B to T002.
  If T001 fails, no final P is accepted. No temporary axiom or sorry is used.

Mathematical dependencies therefore constrain assembly without always forcing
sequential body development. This is single-controller, bounded graph execution;
it is not distributed cross-process proof-job coordination.

## Audit and evidence boundary

Audit B's two gates are detailed in audit-b.md. Source coverage and actual
elaborated types/dependencies are machine-inspected, but meaning still requires
a bound pre-proof source/formal review (or the explicit B-final exception).
Normal final acceptance is machine-only. Compiler success is only one gate. Audit B examines
the actual E/P statements, relevant proof-valued fields and local/project
closure. Imported Mathlib results selected by automation need no source-M match. Pending templates stay pending.

If source M is represented by a theorem parameter in the intermediate graph,
the assembly adapter proves that port using any applicable pinned library result and
exports AuditBExport.P without that extra unproved argument. Source E remains
an explicitly declared external input and is not claimed proved by Lean.
Unresolved internal N ports are permitted only in a disclosed fragment scope.

The earlier six-run norm pilot measured frozen-port proof work, with no full
Audit B acceptance. Version-1 inspection identified unregistered direct uses of ofReal_norm and
iSup_congr; retain that historical finding under its original policy. Version 2
permits such Mathlib use, but it does not retrospectively certify old proofs or
make their timings measurements of fully audited formalization.

Include source/interface authoring, shared first construction, kernel/tool work,
assembly, Audit B review and failures in an end-to-end speed claim. Per-stage
time, summed worker effort, parallel makespan and warm reuse answer different
questions. This architecture is executable; general speed advantage remains
an experimental question.
