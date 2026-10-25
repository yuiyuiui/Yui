# Accepted NL0 revision, frozen translation and Audit B

This is the execution guide for Yui's translation stage. Preserve the accepted
original NL0/Audit A. The runtime adapters compose their existing checks;
Python handles exact edits, versions, scheduling and evidence. Models/humans
still inspect mathematics, choose Lean representations and author local plans.
Automatic semantic compilation of arbitrary papers is not claimed.

## 1. Inspect before extracting

```sh
python3 scripts/source_preparation.py inventory \
  --graph /absolute/original/nl0.json --spec /absolute/original/spec.json \
  --audit-a /absolute/original/audit-a.json
```

The result contains canonical direct consumers and exact paragraph hashes/text.
Start from existing exports. Inspect repeated derivations and their scopes;
do not ask a model to reprove or rewrite every node. Zero useful candidates is
valid: keep the accepted original and skip revision entirely. Fanout is not
avoided proof cost. Tiny helpers may cost more to discover/review than they save.

Models may propose candidates; select only existing derivations with a clear
closed interface. No automatic optimal selection or exhaustive discovery is
promised. Keep discovery, selection and owner intervention visible in costs.

## 2. Stage a bounded patch

`patch.json` has `version: "nl0-local-revision-1"`, `baseline_graph_sha256`,
`spec_sha256`, optional `discovery_and_author_cost_seconds` and `candidates`.
Each candidate has exactly:

- `id`, `proposition`: one complete new internal N record;
- `producer`: one complete new R record under the parent current-v2 schema;
- `derivation`: `{inference: R_ID, paragraphs: [S_ID, ...]}` pointing to the
  already supplied derivation;
- Put the baseline revision/old R/S and current producer separately in the new
  proposition's origin. Historical provenance is not a current dependency edge.
- `expected_avoided_work`: a concrete basis, with unmeasured assumptions disclosed;
- `consumers`: at least two distinct actual consumer records.

Each consumer has `inference`, `before_sha256` (the canonical sorted JSON hash
of the old R), `inputs`, `replacements`, optional retained `applications`, and
`cut`. The direct inputs may retain/remove old ones and add only this new N.
Each replacement gives the stable `paragraph`, `before_sha256` of its full old
paragraph, and preferably `splices: [{old, new}, ...]` plus `uses_after`.
Every old string must match once, with no overlapping spans. Unselected text
is preserved byte for byte. Optional `uses_local_after`/`objects_after` adjust
the explicit accounting. A complete `after` paragraph is also supported for
small paragraphs, but cannot change local fact records or assumption lifetimes.

`cut` gives `old_conclusion`, `shared_instantiation`, `supplied_conclusion`,
`conditions: [{condition, justification}, ...]`, and `continuation`. Spell out
bindings, domains, exceptional sets/representatives and every fact/object the
untouched continuation needs. A new citation alone is not substitution.

Do not change original H/E/M/D, logic, target, old proposition statements, or
unrelated arguments. The adapter rejects overlapping consumer patches, added
consumer source applications and changed local-fact/assumption lifetimes.
Defer unsupported edits instead of expanding to a full proof rewrite.

```sh
python3 scripts/source_preparation.py stage \
  --graph /absolute/original/nl0.json --spec /absolute/original/spec.json \
  --audit-a /absolute/original/audit-a.json \
  --patch /absolute/patch.json --out /absolute/new-revision
```

The output contains unchanged-spec `case/spec.json`, revised `case/nl0.json`,
exact source dependencies, producer/cut packets, pending review templates,
patch and binding manifest. Never overwrite an accepted stage. A later revision
may supply `--incremental /absolute/previous/source-acceptance.json` instead of
ordinary `--audit-a`; the adapter revalidates its chain and rejects cycles.

## 3. Complete actual scoped reviews and accept the revised source

Fill `case/producer-review.json` only from actual fresh reviews of each complete
producer packet. It uses ordinary parent Audit A entries, including checks,
located evidence, source applications and exact fresh-packet replay boundaries.
The producer-only reviewer need not establish the old derivation's provenance
or whole-graph acceptance from a packet that lacks those materials.

