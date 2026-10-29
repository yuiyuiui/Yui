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
criterion, neutral positive/negative examples, `lean_versions`, `status`, and
nonempty `evidence`. The family describes the implementation obstacle; it is
not the mathematical subject label. Existing families are `representation`,
`analysis`, `calculation`, `interface`, `provenance` and `execution`.

`lean_versions` bounds retrieval to declared toolchain versions. It is not a
claim that a recipe, a proof example or all of Mathlib has been tested. The
current curated cards are editorial guidance for the repository's pinned
toolchain, not executable proof templates or empirically validated optimizers.

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

Retrieval is bounded advice. It checks declared toolchain scope and reported
contraindications, returns missing prerequisites, and never marks them proved.
Verify each required fact in the current Lean context before applying a recipe.
The routing helper binds the actual toolchain version and recognizes explicit
execution faults; it does not guess a mathematical subject from formula tokens.
