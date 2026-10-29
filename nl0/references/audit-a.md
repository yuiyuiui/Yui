# Audit A: mathematical review in Yui V2

<!-- yui-nl0-acceptance:begin -->
## Shared mathematical acceptance requirements

Contract version: `yui-v2-nl0-audit-a-1`.

The author and independent auditor use this same mathematical standard. V2
reviews a complete natural-language proof and necessary mathematical detail.
Specific Lean declarations, signatures, representations and proof tactics are
implementation work for nl02lean, not prerequisites for ordinary NL0 review.
The following grouped criteria replace V1's ten separate per-R report rows.

| ID | Review group | Author evidence group | Requirement |
| --- | --- | --- | --- |
| `target` | package | original_context_note | Preserve the complete original theorem, every original H, quantifier, domain, normalization and supplied core proof route. A parameter or definition cannot hide a hypothesis or desired conclusion. |
| `definitions` | package | declaration_check | Define mathematical objects and notation sufficiently for their actual uses. Check types, dependencies, construction guards and legitimate local introductions. A definition grants no unproved property. |
| `sources` | package | original_context_note | Check complete E statements, primary-source identity, context and conditions under the source policy. An explicitly selected native M retains its bound signature checks; authors need not introduce M nodes for ordinary mathematical background. Unavailable originals remain disclosed UNVERIFIED source assumptions. |
| `structure` | package | original_context_note | Verify the actual AND dependency graph, unique producers, absence of cycles and faithful exported statements. Retain every original H and disclose unused H. Internal results are proved, never new roots. |
| `statement_closure` | closure | output_notes | Inputs and output state the mathematical content, objects, domains, quantifiers and conditions their consumers need. Check actual object occurrences and definitions. No missing identification can be supplied by an absent producer proof or a paper equation number. |
| `dependency_closure` | closure | dependency_and_local_assumption_check | Check direct input use, earlier local facts, witness existence and proper discharge of assumptions. No circular dependency, future fact or escaped local object is allowed. Mathematically checked routine background may supplement the packet without prior native lookup. |
| `argument` | inference | dependency_and_local_assumption_check | Verify the complete implication and every output clause at ordinary rigorous mathematical granularity, including material limiting operations, domains and regularity. Compress correct routine reasoning; locate a real gap rather than requiring a transcript of elementary steps. |
| `applicability` | inference | source_application_check | Check actual instantiations and all material premises of invoked E/M or routine background facts, with grounds in inputs or earlier local derivations. Required bridges are proved. A familiar theorem name or a proposed Lean tactic supplies no mathematical justification. |

### Scope and mathematical boundary

Global review owns target/H fidelity, definitions, source statements and graph
consistency. Each local reviewer owns the conditional implication at its R
node. Conditional packet replay has a different input boundary: these statements are conditional premises.
The local reviewer does not re-prove an input N or re-audit its source paper;
the graph and that producer's review establish those separate obligations.
Conversely, an input N exports only its full statement, not unexported facts
from the producer's body. The fifth local criterion, packet_replay, assesses
sufficiency under this exact boundary. The controller records execution
identity and exposure independently of the mathematical judgment.

Review correctness rather than the number of displayed lines. Ordinary valid
textbook compression is allowed. Material missing hypotheses, witnesses,
constructions, scope discharges or core arguments are not implementation gaps.
Return them for located author repair and fresh review. No theorem needs to be re-proved
when its legitimate mathematical source and actual application suffice.

The domain-neutral elementary-language-4 profile retains equality, supplied
definitions, finite arithmetic/order reasoning and finite sums. It is syntax
and elementary calculation policy, not a subject vocabulary or theorem list.
Objects from any field use problem parameters, D definitions or scoped locals.
Neither an author-written calculation list nor a familiar symbol adds a theorem.

### Mathematical background: mathematical-background-v2-1

A reviewer may positively assess a routine, local mathematical fact without
first finding its Mathlib declaration. Record its precise mathematical
statement, actual argument location, available condition grounds and a short
mathematical justification in a background note. Use kind mathematical for an
ordinary background result and elementary for a useful elementary completion.
This is an actual mathematical judgment, not a future TODO or a claim of
native verification. Do not record every algebraic operation.

