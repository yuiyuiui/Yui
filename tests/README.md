# Harness software tests

This is the single software-test suite for the entire harness: shared runtime,
NL0/Audit A, Lean/Audit B and the connections between them. The two stage
directories contain production code and rules; neither owns a second suite.

From the repository root, run:

```sh
python3 -B nl0/scripts/yui.py selftest
```

The command discovers this directory once. Use `selftest --verbose` to list
individual cases. A focused module can also run independently, for example:

```sh
python3 -B -m unittest discover -s tests -p test_audit_b.py -v
```

These are software controls, separate from user-supplied mathematical inputs and
their generated run directories outside this installation. Automatic discovery does not call a model or
start a paper-solving workflow. Native integration cases do run the pinned local Lean installation. The native
handoff test uses the installed Codex client with a deterministic loopback Responses
server, no credentials and no remote model. It verifies actual interruption,
same-thread continuation, tool-result provenance and absence of extra requests;
a missing compatible client is an explicit skip. Synthetic review records exercise validation rules;
they never certify a mathematical proof or substitute for an independent audit.

The PDF readback regression uses an installed `pdftotext` or `pypdf` backend;
without either it reports an explicit skip. Installation controls copy the root
skill to renamed paths containing spaces, omit the tests and optional catalog,
and prepare/status a synthetic job from an unrelated working directory. They
need no removed mathematical examples or benchmark files.
Direct-session prompt preparation is also tested from a relocated copy using
synthetic inputs, environment-selected tools and explicit CLI overrides.

## Responsibility map

| Behavior | Representative test modules |
| --- | --- |
| Entry points, profiles, scheduling, owner handoffs, cancellation and service recovery | `test_job_entry`, `test_queue_controller`, `test_owner_observation`, `test_model_profiles`, `test_remote_retry`, `test_cleanup_tests` |
| Selected targets, qualified source access, and direct-session persistence | `test_target_selection`, `test_source_access`, `test_source_qualification`, `test_direct_runner` |
| Model isolation, task/proof state, transport health and usage accounting | `test_isolation`, `test_execution_state`, `test_own_state`, `test_execution_health`, `test_accounting` |
| NL0 structure, local scope, author release and Audit A evidence | `test_nl0`, `test_closure`, `test_artifact_validation`, `test_author_check`, `test_external_audit`, `test_audit_reuse`, `test_evidence_index` |
| Global PASS admission, retained review/repair pairs, global restoration and combined active slots | `test_parallel_audit`, `test_nl0_review_loop`, `test_role_sessions` |
| Accepted-source preparation, same-role revisions, actual native submit handoffs and user-selected reset | `test_source_preparation`, `test_source_refactor_driver`, `test_minimal_translation`, `test_workflow_policy`, `test_workflow_handoffs`, `test_native_handoff`, `test_stage_completion`, `test_translation_reset` |
| Conditional Lean tasks, concurrency, reuse and assembly | `test_translation`, `test_concurrency`, `test_execution_queue`, `test_shared_parallel`, `test_proof_reuse`, `test_assembly` |
| Pre-proof semantic gate, explicit obstructions, passive progress accounting and same-owner repair | `test_interface_gate`, `test_proof_repair` |
| Owned executable snapshots and streaming request-history readback | `test_runtime_snapshot`, `test_streaming_audits` |
| General advice retrieval, evidence scope and maintenance | `test_strategy_bank` |
| Native signatures, endpoint correspondence and Audit B | `test_signature_comparison`, `test_endpoint_correspondence`, `test_audit_b`, `test_postprocessing`, `test_final_acceptance` |

File names group related behavior; they do not create separate execution suites.
`harness_support.py` supplies common test paths and synthetic profiles.
`tooling/*_fixtures.py` contains reusable data builders, with no test cases.
Static input examples live in `fixtures/`, including `fixtures/lean/`.
`fixtures/legacy/` preserves historical parser inputs and provenance verbatim,
including old absolute paths. Its archived smoke runner is not a supported
entry point and is not executed by discovery; use `selftest` for the current
portable controls. Tests that need live tool locations resolve the current pins.
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
The default carrier launch is fail-fast blocked by `harness_support.py`; an
incomplete mock cannot read authentication or silently call a real model. Config
tests explicitly mock process creation, and native protocol tests explicitly
replace launch with their deterministic loopback carrier. `test_offline_guard`
checks that an unmocked public stage fails before relay/process/credential access,
without entering the production retained-error wait.
7. Remove or merge a case only after identifying equivalent retained coverage.
   A lower test count is not a quality target. A passing count alone does not
   establish that every relevant failure mode is covered.
