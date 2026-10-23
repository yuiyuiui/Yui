# Structured NL0 and Audit A — Candidate 0.3

This directory is an uninstalled candidate. Do not edit, deploy, relink, or
replace the production `rigorous-proof-development` skill. Do not inherit a
historical proof or audit verdict. This candidate implements the NL0/Audit A
boundary; it is not yet a replacement for the full proof-to-publication skill.

## Required reading

Read [the data contract](nl0-format.md),
[self-containment requirements](self-containment.md),
[authoring instructions](nl0-authoring.md), and
[Audit A](audit-a.md) before building or accepting an NL0.
For conditional proofs, contradiction, cases, quantifiers, or induction also
read [logical packaging](logical-rules.md).
Read [the Lean handoff boundary](lean-handoff.md) only when preparing
a formalization handoff. None of these documents automatically dispatches
another agent or authorizes an external service.

## Non-negotiable interface

1. Freeze the original target, parameters, definitions, and **all original
   hypotheses H** before proof construction. H nodes are initial inputs, not
   assumptions awaiting later classification. Adding an H requires a new
   specification and invalidates the affected audit.
2. Keep two graph vertex classes: proposition and inference. Initial
   proposition kinds are exactly `external` (E), `mathlib` (M), and
   `hypothesis` (H). Other propositions are proved `internal` nodes or the
   unique `target` P. Every internal/target node has exactly one producer.
3. Each inference has an explicit set of **direct** inputs, one output, and a
   complete ordinary-language argument with structured citations. Inputs
   jointly support the output (AND), not alternative paths (OR).
4. Store one globally unique notation/definition pair per global object.
   Bind dummy variables locally; do not shadow global symbols. Record types,
   definition dependencies, and any existence prerequisite. A visible
   definition is not a proved property or an existence certificate.
5. Put temporary assumptions **inside the argument**, never among graph
   roots. Export a complete implication, quantified statement, negation, or
   other correctly closed proposition. No top-level local-assumption nodes or
   assumption-promotion mechanism exists in this version.
6. The proof uses only its declared inputs, the referenced definitions, fixed
   logical rules, explicit local calculations, and facts already proved
   earlier in the same argument. Analysis theorems are not “foundations.”
7. Verify M against the exact official mathlib checkout and complete printed
   signatures. For E follow [external-theorem review](external-theorems.md):
   separately verify document identity, occurrence of the result, faithful
   statement, complete context, and version/source eligibility. Review every
   actual application separately, including bindings, every hypothesis and
   proved transformations. A source's existence is not applicability.
   For inaccessible primary text, follow Audit A's
   [ordered retrieval and deferred-review procedure](audit-a.md#paywalled-or-inaccessible-primary-text);
   continue remaining work with blocked citation checks UNVERIFIED and
   explicitly notify the user in the final report.
8. Audit the exact output, argument validity, dependency accounting, source
   applicability, quantifiers, scopes, and all material endpoint/domain/limit
   issues **for every inference**. Acyclicity is not mathematical correctness.
9. During NL0 construction, apply
   [routine completion and substantive proof gaps](nl0-authoring.md#routine-completion-and-substantive-proof-gaps).
   Supply ordinary missing details and verifiable local corrections; stop and
   report a judged substantive gap without automatically researching a new
   proof. Elapsed time or execution difficulty alone is not a mathematical
   error criterion.
10. Enforce both package and per-inference self-containment. An exported
    statement must be usable without its producer's proof. Every mathematical
    object has a global, statement-bound, or legitimate local declaration;
    every invoked fact is a direct input or a previously proved in-scope local
    fact. Source documents, earlier proof bodies, and model memory cannot fill
    missing mathematical content. See the exact rejection rules in
    [self-containment](self-containment.md).
11. Use the [authoring template](../templates/authoring.md) and
    [audit template](../templates/audit-a.md). Audit scaffolds start UNVERIFIED.
    Never derive PASS from author notes or populated metadata. Every R needs
    separate closure reviews and an actual fresh packet-only replay before
    full acceptance; disclose an unperformed replay rather than inventing it.

## Execute

Keep `spec.json` independent of the authoring file. The canonical proof is
`nl0.json`; `NL0.md` and `graph.mmd` are generated views. Do not edit the views
as mathematical authorities.

```bash
python3 scripts/nl0.py check PATH/nl0.json --spec PATH/spec.json
python3 scripts/nl0.py render PATH/nl0.json --spec PATH/spec.json --out PATH/views
python3 scripts/nl0.py packet PATH/nl0.json --spec PATH/spec.json --inference R001
python3 scripts/nl0.py audit-template PATH/nl0.json --spec PATH/spec.json --out PATH/audit-a.json
python3 scripts/nl0.py check PATH/nl0.json --spec PATH/spec.json --audit PATH/audit-a.json
python3 scripts/nl0.py inspect-audit PATH/nl0.json --spec PATH/spec.json --audit PATH/audit-a.json
```

Commands print JSON and return nonzero on a failed gate. `inspect-audit` may
successfully validate the completeness of a FAIL/UNVERIFIED record; its
`audit_receipt_valid` remains false and it is never an acceptance command.
The executable format
and exact meaning of the checks are documented in the data contract. Programs
validate explicit metadata and evidence binding; they cannot recognize every
undeclared theorem or prove a natural-language argument.

New spec/graph files use format v2 and audits use v3. Historical v1 files
require explicit `--legacy`; their receipts cannot establish current-standard
acceptance. Do not silently migrate, overwrite, or relabel old cases. The
archived case-2 authoring script no longer manufactures passing reviews.
The [format example](examples/closed-addition/nl0.json) is a small schema
example with an unperformed audit, not a new benchmark or certification.

## Verdicts and invalidation

- `STRUCTURE-PASSED`: schema, graph, explicit references, frozen specification,
  and definition prerequisites passed the mechanical checks.
- `AUDIT-RECEIPT-VALID`: a complete, matching audit record was checked. This is
  an evidence/coverage verdict, not the program proving the mathematics.
- `DRAFT-AUDIT-PASSED`: the named auditor actually completed Audit A for every
  source, definition, inference, and target obligation. Report whether the
  auditor shared context with the author; never relabel self-audit as an
  independent review or Lean verification.
- `GAP`, `SOURCE-MISMATCH`, `TARGET-MISMATCH`, `ASSUMPTION-MISMATCH`, `INVALID`,
  or `UNVERIFIED`: identify the exact failing obligation and affected closure.

Bind audit records to the canonical graph/spec hashes and evidence file hashes.
Changed claims, inputs, arguments, definitions, assumptions, or sources revoke
the affected verdicts. Version 0.3 conservatively invalidates the whole audit
receipt on any canonical change; fine-grained reuse is future work. Keep failed
reports. Never add the missing conclusion as an H, source theorem, definition
property, structure field, or typeclass merely to close the graph.

## Deliver

Deliver the frozen specification, canonical graph, readable view, bipartite
diagram, primary-source/signature evidence, per-object Audit A, mechanical
results, and the first remaining gap. Describe functional smoke tests and
negative controls separately from mathematical review, isolation, formalization,
and speed experiments. Graph construction and auditing time are real costs.
Explicitly notify the user of every citation check deferred for inaccessible
primary text, including the affected E IDs, attempted retrieval routes and
remaining verification needs. Do not describe a partial audit as fully passed.
