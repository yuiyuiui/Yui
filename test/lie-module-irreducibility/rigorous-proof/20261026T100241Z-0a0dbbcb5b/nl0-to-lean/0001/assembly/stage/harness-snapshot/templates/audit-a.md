# Audit A v3 template

Use [Audit A's shared requirements](../references/audit-a.md#shared-mathematical-acceptance-requirements)
as the same mathematical standard supplied to the author. Existing check keys
are shared criterion IDs; `packet_replay` is the separate execution obligation.
Locate a FAIL under its criterion and actual argument. Do not introduce a new
mathematical permission boundary during review. Author notes/readiness are not
evidence for an independent verdict.

Generate the complete pending record beside a frozen v2 graph:

```bash
python3 scripts/nl0.py audit-template CASE/nl0.json --spec CASE/spec.json --out CASE/audit-a.json
python3 scripts/nl0.py inspect-audit CASE/nl0.json --spec CASE/spec.json --audit CASE/audit-a.json
```

The scaffold contains only UNVERIFIED verdicts, empty check locations and an
unperformed replay. It refuses to overwrite a receipt. Artifact hashes bind
the version; they are not evidence that mathematical review occurred.

## Whole-proof and source checks

Disclose actual reviewer/carrier, prior exposure and material read. Review
target/H fidelity, definitions, E/M sources, signatures and every actual source
application under [Audit A](../references/audit-a.md). Source text is used for
fidelity, not to supply an unstated premise during local replay. Unavailable
citation checks remain UNVERIFIED under the existing retrieval procedure.

## Verified background

Retain all ten checks. Use ordinary rigorous elementary compression. Positively
check eligible omitted basic mathlib facts using probe_background and record
them with record_background_note; no new H, uncertain source or substantive gap
qualifies. The receipt declares background_policy:verified-background-1 and
background_notes per R. Saved notes are retained in from_saved_review completion.
See references/background-notes.md for exact fields and handoff semantics.

## Ten separate checks per R

| Check | Required inspection |
|---|---|
| statement_closure | Complete input/output formulas, binders, conditions and semantics without producer proofs. |
| object_closure | Actual occurrences -> declarations, legitimate instantiation, witness basis and scope. |
| dependency_closure | Actual factual uses -> direct inputs, prior local proofs or fixed logic/calculations. |
| inputs | Correct accepted premises and compatible instantiations. |
| argument | Every required mathematical step, including domains, limits and uniformity. |
| dependency_accounting | Actual role of listed inputs; no theorem hidden in prose, definitions or interfaces. |
| output | Exactly the full output with quantifiers, conditions, constants and endpoints. |
| scope | Assumption discharge, cases and no witness/fact escape. |
| applicability | E/M bindings, each condition, conclusion and proved bridges. |
| packet_replay | An actual fresh-context review with only this packet as mathematical input. |

Each check has `{verdict, notes, evidence, locations}`. `locations` are JSON
pointers inside the packet, such as `/inputs/0/statement`, `/output/statement`,
`/inference/locals/0`, `/inference/argument/1/text`. Explain each judgment from
actually inspected content; do not copy author notes as a generic assurance.

## Replay and findings

The replay record gives `packet_sha256`, `mode`, `carrier`, `prior_exposure`
and `read_materials`. A new background-enabled pass uses `fresh_packet_with_verified_background`, a real carrier
identifier, no previous exposure to this proof, and mathematical materials
equal to the packet hash plus the bound pinned-library evidence hashes.
Old strict empty-note records may retain fresh_packet_only. Skill instructions supply procedure, not facts.
Exclude original proofs, other R bodies, author reviews and expected answers.
Preserve execution evidence. This template grants no external dispatch authority.
Disclose known prior task/proof exposure; do not claim to certify unknown
pretraining contents. Learned facts still need legitimate declared grounds.

Use `same_context_diagnostic` for rereading and `unperformed` when no replay
ran; keep replay/affected overall verdict UNVERIFIED. Substantive missing content remains blocking. Eligible verified background
completion is recorded explicitly rather than silently supplied from memory.
Return repairs to authoring and review the newly frozen revision.

For behavioral controls give the reviewer neutral packets and keep the owner's
answer key separate. Count real located findings. Prefilled FAIL records test
receipt handling only. An unexecuted control suite is NOT_RUN, not a success.
Do not grant a natural-language audit pass from receipt validity alone.
