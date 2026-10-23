# Author a structured NL0

Apply [self-containment](self-containment.md) and the
[authoring template](../templates/authoring.md) throughout. Use format v2;
historical examples are source material, not accepted current templates.

## 1. Understand before freezing

Read the whole supplied work sufficiently to identify the exact target, actual
mechanism, source boundary, definitions, and potential gaps. Record initial
screening as screening, not an audit pass. Keep exploration out of canonical
NL0 until a route is selected. Do not invent a replacement theorem or route
because the existing proof is inconvenient to translate.

## 2. Freeze the original problem

Write `spec.json` first. Extract the target's parameters and all its H nodes
from the original statement. H is already authorized at this point. Record
their source positions; never create candidate hypotheses for later promotion.
Define global symbols once, including parameter ranges, normalization, norms,
representatives, and endpoint meaning. Reserve the entire global symbol set.
Bound indices/quantified variables of external statements remain local binders.
Explicitly freeze the logical primitives. They describe the fixed mathematical
language, not a new place to assume analysis results.

Store definitions and notation together. Separate a formula defining an object
from claims that the object exists, is well defined, belongs to a space, or has
a property. Guard a definition requiring a previously proved existence result.
The resulting prerequisite chain must itself be noncircular.
When an R needs a guarded definition, list its proof guards as direct inputs.
Ancestor availability is insufficient to import a property into the argument.

Fix the logic policy. It may allow classical logic, quantifier rules,
induction, and explicit finite algebra/order calculations. It may not license
unnamed compactness, measure, functional-analysis, or limit theorems.

## 3. Extract the proof interface

Work backward from P and forward through the actual proof. Write a complete
statement for each useful intermediate lemma, then a producing R with explicit
direct inputs. Do not infer proof dependencies merely from paragraph order.
Each N/P has exactly one accepted producer. Keep alternative routes outside
the accepted graph. Array order need not be topological; render topologically.

Split when the premise set or mathematical mechanism changes, when a result is
reused independently, or when a passage deserves a separate audit (density,
uniformity, limit interchange, domain identification). Merge short explicit
calculations with the same local purpose. A conjunction is one proposition,
but do not hide several unrelated difficult obligations in one giant node.

Every local task must be understandable from its expanded definitions, input
statements, and own statement. Never refer to an unexplained “previous bound.”
Choose binders and constant dependencies explicitly: `forall n exists C` is
not `exists C forall n`. Where induction is applied to rescaled points, formulate
the induction invariant universally over those points before starting induction.
State the output so that it can be read without its producing proof. Expand
every claimed formula in the statement itself. Do not write "identity (8.3)
holds", "the previous estimate", or "notation as in the paper". Keep source
labels/locations in provenance. Use declared input IDs/local F IDs in proofs.

## 4. Close every leaf

For each mathematical fact, either identify an exact E/M source or supply an
internal proof. All target-work lemmas remain internal until actually proved.
An authoritative theorem is not permission to assume the project's specialized
bridge. Source inventory may grow during preparation; freeze it before Audit A.

Check M declaration kinds, complete signatures, implicit/typeclass hypotheses,
official module bytes, and the recorded commit. A similar theorem name is not
enough. For E read the exact primary source version, theorem, hypotheses,
normalizations, and errata. If verification is unavailable, keep UNVERIFIED.
For paywalled or inaccessible papers, follow the
[Google-then-Sci-Hub retrieval and deferred-review procedure](audit-a.md#paywalled-or-inaccessible-primary-text).
Continue other work with the inaccessible citation explicitly pending; the
access failure alone is not a substantive proof gap.

## 5. Write each argument

Populate the R's input list before drafting its proof. Use only these inputs,
explicitly referenced definitions, permitted logic/calculations, and earlier
facts established within the same argument. Record each input's actual role
through `uses`. If a new theorem is needed, add it and update the graph first.
Use identifiable S paragraphs, with only their actual direct `uses`, earlier
`uses_local`, and full `produces` F statements. Do not automatically prefix a
copied paragraph with the full input list and treat that as dependency review.

For every object in the actual text, record its legitimate global, statement-
bound, or local declaration. Local declarations give the exact introduction,
kind, start/end S IDs, and input/previous-local basis. Input-bound variables
need instantiation; existential witnesses need an existence basis. Merely
listing a symbol in `objects` or `locals` does not establish these obligations.
Do not invent properties while naming an object. Reverse-check actual text
against the object inventory and factual grounds before handing off.

Package conditional reasoning as a complete proposition. Temporary assumptions
appear only inside the argument with explicit introduction/discharge and
correctly scoped variables. Consult `logical-rules.md`; do not create an L
root, silently assume the desired N, or fill an existence gap with a definition.

For each E/M application bind its variables and discharge every hypothesis.
For E follow [the external-theorem standard](external-theorems.md), preserve
separate citation verdicts and give every actual use its own A ID, including
repeated instantiations within one R. Establish joint integrability before
using Bochner Fubini; a nonnegative Tonelli step is a separate dependency when
it is used, not a consequence of an inapplicable Fubini signature.
Do not treat source fidelity and applicability as one check. Arithmetic
calculations must exhibit the actual identities/inequalities being used.

### Routine completion and substantive proof gaps

When writing NL0, expand the argument along the proof strategy already present
in the original work. Actively supply routine omitted derivations, correct
verifiable typographical errors and non-substantive local mistakes, and write
the complete argument into NL0 without interrupting the user for each item.
Completion must preserve the original target, the original theorem hypotheses
and the core proof strategy.

If a step remains blocked after normal understanding, checking and completion
attempts, carefully assess the obstacle: is it work needed for ordinary
rigorous expansion, or a substantive gap in the original proof? The model
should make this judgment from the mathematical content and actual progress;
no fixed elapsed-time limit or attempt count is a mathematical criterion.

If the obstacle is judged to be a substantive proof gap, stop NL0 construction
for the current proof, preserve the completed work, and report the gap's
location, the unsupported implication and the grounds for that judgment.
Do not automatically start new research on the original problem, seek a new
core proof strategy, or modify the original theorem to make the proof pass.

Recognizing a gap does not require finding a counterexample or proving that
the gap is irreparable. If the only established fact is that completion has
not been achieved, and its substantive nature cannot be judged reliably,
report an "unresolved suspected proof gap" rather than declaring the original
theorem false. Prolonged runtime, network or tool faults, and model capability
limitations alone are not evidence of a mathematical error.

Incorporate completed corrections into the argument and its actual dependency
records. Audit A reviews that revised version; existing hash binding and
invalidation rules still apply.

## 6. Freeze, check, and hand to Audit A

Run the structural gate and regenerate the readable NL0 and diagram. Correct
structural defects without treating that as a mathematics verdict. Freeze file
hashes. A prior prose proof or historical Audit A is candidate input only.
Supply the actual canonical graph and frozen problem to the auditor. Record
whether that auditor shares the author's context or has read Lean references.
Do not claim independent evaluation merely because the audit is a separate file.
Create only an UNVERIFIED audit scaffold with `nl0.py audit-template`. Keep
author notes and verdicts out of fresh packet-only replay inputs. A replay
must actually occur on the recorded packet; an author cannot generate its PASS
from their proof notes. Use the [audit template](../templates/audit-a.md).
