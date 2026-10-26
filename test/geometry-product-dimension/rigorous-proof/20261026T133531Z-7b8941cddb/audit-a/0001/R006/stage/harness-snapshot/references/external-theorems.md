# External-theorem review: required Audit A standard

Apply this standard to every retained E and every actual use of E in an R.
An E keeps the full source theorem; a derived specialization or substantive
translation is an internal N. Use the data contract's audit version 2. These
are reviewer obligations: a filled record or matching hash cannot establish
that a publication or a mathematical assertion is genuine.

## 1. Document identity

Obtain and read the actual primary document. Match author, title, source kind,
publication/release information and exact edition/version to its provenance.
Record a traceable original source, retrieval date, local document and hash.
A search snippet, model answer, secondary citation, or functioning DOI/URL
alone does not establish identity. Books, papers and reliable preprints can
qualify; a DOI and journal publication are not universal requirements. Record
the source category and grounds for treating it as an admissible source.

For paywalled or inaccessible text, use Audit A's
[Google-then-Sci-Hub retrieval procedure](audit-a.md#paywalled-or-inaccessible-primary-text).
If access still fails, skip the blocked citation checks with an explicit
UNVERIFIED record, continue the remaining work, and notify the user in the
final report. This is a deferred check, not a source-verification pass. Do not
replace unavailable primary text with model recollection or a search summary.

## 2. Occurrence of the result

Locate the claimed result in that document and version. Record theorem,
lemma, proposition or corollary label and page/section/paragraph/equation as
available; unnumbered results require an equally reproducible locator. Retain
the relevant primary text or a precise readback record bound to the document.
If the cited document merely points elsewhere without actually stating the
claimed result, follow and correct the source. An explicitly stated theorem in
an authoritative exposition can be cited as such; record its proof attribution
without claiming to have audited the referenced proof recursively.
Distinguish proved assertions from conjectures, questions, heuristics and
numerical observations. Preserve every condition of a conditional result.

## 3. Statement fidelity

Compare the original full statement with the E statement, explicitly covering
objects, domains, scalar fields, spaces, hypotheses, regularity, quantifier
order, parameter intervals/endpoints, degeneracies, constant dependencies and
the exact conclusion (including a.e./everywhere, topology, uniformity,
existence/uniqueness and local/global scope). Record the notation map.
Faithful mathematical meaning, not word-for-word copying, is required.
Alpha-renaming is allowed. Never turn forall-x-exists-C_x into exists-C-forall-x.

## 4. Complete context and definitions

Read the surrounding standing assumptions, definitions and conventions that
govern the result, including referenced context needed to understand it.
Capture any omitted chapter-wide hypotheses and normalization of measures,
norms, transforms, signs or scales. Map the source objects to the global D
ledger. Do not hide a condition outside the proof graph. A substantive
conversion requires an N proof; a renamed symbol is not that proof.

## 5. Version status and source eligibility

Match every locator and statement to the chosen version. Check available
primary version histories, corrections, errata or withdrawal information at
the recorded date and scope. Record relevant findings and their effect;
explain use of an older version. Absence of a discovered correction is not
a guarantee that none exists. Unresolved conflicts remain UNVERIFIED.
Never import the target, an unproved project lemma, or a circular dependency
as E. Previously proved project modules require an expanded graph or a
versioned proof handoff. Do not attribute a combination of sources and a
project bridge to a single published theorem. A conjecture-dependent theorem
must retain that condition, which must be supplied legitimately at application.

## 6. Every actual application

Give each actual E application an inference-local A ID. The same E applied
twice with different bindings has two A records, even within the same R.
For each A inspect the parameter/object bindings, prove every source
hypothesis from declared inputs or displayed local derivations, check types,
definitions and parameter ranges, identify substantive bridge N nodes, and
verify the resulting conclusion supports R's output. Record the evidence for
each individual hypothesis. “The theorem applies” is not a mapping.
Do not add an unproved hypothesis to close an application. An E passed at its
source does not automatically pass at any application site.

## 7. Ownership of derived work

Put substantive specialization, scaling, change of normalization/domain/space/
norm/representation, combinations of sources, and prerequisite lemmas in N.
Each N lists its actual E/M/H/earlier-N inputs and its argument. Do not enlarge
the quoted theorem. Explicit elementary calculations and logical instantiation
may remain inside R; justify them rather than imposing needless graph nodes.

## 8. Separate decisions and reproducible evidence

For each E write five separate review records: `literature_identity`,
`result_location`, `statement_fidelity`, `context_completeness`, and
`version_and_eligibility`. Each contains verdict, concrete notes and hashed
evidence. The first three must never be merged into one blanket PASS.
For each R/A write separate binding, per-hypothesis and conclusion reviews,
the source ID and the proved bridge IDs. Record actual reviewer, carrier,
shared context and reference material read. Self-audit is not independent.

Use PASS only after the check was performed with adequate evidence; FAIL for
an established mismatch/omission/invalid application; UNVERIFIED when necessary
evidence is missing. Inaccessible text does not establish nonexistence. An
established absence of the claimed result in the cited source is a FAIL.
Retain failed records and the exact reason, source location and affected nodes.

## 9. Acceptance, invalidation and trust boundary

Every retained E check and every application must PASS before the graph can
receive DRAFT-AUDIT-PASSED. A load-bearing FAIL/UNVERIFIED blocks descendants
and whole-proof acceptance; diagnostic review may continue. Never replace a
missing verification with a historical audit or a Lean build. Changes to the
source/version, statement, definitions, bindings or condition proofs invalidate
affected reviews; bind the replacement whole receipt to new canonical hashes.

An inaccessible source suspends its citation verification, not the rest of
the workflow: continue available checks and explicitly conditional reasoning,
then report the unfinished citation checks and the UNVERIFIED overall audit
outcome. Descendants cannot receive an unconditional pass based on that
source, and source inaccessibility alone is not a finding of mathematical error.

List all external dependencies in the final verdict. This audit is relative
to those identified theorems; it does not independently reprove their published
proofs or establish a Lean proof of E. Mechanical checks establish record
coverage and byte consistency, not authenticity or mathematical correctness.
