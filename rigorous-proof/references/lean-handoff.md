# Boundary to Lean, Audit B, and Audit C

This prototype implements NL0 and Audit A only. It does not yet implement or
revalidate the production skill's Lean translation, recursive theorem-signature
audit, NL1 reconstruction, round-trip audit, state-graph integration, or delivery
workflow. Do not describe this candidate as a complete replacement.

A future Lean consumer receives the fixed target/H/definitions, permitted E/M,
the entire graph, Audit A, source evidence, and one expanded task packet per R.
Packets include exact direct input statements, definition closure and its
prerequisites, the complete output, source signatures/applications, and proof
argument. They are views of the same authority, not independent editable plans.
Under v2, every output port already includes its full mathematical content;
the consumer must not mine a producer proof for a stronger or missing result.
The per-R packet omits non-input H/ancestor claims and source-proof locators.
Global target context may orient the whole translation but does not enlarge a
node's permitted premises. Definition guards needed by R are direct inputs.
An incomplete output or undeclared object is returned to NL0/Audit A before
formalization, rather than silently repaired by the formalization worker.
Historical v1 receipts cannot establish this interface's current acceptance.

Map every N/P and substantive bridge to actual Lean declarations. Interface
elaboration, coercion work and proved equivalent reformulations need not become
new mathematics, but any changed mechanism or new substantive theorem must
return to NL0/Audit A. Missing APIs or tactics alone are formalization gaps,
not evidence that the mathematics is false.

New project/opaque axioms, `sorry`, structure fields holding missing results,
and typeclass assumptions cannot fill an audited obligation. Even a local build
against temporary interfaces is not an assembled proof. Final B must inspect
the actual expanded target signature and all non-library assumptions; C must
reconstruct NL1 from actual Lean dependencies, not from recollection of NL0.

No acceleration is claimed by this handoff. Measure authoring, source lookup,
Audit A, model reasoning/tool time, assembly and final checks separately.
Parallel conversion requires stable interfaces and final proof closure; the
critical path, total work and success rate all matter. The Koch smoke test
below is a functional test and natural-language audit, not that experiment.