Fill `case/cut-review.json` from the paired cut packets. Its checks are
`existing_derivation`, `condition_discharge`, `conclusion_match`,
`continuation_preservation`, `dependency_accounting`. Require an actual verdict,
specific notes, evidence and the paired `/before`, `/after`, `/contract`,
`/old_derivation`, `/producer_source_derivation`, `/shared_statement`, `/input_statements_before`,
`/input_statements_after`, `/global_context` locations. Evidence paths are relative
to `case/`, as in the parent checker. This is delta review with baseline access,
not a new independent fresh replay of the whole consumer. E/M applications
retain the parent schema; N uses belong in inputs/citations/explicit prose.
`old_derivation` is this consumer's actual replaced baseline proof.
`producer_source_derivation` is the one selected original proof of the shared
intermediate result, which may come from another consumer. Different final
consumer goals are expected; compare the shared intermediate conclusion instead.
Keep each generated `packet_sha256`: a review from a different cut packet cannot
be reused merely because IDs and pointer names coincide. Exact reuse after
record-only changes requires byte-identical source and actual reviewed packets,
with original verdicts, evidence, carrier and acquisition cost retained.

```sh
python3 scripts/source_preparation.py check --out /absolute/new-revision
```

This writes `source-acceptance.json`. It retains original audit qualifications,
records new-full/substitution/inherited coverage and invokes the parent rules
for new producers. Unchanged consumers/downstream conditional arguments need
no new mathematical replay when their inputs, context and conventions remain
unchanged. Python still rechecks the graph and exact preserved bytes.

`INCREMENTAL-AUDIT-A-PASSED` requires an accepted current-v2 baseline and every
actual local review. A missing/unverified baseline yields development-only local
review and cannot enter the complete production gate. No new receipt falsely
claims the parent issued a fresh whole-graph audit-v3 pass. Hashes do not prove
mathematical correctness or authenticate a reviewer who fabricates judgment.

## 4. Author and freeze the IR

Choose object views, input/output types, planned typed conversion interfaces, shared
ports and local T plans jointly. Preserve natural NL0 node boundaries. Export
every fact needed by another task; no shared result is an ambient definition.
The source graph is now fixed. Representation/API difficulties remain Lean
engineering; substantive source changes require a separately reviewed revision.

For the whole workflow the contract's relative `source.path` points to exact
canonical NL0 bytes, not a summary. `source_steps` copy every argument paragraph
with distinct implementation IDs. The controller copies these paragraphs and
note locations from the accepted source rather than asking the author to
transcribe them. The author supplies types and local plans, and can save partial
JSON before completing the whole interface.

The default freeze uses a mechanically checked binding with
`source_graph_sha256`, `contract_sha256`, `plan_sha256`, `paragraph_mapping` and
`source_outputs`. It checks exact source coverage and direct boundaries and runs
Lean type elaboration. This binding is **not a semantic review receipt**; the
recorded semantic status is `PENDING_AUDIT_B`. Actual source/type fidelity is
reviewed with the completed Lean proof in final Audit B. A separately requested
interface review remains supported through `--interface-review`; it is not a
mandatory extra model stage.

```sh
python3 scripts/workflow.py freeze /absolute/new-workflow \
  --graph /absolute/new-revision/case/nl0.json \
  --spec /absolute/new-revision/case/spec.json \
  --incremental /absolute/new-revision/source-acceptance.json \
  --contract /absolute/interface/contract.json --plan /absolute/interface/plan.json \
  --interface-binding /absolute/interface/accepted-interface-paths.json \
  --max-concurrency auto
```

Without extraction use original graph/spec and ordinary `--audit-a`. Freeze
binds original/revised source, evidence, IR, mechanical binding (or optional review), source paragraphs and code.
Any later change blocks the next stage. It does not regenerate old task packets
or automatically rerun mathematical audits.
`freeze-seal.json` binds the complete run manifest, including configuration and
source-output mapping. Editing that manifest invalidates the gate. This is
integrity bookkeeping, not authentication of an owner who rewrites every record.

## 5. Run bounded proof work and actual assembly

Follow [the execution protocol](execution-protocol.md) for queue ownership,
per-case budgets, structured status, cancellation and finite batch exit.

```sh
python3 scripts/workflow.py run /absolute/new-workflow \
  --shared-store /absolute/project/shared-store --timeout-seconds 180
```

