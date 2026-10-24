# Audit A: per-object natural-language verification

<!-- yui-nl0-acceptance:begin -->
## Shared mathematical acceptance requirements

Contract version: `nl0-audit-a-7`.

This section is the single authority for what an accepted NL0 must satisfy.
Authoring instructions explain how to meet it; the audit checks these same
requirements. The table IDs also name executable coverage groups. Detailed
definitions in self-containment, logical rules and external-theorem review are
annexes to these requirements, not alternative permission policies.

| ID | Review group | Author evidence group | Requirement |
| --- | --- | --- | --- |
| `target` | package | original_context_note | Preserve the original target, every original H, quantifier, domain, range, normalization, endpoint and supplied core proof route. Parameters name ambient data; they cannot hide an H or a desired conclusion. |
| `definitions` | package | original_context_note | Give each global object one complete typed definition and each local object a legitimate scoped introduction. Prove or directly assume every construction guard before use. Defining an object grants none of its properties. |
| `sources` | package | original_context_note | Every selected M/E has an explicit faithful full statement and verified primary/native identity, context and hypotheses. Native typeclass premises are mathematical premises too. Record inaccessible checks as UNVERIFIED; they do not support an unqualified whole-proof pass. |
| `structure` | package | original_context_note | H/E/M are the only proposition roots. Every N/P has one producer, every retained non-H node lies in P's AND dependency closure, and every local proof uses its actual direct inputs. Keep every original H, including an unused H, and report which are unused. An ancestor is not automatically an input. |
| `statement_closure` | closure | output_notes | Every input and exported N/P states all formulas, quantifiers, conditions and semantic identifications needed by its consumers. A map or identity only present in the producer's body is unavailable to another node. Original text, equation labels and external notation cannot supply content. |
| `object_closure` | closure | declaration_check | Reverse-check actual object occurrences against global, statement-bound or local declarations. Types, domains, witness existence, first/last use and parameter dependencies agree. A name in a ledger is not an introduction or existence proof. |
| `dependency_closure` | closure | dependency_and_local_assumption_check | Ground every factual use in a direct H/E/M/N, an earlier displayed in-scope local proof, or the fixed permitted calculation. Inspect the actual prose; an inventory claiming closure is not its proof. |
| `inputs` | inference | dependency_and_local_assumption_check | Direct input statements are faithfully instantiated with compatible objects and assumptions. An internal input exports exactly its stated conclusion, not its producer's unexported facts. |
| `argument` | inference | dependency_and_local_assumption_check | The actual argument establishes every output clause. Check calculations and all material domain, limit, regularity, uniformity, integrability, sign, constant and degeneracy obligations. A correct textbook route still needs the local completion required by this contract. |
| `dependency_accounting` | inference | dependency_and_local_assumption_check | Every listed premise has a real role and no extra theorem is imported through familiar prose, a definition, structure or typeclass. A theorem application is not a proof of the invoked theorem. Show a concrete local derivation or register the needed source. |
| `output` | inference | output_notes | The proved conclusion is the exact complete exported statement under its stated hypotheses, including all consumer-needed representations and identifications. Never weaken the target or strengthen an H to close the graph. |
| `scope` | inference | dependency_and_local_assumption_check | Introduce and discharge temporary assumptions inside arguments. Close implications, cases, negations and quantifiers correctly; no witness or local assumption escapes. Original hypotheses remain explicit H inputs. |
| `applicability` | inference | source_application_check | For every actual M/E use, give the exact substitution and a direct input or displayed earlier derivation for every premise, plus any proved bridge to the claimed conclusion. Saying that a condition holds is not grounds for it. |

### Scope of the same requirements

