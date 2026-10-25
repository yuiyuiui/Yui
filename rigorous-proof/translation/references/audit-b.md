# Audit B: faithful NL0 translation and Lean proof closure

Audit the frozen source and actual exported proof. This stage has two gates:
**semantic/dependency concordance** and **a clean checked Lean proof**. Both
must pass. The checker is an evidence organizer and kernel-inspection adapter;
it cannot decide arbitrary natural-language meaning automatically.

## 1. Freeze authority and coverage

For a whole proof use the current structured NL0 graph, specification, Audit A
receipt, definitions, source ledger, and pinned Lean/mathlib. Revalidate source
and Audit A bindings. Do not replace these with a formalizer-authored summary.
An accepted local revision may instead supply the incremental record from
source_preparation.py. Revalidate the original accepted A, protected content,
new producer/cut reviews and every evidence binding; carry qualifications forward.
This reads existing mathematical reviews rather than rerunning them inside B.
A plain extracted fragment must be labelled development-only, accompanied by
its full independent mathematical inventory and original source bytes. Its
coverage/extraction itself needs semantic review. Never promote it to a
whole-case audit or inherit current Audit A from a legacy proof.

Map every H, E, M, N, P and global definition D. Preserve unused original H in
the final theorem and report unused inputs. Coverage is exact at this source
boundary. An NL0 node has a primary Lean realization and may have multiple
proved administrative helpers; counting all Lean declarations is not the
coverage test. Helpers need explicit roles, complete signatures and proof/dependency
checks. They cannot contain a new assumption, imported mathematical fact or
changed target disguised as implementation detail.

## 2. Review each source/formal pair

Read the full source item and actual elaborated Lean type, not just its name.
Check variables, universes, domains, quantifiers/order, all explicit and implicit
parameters, hypotheses, exceptional cases, constants, uniformity, and conclusion.
Check a.e./pointwise equality, representatives, sup/ess sup, finite/extended
ranges, measures, norms, normalization and domain restrictions when relevant.

- **H**: the actual original hypothesis, without strengthening it or silently
  dropping it. A theorem argument is a mathematical assumption even when it
  does not appear in `#print axioms`.
- **E**: exactly the NL0 external theorem, including all conditions and the
  general statement before specialization. Bundled data/fields must correspond
  field by field. Do not add a project corollary to a published theorem's record.
  Audit A owns verification against the publication; B verifies NL0-to-Lean
  fidelity and carries A's unresolved citation qualifications forward.
- **M**: the actual named, proved declaration in the pinned library, with the
  complete general signature and each used specialization/condition checked.
  A root M port must be discharged by a checked library proof before export;
  it cannot remain an unproved additional hypothesis merely because it is
  called a library theorem.
- **N/P**: the same mathematical conclusion under exactly the allowed inputs
  and definitions, with a real proof. Keep the source dependency boundaries.
  A substantive new mathematical fact returns to a new NL0/Audit A version.
- **D and representations**: the declared mathematical meaning, definition body,
  binding/scope and any existence/domain guards. Distinct Lean views need the
  actual proved relation required by their use; a registry label is not a proof.

Use definitional equality against the reviewed types where possible. If an
equivalent representation is not definitionally equal, prove the bridge and
export the canonical source-facing statement. Do not mark approximate or
"morally equivalent" content PASS. The current executable adapter checks
canonical definitional equality; it does not synthesize these bridges.

## 3. Audit dependencies and hidden assumptions

Inspect actual proof constants, including those selected by automation. The
adapter recursively inspects project-owned declarations and their type/value
references, reports all binder kinds, and follows project structure constructors
to expose proof fields. Review project instances, coercions, selectors and
data fields for hidden mathematical obligations. The source and full elaborated
types remain available for checks that this conservative traversal cannot decide.

Each directly used imported mathematical proof must correspond to a permitted
source M, or a specific calculation explicitly declared in the NL0 logic policy.
Fixed logical constructors/congruence rules are recorded separately. A named
M's already-checked library-internal proof is a trusted boundary; do not demand
that its entire transitive mathlib proof be copied into NL0. Canonical imported
data/definition implementations are a pinned substrate, not extra freely usable
project theorems. Their relevant mathematical meaning still needs review.

An unmatched imported mathematical result blocks B as
`UNMAPPED_IMPORTED_MATHEMATICAL_RESULT`. Explain whether it needs a new source
node/Audit A review or can be proved locally from the allowed inputs. Do not
silently classify it as "standard" or permit every mathlib theorem. This is a
dependency-accounting/formalization issue, not evidence that NL0 is false.

Preserve source R input boundaries. Implementation-only T steps can expand
within a source inference, but cannot borrow another source node not listed
as its input. All cached/shared proofs must match current definitions, types,
conditions and allowed sources. Final assembly must supply their real proofs;
conditional worker success does not close an unfinished shared producer.

## 4. Check the actual Lean proof

Use the recorded pinned toolchain, clean mathlib source/dependency manifest and
offline fresh verifier. Recheck each local proof without sibling declarations,
the exact assembled root, and the source-facing root with library M ports
discharged. Print/extract full elaborated signatures and axiom dependencies.
Scan project input for missing proofs, custom axioms, axiom-like opaque results
and unchecked metaprogramming. Read warnings rather than suppressing them.
The adapter's header scan is conservative; unsupported headers require an
explicitly reviewed adapter, not an ignored failure.

