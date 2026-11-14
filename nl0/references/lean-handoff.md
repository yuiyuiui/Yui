# Handoff from NL0 to Lean and Audit B

Yui implements NL0/Audit A and a separate typed translation/Audit B stage.
Use [the translation entry](../../nl02lean/references/stage.md) and
[integrated workflow](../../nl02lean/references/integrated-workflow.md) after
source acceptance. NL1, Audit C and arbitrary Lean-repository reconstruction
are outside this implementation. A passing source audit is not a Lean proof.

The Lean consumer receives the fixed target/H/definitions, permitted E/M,
and every accepted node-local background note with its bound source evidence,
the entire graph, Audit A, source evidence, and one expanded task packet per R.
Packets include exact direct input statements, definition closure and its
prerequisites, the complete output, source signatures/applications, and proof
argument. They are views of the same authority, not independent editable plans.
Under v2, every output port already includes its full mathematical content;
the consumer must not mine a producer proof for a stronger or missing result.
The per-R packet omits non-input H/ancestor claims and source-proof locators.
Global target context may orient the whole translation but does not enlarge a
node's permitted premises. Definition guards needed by R are direct inputs.
Eligible background notes join the effective local inputs without rewriting
the author graph. Bind their supplement hash in the typed interface.
An ineligible incomplete output or undeclared object is returned to NL0/Audit A before
formalization, rather than silently repaired by the formalization worker.
Only current-format receipts can establish this interface's acceptance.

Map every N/P and substantive bridge to actual Lean declarations. Interface
elaboration, coercion work and proved equivalent reformulations need not become
new mathematics, but any changed mechanism or new substantive theorem must
return to NL0/Audit A. Missing APIs or tactics alone are formalization gaps,
not evidence that the mathematics is false.

New project/opaque axioms, `sorry`, structure fields holding missing results,
and typeclass assumptions cannot fill an audited obligation. Even a local build
against temporary interfaces is not an assembled proof. Final B must inspect
the actual expanded target signature and all non-library assumptions.

No acceleration is claimed by this handoff. Measure authoring, source lookup,
Audit A, model reasoning/tool time, assembly and final checks separately.
Parallel conversion requires stable interfaces and final proof closure; the
critical path, total work and success rate all matter. Internal regression
fixtures are functional controls, not new mathematical tests or benchmarks.

Before parallel translation, preserve the mathematical information actually
needed by each obligation: domains and hypotheses, the meaning of equality or
convergence (pointwise, almost everywhere, norm, and so on), dependencies of
uniform bounds, and conditions for exchanging limits, derivatives, sums or
integrals when the argument uses them. Resolve a genuine ambiguity in the
existing step/explanation fields. Do not expand every routine inference into a
separate node or prescribe Lean tactics in NL0. A long formal implementation is
not by itself a gap in the accepted mathematical argument.