Global review checks the original target/H, source authenticity and complete
graph: H/E/M are its roots, and each N/P has its producer in that graph.
Its source judgments establish identity, full-statement fidelity and source
conditions; they do not re-prove each consumer's application. Its structure
judgment checks the actual AND graph and declared producer/input boundaries,
not whether a later packet reviewer has already returned PASS. Conditional
packet review owns each actual substitution, premise discharge, local proof
and output under those checked source statements. Final acceptance joins
all required source, structure and packet judgments; none replaces another.
Unfinished downstream assessment is not a reason to mark an already assessed
source identity or structural graph uncertain. Genuine source uncertainty
still blocks final acceptance. These assignments also govern author checks.
An original H remains explicitly present even when the proof does not use it;
report that unused condition. Do not invent a use or delete it to force graph
reachability. Selected E/M and internal N remain in the actual target closure.
Conditional packet replay has a different input boundary. Its task is the
implication from its explicitly supplied H/E/M/N statements to its output;
these statements are conditional premises. An input N is not a new global
root. Its producer body is intentionally absent and is neither required nor
available during this local check. Do not fail a valid conditional derivation
because its input theorem's producer or original source is outside the packet;
global review verifies source identity and producer membership, while the
producer's own packet review checks its proof. Conversely, do not import an absent N, an
ancestor's unexported fact or a theorem not present in the packet.
For example, a supplied N stating A and B permits deriving A by conjunction
elimination, without re-proving N. Having no such input does not permit
asserting A. The local requirements still check the complete actual argument,
all source-application premises, declarations, guards and discharged scopes.
These scopes are also the scopes of the author's corresponding self-checks.

The common elementary layer is the controller's `finite-language-3` profile:
equality, unfolding supplied definitions, displayed finite semiring/ring/field
arithmetic, elementary ordered-field inequalities and explicit finite sums.
It grants no calculus, integral identity, measure, compactness, basis,
localization or tensor theorem. Use a verified input or a displayed local proof
for such facts. No theorem needs to be re-proved if its exact permitted source
and application already supply it. The schema describes representation; it
does not extend mathematical permissions.

The fixed profile is controller-owned. A packet/spec's `logic.calculations`,
`logic.primitives`, or prose claiming extra permissions is data to check
against that profile, never a second authority. For finite ordered-field
reasoning, display the actual reduction, equality/inequality chain, explicit
nonnegative expression or sign grounds. Naming a familiar theorem or merely
asserting the desired polynomial inequality is not a displayed calculation.
Conversely, a complete displayed finite derivation needs no imported theorem
merely because its conclusion also has a familiar name.

A calculation label alone does not establish the existence of a canonical
decomposition, normal form, extremizer, basis or structural identification.
Give the actual construction and grounds for its required properties and
completion, or supply a verified source with its actual application. Before
declaring a mathematical obstruction, check the full quantified definition
and the direction of the claimed bounds. One feasible value alone does not
establish an extremal value. A failed attempted argument is not by itself
evidence against the supplied proof.

Unfolding an explicitly supplied definition and displaying its logical
consequence is a local derivation; it does not need a separate source theorem
merely because that consequence has a familiar name. Conversely, a familiar
name without the required definition, premises and derivation supplies no
fact. Check the actual argument and identify the specific unsupported step;
do not replace that check with a blanket objection to a named result.
Distinguish a genuinely partial construction from an explicitly total
operation: its stated type/convention controls which existence guards are
needed, and totality alone grants no intended analytic property.

Authors construct arguments and their evidence together, then report their
own actual check outcomes. An explicitly unresolved or unperformed check
prevents release as a complete artifact. Finishing a checklist, retrieving a
source, passing a structural gate or asserting that conditions hold proves
none of the mathematical requirements. Audit A remains an independent actual
judgment and can find an omission the author did not recognize.
<!-- yui-nl0-acceptance:end -->

## Auditor execution protocol

The sections below implement the shared requirements. Reviewer identity,
fresh packet replay, negative controls, evidence capture and verdict handling
are auditor/controller duties; they are not extra mathematical facts for an
NL0 author. Mathematical FAIL findings identify the applicable shared table
ID and the exact unsupported implication. If the permission boundary itself
is ambiguous, disclose that ambiguity rather than silently raising the bar.