Eligibility requires a correct standard local step with all premises already
available, no new H and no substantial new core proof or changed route.
Important external tools remain explicit E inputs; a missing project result
or uncertain source cannot be waived as background. If an explicitly supplied
native mathlib note is retained, its full bound evidence is still validated.
No field-specific whitelist determines eligibility.

The accepted authority is immutable author NL0 plus its hash-bound mathematical
review supplement. It is a natural-language audit under the V2 policy, not a
V1 native-background receipt. At nl02lean, workers must discharge all necessary
facts by actual Lean proofs or checked library use; a note never becomes an
unproved H, axiom or extra external assumption. The exact implementation may
differ while preserving the mathematical meaning.

### Actual review and result qualification

Independent reviewers assess the actual content; schema validation does not
prove mathematics. An unexamined item remains unread/read. A mathematical
uncertainty is assessed UNVERIFIED, not PASS. Missing or conflicting assessments
block acceptance. Ordinary source-access deferral follows the conditional-source
policy and must appear in final warnings; it cannot yield unqualified PASS.

Use short located reasons for straightforward PASS items and enough detail to
make a defect or uncertainty actionable. Avoid duplicate explanations across
criteria. A concise report still covers every required mathematical check.
Do not read author self-check notes, old verdicts, other R proof bodies, other
case results or personal proof skills to manufacture independent approval.
<!-- yui-nl0-acceptance:end -->

## Execution protocol

1. Freeze the original problem, spec and NL0. A separate fresh global reviewer
   reads the exhaustive global-overview.json, relevant canonical content and
   source evidence. Review each D and selected E/M; the overview is data, not
   an assessment. Do not infer absence from a partial page.
2. Complete global source/graph review before dispatching local R reviews.
   Up to the explicitly confirmed N independent R reviewers work concurrently.
   Each receives only its own packet and V2 rules. Review full arguments,
   actual applications and definitions; input N statements are conditional.
3. Prefer one complete artifact with an explicit coverage map. Use
   record_review_item and read_review_progress only for useful checkpoints.
   record_background_note is optional; a complete artifact may include its
   actual notes directly. Batch reading several declared fragments is available.
4. Each local report has inference, packet_sha256, verdict, notes, checks,
   findings and optional background_notes. The checks map contains exactly
   statement_closure, dependency_closure, argument, applicability, packet_replay.
   Each row has verdict, notes and resolving packet locations. E applications
   additionally retain actual binding, per-hypothesis, conclusion and bridge
   assessments; this is mathematical applicability, not a Lean API inventory.
5. Global reports have target_review, definition_reviews, source_reviews,
   structure_review and findings. Each E adds citation_checks for
   literature_identity, result_location, statement_fidelity,
   context_completeness, version_and_eligibility. Inaccessible primary text
   leaves blocked checks UNVERIFIED while remaining assessment continues.
6. A blocking finding needs its actual location, explanation and a short exact
   quotation from that location. Preserve the defect and untouched coverage.
   Return located mathematical repairs to the author; review changed scopes
   independently. Do not resample a mathematical rejection or silently erase it.
7. The collector checks complete coverage, consistency, exact bytes and actual
   independent execution before producing the V2 audit-format-4 receipt.
   Old V1 receipts are not silently upgraded. Inherited V2 judgments retain
   their original source/rule hashes, exposure and costs.

## Sources, scopes and final handoff

Use [external theorem review](external-theorems.md) and
[conditional sources](conditional-sources.md) for source identity, exact
statements and warnings. Reuse adequate original text; several theorem uses
may share one staged readback. Each application still discharges its own
premises. No successful download or guessed Mathlib availability is approval.

Use [logical rules](logical-rules.md) for local scopes and
[background notes](background-notes.md) for the mathematical supplement.
The ordinary complete result remains relative to explicit E assumptions.
An inaccessible E original permits only a source-qualified result. Translation
retains this exact audit and supplement until reviewed mathematical changes
invalidate affected scopes. Typed interfaces, native checking, standalone
assembly and independent semantic Audit B are separate later gates.

## Paywalled or inaccessible primary text

Follow [conditional sources](conditional-sources.md). Preserve the complete
secondary statement and actual access evidence; unavailable source checks
stay UNVERIFIED. Continue other work only with an explicitly qualified source
assumption, and report warn.json/warn.md. No unqualified full PASS is granted.
