# Current working architecture

## Three semantic stages

1. Structured NL0/Audit A owns the mathematics and permitted inputs.
2. Typed translation produces an actual Lean proof along that route.
3. Audit B checks source/formal concordance and real kernel closure.

The parent candidate implements stage 1. This companion implements a typed
graph translation prototype and a review-bound Audit B adapter. Neither an
interface contract nor a local proof plan is itself a proved mathematical step.

## Two graph levels

The source graph has H/E/M/N/P proposition vertices and R inference vertices.
A particular R or prepared fragment may be implemented by several T obligations.
These T steps are implementation proof ports, not automatic new NL0 theorems.
Each carries its complete Lean type, direct inputs, source-paragraph mapping
and mechanism. Substantive new mathematics returns to the source graph/Audit A.

The current runner consumes one frozen contract/plan. The legacy model pilot
can generate interfaces/plans for its three prepared development extracts, using
an owner-reviewed interface oracle. It is not a general semantic NL0 compiler.
A whole-paper controller that automatically discovers every representation,
converts all source R nodes and joins arbitrary dependent witness interfaces is
not implemented. Audit B can cover a whole structured graph only when the
provided actual assembly and mapping cover all its nodes.

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
| Source/IR freeze | Preserve baseline, accepted source, definitions, target/H/E/M, exact paragraph/output mapping and direct input boundaries | workflow.py freeze; located interface review plus immutable bindings |
| Interface authoring | Choose source-faithful Lean representations and complete input/output types | contract.json; model proposal plus real semantic review |
| Local planning | Define useful typed T ports, direct input IDs and source correspondence | plan.json; structural/type checks in ir.py |
| Explicit reuse | Match a reviewed common port against a supplied project source store | shared_lemmas.py, initial index, full conditional types |
| Local proof work | Fresh worker proves only its own conditional obligation; direct proof by default | Stage in model_pilot.py; fixed search/read/check/submit tools |
| Bounded execution | Launch independent conditional bodies; deduplicate compatible shared jobs within one graph | scheduler.py; pending/running/results and actual intervals |
| Assembly | Apply every real local proof and discharge internal T dependencies | Actual Translation.P and a fresh verifier |
| Audit B | Independently review source/type meaning, inspect actual dependencies/fields, resolve source M ports and check final export | audit_b.py, audit_probe.lean, located semantic receipt |

All model stages share a disclosed `max_concurrency=auto|N` budget. The CLI's
unknown hard limit resolves auto to a fallback of two, never a claimed maximum.
Record requested/effective values, basis, observed peak and queue intervals.
No-extraction uses the accepted original graph directly. Source changes after
freeze require a new revision, not continued mutation of dispatched packets.

Global mathematical identity does not force a global Lean representation. A
view record selects a local expression/type; explicit proved input relations
justify crossings. The current implementation keeps fixed cross-node parameters
within one contract and permits local views/definitions. It does not choose an
optimal view or generate an arbitrary bridge automatically.

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
a real source/formal review. Compiler success is only one gate. Audit B examines
actual imported proofs, proof-valued parameters/fields and local/project closure,
including unlisted results selected by automation. Pending templates stay pending.

If source M is represented by a theorem parameter in the intermediate graph,
the audit adapter proves that port using the actual library declaration and
exports AuditBExport.P without that extra unproved argument. Source E remains
an explicitly declared external input and is not claimed proved by Lean.
Unresolved internal N ports are permitted only in a disclosed fragment scope.

The earlier six-run norm pilot measured frozen-port proof work, with no full
Audit B acceptance. The new stricter inspection identifies unregistered direct
uses of ofReal_norm and iSup_congr in its source inventory. Preserve that result
as a dependency finding; do not rewrite its frozen source or claim its old
timings already measure fully audited NL0 formalization.

Include source/interface authoring, shared first construction, kernel/tool work,
assembly, Audit B review and failures in an end-to-end speed claim. Per-stage
time, summed worker effort, parallel makespan and warm reuse answer different
questions. This architecture is executable; general speed advantage remains
an experimental question.
