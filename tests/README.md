# Software tests

Run [local adaptation](../setup/README.md) before native testing. Test output,
compiler scratch, child processes and machine-specific configuration stay
outside the tracked source tree.

## Choose a test scope

`selftest --quick` checks the public workflow package, input bindings,
acceptance rules and runtime snapshots. For a local change, add each affected
area. The runner executes the shared core once and includes the selected
producers and consumers. For a release, a maintenance baseline or a change to
shared orchestration, use full discovery.

```sh
.venv/bin/python -B nl0/scripts/yui.py selftest --quick
.venv/bin/python -B nl0/scripts/yui.py selftest --quick --area basis
.venv/bin/python -B nl0/scripts/yui.py selftest --quick --area cleanup --area recovery
.venv/bin/python -B nl0/scripts/yui.py selftest --all
```

| Area | Behavior checked |
| --- | --- |
| `basis` | Correct a rejected source in the author session and verify the frozen source at the NL0 handoff |
| `cleanup` | Verify file ownership, stop an owned process tree, and protect unrelated processes |
| `lean` | Bind a proof packet to its inputs, inspect a Lean export and reject changed review material |
| `recovery` | Qualify retained proof work and reject unsafe process or checkpoint reuse |
| `runner` | Check test discovery, selection, environment handling and reported outcomes |

The [quick manifest](quick.json) lists the core and area selectors. Both
`selftest` and `selftest --all` discover the full suite. New tests enter full
discovery through the usual environment catalogue. Each report records its
scope, areas, selected test IDs, outcomes and wall time. Quick runs write
`.runtime/test-report-quick.json`. Full runs use `.runtime/test-report.json`.

## Select an environment or individual tests

```sh
.venv/bin/python -B nl0/scripts/yui.py selftest --group none
.venv/bin/python -B nl0/scripts/yui.py selftest --group current
```

`none` tests do not resolve or run Lean. `current` tests use the environment
selected during local adaptation. `requirements.json` declares each test's
requirements; an unclassified test is an error. The selector also supports
an explicitly declared exact environment, but the maintained tests contain no
archived problem that requires an old global toolchain.

For maintenance, run the changed modules and their direct consumers:

```sh
.venv/bin/python -B tests/run_tests.py test_job_entry test_runtime_snapshot
```

The runner accepts module, class and method names, plus unittest-style
`discover -s/-p` selection. `--environment` supplies an explicit checked local
descriptor. `--comparison-environment` optionally enables a real second-pair
comparison. Ordinary tests need only the currently selected pair.
The imported-code version-guard case requires a different Lean version; missing
or same-version comparisons are explicitly reported as `SKIP` with a reason,
including in quiet output and JSON. They never count as cross-version passes.
The overall result says `PASSED_WITH_SKIPS` and includes outcome counts.
Reports identify both selected environments when comparison is requested.
`--report /absolute/path/report.json` retains an execution report outside the
repository.

Each selected group gets its own process and temporary root. The runner cleans
owned scratch and child processes on success, failure and catchable
interruption. Unconfirmed cleanup fails the run and retains diagnostic evidence.
It preserves shared compiler caches and unrelated processes. Provider and
notification controls prevent a software test from silently calling a real
model or messaging the user.

## Maintained responsibilities

| Responsibility | Representative controls |
| --- | --- |
| Installation and current-format jobs | `test_local_setup`, `test_setup_native`, `test_job_entry`, `test_lean_environment`, `test_runtime_snapshot` |
| Current NL0 structure and independent Audit A | `test_closure`, `test_review_contract`, `test_nl0_review_loop`, `test_review_controllers` |
| Four-stage routing and dependency discharge | `test_basis`, `test_basis_workflow`, `test_basis_case_batch`, `test_b2lean`, `test_basis_closure_levels` |
| Current native client, errors and accounting | `test_native_protocol`, `test_native_client`, `test_native_faults`, `test_native_recovery`, `test_carrier_reader`, `test_execution_state` |
| Lean interfaces, local proofs and final assembly | `test_interface_gate`, `test_graph_runner`, `test_assembly`, `test_audit_b`, `test_final_acceptance` |
| Retained work, cancellation and cleanup | `test_interrupted_resume`, `test_proof_io_recovery`, `test_basis_closure_recovery`, `test_controller_cleanup`, `test_process_queries`, `test_process_recovery` |
| Version-independent strategy references | `test_bank_versions`, `test_strategy_bank`, workflow strategy-reference suites |

Generic fixtures are deliberately small and synthetic. Their environment is
filled from the selected test descriptor. They are not copies of a historical
research task and do not certify a theorem or model capability. Source and
review metadata in deterministic provider controls are labeled synthetic.
Mathematical examples and model benchmarks belong in the separate Yui-results
repository, not the installed harness.

Reconnect controls reproduce a parent stream failure while its dispatched tool
is still working, then read the finished batch from the recovering turn without
dispatching it again. An intentional generic-continuation variant must fail that
acceptance case. A separate real Codex/Code Mode test reads the saved return after
a local provider disconnect and checks the native input provenance. These are
deterministic fault-injection tests, not measurements of VPN outage duration or
proof-performance benchmarks.

Process recovery controls exercise an actual slow subprocess, the public
diagnosis/decision CLI, and real Lean compilation followed by injected process
query exhaustion. They require cleanup confirmation and the remaining axiom
checks without compiling the proof again. Owner-AI advice and notification
delivery use deterministic software fixtures; they do not establish live desktop
delivery or the cause of a historical OS slowdown.
The idle-owner control runs the real notifier against a deterministic local
queue executable, which wakes only with `--resume` and executes the genuine
diagnosis/decision CLI. Separate controls retain zero-exit resume warnings and
reject queue success as evidence of takeover.

Workflow protocol changes also follow [the maintenance guide](../workflow/SKILL.md):
run the registered Workflow Builder audit before and after a change, retain
independent acceptance expectations, and record an accepted baseline only after
the required checks pass. A prior test report does not establish the status of
newly edited source.
