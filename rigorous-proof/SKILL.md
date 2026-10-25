---
name: rigorous-proof
description: Use Yui to make an existing mathematical proof self-contained as structured NL0 with Audit A, then optionally translate it through typed interfaces into Lean with source-faithful Audit B. Supports NL0-only, translation from an accepted NL0, and full workflows. Do not infer proof correctness from schema checks or introduce unproved assumptions to close a goal.
---

# Yui: rigorous proof development

Use the smallest requested track. Preserve the original problem, hypotheses,
definitions and proof route. The two stages share one specification and explicit
invalidation rules; completing stage one does not require stage two.

## Select a stage

1. **NL0 and Audit A.** Use [Audit A's shared acceptance requirements](references/audit-a.md#shared-mathematical-acceptance-requirements)
   as the single mathematical standard for both author and auditor.
   Read [the NL0 stage](references/nl0-stage.md),
   [format](references/nl0-format.md), [self-containment](references/self-containment.md),
   [authoring](references/nl0-authoring.md), and Audit A's role-specific execution protocol.
   Read [external-source review](references/external-theorems.md) for citations
   and [logical packaging](references/logical-rules.md) for local assumptions.
   Use `scripts/nl0.py`; its explicit accounting is not a mathematical prover.
   Controllers and reviewers follow [completion and local repair](references/review-execution.md)
   for serial audit coverage, exact evidence inheritance and stage boundaries.
2. **Translate an accepted NL0 and run Audit B.** Verify the supplied Audit A
   authority and exact source version first; do not reconstruct or re-audit an
   unchanged proof. Start with [minimal translation](translation/references/minimal-translation.md).
   Read [translation](translation/references/stage.md),
   [the working sequence](translation/references/integrated-workflow.md), and
   [Audit B](translation/references/audit-b.md). Operators use
   [execution and file-based control](translation/references/execution-protocol.md)
   for parallel queues, status and stops; workers need only their frozen packet.
   After local proofs complete, the serial postprocessing author follows
   [assembly and source-facing export](translation/references/assembly.md),
   then hands actual checked evidence to a separate independent Audit B reviewer.
   Use
   `translation/scripts/source_preparation.py` for bounded shared extraction,
   then `workflow.py` for source/IR freeze, proof work and final gates.
3. **Full workflow.** Complete track one, then track two. A changed mathematical
   statement or new theorem returns to the affected NL0/Audit A boundary.

## Mathematical invariants

- Accepted NL0 is a complete natural-language proof relative to explicit H/E/M,
  fixed logic and its hash-bound verified background supplement. Important
  tools remain explicit; ordinary correct elementary reasoning needs no
  exhaustive calculation chain. See [background notes](references/background-notes.md).
- Each inference uses only its direct inputs, global definitions and explicitly
  established in-scope local facts or positively checked node-local background
  notes. Notes never add H or repair a substantive gap. Source papers and producer proof bodies do
  not fill gaps in a task packet.
- Preserve one global mathematical identity while allowing local Lean views.
  Cross-view conversions need proved, explicitly permitted inputs.
- Shared mathematical extraction is a bounded local change at translation entry.
  Review its new producer and substitution cuts; inherit unchanged evidence.
  Freeze the revised NL0 before final IR and worker packets.
- Local conditional bodies may run concurrently. Assembly must discharge every
  internal dependency with an actual checked proof; conditional checks alone
  are not a final result.
- Audit B checks exact semantic correspondence, allowed assumptions, definitions,
  actual full kernel signatures/dependencies, and fresh Lean closure. Its
  reviewer is an actual model/human judgment, not an automatically populated PASS.
- Stop on a judged substantive mathematical gap. Ordinary expansion and local
  verifiable corrections remain allowed. Difficulty or elapsed time does not
  establish that a mathematical claim is false.

## Clean execution and accounting

Operators use [execution terminology](references/terminology.md) to distinguish
Codex conversations, native subagents, Yui jobs, worker slots and controllers.
Use the logical phase names **NL0 worker**, **preprocessing worker**,
**formalization workers (N slots)** and **postprocessing worker**. A logical
worker may contain several separate author/reviewer threads and program steps;
N limits only concurrent local Lean proof jobs.
Report executor termination separately from mathematical acceptance.

Read [isolation](references/isolation.md) and [measurement](references/measurement.md)
before any model test or benchmark. Run model authoring, planning, proof and
review stages through the isolated carrier. The interactive developer's memory,
other personal skills, expert packages, old task outputs and hidden reference
proofs are never an input source for these stages.

The Yui arm receives only the declared Yui rules and task material. The direct
arm receives a minimal task/tool contract and the same mathematical inputs,
without Yui planning, strategy or shared-proof guidance. Log actual transmitted
instructions, complete allowed inputs, tool schemas/results, model identity,
phase, usage and health. Never execute model-generated Python or shell text.

Use the phase profiles in `config.json`: NL0/Audit A uses
`gpt-6.1-sol/high/Standard`; NL0-to-Lean (including preparation) and Audit B use
`gpt-6.1-sol/high/Standard` in the current test configuration. Freeze and record each stage's selected profile;
never silently substitute a stronger model or fallback.
Resolve default concurrency
before dispatch and record its basis; do not claim an unknown backend maximum.
The concurrency parameter limits Lean proof jobs only. NL0 authoring,
preparation, Audit A, interface work and Audit B use one serial lane per case.
Count root/controller, worker, review and retry calls. Cached/reasoning tokens
are subsets of input/output totals, not extra tokens. Missing usage is unknown.

Return the exact accepted scope, source/formal artifacts, unresolved citations
or gaps, actual execution health, time/token breakdown, and reproducible commands.
Do not claim a universal NL0 compiler, an unconditional proof of literature
inputs, completed Audit C, or acceleration from this prototype alone.
