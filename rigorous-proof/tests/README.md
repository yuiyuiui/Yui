# Harness software tests

This is the single software-test suite for the entire harness: shared runtime,
NL0/Audit A, Lean/Audit B and the connections between them. The two stage
directories contain production code and rules; neither owns a second suite.

From the repository root, run:

```sh
python3 -B rigorous-proof/nl0/scripts/yui.py selftest
```

The command discovers this directory once. Use `selftest --verbose` to list
individual cases. A focused module can also run independently, for example:

```sh
python3 -B -m unittest discover -s rigorous-proof/tests -p test_audit_b.py -v
```

These are software controls, separate from the mathematical example runs in
the repository's `test/` directory. Automatic discovery does not call a model or
start a paper-solving workflow. Native integration cases do run the pinned
local Lean installation. Synthetic review records exercise validation rules;
they never certify a mathematical proof or substitute for an independent audit.

## Responsibility map

| Behavior | Representative test modules |
| --- | --- |
| Entry points, profiles, scheduling, cancellation and service recovery | `test_job_entry`, `test_queue_controller`, `test_model_profiles`, `test_remote_retry`, `test_cleanup_tests` |
| Model isolation, task/proof state, transport health and usage accounting | `test_isolation`, `test_execution_state`, `test_own_state`, `test_execution_health`, `test_accounting` |
| NL0 structure, local scope, author release and Audit A evidence | `test_nl0`, `test_closure`, `test_artifact_validation`, `test_author_check`, `test_external_audit`, `test_audit_reuse`, `test_evidence_index` |
| Accepted-source preparation and stage handoff | `test_source_preparation`, `test_source_refactor_driver`, `test_minimal_translation`, `test_workflow_policy` |
| Conditional Lean tasks, concurrency, reuse and assembly | `test_translation`, `test_concurrency`, `test_execution_queue`, `test_shared_parallel`, `test_proof_reuse`, `test_assembly` |
| General advice retrieval, evidence scope and maintenance | `test_strategy_bank` |
| Native signatures, endpoint correspondence and Audit B | `test_signature_comparison`, `test_endpoint_correspondence`, `test_audit_b`, `test_postprocessing` |

File names group related behavior; they do not create separate execution suites.
`harness_support.py` supplies common test paths and synthetic profiles.
`tooling/*_fixtures.py` contains reusable data builders, with no test cases.
Static input examples live in `fixtures/`, including `fixtures/lean/`.
Helpers must not import `test_*.py`; a test must not depend on another test having
run or imported first. Scripts in `tooling/` that support explicit experiments
are not executed by unittest discovery.

## Maintenance rules

1. State the observable behavior or regression a case protects. Check outputs,
   rejected inputs, preserved files, evidence bindings or actual side effects.
   Avoid assertions about private implementation shape alone.
2. Before adding a case, inspect the existing owner of that behavior. Reuse its
   fixtures; extend a test or use named subtests for equivalent input variants.
   Do not copy a scenario into another module solely because the caller differs.
3. Keep separate tests when they protect different boundaries: a local validator
   rejecting an input does not establish that the public workflow invokes it.
   Preserve meaningful positive, boundary, tampering, failure and recovery cases.
4. Mock only dependencies outside the behavior being tested. Assertions must
   exercise production code, not merely confirm a value returned by the mock.
5. Native checks are necessary for claims about Lean elaboration, signatures or
   trust. Reuse an immutable compiled fixture within a class where appropriate;
   give mutation tests their own temporary copies. Do not replace native checks
   with invented success receipts to make the suite faster.
6. Run tests in temporary directories. Preserve repository examples, archived
   results and shared toolchain files. Never require credentials or network model
   calls for automatic software tests.
7. Remove or merge a case only after identifying equivalent retained coverage.
   A lower test count is not a quality target. A passing count alone does not
   establish that every relevant failure mode is covered.
