# Controller and workflow software tests

Run `python3 -B -m unittest discover -s tests -v` from the skill repository.
Native tests require the compatible Codex executable; kernel tests require the
configured pinned Lean/Mathlib environment. A skipped native test is not a
native integration pass. The suite blocks accidental live model calls and real
owner-task notifications through harness_support.py.

These are software tests. Synthetic reviewer judgments and deterministic
provider replies do not certify a mathematical proof or a model's capability.
The full mathematical test cases/results are maintained separately.

| Boundary | Main tests | Required behavior |
| --- | --- | --- |
| Installed invocation and frozen runtime | test_job_entry.py, test_runtime_snapshot.py | Bind actual inputs/settings; no mutable installation drift or undeclared runtime files. |
| Native configuration and isolation | test_native_protocol.py, test_model_profiles.py, test_isolation.py | Fixed requested profile, approved input/tool boundaries, no Yui model HTTP listener or endpoint rewriting. |
| Selected native components | test_native_runtime.py | Same-installation helper discovery; missing, nonexecutable, escaping, version-mismatched or mutated components fail before dispatch. |
| Actual Code Mode and local faults | test_native_code_mode.py, test_native_protocol.py | Real custom `exec` invokes the installed helper, reads frozen input, checks and submits; real helper spawn denial after a checkpoint pauses without continuation or cleanup. Printed lookalike errors remain ordinary output. |
| Real native submission | test_native_client.py | Persist the artifact, stop the current work, confirm completion, preserve the role; delayed provider tails cause no synthetic relay fault or extra inference. |
| Retained role and successful closure | test_native_client.py, test_role_sessions.py, test_stage_completion.py | Reuse the same process/thread; only the approved completed-role boundary or user cancellation releases it. |
| Native-to-A collection | test_native_review_pipeline.py | Actual Codex processes, coverage contracts and collectors produce bound receipts; a global FAIL cannot dispatch local reviews. Judgments remain synthetic software fixtures. |
| Native error after actual progress | test_native_faults.py | A persisted checkpoint survives real endpoint errors, mid-stream closure and idle timeout; no successful tool is replayed. |
| Retry, pause, resume, cancel | test_native_faults.py, test_remote_retry.py, test_fault_control.py | 60-second/30-retry policy, one actual minute wait, exact incident-bound manual resume, cancellable retained waits and isolated notifications. |
| Post-recovery record eligibility | test_native_faults.py, test_execution_health.py | The real recovered native record reaches the review gate; auth recovery requires the matching bound operator resume. Historical faults/partial usage remain disclosed. |
| Stdout/RPC faults and stale events | test_carrier_reader.py, test_native_protocol.py, test_carrier_cancellation.py | Fail visibly on invalid/closed native output; foreign/stale messages cannot execute tools or complete the current work. |
| Accounting | test_native_protocol.py, test_accounting.py, test_phase_metrics.py | Difference cumulative native counters; do not sum duplicate snapshots, subsets or copied stage evidence. Missing provider coverage/tier stays unknown. |
| Initial author and global Audit A | test_nl0_review_loop.py, test_review_contract.py, test_review_controllers.py | Complete global coverage/findings before the same-author revision or local admission. Receipt submission alone cannot grant PASS. |
| Parallel local A and global escalation | test_nl0_review_loop.py, test_parallel_audit.py | Node-local modifications, shared active slots, exact merged reviewed versions, restored global role and affected-scope rechecks. |
| Shared extraction and interface preparation | test_source_refactor_driver.py, test_source_preparation.py, test_workflow_handoffs.py, test_interface_controls.py | Skip unchanged incremental review; retain the approved author/reviewer pair and recheck actual changed scope before freeze. |
| Frozen interfaces and parallel Lean | test_interface_gate.py, test_shared_parallel.py, test_graph_runner.py, test_proof_repair.py | No unreviewed worker dispatch, no E/P mutation, local repair stays with its author; global connection work preserves the frozen authority. |
| Native Lean limits and advice | test_native_timeout_advice.py, test_execution_queue.py | One-call timeout is distinct from task completion; same-worker typed repair, cancellation and no success from partial conditional bodies. |
| Assembly, kernel closure and final acceptance | test_assembly.py, test_audit_b.py, test_final_acceptance.py, test_postprocessing.py | Compile actual full files, close dependencies and trust; machine B inherits only exact reviewed semantics. B-final cannot cover invalid proof/closure. |
| Exception decisions and final cleanup | test_translation_reset.py, test_workflow_handoffs.py, test_cleanup_tests.py | User-selected drift/recheck/reset/delivery is explicit; preserve original-goal status, exact ownership and scientific evidence. |