The workflow's concurrency is fixed at freeze: `auto` uses a confirmed backend
cap when available, otherwise the CLI's disclosed fallback two. A positive N is
user-controlled, constrained only by a known backend hard limit. Print requested,
effective and reason; record observed peak, per-stage queue/start/end and total
time. The proof budget covers proof jobs, retries and their optional diagnostics;
preparation and reviews use a separate serial lane. One case ledger includes
all phases. This is not account-wide distributed rate control.
Other cases own separate budgets. Python coordination consumes no model slot.
Free slots take the next queued job with a fresh model context for that node.

Proof workers see only their frozen ports, allowed statements, own NL paragraphs
and relevant definitions/views. No sibling proof or reference answer is sent.
Shared source lookup is exact, rechecked by Lean, and a miss launches ordinary
proof work. Shared production and conditional consumers may run concurrently;
actual assembly closes every dependency. Failure leaves the root unfinished.

`run_graph.py --max-concurrency auto|N` remains a frozen-port-only command;
`model_pilot.py` provides the internal isolated proof stage. Neither alone
claims whole-proof Audit B. Integer `--workers` / `--max-model-stages` remain
compatibility aliases, with conflicts rejected.

## 6. Execute Audit B and finish

After all local jobs pass, use one serial postprocessing author under
[the assembly protocol](assembly.md). The existing mapping author performs
this work: complete actual library discharges, close the source-facing root,
build standalone `Proof.lean`, then prepare kernel inspection and the review
packet. Keep this thread separate from the subsequent independent reviewer.
Standalone assembly, inspector execution and semantic review have separate
recorded outcomes. An unchanged checked mapping is reused for its submission;
it does not require another identical native build or another model author.

```sh
python3 scripts/workflow.py audit-prepare /absolute/new-workflow
```

Read source and actual types; complete the pending `audit-b/mapping.json`,
including actual E/P encoded types and concise direct/equivalent correspondence
explanations. P includes all hypotheses. Supply `library_terms` only for retained
M ports; Mathlib itself needs no source-registration or signature ledger. Types
and explanations remain unreviewed proposals until independent B.

```sh
python3 scripts/workflow.py audit-build /absolute/new-workflow
```

Read complete kernel/source evidence, then write a real located semantic
review using [Audit B](audit-b.md). Revalidate ordinary or incremental A; do not
repeat A mathematics inside B. Inspect actual dependencies/hidden fields and
the final exported root, not just compiler success. No unresolved internal
project assumption or local axiom is allowed. Pinned Mathlib results are freely
available and are not checked against NL0 M names or uses. External publications remain
declared source-faithful inputs, not theorems proved by Lean.
Validate location format before ending a model review: every pointer must
resolve and include the required paired locations from mechanical.json. Keep
actual FAIL/UNVERIFIED judgments. A metadata defect can be corrected without
rerunning unchanged Lean proofs or NL0 mathematics, with the old record retained.

```sh
python3 scripts/workflow.py audit-check /absolute/new-workflow \
  --review /absolute/new-workflow/audit-b/completed-review.json
```

Only a genuine whole-source Audit B pass yields `WORKFLOW-PASSED`. Retain failed
attempts and distinguish model-budget exhaustion from execution faults. Final
reports separate preparation, freeze, proof makespan, queued/model-stage costs,
assembly and audit; uninstrumented owner work stays UNMEASURED. Cold and warm
reuse costs are separate, first construction is not free, and nested tool time
is not added twice. Functional success does not establish general acceleration.

## Sources carrying verified background notes

Start from the accepted NL0 plus Audit A supplement. New interfaces use
`node_local_reference`: keep original H/E inputs and optional M ports, bind the full supplement
hash, and retain each node's notes as on-demand implementation references. Do
not pre-type or promote every note into an additional M input. The controller
attaches exact note IDs to the relevant paragraphs. This requires no source
rewrite and no fresh Audit A. Mathlib use is globally available in stage two;
notes remain local references, not permissions. Legacy `promoted_inputs` contracts
remain supported for reproducibility.

Preserving this authority does not require every proof worker to read every
justification. Its initial prompt contains a compact index for its selected
notes; it can request one full note by ID when useful. Apply the
[local note procedure](translation-rules.md#use-local-audit-a-notes-when-they-can-shorten-an-implementation-route)
to connect existing conditions to a Lean interface premise, without changing
source facts or adding mandatory analysis stages.
