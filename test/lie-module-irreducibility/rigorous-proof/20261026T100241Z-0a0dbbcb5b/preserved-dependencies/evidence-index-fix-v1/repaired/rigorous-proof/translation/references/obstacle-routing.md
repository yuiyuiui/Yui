# Indexed obstacle diagnosis and strategy retrieval

This is an optional fallback, disabled by default in the current model runner.
Direct successful proof work pays no mandatory diagnosis/retrieval call.
The 20 historical cards remain available; expansion is paused pending evidence
of benefit. The local guidance comparison is in
`experiments/lean-guidance-falsification-v1/` at the repository root; its rules
and diagnosis arms did not meet the prespecified practical improvement gate.
This does not establish that every possible prompt or strategy is ineffective.

Checked shared theorem lookup is a separate deterministic mechanism described
in shared-lemmas.md; it does not query these advice cards.

## Query the first blocked transition

If its local audited-note index already suggests the missing premise or
transport, consult that note before a broad strategy search. Follow the
[local note procedure](translation-rules.md#use-local-audit-a-notes-when-they-can-shorten-an-implementation-route)
inside the current worker; neither note nor strategy lookup is mandatory when
the next local repair is clear.

Capture its contract/plan/step hashes, goal, exact local context, compiler
diagnostic, attempted code and progress made. Separate these observations from
a proposed root cause. A `type mismatch` can be a coercion issue, incompatible
representatives, a changed mathematical statement, or a library/API mismatch.

Use a compact diagnostic:

```json
{
  "family": "representation",
  "tags": ["norm", "supremum", "ENNReal"],
  "facts": ["real_norm_equality"],
  "contraindications": [],
  "lean_version": "4.32.2"
}
```

Families are `representation`, `analysis`, `calculation`, `interface`,
`provenance`, `execution`, or `unknown`. A model may classify the diagnostic
once using this small taxonomy. It need not see or compare the entire bank.
The deterministic `diagnose` helper supplies candidate tags only for explicit
observations; low-information diagnostics abstain. Its output is not a
mathematical error judgment. Do not use elapsed time as a gap classifier.

At the model-tool boundary, `grounded_query` reads the exact pinned version
from the immutable contract and uses the real target/direct-input context to
correct common observed-feature routes. A model's vague 'Lean 4' string or
generic `interface` label does not force a failed lookup. Preserve both the
reported query and the grounded route in the receipt. This normalization
does not prove preconditions or turn candidate classification into a root cause.

## Indexed search

The build command materializes family/tag inverted postings and separate card
files. The search command intersects specific postings where possible, then
ranks at most 64 metadata candidates, filters toolchain and contraindications,
and opens at most three complete cards. It reports posting size, candidates
scored, cards read and truncation. The prototype may miss a useful strategy;
bounded retrieval is not completeness. Rephrase the observed problem or refine
the family/tags after a miss rather than loading all recipes into context.

```sh
python3 scripts/strategy_bank.py build
python3 scripts/strategy_bank.py query --json \
  '{"family":"representation","tags":["norm","supremum"],"facts":["real_norm_equality"],"lean_version":"4.32.2"}'
```

The returned `applicability` is `PRECONDITIONS_REPORTED` only when the query
claims all required facts. Those claims still need checking against the actual
Lean context/proofs. Otherwise it is `CONDITIONAL` with explicit missing facts.
It is never a proof that a condition holds or that the strategy will succeed.
An incompatible version returns no recipe; verify and version a new instance.

## Strategy card

Each card includes an abstract obstacle, observations that suggest it, required
facts, contraindications, an operation sequence, verification/stop condition,
a positive and negative example, compatible checked version, located source
evidence and evidence status. Historical source code supports a pattern;
it does not prove a universally applicable recipe. `RETROSPECTIVE_PATTERN`
and `PILOT_EXERCISED` remain different labels.

Record a new application with the pre-state, chosen card/version, verified
preconditions, attempted patch, compiler result, mathematical correspondence
and time. A failure is useful evidence; do not delete it or label it a repaired
mathematical gap. Promote recipes only from observed applications, and test
generalization on material not used to design the card before claiming utility.

This is initially a local Python library/tool boundary. MCP can expose the same
query later; adding MCP does not improve the recipes or their correctness.
