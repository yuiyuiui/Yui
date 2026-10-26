# Self-containment details

This is the detailed meaning of Audit A's `statement_closure`,
`object_closure` and `dependency_closure` requirements. The
[shared Audit A section](audit-a.md#shared-mathematical-acceptance-requirements)
is the acceptance authority for author and auditor; this annex supplies
interpretation and examples, not an independent permission policy.

## Two boundaries

Accepted NL0 is a complete proof relative to its declared H/E/M roots, frozen
logical foundation and version-bound verified background notes. It is not an outline requiring the original manuscript to
recover missing definitions, formulas, assumptions, or arguments. E/M statements
are fully restated; their primary sources are inspected for provenance, not
used to supply unstated premises. The fixed library's own proof dependencies
need not be recopied. The target work's internal results must be proved here.

Every R must also be checkable from its packet alone: the complete statements
of its direct inputs, their required definitions/declarations, its complete
output, its local declarations, and its own argument. Another R's proof body,
an ancestor not listed as an input, an ambient original H, an original-source
crosswalk, or remembered material is not an additional mathematical resource.
Whole-target/source-fidelity checks are separate from this local proof check.
Under verified-background-1, local review may additionally verify routine
pinned-mathlib facts using logged read-only queries and record them in the
receipt. They join this R's effective dependencies, without new H or a graph
rewrite. See [background notes](background-notes.md). Mathematical uncertainty
still blocks; ordinary correct elementary compression alone does not.

Original theorem conditions are H nodes, including conditions that could be
encoded in a refined type. Parameters introduce ambient data/structures, not
an ambient stock of original hypotheses. For example, declare a vector and
put its required nonzero condition in H; do not write “nonzero vector” in its
parameter type and use that condition from an empty input list. The same rule
applies to characteristic/range conditions and equations. An R must list every
original H it actually uses. Standard structure operations/axioms and the fixed
finite-language rules remain available; no new substantive theorem is added.

An output must be understandable and callable without reading its producer's
argument. Include the actual equalities/inequalities, binder types, hypotheses,
parameter windows, constant dependencies, representatives and a.e./pointwise
meaning. Global defined notation can be expanded from the packet. A formula
number, theorem name, or paragraph location cannot replace mathematical content.
Source locators belong in provenance fields. New mathematical prose uses direct
input IDs and previously proved local F IDs, not inherited numbered references.

## Object closure

For every mathematical object actually appearing in a statement, definition,
local declaration, or proof, locate one legitimate declaration:

1. A frozen parameter, explicit logical primitive, or global D definition.
   State its meaning, type/domain and parameter dependence. Global primitives
   cover mathematical language and the fixed logic/finite calculations only;
   they cannot license unnamed analysis theorems.
2. A binder inside the current proposition's full statement. Its scope remains
   that statement. A variable bound in an input does not become a free object
   in the consuming proof; instantiate the statement explicitly.
3. A local declaration before first use, recording its kind, type, exact
   declaration, introduction basis, and scope. An arbitrary variable requires
   legitimate quantifier introduction; a definition uses already available
   objects; a witness requires an input or an earlier local existence proof.

A declaration cannot grant existence, uniqueness, invertibility, regularity,
or a desired property merely by naming an object. Those obligations require
proof. Any D guard needed to use the object must be a direct R input, not a
theorem silently recovered from ancestor closure. Record mutually compatible
choices and witness dependence. Temporary assumptions stay inside R and must
be correctly discharged. Branch witnesses, local facts and local notation
cannot escape their scopes. Export a quantified or conditional statement when
needed, rather than a free private name. Global names are reserved; dummy
variables may be reused in disjoint local scopes.

## Dependency closure

Inventory actual factual uses from the prose back to their grounds, not just
from an input list forward to a generic `uses` list. Each substantive imported theorem, prior project lemma or original
assumption must be a direct input. Eligible omitted basic library uses are
recorded as verified audit notes in the effective dependency ledger. A definition supplies meaning, not a theorem. An R output is not its
own premise. Adding the desired formula as an unproved input is not a repair.

Explicit local calculations and fully proved intermediate facts may remain
inside R. Give a reused local fact a full F statement and identify its earlier
derivation and open assumptions. No separate graph vertex is needed for every
algebraic equality. A nontrivial imported result cannot be called a local
calculation. Substantive reusable lemmas should become N/R pairs; any fact
reused by another R must be exported in a complete proposition statement.

The controller owns `spec.logic.calculations` and the primitive vocabulary
(`scripts/foundations.py`). The clean author tool binds omitted metadata and
rejects extra author permissions or task-specific primitives. This fixed
language grants no MVT, FTC, Fubini, convergence, compactness or regularity
theorem. Such facts need a declared input or an actual local derivation.
An author-written permission claim, in any field or prose, has no authority.
Ordinary typed arithmetic notation is part of this fixed language: natural
numbers, integers, rationals, reals and complex numbers mean their standard
structures with usual numerals and operations. Finite calculations include
their zero/one laws, such as `a+0=a`, as well as explicit algebra/order
derivations. Do not demand a separate E/M for an operation token or an allowed
finite calculation. This does not grant calculus, topology or measure theorems.
Conversely, inspect an actual displayed local derivation before demanding a
duplicate E/M input for its conclusion. A named consequence proved by permitted
finite algebra/order steps is not an imported premise. If a local derivation
fails, locate its unsupported implication rather than its absent theorem name.

Metadata accounts for the argument but never replaces it. Copying all inputs
into a single `uses` record, registering a symbol without declaring it in the
proof, or writing a PASS label cannot establish closure.

## Operational acceptance

1. Author using the node template. Reverse-check the actual prose for missing
   declarations, unexpanded references and unlisted facts before freezing.
2. Generate a packet for each R. The v2 generator supplies no original proof,
   producer proofs, provenance file locators, extra ancestor statements or
   undeclared ambient H. Direct source contracts and required definitions are
   included. Packet hashes bind the mathematical input actually reviewed.
3. Review all closure/inference checks, admitting positively checked routine
   background notes under the shared policy. Record concrete packet locations and reasons for every verdict.
4. Perform a fresh local replay with disclosed controlled background lookup. The reviewer gets the skill instructions
   and that packet plus logged pinned-mathlib queries, without original proof,
   other R bodies, author review
   notes, old verdicts, or an answer key. Record the actual carrier, packet hash,
   prior exposure and mathematical material read. Skill instructions supply no
   extra mathematical premise. Do not falsely claim a same-context rereading
   is a fresh replay. This rule does not authorize starting a new external
   service or agent; if the required carrier has not been used, keep replay
   UNVERIFIED and report that limit.
   Prior exposure means known task/proof material supplied or read in earlier
   contexts; this is not a claim about unknown pretraining contents. Learned
   mathematical knowledge cannot replace a missing declared premise or proof.
5. An ineligible missing declaration, missing statement content, unlisted substantive theorem or need
   to look outside the packet blocks acceptance. Record the defect; do not
   silently repair it while assigning PASS. Return substantive/structural defects to authoring and review the frozen
   revision; eligible background notes need no author rewrite. Routine completion does not require a
   separate user interruption for every omission. Distinguish a representation
   defect from a substantive mathematical gap under the existing gap policy.

The code rejects explicit malformed references, inventories, scopes, guards
and receipts. Its reference-pattern checks are conservative diagnostics, not a
parser for all mathematical language. An omitted inventory entry or unnamed
theorem hidden in prose still requires actual semantic review. Freshness and
truthful reviewer identity need execution evidence; record shape/hashes cannot
authenticate them. No natural-language audit is a Lean kernel certificate.