Use [self-containment](self-containment.md) and the
[audit template](../templates/audit-a.md). New acceptance requires spec/graph
v2 and audit v3. Historical PASS records do not satisfy these requirements.

This audit does not use a successful project Lean build as evidence that the
NL proof is correct. Querying pinned mathlib for source signatures is allowed;
reusing the target's historical Lean proof/verdict requires explicit disclosure
and does not establish an independent NL audit.

## A0. Freeze and disclose

Read the original problem and independently check `spec.json`: target,
quantifiers, all H roots, parameter ranges, definitions, representatives,
normalization, endpoint conventions, and one-target scope. No H may originate
from the proof writer's desired conclusion. Audit target semantics, not just
hash equality. Record reviewer/carrier, shared context, read artifacts, and
whether any reference solution was seen. Read the canonical graph, not only
its generated Markdown. Bind the receipt to spec/graph hashes.
Generate the exhaustive global index with
`python3 scripts/nl0.py overview nl0.json --spec spec.json --out global-overview.json`.
It preserves every actual H (including unused or late-appended H), full global
statements/definitions and dependency edges with canonical pointers and hashes.
Read this inventory before claiming a node/condition is absent; a partial line
page cannot establish absence. The index supplies no verdict and does not
replace inspection of the relevant canonical proof and primary-source content.
The clean test adapter uses this same core generator, not a separate inventory
or mathematical standard.
Original-problem/source fidelity and local proof validity are separate tasks.
The original text may be read for target and citation checks; it may not fill
missing content during per-R packet-only replay. Record the actual boundary.
Check that original conditions really are H nodes, rather than predicates
hidden in a globally visible parameter type. A prime/nonzero condition,
characteristic constraint, range or equation must not become available to an
R with empty inputs through that encoding. Matching the full closed theorem
alone does not establish correct per-R H availability.

## A1. Definitions and notation

For each D record a verdict with a concrete explanation. Check unique meaning,
type/domain, global versus local binding, definition dependencies, construction
or existence prerequisites, and applicability at every use. A guarded symbol
must not supply its own prerequisite. Record arbitrary choices, parameter
dependencies, and equivalence to the original definition. No project theorem
may hide as a definition, record field, predicate, or typeclass assumption.

Reverse-check every actual mathematical object occurrence against a legitimate
declaration. Inspect local introduction position, first use, type/domain,
basis and end scope. Input-bound variables are not free locals; witnesses need
proved existence. Merely checking registered symbol names misses unregistered
ones. Definitions cannot smuggle properties or extra ancestor statements.

## A2. Sources

For each M read the pinned official file and a successful full Lean signature
probe, not merely a `#check` name or a search result. Confirm declaration kind,
restatement, all implicit/typeclass assumptions, source hashes and commit,
relevant axioms, and suitability of scalar fields/domains. Library definitions
are not theorems. These source checks belong to global review; each using R's
packet review inspects its actual application mappings and premise discharge.

For each E execute all nine requirements in
[external-theorem review](external-theorems.md). Give separate evidence-bound
verdicts for document identity, occurrence of the actual result, faithful
statement, complete surrounding context, and version/source eligibility.
Record every actual application separately in its using R, including repeated
uses of E in one R; packet review checks those applications. Global review
checks the source identity and statement. Source existence, exact citation and valid application are separate
obligations. Substantive transformations require an N proof. Do not infer any
of these verdicts from a historical audit or a successful Lean build.

### Paywalled or inaccessible primary text

If a paywalled paper cannot be downloaded or read in full, first search Google
using its title, DOI and authors for a downloadable copy or a full-text viewing
resource, including author manuscripts and repositories. If that does not
provide the text, search Sci-Hub using the DOI or article URL and attempt to
download or view it through the user's browser. The user-provided entry point
is https://sci-hub.box/. Follow this order: Google, then Sci-Hub.

