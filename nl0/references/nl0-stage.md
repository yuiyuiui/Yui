# NL0 and Audit A stage

This is stage one of Yui. It may be used independently, or its accepted artifacts may feed the translation stage. Existing production skills and historical proof verdicts are not imported by invoking Yui.

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

## Shared standard and execution responsibilities

[Audit A's shared mathematical requirements](audit-a.md#shared-mathematical-acceptance-requirements)
are the single acceptance authority. Their stable IDs bind the author guide,
author inspection groups and mathematical audit checks. The clean author and
Audit A receive the same frozen section/version/hash directly. The format and
self-containment documents supply schemas and detailed meanings; they do not
expand the trusted elementary layer.

Author the frozen original problem using the [construction guide](nl0-authoring.md)
and [tool template](../templates/authoring.md). Build the actual proof,
declarations, source contracts and input/output interfaces together. Preserve
routine completion and substantive-gap handling in that guide.

At release, inspect the stored own packets and report actual readiness. Keep
known unresolved findings open until their located correction or justified
withdrawal. Complete notes alone do not finish authoring. An unfinished draft
is preserved as unfinished, without an ordinary first-acceptance audit.

The auditor separately performs the execution protocol in Audit A: source
verification, global review, fresh packet-only replay, actual judgments and
recorded evidence. Authors do not generate those verdicts. The NL0 author and
global Audit A are serial. After the global stage, independent frozen R packets
are reviewed with the confirmed N workers. Separate cases can run concurrently.

## Execute

Keep `spec.json` independent of the authoring file. The canonical proof is
`nl0.json`; `NL0.md` and `graph.mmd` are generated views. Do not edit the views
as mathematical authorities.

```bash
python3 nl0/scripts/nl0.py check PATH/nl0.json --spec PATH/spec.json
python3 nl0/scripts/nl0.py render PATH/nl0.json --spec PATH/spec.json --out PATH/views
python3 nl0/scripts/nl0.py packet PATH/nl0.json --spec PATH/spec.json --inference R001
python3 nl0/scripts/nl0.py audit-template PATH/nl0.json --spec PATH/spec.json --out PATH/audit-a.json
python3 nl0/scripts/nl0.py check PATH/nl0.json --spec PATH/spec.json --audit PATH/audit-a.json
python3 nl0/scripts/nl0.py inspect-audit PATH/nl0.json --spec PATH/spec.json --audit PATH/audit-a.json
```

Commands print JSON and return nonzero on a failed gate. `inspect-audit` may
successfully validate the completeness of a FAIL/UNVERIFIED record; its
`audit_receipt_valid` remains false and it is never an acceptance command.
The executable format
and exact meaning of the checks are documented in the data contract. Programs
validate explicit metadata and evidence binding; they cannot recognize every
undeclared theorem or prove a natural-language argument.

New spec/graph files use format v2 and mathematical-NL0 audits use v4.
A detailed-NL0 audit v3 does not establish current format-4 acceptance. Historical v1 files
require explicit `--legacy`; their receipts cannot establish current-standard
acceptance. Do not silently migrate, overwrite, or relabel old cases. The
archived case-2 authoring script no longer manufactures passing reviews.
The [format example](../../tests/fixtures/closed-addition/nl0.json) is a small schema
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
- `DRAFT-AUDIT-CONDITIONAL`: complete review relative to explicit external
  statements whose primary sources remain unverified. Preserve the source
  warnings and follow the [conditional-source policy](conditional-sources.md).
- `GAP`, `SOURCE-MISMATCH`, `TARGET-MISMATCH`, `ASSUMPTION-MISMATCH`, `INVALID`,
  or `UNVERIFIED`: identify the exact failing obligation and affected closure.

Bind audit records to the canonical graph/spec hashes and evidence file hashes.
Changed claims, inputs, arguments, definitions, assumptions, or sources revoke
the affected verdicts. Reuse is limited to previously qualified unchanged items
whose current content, dependencies, review scope and evidence bindings still
verify. Changed or newly required items need actual review; missing or stale
evidence cannot grant acceptance. Preserve the earlier findings and failed
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
