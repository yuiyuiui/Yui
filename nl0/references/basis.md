# Optional unconditional formalization

`--track full --formalization unconditional` selects
`2basis -> shared NL0/Audit A -> shared nl02lean/Audit B -> b2lean`.
The default is `conditional`; `full` still means both existing stages, not an
unconditional theorem. Existing jobs without `formalization` remain conditional.
Unconditional entry starts before NL0: accepted NL0 cannot skip the required
original-target/basis Audit A through `translate`.

## Authority

The original selected target and documents remain immutable authority for H,
quantifiers, domains, parameters, normalizations, constant dependencies and any
specified algorithm. 2basis may change the proof route and representations.
The model chooses mathematical reductions. Python checks records, versions,
actual Lean proofs and interfaces; it does not certify source fidelity.
No difficulty scores, forced reduction tree or Mathlib-use whitelist apply.

One subsequent Audit A receives original documents, `basis-proof.md`, complete
`basis-registry.json`, retained source evidence and `proof-context.json`.
Its global lane checks original-target fidelity, replacement dependencies and
structure; ordinary local R lanes check all new arguments. There is no preceding
full mathematical audit of 2basis. NL0 faithfully presents the active basis route,
without requiring the original proof route to remain unchanged. Review reuse
includes active context; source warnings retain their original qualification.

## Submission schema

Submit an object with exactly:

```text
version: "yui-basis-1"
full_target: exact target-selection.json full_target
proof: complete basis-reduced natural-language proof
lean_header: "import Mathlib\n" followed by needed object definitions
dependencies: [dependency, ...]
replacements: [{original_dependency, replacement:[B IDs], explanation}, ...]
```

Each dependency has exactly:

```text
id: B001 (three or more digits)
category: 1 | 2 | 3 | 4
statement: complete mathematical statement
origin: {kind, reference, revision, evidence:[evidence reference, ...]}
compatibility: native | adapted | internal | unresolved
uses: [other B IDs]
port: E001 | M001 | null
lean: {type: closed Lean proposition, proof: tactic body after "by"} | null
justification: actual source/reduction/compatibility account
```

Origin kinds are `mathlib`, `lean-library`, `derivation`, `textbook`, respectively.
Reference identifies the actual declaration/public source/theorem or derivation;
revision identifies its version/edition. Category and compatibility are distinct:
a Mathlib result from another version is still class 1, possibly `adapted`.

- Class 1/native: direct Mathlib (`port:null`) or optional M port.
- Class 1/adapted and class 2: provisional E port with actual checked proof in
  the pinned target environment. Prepare needed adapters and retained source
  attribution now; no whole-library migration prerequisite.
- Class 3: `internal`, `port:null`, `lean:null`, nonempty `uses`. Give a concrete
  derivation in the proof, recursively from 1/2 via other 3, with no unresolved
  4. Existing NL0/T workers prove it internally; it cannot become an E premise.
- Class 4: `unresolved`, E port, `lean:{type,proof:null}`. Retain a verified
  complete textbook theorem and evidence. Missing sources, contradictions,
  unspecified statements and internal proof gaps are not 4.

`uses` records genuine dependencies; unknown IDs and cycles are rejected.
Prepared 1/2 proofs may refer to other prepared 1/2 proofs as `YuiBasis.Bddd`.
Their closed types bind their own parameters/typeclasses, without project H/E.
Use inline local Lean constructions for private helpers. All used 1/2 proofs
must compile and pass dependency/axiom inspection in 2basis. The header contains
object definitions, not axioms, theorem declarations or executable metaprogramming.

Evidence is `{input:"declared-document-ID"}` or an actual retained own-stage
`{path,sha256}`. Class 4 requires evidence. References bind actual bytes;
source completeness and classification still belong to Audit A. Evidence is
staged for the later author and reviewer.

Use `base_candidate:N` with JSON-pointer patches into the basis object, or
`accept_candidate:N`. `base_input:"prior-basis.json"` continues user-requested
reduction. Every revised artifact receives the same real native checks.
Compiler/resource nonpass is feedback, not mathematical impossibility.

For long reductions, `save_basis_draft` saves partial work without running Lean;
`read_basis_draft` reads only that author's actual saved candidates, with bounded
JSON-pointer pagination. A context-reset checkpoint names the newest draft and
last machine-checked candidate separately. Saving does not make a proof complete.

## Remaining class 4 and errors

The existing retained controller records an exact `basis-decision` incident.
Only explicit user choices authorize these commands:

```sh
python3 -B nl0/scripts/yui.py basis-decision RUN --incident ID --action stop
python3 -B nl0/scripts/yui.py basis-decision RUN --incident ID --action continue
python3 -B nl0/scripts/yui.py basis-decision RUN --incident ID --action accept-conditional
```

Continue retains the author/prior artifact. Accept binds exact residual IDs and
artifact, without approving future additions. Stop records an unfinished
user-stopped outcome and releases owned roles. Stale/changed/dead-owner decisions
are rejected. No silent conditional fallback.

Transport faults, cancellation, budgets and native limits use existing handling.
Unexpected faults retain evidence at PAUSED_ERROR, without authorizing cleanup
of real runs. Test cleanup is a separate test-only boundary.

## Shared translation and final closure

The interface author receives prepared basis header/E types. Preserve that
header prefix and exact E types; independently review the NL/Lean correspondence
before freezing. Original H and whole target retain ordinary semantic review.
All shared proof, repair, assembly and worker machinery is reused.

After machine Audit B, b2lean applies prepared 1/2 proofs to `AuditBExport.P` and
generates `YuiClosed.P`, with only H and explicitly approved 4. Compile the final
standalone source and inspect its actual full signature and transitive trust.
An old conditional receipt cannot establish final closure. No final NL model.
Missing proofs, extra premises, signature/source/version drift, unexpected axioms
or incomplete inspection fail acceptance.
An exception with unconfirmed native shutdown retains a marked workspace and
diagnostic for owned cleanup; normal completed native checks release scratch.

`b2lean/Proof.lean`, `check.json` and `report.json` bind the final export.
Only closed output with unqualified upstream authority is `UNCONDITIONAL_LEAN`
and `WORKFLOW-PASSED`. Approved 4 yields `CONDITIONAL_LEAN`. A closed kernel proof
with remaining source qualifications is `CLOSED_LEAN_SOURCE_QUALIFIED`, with
`closure.kernel_closed:true` but no unconditional workflow acceptance. Both
qualified cases remain `WORKFLOW-CONDITIONAL`, with warnings and an unmet
unconditional goal. Interface drift cannot inherit exact frozen closure.
