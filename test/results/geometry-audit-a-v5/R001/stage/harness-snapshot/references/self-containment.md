# Self-containment: the acceptance contract

## Two boundaries

NL0 is a complete proof relative only to its declared H/E/M roots and frozen
logical foundation. It is not an outline requiring the original manuscript to
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
from an input list forward to a generic `uses` list. Each imported theorem,
prior project lemma or original assumption used directly must be a listed
input. A definition supplies meaning, not a theorem. An R output is not its
own premise. Adding the desired formula as an unproved input is not a repair.

Explicit local calculations and fully proved intermediate facts may remain
inside R. Give a reused local fact a full F statement and identify its earlier
derivation and open assumptions. No separate graph vertex is needed for every
algebraic equality. A nontrivial imported result cannot be called a local
calculation. Substantive reusable lemmas should become N/R pairs; any fact
reused by another R must be exported in a complete proposition statement.

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
3. Review statement, object and dependency closure separately, then the actual
   inference. Record concrete packet locations and reasons for every verdict.
4. Perform a fresh packet-only replay. The reviewer gets the skill instructions
   and that packet, without the original proof, other R bodies, author review
   notes, old verdicts, or an answer key. Record the actual carrier, packet hash,
   prior exposure and mathematical material read. Skill instructions supply no
   extra mathematical premise. Do not falsely claim a same-context rereading
   is a fresh replay. This rule does not authorize starting a new external
   service or agent; if the required carrier has not been used, keep replay
   UNVERIFIED and report that limit.
   Prior exposure means known task/proof material supplied or read in earlier
   contexts; this is not a claim about unknown pretraining contents. Learned
   mathematical knowledge cannot replace a missing declared premise or proof.
5. A missing declaration, missing statement content, unlisted theorem or need
   to look outside the packet blocks acceptance. Record the defect; do not
   silently repair it while assigning PASS. Return it to authoring, freeze the
   revision, and review that version. Routine completion does not require a
   separate user interruption for every omission. Distinguish a representation
   defect from a substantive mathematical gap under the existing gap policy.

The code rejects explicit malformed references, inventories, scopes, guards
and receipts. Its reference-pattern checks are conservative diagnostics, not a
parser for all mathematical language. An omitted inventory entry or unnamed
theorem hidden in prose still requires actual semantic review. Freshness and
truthful reviewer identity need execution evidence; record shape/hashes cannot
authenticate them. No natural-language audit is a Lean kernel certificate.
