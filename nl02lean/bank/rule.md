# Maintaining the optional Lean strategy bank

This bank stores reusable implementation advice. It grants no mathematical
premises, proves no theorem, and does not alter NL0 or Audit A/B. Normal full
workflows leave free-form strategy queries disabled. Yui proof workers separately
receive frozen ST020 after verified native wall/heartbeat exhaustion, with no
extra model call. Successful and ordinary-error checks do not query advice.
Maintaining the bank after a run is an explicit user choice; a run never updates
it automatically.

## Scope and admission

Keep a procedure only when its obstacle, prerequisites and verification can
be stated independently of the problem that suggested it. Broad mathematics
is welcome: analysis, algebra, geometry, probability, number theory,
combinatorics, topology and logic. `general` covers cross-field implementation.
These labels describe applicability, not proof permissions.

Do not add recipes specific to PDE, harmonic analysis, dynamical systems, a
particular equation, paper, named solution, parameter regime or benchmark.
Remove that specialization if a useful general procedure remains; otherwise
omit the card. Do not replace a specific recipe with a vague slogan: a card
needs actionable steps and a way to test whether those steps apply.

The live bank must not contain original proof excerpts, historical node IDs,
run IDs, case paths, named project declarations, old verdicts or reconstructed
reference answers. This applies to titles, tags, examples and evidence as well
as the main procedure. Generic examples may illustrate the operation and a
counterexample to misuse without reproducing an earlier proof.

## Optional extraction after a workflow

1. Read the retained work record and actual diagnostics after the workflow.
   Identify an implementation obstacle and the action that addressed it.
   A successful final theorem alone does not show which action helped.
2. Write the transferable procedure without the original theorem, node names,
   numerical constants or hidden assumptions. List the prerequisites and the
   circumstances in which it must not be used. Merge an existing equivalent
   card rather than adding a duplicate.
3. Separate observation from inference. A newly generalized card has status
   `GENERAL_GUIDANCE`, even if the original application passed. Claim broader
   utility only after independent applications support it; retain failures and
   missing evidence in the work records. Do not label an editorial rewrite as
   a tested speedup or a mathematically verified strategy.
4. Keep detailed source provenance and original proof material with the user's
   work records, outside this live retrieval bank. A bank evidence record is
   a sanitized design/observation/control note, not a copy of those materials.
   When useful, write a neutral synthetic control with its own positive and
   negative cases. Its result supports only the property actually tested.
5. Edit `strategies.json`, increment the changed card's `revision`, review every
   field for specialization and leakage, rebuild, and run the controls below.
   Existing completed runs and their frozen bank copies are not rewritten.

## Card contract

Each card needs a stable `ST` identifier, positive integer `revision`, title,
broad `domains`, retrieval `family` and `tags`, an obstacle, explicit
`preconditions` and `contraindications`, an ordered `procedure`, a verification
criterion, neutral positive/negative examples, `reference_environments`, `status`, and
nonempty `evidence`. The family describes the implementation obstacle; it is
not the mathematical subject label. Existing families are `representation`,
`analysis`, `calculation`, `interface`, `provenance` and `execution`.

`reference_environments` records paired `lean_version` and exact `mathlib_commit`
values, with `basis: historical_configuration`. These are the recorded reference
contexts, not compatibility restrictions or evidence of successful execution.
Every strategy can be browsed and explicitly read under any current version,
including before a Lean environment is selected. Each catalog item and complete
card discloses its reference environments. The current curated cards retain
the historical Lean 4.32.2 / Mathlib 905b95818eb32af7874a58b427f50c1711a5e96c
configuration recorded when they were maintained; this does not claim that
their recipes or examples were compiled there.

The reader must adapt declaration names, APIs, syntax, types and hypotheses and
check the actual implementation in the current task's selected environment.
Catalog/card replies explicitly mark `reference_only` and
`current_environment_verification_required`. A read never changes environment
selection, proves a premise or authorizes proof acceptance. Ranked search and
the frozen ST020 timeout reference follow the same cross-version rule.

New bank indexes use format 3 and current tool replies use `StrategyReply@2`.
Historical frozen jobs retain their old executable/data snapshots and contracts;
maintenance does not rewrite those jobs or their evidence.

Evidence records have exactly `kind`, `path`, `sha256`, and `note`. `path` is
relative to this bank, must stay inside it, and names a sanitized text record.
Kinds are `design_rule`, `generalized_observation` and `synthetic_control`.
For editorial cards this document records the admission policy; it is not
evidence of successful application. Record uncertainty explicitly in `note`.
Do not embed proof excerpts, old case identifiers or external source paths.

The builder checks identifiers, required fields, broad domain labels, duplicate
IDs, evidence hashes and known case-ID syntax. These are structural checks.
The maintainer must still judge whether the procedure is truly general and
whether evidence claims are justified; no keyword filter can certify that.

## Rebuild and check

Run from the Yui repository root:

```sh
python3 -B nl02lean/scripts/strategy_bank.py build
python3 -B -m unittest discover -s tests -p 'test_strategy_bank.py'
```

`strategies.json` is the editable source. `cards/` and `index.json` are generated;
the builder removes obsolete generated cards after validation. Do not edit
those outputs independently. Keep this document, evidence and index in sync.

Retrieval is bounded advice. Search checks reported contraindications and task
relevance, returns missing prerequisites, and never marks them proved. Explicit
ID lookup remains available for every card regardless of source or current version.
Verify each required fact in the current Lean context before applying a recipe.
The routing helper records the actual task version as context and recognizes
explicit execution faults; that version never filters references. It does not
guess a mathematical subject from formula tokens.
