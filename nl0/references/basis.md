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

The [foundation planning strategy](basis-planning.md) covers parallel research, shared dependencies and the transition from a draft graph to native proofs.

## Submission schema

Submit an object with exactly:

```text
version: "yui-basis-2"
global_graph: {propositions:[{id,statement}], inferences:[{id,inputs,output,basis:[B IDs]}]}
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
- Class 3 is a checked derivation with nonempty `uses`. Supply a pinned type and proof. Use a provisional E for direct consumers and null for a dependency used only by another prepared declaration. The final export applies the prepared proof.
- Class 4: `unresolved`, E port, `lean:{type,proof:null}`. Retain a verified
  complete textbook theorem and evidence. Missing sources, contradictions,
  unspecified statements and internal proof gaps are not 4.

`uses` records genuine dependencies; unknown IDs and cycles are rejected.
Prepared declarations may use their declared predecessors as `YuiBasis.Bddd`. Class 3 can depend on earlier prepared derivations. Classes 1 and 2 use existing pinned or adapted declarations.
Their closed types bind their own parameters/typeclasses, without project H/E.
Use inline local Lean constructions for private helpers. All used 1/2/3 proofs
must compile and pass dependency/axiom inspection in 2basis. The header contains
object definitions, not axioms, theorem declarations or executable metaprogramming.

Evidence is `{input:"declared-document-ID"}` or an actual retained own-stage
`{path,sha256}`. Classes 2 and 4 require retained evidence in new submissions. References bind actual bytes.
the basis reviewer checks source completeness and classification before release. The shared Audit A also reviews the actual later uses.

Use `base_candidate:N` with JSON-pointer patches into the basis object, or
`accept_candidate:N`. `base_input:"prior-basis.json"` continues user-requested
reduction. Every revised artifact receives the same real native checks.
Compiler/resource nonpass is feedback, not mathematical impossibility.

For long reductions, `save_basis_draft` saves partial work without running Lean;
`read_basis_draft` reads only that author's actual saved candidates, with bounded
JSON-pointer pagination. A context-reset checkpoint names the newest draft and
last machine-checked candidate separately. Saving does not make a proof complete.

## Early statement and use review

Only a submitted, machine-checked basis enters the separate basis reviewer role.
It compares the prepared declarations and residual assumptions together against the original sources, the
rewritten use and the propositions printed by Lean. For class 4 it reads the
value of the proposition definition. The comparison covers quantifier order,
uniform constants, domains, assumptions, direction, definitions and adapters.
The basis reviewer checks each prepared class 3 and its consumers. The retained v1 format represents historical NL-only derivations.

The reviewer submits a located PASS, FAIL or UNVERIFIED for every assigned item.
A normal-policy nonpass goes back to the same basis author with the prior
artifact and findings. First-pass policy retains the first nonpass. Saving or
checking drafts costs no reviewer call. Each submitted revision uses at most
one review batch. An empty scope uses zero calls. Exact previous assessments
can be reused within the case when their sources, rules, shared route and
connected dependencies and uses still match. Unchanged rejected work retains
its findings and pauses. The execution ledger includes both roles.

The active context binds the selected basis, native check and semantic report.
Downstream readback verifies their inputs and the reviewer's complete submission.
Historical native-only contexts use their original runtime snapshots.

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
user-stopped outcome and releases owned roles. The batch reads its incident and
control after case exit and admits the next queued case. A case deadline also
applies while the operator choice is pending. Stale/changed/dead-owner decisions
are rejected. No silent conditional fallback.

Transport faults, cancellation, budgets and native limits use existing handling.
Unexpected faults retain evidence at PAUSED_ERROR, without authorizing cleanup
of real runs. Test cleanup is a separate test-only boundary.

## Explicit revision of a downstream basis defect

If a global NL0 or interface role finds a conflict in a frozen B statement or
Lean type, use `report_basis_defect`. Identify the exact field and value, quote
the original source and the affected use, and explain the correction. A local
proof worker can send a connection problem through its existing diagnosis
route. The global reporting stage checks the citations against the documents it
was given. A valid report pauses the case as `BASIS_REVISION_REQUIRED`.

Inspect the finding before choosing a revision. To continue, cancel the paused
case, wait for the case and its worker processes to exit, then run

```sh
python3 -B nl0/scripts/yui.py resume RUN --repair-basis --prepare-only
python3 -B nl0/scripts/yui.py execute NEW_RUN
```

The new job starts from the previous basis and the located objection under the
original target, profiles, policy, worker limit and deadline. The prior run keeps
its evidence and costs. The revised basis must pass the native and correspondence
checks, including a response to the objection for a retained formal item. New
NL0, Audit A, interface, proof and final checks follow. If the old round had
completed local Lean bodies, an identical local program and use context may
supply a candidate after the new interface freeze. The proof queue checks it
with the current kernel before skipping a worker. Audit A's whole-context
binding invalidates the previous acceptance. Any new residual choice requires
its own operator decision.

## Shared translation and final closure

The interface author receives prepared basis header/E types. Preserve that
header prefix and exact E types; independently review the NL/Lean correspondence
before freezing. Original H and whole target retain ordinary semantic review.
All shared proof, repair, assembly and worker machinery is reused.

After machine Audit B, b2lean applies prepared 1/2/3 proofs to `AuditBExport.P` and
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
