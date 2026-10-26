# Yui translation and Audit B

Preserve the given mathematical proof route, target, hypotheses and allowed
external results. Keep the original NL0/Audit A artifacts immutable. Treat
legacy fragments as development inputs, not newly Audit-A-approved packages.

Start with [the minimal translation procedure](minimal-translation.md).
Read [architecture](architecture.md) and [translation rules](translation-rules.md)
when their details are needed; do not preload every reference.
At translation entry, use [local source refactoring](source-refactoring.md)
and its [revision record](../templates/source-refactoring.md) if sharing requires
changing NL0. Extract existing derivations with an explicit patch boundary;
do not reconstruct NL0 or repeat the whole audit. This is not an additional
step for NL0-only work. Preserve old evidence, review new proofs/substitution
cuts. Use `scripts/source_preparation.py` to validate the inheritance and actual
new reviews; the parent checker still owns ordinary Audit A authority.
Read [the integrated execution guide](integrated-workflow.md) when
staging a revision or executing a complete source-to-Audit-B workflow.
Use [the working pipeline map](workflow.md) to distinguish source
R nodes, implementation T obligations, actual assembly and Audit B.
Use [obstacle routing](obstacle-routing.md) when a transition stalls.
Use [local audited-note guidance](translation-rules.md#use-local-audit-a-notes-when-they-can-shorten-an-implementation-route)
when its current goal needs a premise or transport already explained by a note;
familiar direct proof work requires no note lookup.
Read [the experiment protocol](experiments.md) before a model run.
Read [shared lemmas](shared-lemmas.md) when freezing a reusable
interface or supplying a shared store. [The skill entry](../../SKILL.md)
connects this translation module to the NL0/Audit A stage.

The IR is a typed proof plan with unproved obligations. Python validates its
explicit structure and renders Lean; Lean proves transitions and assembly.
Neither component establishes natural-language fidelity automatically. Record
an external/complete-target fidelity review in final Audit B and distinguish its actual
scope. The default interface freeze is mechanical, with semantic status
`PENDING_AUDIT_B`; a separate pre-proof model review is optional.

Use the scripts described in those references. Keep
each input, plan, proof and feedback hash, retain failed attempts, and invalidate
affected descendants after an interface change. Do not add an assumption,
external theorem, opaque declaration or structure field to close an obligation.

All proved results in the pinned Mathlib environment are freely available in
stage two; no source-M registration or use-permission audit is required. A new
external axiom or stronger hypothesis must return to the affected source
boundary. An API/type conversion difficulty alone is FORMALIZATION-ENGINEERING.

Only stable interfaces permit proof-body parallelism. Prove each local theorem
against explicit direct inputs, then discharge every internal input during
assembly. Do not report conditional local checks as final proof closure.
After the queue completes, the serial postprocessing author follows
[assembly and export](assembly.md), compiles the complete source-facing proof,
and hands real checked evidence to a separate independent Audit B reviewer.

Keep mathematical object identity global and Lean implementation views local.
Freeze cross-node ports and planned typed conversion obligations. Their proof
bodies are worker tasks; assembly/Audit B must supply every actual conversion.
The interface preflight checks types and source boundaries. Final Audit B checks
semantic fidelity of those choices against the completed proof.
Do not require one Lean type for every use of an object. A view record documents
a choice; it neither proves equivalence nor chooses the best representation.

Preserve natural NL0 node boundaries. An already justified shared lemma may
be exported once and referenced by multiple nodes. A substantive mathematical
extraction changes the NL0 dependency graph and requires affected Audit A review.
Implementation-only factoring is checked through assembly and endpoint fidelity.

Default to direct proof work. Strategy lookup is optional, not a mandatory
diagnosis pass or a proved fact. Keep recipes separate from checked Lean proofs.
Supply a shared store explicitly, record its initial index and complete allowed
conditional interfaces, and recheck every reuse in the current local context.
Cache misses return to ordinary proof work. Source reuse still costs Lean
elaboration; there is no .olean cache or automatic semantic adapter here.

For accepted current structured NL0 use `scripts/workflow.py`: freeze the
source and type-checked IR, run proof work, then prepare/build/check Audit B. It
requires exact source paragraphs, output mapping and project-input boundaries;
Mathlib references are excluded from input-permission comparisons.
This is artifact orchestration; models/humans still choose representations
and review mathematical fidelity. It does not automatically translate arbitrary
papers or select optimal types. No-extraction is a normal path.

Use `scripts/run_graph.py` for frozen ports/plans. `model_pilot.py` is the internal isolated proof-stage carrier; clean text author/review stages are in the parent scripts/clean_stage.py. Both use `scheduler.py` for bounded
graph-internal workers. A duplicate shared job within a graph has one producer; downstream
conditional bodies may run at the same time. Record pending/running/completed
jobs. An unfinished producer prevents final closure even if its consumers pass.
Expose `--max-concurrency auto|N` and print the resolved backend/bound/reason
before dispatch. Unknown CLI hard caps use the disclosed fallback of two, not
a claimed maximum. Proof jobs share their case proof budget; preparation and
reviews use a separate serial budget and the same all-stage ledger. Record
proof-only utilization separately from review activity, queue time and intervals.
Legacy integer options are compatibility aliases.
Here a run is one case, not a multi-case batch. Python coordination does not
occupy a model slot. Apply [the execution protocol](execution-protocol.md) for
the node queue, structured status file, scoped cancellation and finite exit.

This stage produces translation artifacts and checked local Lean evidence.
`FRAGMENT-ASSEMBLED` is not an Audit B verdict. After translation, read and apply
[Audit B](audit-b.md) and its [review template](../templates/audit-b.md).
Map each original external E and complete P to its actual encoded Lean type
with a short direct/equivalent correspondence explanation. P includes its
parameters, hypotheses and conclusion. The independent reviewer checks these
notes against source, actual types and relevant definitions. No separate
M/H/N/D semantic ledger is required. Run the fresh standalone build and kernel
closure checks; pending receipts cannot pass. Preserve inherited qualifications
and distinguish development checks from whole-proof acceptance.

Use `scripts/audit_b.py` and its trusted inspector for these generated graphs.
A suggested explanation, equal label or compiler pass is not semantic evidence.
Version-2 Audit B permits faithful equivalent encodings without a redundant
literal Mathlib representation; actual cross-representation conversions still
need checked proofs. Report end-to-end costs including audit work and failures.
No general acceleration or completed Audit C follows from this stage alone.
