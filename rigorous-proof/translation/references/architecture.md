# Typed interface and transition IR, versions 1 and 2

Version 1 remains readable without rewriting historical inputs. Version 2 adds
explicit object views and reviewed shared exports; it does not change NL0's
mathematical authority. This is Yui's implemented translation module.

## Two layers of authority

The authoritative NL0 and Audit A are immutable within a translation run.
A translation-entry extraction may produce a separately versioned source under
[the local revision protocol](source-refactoring.md), never overwrite the old
authority. Its actual scoped reviews and unchanged baseline are combined by
source_preparation.py; a worksheet alone cannot establish acceptance. After source selection and
acceptance, an IR is a derived artifact:

1. An **interface contract** fixes source/packet hashes, toolchain, shared
   Lean definitions, parameters, exact direct premises, the conclusion and the
   correspondence of these expressions with NL0. Creating this contract is
   formalization work, not free preprocessing. A semantic reviewer must accept
   representation choices before parallel proof-body work. A source-fidelity
   review cannot be replaced by exact string comparison.
2. A **transition plan** maps NL0 paragraphs to typed local obligations with
   explicit inputs. It binds the interface-contract hash. Each obligation is
   a proposition under the shared parameter types and only its listed inputs.
   Its proof is a separate artifact. A well-typed plan can still be false.

The core transition engine consumes a frozen interface contract. A fresh model
or human may author this interface from the accepted NL0, explicit representation
choices and library tools. A separate actual semantic review compares the result
with the source; elaboration alone cannot do this. Internal regression fixtures
also contain prepared interfaces for deterministic controls. Those fixtures and
their reference ports are never model-visible inputs to a mathematical test.
Reports include interface authoring/review costs; unmeasured owner work is labeled.
Legacy extracts do not inherit current Audit A status.

## Contract file

