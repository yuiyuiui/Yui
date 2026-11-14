# Typed interface and transition IR

The current interface format is version 2, with explicit object views and
reviewed shared exports. It does not change NL0's mathematical authority.

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
   formalization work, not free preprocessing. Normal entry requires actual independent semantic review before freeze.
   Final machine Audit B checks preservation of that reviewed encoding plus
   complete proof integrity. Exact strings alone cannot establish source fidelity.
2. A **transition plan** maps NL0 paragraphs to typed local obligations with
   explicit inputs. It binds the interface-contract hash. Each obligation is
   a proposition under the shared parameter types and only its listed inputs.
   Its proof is a separate artifact. A well-typed plan can still be false.

The core transition engine consumes a frozen interface contract. A fresh model
or human may author this interface from the accepted NL0, explicit representation
choices and library tools. The normal pre-proof reviewer compares source and complete E/P types/definitions.
Final machine Audit B inherits that authority only if actual native evidence
preserves it. The lower-level compatibility path may record `PENDING_AUDIT_B`;
that path still requires actual semantic review and does not satisfy normal admission. Internal regression fixtures
also contain prepared interfaces for deterministic controls. Those fixtures and
their reference ports are never model-visible inputs to a mathematical test.
Reports include interface authoring/review costs; unmeasured owner work is labeled.
Development fragments do not inherit Audit A status.

## Contract file

`contract.json` contains `version: 2`, `id`, `source` (relative file and SHA256),
`source_steps` (the fragment's complete NL argument), `pins`, `header`,
`parameters` (`name`, `type`), `premises` (`id`, `type`, `kind`, `statement`),
`conclusion` (`statement`, `type`), `representation` and `review`. New whole-source
authors also supply `endpoint_correspondence`: a short direct/equivalent
explanation for each E and P, including all target hypotheses. When a development interface omits these notes, postprocessing supplies them
without editing proofs; normal admission still requires their semantic review.
`header` holds the frozen imports/definitions selected during interface authoring;
proof workers cannot edit it. `review` records reviewer/exposure and pending issues;
it cannot grant Audit A/B. `representation` records equality/convergence mode,
norm/range, measure, representative and normalization choices when relevant.

Parameter records may additionally specify `binder_kind: explicit|implicit|instance`,
defaulting to `explicit`. This renders `(x : X)`, `{x : X}`, or `[x : X]`
respectively, so an arbitrary field/space can supply its legitimate typeclass
data in the Lean context. Binder style is preserved through types, assembly,
shared-proof keys and Audit B signatures. It supplies no new mathematical
assumption: the corresponding field/structure prerequisites still need exact
source correspondence review. Ordinary existing contracts retain their default.

`premises` contain project H/E inputs and optional M discharge ports, not extra
unproved facts. New translations can apply any pinned Mathlib result directly,
without an M port or permission record. In a
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

The implementation keeps a fixed cross-node parameter context. Different internal
views may be defined locally. It does not yet synthesize arbitrary per-node
parameter adapters. [Shared lemmas](shared-lemmas.md) specify frozen exports,
permissions, exact reuse keys, physical storage and invalidation.

The implementation uses exact text for terminal interface identity after whitespace
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
statement/input changes invalidate their downstream closure. The frozen record binds
the complete contract and plan. Cached results with stale hashes
must fail before compilation.

The current `scheduler.py` executes bodies within one graph concurrently,
including mathematically dependent conditional bodies, after a typecheck gate.
It records actual start/end intervals and assembles the real proofs. Shared
exports can be sourced from an explicit checked source store. `run_graph.py`
defaults to `max_concurrency=auto`, resolving to the frozen T-node count.
Earlier local Audit A reviews independently default to their current R-node count.
An explicit positive N caps each separate local phase. All local model stages share their case's ledger;
other cases own separate budgets. Python coordination consumes no model slot.
Free slots take the next queued node with a fresh model context. See
[the execution protocol](execution-protocol.md) for records, stops and ownership.
Queue intervals and observed
peak are recorded separately from requested bounds. Bank access is
disabled by default and optional when enabled.

## Status boundary

- `IR-STRUCTURE-PASSED`: explicit format, binding and graph checks only.
- `IR-TYPES-CHECKED`: Lean elaborated all local proposition types.
- `LOCAL-PROOF-CHECKED`: a named conditional T proof compiled.
- `FRAGMENT-ASSEMBLED`: all local proofs and the fixed P compiled together,
  with only the reported fragment premises and kernel foundation axioms.
- `SEMANTIC-REVIEWED`: the named reviewer inspected target/input/route
  correspondence; disclose owner/reference exposure and unresolved items.

None is a new whole-case Audit A/B or evidence of acceleration.
[Audit B](audit-b.md) independently checks every external statement and the
complete target (including hypotheses) against actual Lean types and relevant
definitions, guided by concise author explanations. Pinned Mathlib results are
freely available; no imported-theorem permission ledger is required. Fresh
assembly and root trust inspection remain necessary. Earlier fragment checks
have not retrospectively passed the changed policy. A complete generic Lean
repository adapter and Audit C/NL1 reconstruction remain outside Yui.

## Accepted background supplement

The source authority includes verified node-local Audit A background notes.
Bind its supplement hash in `contract.source.background_supplement_sha256`
before interface freeze. New contracts use `source.background_mode:
node_local_reference`: original M references remain available, but notes are node-local
implementation references rather than extra typed premise ports. Elementary
notes inform local Lean work. The source argument remains unchanged.
Do not create new assumptions or forget notes when constructing task packets.
Audit B requires actual Lean closure; these notes do not restrict Mathlib use.

The interface source also retains the complete `background_supplement`, not
just its hash. Plan steps list the relevant qualified note IDs, for example
`background_notes:["R004.BG001"]`. Workflow freeze checks the paragraph mapping;
local Lean packets receive only their selected notes.

Canonical packets retain those complete notes. The Yui proof carrier projects
them to a compact local index in its initial prompt and supplies a scoped
`read_background_note` tool for full readback. Source/plan bindings and local reference isolation remain in place. The versioned access policy is
`local-background-on-demand-1`, recorded by translation carrier `yui-0.1.1`;
it is not retroactively attributed to old runs or pooled with their timing.