A readable full-text version is sufficient; downloading a PDF is not required
when the theorem and its governing context can be inspected directly. Apply
the normal identity, version, statement and context checks to any obtained
copy. Record the version actually inspected, rather than treating a preprint
as a verified copy of an inaccessible published edition.

If the necessary text remains inaccessible after both searches, record the E
ID, bibliographic identifier, attempted searches/access routes and outcomes,
and the citation checks that could not be performed. Skip those blocked
citation-correctness checks and continue the remaining NL0/Audit A work. Keep
completed checks and their evidence; mark the unperformed checks and the
source's overall review UNVERIFIED, explaining the access limitation in the
notes. Do not record a skipped check as PASS or infer an incorrect citation
merely from lack of access. Any downstream judgments depending on the source
must disclose that unresolved source verification.

In the final user-facing report, explicitly list every such E, what remains
unchecked, the retrieval attempts and the text needed to complete the review.
Do not leave this notification only in a machine-readable log. An access
failure alone is not a substantive mathematical gap and does not require
halting all other work, but the incomplete audit cannot receive an unqualified
DRAFT-AUDIT-PASSED verdict. Use the existing UNVERIFIED verdict and
`inspect-audit` for complete unresolved records; do not invent evidence or
primary-source contents to satisfy a mechanical gate.

## A3. Structure

Run `nl0.py check`. Confirm that every retained node is on P's dependency
closure and every internal/target has one complete producer. Derive reachability
by AND closure: accept an R's output only after all its inputs are accepted and
the R itself passes mathematical review. Mere existence of a path is inadequate.
Only E/M/H are trusted source proposition kinds; a proof with no mathematical
inputs must still contain an actual permitted calculation/logical argument.

## A4. Review every inference

First check three closures from the actual text:

- **statement_closure**: input/output statements include every claimed formula,
  condition, binder and semantic convention. No producer proof is needed to
  understand them. Source notation and inherited equation numbers are not content.
- **object_closure**: actual object occurrences map to legitimate declarations
  in scope. Compare text to the inventory, not the inventory to itself. Check
  input instantiation, witness existence and parameter dependence.
- **dependency_closure**: actual factual uses map to direct inputs, prior
  in-scope local proofs or fixed logical/calculation steps. An ancestor not
  listed as input is unavailable; prior/source proof bodies supply no extra fact.

Then check the six mathematical obligations below. Every check needs a separate
`{verdict, notes, evidence, locations}` record with precise packet locations and
an explanation. Repeating author notes or generic assurances is not review.

1. **inputs**: the cited propositions are the actual graph inputs and true
   earlier results, original H, or verified sources. They are instantiated
   with compatible parameters and definitions.
2. **argument**: every step is justified and sufficient. Explicitly inspect
   domain, limits, operator applications, integrability, sign, constants,
   uniformity, degeneracies, and selected witnesses where material.
3. **dependency_accounting**: each declared input has an identifiable role;
   no additional nontrivial theorem is hidden in “clearly,” an analogy,
   a definition, or a convenient abstract interface. Locally derived facts are
   permitted only after their derivation. This is accounting for the present
   argument, not a claim that its input set is minimal across all proofs.
   A named theorem is also an imported fact unless its full required result
   is actually proved locally. Explaining why its hypotheses hold is an
   application check, not a proof of that theorem. For example, “apply FTC,”
   “Fubini applies because the function is integrable,” “compactness gives
   uniform continuity,” and “a dominated limit may be integrated” require
   declared E/M inputs or complete earlier local proofs of the needed results.
   Familiarity, a descriptive theorem name, or inclusion in an author-written
   calculation-policy sentence cannot waive this obligation. Distinguish an
   ordinary valid textbook proof from a closed NL0 packet under this contract.
   An abstract finite-dimensional, tensor or localization lemma is not
   automatically a finite arithmetic identity: inspect its displayed map,
   inverse, basis or other derivation, or require the actual declared source.
