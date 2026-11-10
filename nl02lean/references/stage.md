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
Neither component establishes natural-language fidelity automatically. The normal entry obtains full external/target fidelity review independently
before freeze. Final machine Audit B checks that actual E/P, their defining
environment and complete native proof still match that reviewed authority.
Only proof-valid interface drift opens exceptional B-final semantic review. Lower-level legacy mechanical
freezes may still record `PENDING_AUDIT_B`; that is not the normal pre-proof gate.

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
After the queue completes, attempt mechanical [assembly and export](assembly.md).
Use the serial connection author only for actual repair under the immutable
contract. Compile and inspect the complete source-facing proof before final
machine acceptance or a proof-valid B-final exception.

Keep mathematical object identity global and Lean implementation views local.
Freeze cross-node ports and planned typed conversion obligations. Their proof
bodies are worker tasks; assembly/Audit B must supply every actual conversion.
The normal interface preflight checks types, source boundaries and actual
independent source/type judgments. Final machine Audit B checks preservation of those independently reviewed
choices in the completed proof.
Use [proof diagnosis and reviewed repair](proof-repair.md) for structured worker
obstructions, passive progress records and the serial proof-connection boundary.
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
before dispatch. Default `auto` uses the frozen T-node count, including shared
lemmas and representation conversions; an explicit positive N caps the queue.
Proof jobs share their case proof budget; translation
preparation and Audit B use a separate serial budget and the same all-stage ledger.
Earlier local Audit A R reviews have their own N-slot budget. Record
proof-only utilization separately from review activity, queue time and intervals.
Legacy integer options are compatibility aliases.
Here a run is one case, not a multi-case batch. Python coordination does not
occupy a model slot. Apply [the execution protocol](execution-protocol.md) for
the node queue, structured status file, scoped cancellation, retained errors and successful role finalization.

This stage produces translation artifacts and checked local Lean evidence.
`FRAGMENT-ASSEMBLED` is not an Audit B verdict. After translation, read and apply
[Audit B](audit-b.md) and its [review template](../templates/audit-b.md).
Map each original external E and complete P to its actual encoded Lean type
with a short direct/equivalent correspondence explanation. P includes its
parameters, hypotheses and conclusion. The independent pre-freeze reviewer
checks these notes against source/types/definitions; B-final repeats semantic
responsibility only for the explicit valid-proof/interface-drift exception. No separate
M/H/N/D semantic ledger is required. Run the fresh standalone build and kernel
closure checks; pending receipts cannot pass. Preserve inherited qualifications
and distinguish development checks from whole-proof acceptance.

Use `scripts/audit_b.py` and its trusted inspector for these generated graphs.
A suggested explanation, equal label or compiler pass is not semantic evidence.
Version-2 Audit B permits faithful equivalent encodings without a redundant
literal Mathlib representation; actual cross-representation conversions still
need checked proofs. Report end-to-end costs including audit work and failures.
No general acceleration or completed Audit C follows from this stage alone.
### Using a generic intermediate result

Name a generic producer's declaration universes in its step, for example
`"universe_params":["u","v"]` with `Type u` for the ambient type and `Type v`
for its indexing type. Use fresh names not declared in the public header.
Ordinary monomorphic steps keep the existing `inputs` form. A current preflight
rejects anonymous `Type*`/`Sort*` in a T statement consumed by another step:
copying that text into a local hypothesis would silently fix its universes.

An internal consumer still lists the producer in `inputs`. Also specify the
producer's universe levels **in declaration order** and the actual applications
the proof needs. For instance, for a one-universe producer quantified over a
metric space, this consumer has a use at the concrete space `Rn n`:

```json
{"input_instances":{"T005":[{"levels":["0"],"uses":[{"args":["Rn n"]}]}]}}
```

The local binder is `h_T005`. Additional instances of the same producer in
this consumer are named `h_T005_2`, `h_T005_3`, etc. Each use may declare
`parameters` with the usual name/type/binder_kind syntax, for objects introduced
inside a proof. With `levels:["u","0"]`, a probe can use an arbitrary ambient
`M : Type u` and a small index such as `Fin n`. In `args` a string is a Lean
argument and a positive integer is a projection (e.g. 2 for `.2`). Optionally
supply `expected` to check the resulting type, or `explicit:true` to use
`@h_T005`. For an entire unapplied input use empty args with its expected type.

On the 2basis route, a direct foundation in `working-foundation-ports.json`
with `universe_params` supports the same `levels` and `uses` rows. Supply them
when a call needs a particular level, including the universe of a type introduced
inside the consumer. Lean checks the call against the frozen proposition and
connects it to the checked foundation theorem. Hypotheses and unresolved or
conditional assumptions keep their ordinary local binders.

Preflight compiles these actual calls and the dependency connections together
before dispatch. Its synthetic signature witnesses take a private `False`
assumption; they are discarded, never provided to a worker, and never exported.
Assembly uses the actual proved upstream theorem at each selected instance.
Internal repair may revise step-local universes and uses, and must preserve
the source hypotheses, public definitions and target. A proof worker discovering
a new incompatible use should report the producer, consumer and actual Lean error.