Reject a decoy/wrapper proving a different statement, a changed hypothesis,
an unfinished local proof, custom axioms or stale proof bytes. Report permitted
foundation axioms explicitly. Compilation does not establish natural-language
fidelity, citation truth or absence of additional theorem parameters by itself.

## 5. Execute and record a real review

The rules and [human review template](../templates/audit-b.md) are the skill
part. `scripts/audit_b.py` implements three steps for this candidate's generated
conditional graphs (contract v1/v2). It is not a general multifile Lean-project
auditor or an automatic semantic judge.

```sh
python3 scripts/audit_b.py prepare /absolute/new-audit \
  --contract /absolute/case/contract.json --plan /absolute/case/plan.json \
  --proofs /absolute/run/proofs.json \
  --graph /absolute/case/nl0.json --spec /absolute/case/spec.json \
  --audit-a /absolute/case/audit-a.json
```

For a locally revised current source use
`--incremental /absolute/revision/source-acceptance.json` instead of
`--audit-a` in the command above. The parent audit-v3 format remains unchanged;
a worksheet or development-only local review cannot grant current acceptance.
See [the integrated freeze/run/audit guide](integrated-workflow.md).

Read the independent NL0 first, then complete `mapping.json`: every source ID's
actual selector and reviewed full expected type. A premise selector is
`premise:H001`; a local result is `decl:Translation.T001`; the required exported
target is `decl:AuditBExport.P`. These examples are selectors, not replacement
mathematical statements. The preparer's suggested types are UNVERIFIED proposals
and must not be accepted simply because they repeat the formalizer's contract.
For M also provide the full library type and a tactic body `library_term`
implementing its local root use. `calculation_links` maps exact library names
to indices in the source's declared `logic.calculations`, each separately reviewed.

```sh
python3 scripts/audit_b.py build /absolute/new-audit
```

This produces actual kernel types/dependencies, fresh local/root checks,
mechanical findings, a full review packet and a pending JSON review template.
Every template verdict is UNVERIFIED. Read the paired full statements and
proofs, and write a separate review with located notes/evidence for each source
node, implementation declaration and global check. Do not generate PASS by
looping over the template. Disclose whether the reviewer authored the proof,
saw reference answers, or used the same context. A self-review is not independent.
Before ending a model review stage, validate paired required pointers against
`mechanical.json` and resolve every pointer in `review-packet.json`. Give format
errors back within that stage; a reviewer may still submit FAIL/UNVERIFIED.
Location corrections never justify changing a mathematical verdict to PASS.
If a later owner corrects reference-only metadata, retain the raw review and
disclose the intervention rather than claiming an untouched independent receipt.

```sh
python3 scripts/audit_b.py check /absolute/new-audit \
  --review /absolute/new-audit/completed-review.json
```

The checker rejects unperformed/incomplete reviews, changed inputs, types,
proofs, inspection tools, review packets or evidence. Source/actual signature
pointers are mandatory. These are provenance and receipt checks, not an
authentication system or mathematical validation of a reviewer who writes a
false assertion. Semantic judgment remains the reviewer's responsibility.

`AUDIT-B-PASSED` requires complete whole-graph coverage, current upstream Audit A,
all mechanical gates and all actual semantic reviews. A development fragment or
unverified upstream A can at most receive `DEVELOPMENT-AUDIT-B-PASSED` with its
scope/qualifications. A receipt proves neither external publications in Lean
nor model-independent certification. Preserve all failures. Edits revoke the
affected audit; start a new audit directory instead of overwriting evidence.

Record preparation, kernel inspection and semantic-review cost separately and
include them when claiming end-to-end formalization acceleration. Exact frozen
audit results may be reused only within their recorded scope and dependency
versions. Audit C/NL1 round-trip reconstruction is a different future stage.

## Audit A background notes

Source concordance includes the accepted background supplement. Omitted basic
M registration supplied during Audit A is disclosed as such. Validate its
policy, evidence and hash. With `source.background_mode: node_local_reference`,
map only the original H/E/M/N/P/D inventory. The note bodies remain references;
do not generate extra M ports or mapping entries for every note. The dependency
inspector records actually used note declarations and checks their permission
at the corresponding source inference. A note from another inference cannot
authorize that use. The semantic reviewer checks the actual instantiation,
conditions, source evidence and complete Lean representation.

Old contracts without this field retain the `promoted_inputs` interpretation
and its effective M mapping. Notes are no additional original H or external
axioms. Mathematical acceptance of a note cannot stand in for a compiled Lean
implementation. Interface semantics deferred before proof work remain pending
until this actual final review; no prior interface PASS is assumed.

The kernel inspector distinguishes ordinary proof constants from registered
typeclass instances occurring exclusively in actual instance-argument positions.
The latter are recorded as representation support and receive explicit semantic
review of their full signatures and available source conditions. This does not
license an instance used as an ordinary proof, a new hypothesis, or arbitrary
Mathlib results. Do not require a separate NL0 M node for every implicit
structure projection inserted by elaboration.