`contract.json` contains `version: 1` or `2`, `id`, `source` (relative file and SHA256),
`source_steps` (the fragment's complete NL argument), `pins`, `header`,
`parameters` (`name`, `type`), `premises` (`id`, `type`, `kind`, `statement`),
`conclusion` (`statement`, `type`), `representation` and `review`.
`header` is owner-reviewed, immutable Lean imports/definitions, never a model
output channel. `review` records actual reviewer/exposure and pending issues;
it cannot grant Audit A/B. `representation` records equality/convergence mode,
norm/range, measure, representative and normalization choices when relevant.

Parameter records may additionally specify `binder_kind: explicit|implicit|instance`,
defaulting to `explicit`. This renders `(x : X)`, `{x : X}`, or `[x : X]`
respectively, so an arbitrary field/space can supply its legitimate typeclass
data in the Lean context. Binder style is preserved through types, assembly,
shared-proof keys and Audit B signatures. It supplies no new mathematical
assumption: the corresponding field/structure prerequisites still need exact
source correspondence review. Ordinary existing contracts retain their default.

`premises` are exact direct H/E/M/N inputs, not extra convenient facts. In a
multi-node package, an N port is resolved by its actual upstream declaration.
Within one fragment, a conditional result may retain its declared N port, but
the report must say that the larger proof was not assembled. Definitions must
be fully supplied in the frozen header; existence guards remain premises.

## Plan file

`plan.json` contains the contract's `version`, `contract_sha256`, `representation_notes`,
`steps` and `terminal`. Each step has `id` (`Tddd`), `statement` (Lean Prop),
`inputs` (direct premise IDs or other T IDs), `source_steps` (NL paragraph IDs)
and `explanation`. The terminal statement must equal the frozen Lean conclusion.
Every step must reach terminal and every source paragraph must be covered.
The dependency graph must be acyclic. Full source text is retained; a hash or
paragraph ID is not a replacement for mathematical content.

Version 2 optionally adds `objects` to the contract. Each object has an Oddd ID,
a complete mathematical `definition` and named `views` with Vddd IDs,
`lean_type` and `meaning`. Identity is global; views are selected per step with
`representations: [{object, view, expression}]`. The frozen types-only gate
checks each expression against its declared Lean type under that step's inputs.
Semantic fidelity is still separately reviewed. Nodes may also record
`bridges: [{object, from, to, input, explanation}]`; every bridge provider must
be an actual direct input. Records cannot replace the bridge proof.
The input's complete proposition determines what the bridge actually supplies:
it may transport a particular equality/property without asserting a general
isomorphism or a conversion in both directions. Check that narrower role in the
correspondence review; matching two view IDs is not a semantic proof.

The prototype keeps a fixed cross-node parameter context. Different internal
views may be defined locally. It does not yet synthesize arbitrary per-node
parameter adapters. [Shared lemmas](shared-lemmas.md) specify frozen exports,
permissions, exact reuse keys, physical storage and invalidation.

The prototype uses exact text for terminal interface identity after whitespace
normalization. Equivalent reformulations require a proved bridge or a reviewed
new contract version. This conservative constraint is an implementation choice,
not a claim that mathematical equivalence is textual equality.

## Generated Lean

Each T becomes a standalone conditional theorem. Only its declared input
proofs are binders. It cannot see another T declaration during local checking.
The generated final P applies the actual local theorems in topological order
and discharges every T input. No `sorry`, auxiliary axiom, project predicate,
unproved instance or placeholder module is generated at any stage.

The initial implementation supports ordinary Lean Prop obligations under a
fixed context, not dependent witness export or arbitrary tactic-state mutation.
Package witnesses in an existential/structure statement; projections and
existence-dependent definitions need explicit contracts. Such packaging cannot
add fields holding results absent from the original theorem.

## Parallel execution and invalidation

All local proof bodies may be developed concurrently after the contract and
plan interfaces are frozen: an input T is a local theorem parameter, not an
axiom. Mathematical dependencies govern final assembly, not necessarily worker
launch order. Shared definition changes invalidate every affected interface;
statement/input changes invalidate their downstream closure. Version 1 binds
the entire contract/plan hash conservatively. Cached results with stale hashes
must fail before compilation.

The current `scheduler.py` executes bodies within one graph concurrently,
including mathematically dependent conditional bodies, after a typecheck gate.
It records actual start/end intervals and assembles the real proofs. Shared
exports can be sourced from an explicit checked source store. `run_graph.py`
defaults to `max_concurrency=auto`, resolving to a disclosed fallback two when
the CLI hard cap is unknown. All local model stages share the run budget.
Queue intervals and observed
peak are recorded separately from requested bounds. Bank access is
disabled by default and optional when enabled. Historical 0.4 runs still used
sequential bodies and must retain that interpretation.

## Status boundary

- `IR-STRUCTURE-PASSED`: explicit format, binding and graph checks only.
- `IR-TYPES-CHECKED`: Lean elaborated all local proposition types.
- `LOCAL-PROOF-CHECKED`: a named conditional T proof compiled.
- `FRAGMENT-ASSEMBLED`: all local proofs and the fixed P compiled together,
  with only the reported fragment premises and kernel foundation axioms.
- `SEMANTIC-REVIEWED`: the named reviewer inspected target/input/route
  correspondence; disclose owner/reference exposure and unresolved items.

None is a new whole-case Audit A/B or evidence of acceleration. The prototype
does not automatically audit unrestricted mathlib automation dependencies.
Review used library facts and do not infer permitted-premise fidelity merely
from kernel acceptance. [Audit B](audit-b.md) is now a separate implemented
rule/template/checker stage for these generated graphs. It inspects actual
elaborated types, project structure fields, instances/dependencies and source
mapping, then requires actual semantic reviews. Earlier fragment checks have
not retrospectively passed it. A complete generic Lean-repository adapter and
Audit C/NL1 reconstruction remain outside Yui.
