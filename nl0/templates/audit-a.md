# Yui V2 Audit A template

Use the [shared mathematical requirements](../references/audit-a.md#shared-mathematical-acceptance-requirements)
for both author and auditor. Generate a pending audit-format-4 scaffold with:

```sh
python3 -B nl0/scripts/nl0.py audit-template CASE/nl0.json --spec CASE/spec.json --out CASE/audit-a.json
```

The scaffold contains UNVERIFIED judgments, empty locations and unperformed
replay. It is not a mathematical review. The independent global lane checks
target/H, definitions, E/M sources and graph. Up to N fresh local R reviewers
then assess their actual conditional packets under five grouped criteria:

| Check | Mathematical responsibility |
| --- | --- |
| statement_closure | Complete statements, object meaning, declarations and exact output. |
| dependency_closure | Actual input use, available local facts, guards, witnesses and assumption discharge. |
| argument | Complete correct implication with material details and no substantive gap. |
| applicability | Real source/background instantiation and all required conditions. |
| packet_replay | Sufficiency within the exact supplied mathematical packet boundary. |

Each row has verdict, notes and resolving packet locations (the collector adds
evidence). Prefer one complete structured artifact with coverage for all
required pointers. Keep PASS reasons concise; locate and explain defects or
uncertainty. Never fill unexamined items with PASS. Use optional checkpoint
rows only when they help preserve actual work. No extra reviewer is required
per routine background fact.

background_notes may contain elementary or mathematical facts with exact
statement, location, actual grounds and justification. No native Mathlib
probe is required. See [background notes](../references/background-notes.md).
They are never new assumptions or unresolved TODOs. Important source theorems
and substantial missing arguments keep their ordinary explicit obligations.
The replay mode is fresh_packet_with_mathematical_background with an actual
carrier, packet hash and honest prior exposure/material list. Execution
qualification is checked separately. V1 receipts are not relabeled as V2.

Each E retains source fidelity and each actual application retains bindings,
per-hypothesis, conclusion and bridge checks. Missing primary text remains
qualified UNVERIFIED under the source policy. The final independent Audit B
and actual standalone Lean compilation remain separate requirements.