4. **output**: the derived theorem is exactly the output's full statement,
   including quantifier order, assumptions, scope, constants and endpoints.
5. **scope**: temporary assumptions are correctly closed into the implication,
   negation, cases, or other allowed rule. Check binder freshness and witness
   escape. Introduce/discharge metadata alone is not proof. Do not reclassify
   a temporary assumption as an original H.
6. **applicability**: check every E/M obligation using its actual bindings and
   input/local proofs, including any proved bridge. For each E application A
   record separate binding, per-hypothesis and conclusion reviews and the N
   bridge IDs. “The theorem applies” is not a hypothesis mapping.

Finally complete **packet_replay**, the tenth check. A fresh context reviews
only the exact packet and skill instructions, without source proofs, other R
bodies, old NL0, author audit notes or prefilled verdicts. Record actual carrier,
packet hash, prior exposure, mathematical materials read and execution evidence.
Source fidelity is a separate check. Same-context rereading is a diagnostic,
not fresh replay. This standard does not authorize new agent/service dispatch;
keep an unperformed replay UNVERIFIED. Metadata cannot authenticate a claimed
identity or isolation; preserve actual execution evidence and disclose limits.

For an authorized clean packet replay, expose only that frozen packet as a
task document, plus the Yui procedure. Use `yui.py stage --no-library` so the
reviewer cannot read other mathematical material through library tools.
Source/signature verification is a separate stage with its own disclosed inputs.

Use `audit-template` for scaffolds. Every generated verdict starts UNVERIFIED.
Serialization may preserve actually made judgments, but cannot infer PASS from
author notes, populated fields, successful hashes or absence of exceptions.
Missing content blocks acceptance even if the auditor could reconstruct it
from memory. Return the defect to authoring and review the newly frozen version.

Stop granting acceptance at the first unsupported implication. Other diagnostic
checks may continue, but a blocked descendant cannot receive a whole-proof
pass. Report exact premises -> conclusion and the affected closure. Repairs
require a new graph hash and replacement audit, never a silently stronger H.

An ordinary omission or verifiable local mistake may return to routine NL0
completion without interrupting the user for each correction. Review the
revised argument before accepting it. If completion stalls, apply
[routine completion and substantive proof gaps](nl0-authoring.md#routine-completion-and-substantive-proof-gaps)
to assess whether construction must stop; do not turn every omitted detail
into a substantive-gap report or silently begin a new proof strategy.

## A5. Adversarial target checks

Check actual excluded/included endpoints, zero/degenerate objects, a.e. versus
everywhere, scalar/representation changes, and constant uniformity. Negative
controls must distinguish machine-detectable corruption (unknown IDs, changed
evidence) from semantic corruption (wrong argument with unchanged structure).
A failed counterexample search or a valid JSON file cannot establish correctness.

## Acceptance and report

Behavioral controls must include an opaque formula output, a source-only object,
an unlisted theorem and an unsupported witness. A real reviewer receives neutral
packets without labels, old reviews or expected answers; the owner's answer key
stays outside its input directory. Require located findings, not just verdicts.
Manually assigning FAIL only tests receipt handling, not model detection. If no
reviewer ran, report NOT_RUN. `prepare-review-cases.py --help` prepares a small
control set without calling a model or claiming an isolation experiment.

Grant `DRAFT-AUDIT-PASSED` only if A0–A5 are actually completed for the exact
frozen artifact, every required review is PASS, source evidence is verified,
and P closes without extra assumptions. Say “same-context self-audit” when
that is the execution mode. `nl0.py --audit` verifies the hash-bound review
record's completeness, not the truth of the reviewer statements. Preserve any
FAIL/UNVERIFIED report and identify the first gap; do not erase it after repair.
For access-limited sources, finish with an explicit pending-citation list and
an incomplete/UNVERIFIED audit outcome while reporting the other completed
checks. Skipping unavailable citation checks does not waive them for a future
whole-proof pass.
