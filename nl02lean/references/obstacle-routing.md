# Indexed obstacle diagnosis and strategy retrieval

Free-form strategy lookup is optional and disabled in normal full workflows.
Successful proof work pays no mandatory diagnosis or retrieval call. The bank contains
generalized advice, not proof templates or automatically accepted premises;
no performance benefit is established by its presence.

## Automatic native resource feedback

Normal Yui proof queues separately freeze ST020 and its source/index/evidence
hashes at entry. A failed main-proof or auxiliary check with actual structured
`LEAN_TIMEOUT` metadata or a native heartbeat-exhaustion diagnostic receives
`repair_advice` in that same tool result. The same worker first follows the
applicable diagnostic branch, then checks a small fragment and the unchanged
complete target. No retrieval model or fresh proof session is started.

This does not enable arbitrary `find_strategies` queries. Successes, ordinary
type errors, cancellation, provider faults, native cleanup faults and direct-arm
work do not trigger this delivery. A missing, modified or version-inapplicable
card yields explicit unavailable-advice metadata while preserving the native
failure and ordinary local repair. Advice never changes acceptance or adds a
premise. Retained tool logs and stage manifests identify the policy and card.

Checked shared theorem lookup is a separate mechanism described in
[shared-lemmas.md](shared-lemmas.md). It does not query these advice cards.

## Query a concrete implementation obstacle

First identify the failed local transition from its goal, exact context,
compiler diagnostic and attempted application. If the local audited-note index
already addresses the missing premise or transport, follow the
[local note procedure](translation-rules.md#use-local-audit-a-notes-when-they-can-shorten-an-implementation-route).
Do not infer a mathematical gap from elapsed time or one compiler error.

A compact query describes the implementation family and observed obstacle:

```json
{
  "family": "representation",
  "tags": ["conversion", "congruence"],
  "facts": ["source_relation"],
  "contraindications": [],
  "lean_version": "4.32.2"
}
```

Families are `representation`, `analysis`, `calculation`, `interface`,
`provenance`, `execution`, or `unknown`. Select a family from the actual failed
operation; abstain when the diagnosis is unclear. The helper does not guess a
strategy from mathematical keywords, specific library names or formula tokens.
It only recognizes explicit execution-fault flags. A transport failure is not
a mathematical rejection.

At the tool boundary, `grounded_query` supplies the exact pinned version from
the immutable contract and preserves the reported classification when no
execution fault is supplied. It records both inputs to the routing decision.
Neither reported prerequisites nor the selected family are independently
verified by this step.

## Bounded retrieval and evidence

The index contains family/tag postings and card metadata. Retrieval scores at
most 64 candidates and reads at most three cards. It reports truncation and
the number scored and read. The source/index, selected card and evidence hashes
must match. Retrieval can miss a useful strategy; no completeness is claimed.

Run from the Yui repository root:

```sh
python3 -B nl02lean/scripts/strategy_bank.py query --json \
  '{"family":"representation","tags":["conversion","congruence"],"facts":[],"lean_version":"4.32.2"}'
```

`PRECONDITIONS_REPORTED` means that the query lists every prerequisite; it does
not mean those prerequisites are proved. `CONDITIONAL` lists missing ones.
Check them in the current proof context before applying the advice. Reported
contraindications and an out-of-scope toolchain exclude a card. Version scope
is a retrieval constraint, not evidence of successful proof compilation.

Cards use neutral examples and qualified evidence summaries. They contain no
historical proof excerpts, node identifiers or reference answers. Current cards
are `GENERAL_GUIDANCE`, not inherited successful runs. See
[the maintenance rule](../bank/rule.md) before optionally extracting a strategy
after a workflow. Keep detailed original provenance in the work records outside
the live bank and never feed evaluations back to a measured proof session.
