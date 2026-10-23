# Audit A: per-object natural-language verification

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
Original-problem/source fidelity and local proof validity are separate tasks.
The original text may be read for target and citation checks; it may not fill
missing content during per-R packet-only replay. Record the actual boundary.

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
are not theorems. Inspect the actual application mappings in each using R.

For each E execute all nine requirements in
[external-theorem review](external-theorems.md). Give separate evidence-bound
verdicts for document identity, occurrence of the actual result, faithful
statement, complete surrounding context, and version/source eligibility.
Record every actual application separately, including repeated uses of E in
one R. Source existence, exact citation and valid application are separate
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