Real-native test endpoints are deterministic terminal services on loopback.
They receive requests directly from the genuine Codex executable and never
forward a request to a real model. Timing, endpoint fault injection and mocked
notification sinks remain test-only. Production has no local model listener.
Native fault events sometimes expose only an opaque error in a particular
Codex version; unsupported meanings must remain unknown and paused rather than
being inferred from arbitrary prose. Native usage tests never invent response
IDs or claim exact provider accounting from work-level counters.

Historical raw-wire exposure/usage readers retain regression coverage for old
archives. They do not enable a legacy carrier in new runs. Obsolete live-relay
implementation tests were removed; their relevant handoff/fault/ownership
requirements are exercised through the native tests above.

## Native migration validation record (2026-10-31)

Full discovery completed with 859 tests in V1 and 869 in V2. Subsequent affected-module regression completed with 179 tests per version, including the final native fault classification, usage and capability metadata changes. Two additional native-to-A collector integration tests per version passed afterward. Skill validation and diff checks are separate release checks. These numbers record this migration checkpoint; later additions may change discovery counts.

## Code Mode execution repair validation (2026-10-31)

The full suites passed: 883 tests in V1 and 893 in V2. The final affected native
suite passed 63 tests per version after the last legacy-receipt compatibility
assertion was added. These tests exercise actual custom `exec` calls through
Codex's helper, real denied process execution, retained pause, remote failures
before headers and during a response, and owned process-group cleanup. The
existing controller/Lean regression still covers the complete workflow.

Both versions also passed an isolated live-model input-read/check/submit test
using gpt-6.1-sol/high with Standard requested and no fallback. This tests the
production tool chain, not mathematical acceptance. Actual service tier remains
unverified when the native client does not expose it. Compact evidence and log
hashes are in [native-execution-validation.json](native-execution-validation.json).

## Obsolete runtime cleanup validation

The complete catalogues exercised 869 V1 and 879 V2 controls, including actual
Lean inspection, standalone assembly and deterministic native-carrier faults.
One migrated cancellation fixture initially checked the already-submitted role
instead of its still-active sibling. The fixture was corrected; all 23 proof
repair controls then passed in each variant. The shared-proof-graph inspector
regression also passed with actual Lean under its 30-second control limit.
No model inference or production owner notification is part of these checks.

## Canonical main and detailed alternative

The mathematical-NL0 policy controls now exercise the default `rigorous-proof`
identity and `rigorous-proof/<run-id>/` output namespace. The detailed workflow
is retained on `nl0-detail`; historical V1/V2 counts above describe their original
checkpoints. The shared-term inspector control runs actual Lean with a shared
proof graph and checks full types, dependencies and axioms without an obsolete
proof-use classifier. Native fault, retained-role handoff and explicit repair
controls exercise the current carrier; raw HTTP/SSE observers are removed.

Final consolidation validation: canonical main passed all 879 controls in
717.376 seconds. A Git-exported nl0-detail snapshot independently passed all
869 controls in 757.856 seconds. Both complete runs exited successfully, with
no model inference. The canonical synthetic fixture retains UNVERIFIED status;
only its packet hashes were regenerated after the identity migration.
