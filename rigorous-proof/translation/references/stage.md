# NL0-to-Lean Translation and Audit B — Candidate 0.4

Preserve the given mathematical proof route, target, hypotheses and allowed
external results. Keep the original NL0/Audit A artifacts immutable. Treat
legacy fragments as development inputs, not newly Audit-A-approved packages.

Read [architecture](architecture.md) and
[translation rules](translation-rules.md) before building an IR.
At translation entry, use [local source refactoring](source-refactoring.md)
and its [revision record](../templates/source-refactoring.md) if sharing requires
changing NL0. Extract existing derivations with an explicit patch boundary;
do not reconstruct NL0 or repeat the whole audit. This is not an additional
step for NL0-only work. Preserve old evidence, review new proofs/substitution
cuts. Use `scripts/source_preparation.py` to validate the inheritance and actual
new reviews; the unchanged parent checker still owns ordinary Audit A.
Read [the integrated execution guide](integrated-workflow.md) when
staging a revision or executing a complete source-to-Audit-B workflow.
Use [the working pipeline map](workflow.md) to distinguish source
R nodes, implementation T obligations, actual assembly and Audit B.
Use [obstacle routing](obstacle-routing.md) when a transition stalls.
Read [the experiment protocol](experiments.md) before a model run.
Read [shared lemmas](shared-lemmas.md) when freezing a reusable
interface or supplying a shared store. Use [the directory map](../../SKILL.md)
to distinguish this implemented companion from the separate NL0/Audit A part.

The IR is a typed proof plan with unproved obligations. Python validates its
explicit structure and renders Lean; Lean proves transitions and assembly.
Neither component establishes natural-language fidelity automatically. Record
a separate statement/dependency/route review and distinguish its actual scope.

Use the scripts and maintained examples described in those references. Keep
each input, plan, proof and feedback hash, retain failed attempts, and invalidate
affected descendants after an interface change. Do not add an assumption,
external theorem, opaque declaration or structure field to close an obligation.

Pinned mathlib is the library implementation substrate. A new substantive
mathematical fact not justified by NL0's direct inputs must return to NL0/Audit A;
an API/type conversion difficulty alone is FORMALIZATION-ENGINEERING.

Only stable interfaces permit proof-body parallelism. Prove each local theorem
against explicit direct inputs, then discharge every internal input during
assembly. Do not report conditional local checks as final proof closure.

Keep mathematical object identity global and Lean implementation views local.
Freeze cross-node ports; supply proved conversions as explicit direct inputs.
Do not require one Lean type for every use of an object. A view record documents
a choice; it neither proves equivalence nor chooses the best representation.

Preserve natural NL0 node boundaries. An already justified shared lemma may
be exported once and referenced by multiple nodes. A substantive mathematical
extraction changes the NL0 dependency graph and requires affected Audit A review.
Implementation-only factoring still needs a recorded correspondence review.

Default to direct proof work. Strategy lookup is optional, not a mandatory
diagnosis pass or a proved fact. Keep recipes separate from checked Lean proofs.
Supply a shared store explicitly, record its initial index and complete allowed
conditional interfaces, and recheck every reuse in the current local context.
Cache misses return to ordinary proof work. Source reuse still costs Lean
elaboration; there is no .olean cache or automatic semantic adapter here.

For accepted current structured NL0 use `scripts/workflow.py`: freeze the
source and reviewed IR, run proof work, then prepare/build/check Audit B. It
requires exact source paragraphs, output mapping and direct-input boundaries.
This is artifact orchestration; models/humans still choose representations
and review mathematical fidelity. It does not automatically translate arbitrary
papers or select optimal types. No-extraction is a normal path.

Use `scripts/run_graph.py` for frozen ports/plans, or `model_pilot.py` for the
existing NL/interface/planning pilot. Both use `scheduler.py` for bounded
graph-internal workers. A duplicate shared job within a graph has one producer; downstream
conditional bodies may run at the same time. Record pending/running/completed
jobs. An unfinished producer prevents final closure even if its consumers pass.
Expose `--max-concurrency auto|N` and print the resolved backend/bound/reason
before dispatch. Unknown CLI hard caps use the disclosed fallback of two, not
a claimed maximum. All model stages in one run share one budget; record actual
peak, queue time and intervals. Legacy integer options are compatibility aliases.

This candidate produces translation artifacts and preliminary Lean evidence.
`FRAGMENT-ASSEMBLED` is not an Audit B verdict. After translation, read and apply
[Audit B](audit-b.md) and its [review template](../templates/audit-b.md).
Map every source H/E/M/N/P/D to actual complete Lean types and dependencies;
review definitions, hidden parameters/fields and source fidelity. Run the
fresh kernel/signature/dependency gates, then perform the located semantic
review. Pending receipts cannot pass. Preserve all qualifications and distinguish
development checks from whole-proof acceptance under current Audit A.

Use `scripts/audit_b.py` and its trusted Lean inspector for this generated-graph
adapter. Neither a suggested mapping, equal name/count nor a compiler pass is
semantic evidence. Imported mathematical facts absent from the permitted source
ledger block B; return substantive additions to NL0/Audit A. Report end-to-end
costs including audit work, failed attempts and evidence limits. No general
acceleration or completed Audit C follows from adding this stage.
