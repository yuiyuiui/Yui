# Controller and workflow software tests

Use the local interpreter with `workflow/requirements.txt` installed. Run `.venv/bin/python -B tests/run_tests.py` (or `yui.py selftest`) from the skill repository. The public workflow suite runs the CLI through a scripted native provider, actual Lean, the optional audited checkpoint, explicit cleanup and independent readback. Set `YUI_TEST_COMPARATOR` to a compatible upstream executable to compare all three Lean exports and two incorrect candidate proofs after cleanup. The Comparator host dependencies and sandbox follow the upstream platform requirements. For maintenance also run the registered workflow-builder's `audit workflow --require-baseline`.
The runner always cleans its owned temporary root and recorded child processes,
including hidden files, native workspaces and compiled scratch output. Success,
test failures, Python exceptions, SIGINT and SIGTERM share the cleanup path.
Unconfirmed shutdown retains diagnostics and fails cleanup; unrelated processes,
symlink targets and shared Lean/mathlib caches are preserved. SIGKILL cannot run
an exit handler, so its marked root and process ledger remain for diagnosis.
Direct `python3 -B -m unittest discover -s tests -v` remains supported, without
the enclosing cleanup guarantee. Select individual modules with, for example,
`python3 -B tests/run_tests.py discover -s tests -p test_basis.py -v`.
Native tests require the compatible Codex executable; kernel tests require the
configured pinned Lean/Mathlib environment. A skipped native test is not a
native integration pass. The suite blocks accidental live model calls and real
owner-task notifications through harness_support.py.

For a maintenance change, run the affected modules and direct consumers first;
full discovery is a separate broad check. Select an actual installed pair with
`YUI_LEAN_ROOT` and `YUI_MATHLIB_ROOT` for native tests. Pure controller cases
should not need a Lean process; historical-version fixtures keep their explicit
historical selection.

## Personal theorem catalog removal

The removed feature was the root `library/` directory, its manual index and
cached-probe shortcut. Native Mathlib lookup, stage-owned source receipts and
explicit external Lean libraries are retained. The acceptance boundaries are:

| Requirement | Independent witness |
| --- | --- |
| New jobs ignore obsolete catalog configuration and contain no catalog | `test_job_entry.JobEntryTests.test_new_job_has_no_personal_catalog_state_or_external_discovery` |
| A standalone installation works without catalog data | `test_job_entry.JobEntryTests.test_standalone_copy_prepares_and_reports_without_repository_or_test_support` |
| Old frozen snapshots remain readable and reject changed bindings/files | `test_runtime_snapshot.RuntimeSnapshotTests` and `test_job_entry.JobEntryTests.test_old_job_catalog_is_only_an_immutable_legacy_binding` |
| Authors retain native source queries but no personal-index tool | `test_own_state.OwnStateTests.test_author_keeps_native_queries_without_a_personal_catalog_tool_or_snapshot` |
| A formerly indexed theorem is queried natively in the selected pair on every request | `test_probe_evidence.NativeProbeWithoutCatalog` (actual Lean, no model) |
| Exact source evidence, alias handling and same-stage renumbering still work | `test_artifact_validation`, `test_background`, `test_evidence_index` |
| Explicit external compiled Lean libraries remain separate | `test_lean_libraries` and the registered workflow `external-lean-libraries` suite |

Basis controls are in `test_basis.py`, `test_basis_author.py`, `test_basis_workflow.py`, `test_b2lean.py`
and `test_test_cleanup.py`. They cover legacy/default requests, all four source
classes, origin versus compatibility, source/target/port binding, exact user
decisions, one shared review/proof route, operational continuation, real native
proof/adapters, universes/typeclasses, residual assumptions, trust and tampering.
Review/source/user-choice fixtures are explicitly synthetic software controls;
passing them is not an independently audited research-proof benchmark.

The complete case/batch regressions in `test_basis_case_batch.py` run real child
controllers, loopback native clients, Lean, Audit A collection, interface freeze,
Audit B and final discharge. They cover all residual choices, early mismatch and
same-role repair, stopping with a queued sibling, late explicit basis revision,
first-pass measurement, cancellation and deadlines. `test_basis_fidelity.py`
checks submission evidence, coverage and item-level reuse. The global/local
negative review regressions are in `test_nl0_review_loop.py`.

These are software tests. Synthetic reviewer judgments and deterministic
provider replies do not certify a mathematical proof or a model's capability.
The full mathematical test cases/results are maintained separately.

## Whole-file timeout policy validation (2026-11-13)

Full discovery exercised 1,237 tests with actual Lean and deterministic native
clients. One existing composed-fragment test still expected the old 360-second
whole-file limit; its expectation was updated to 1,800 seconds and the complete
eight-test local-helper module then passed. All other full-discovery checks
passed, with no skips. Runtime source bytes were identical between discovery
and that corrected-expectation rerun. New controls cover local versus whole-file
initial limits, 30/45/60-minute escalation, code repair at the current allowance,
shorter deadlines, the sixty-minute ceiling, actual diagnostic/native handoff,
and rejection of successful-looking partial output after a timeout in assembly,
Audit B and final b2lean closure. No live model inference was used.

Submission protocol ownership and intentional draft-language boundaries are in
[interface-contracts.md](../docs/interface-contracts.md). `test_artifact_protocol.py`
checks the schema actually advertised to producers against saved/direct
submissions and downstream readers, including located rejection and correction
through the native client. A fixture that hand-builds only valid consumer data
does not establish producer/consumer contract consistency.

The 2026-11-06 interface-contract validation exercised all 1,134 tests in 111
modules, then reran the affected suites after fixes. Final reruns passed 87
tests with no skips and successful owned-resource cleanup. The exact scope,
intermediate failures and replay evidence are recorded in
[the validation record](../docs/interface-contracts.md#validation-record-2026-11-06).

Strict-interface regressions use actual Lean to reject non-inferable hidden
parameters in goals and inputs, accept explicit named arguments and legitimate
inference, reject non-proposition obligations, and check unused public premises
in the complete export signature. Internal-repair controls exercise protected-field
rejection, dependency impact, retained author/reviewer
routing after a rejected revision, actual delta receipt binding, current proof
rechecking and final native/machine acceptance on a neutral fixture. All reviewer
judgments in these controls are synthetic. Empty compiler-obstruction reports
cannot close authors, and non-resumable alerts advertise no unusable resume.
Closed-role restoration checks its saved bindings. Removed proof nodes retain
their obstruction and may close only with the accepted final replacement.

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
| Native Lean limits and advice | test_translation_timeout_policy.py, test_whole_file_timeouts.py, test_native_resource_limits.py, test_native_timeout_advice.py, test_execution_queue.py | Source-bound diagnosis; local 6/12/18/24/30-minute and whole-file 30/45/60-minute limits; unchanged-allowance code repair; partial-output rejection; real native-client handoff; shorter deadlines, heartbeat limits and case isolation. |
| Local Lean helpers | test_incremental_and_storage.py, test_local_helpers.py | Compiled imports, exact transitive file-local context, targeted replacement, invalidated receipts, rollback, final composition and machine Audit B. |
| Checked local helper modules | test_local_helpers.py | Real helper chains, same-node binding, changed/missing/cyclic helper rejection, whole-file compilation and actual kernel dependency inspection. |
| Diagnosis within a retained proof session | test_live_proof_diagnosis.py, test_native_proof_diagnosis.py | All occupied slots may request review without deadlock; original native author resumes after its tool response. Only qualified substantive defects permit handoff; resource-only and uncertain reports keep the author. |
| Assembly, kernel closure and final acceptance | test_assembly.py, test_audit_b.py, test_final_acceptance.py, test_postprocessing.py | Compile actual full files, close dependencies and trust; machine B inherits only exact reviewed semantics. B-final cannot cover invalid proof/closure. |
| Exception decisions and final cleanup | test_translation_reset.py, test_workflow_handoffs.py, test_cleanup_tests.py | User-selected drift/recheck/reset/delivery is explicit; preserve original-goal status, exact ownership and scientific evidence. |
| Whole-case deadline across real stages | test_controller_deadlines.py, test_controller_linked_budgets.py, test_controller_deadline_edges.py | Actual native interruption, global A, checked Lean work, two active proof workers plus a queued worker, real case pause/cancel, initialization/retry/native-check deadlines and external-cancel races preserve evidence without fresh work or worker-pause deadlocks. |
| Historical execution health | test_controller_linked_budgets.py, test_controller_deadline_edges.py, test_translation_reset.py | A recovered provider fault remains attributable across healthy retained-role revisions and explicit translation reset; changed/missing evidence cannot establish healthy budget exhaustion. |
| Real process families and operator cleanup | test_controller_cleanup.py, test_cleanup_tests.py | An exited leader cannot hide a live child; TERM-resistant children require follow-up. Reused identities, foreign groups, query failures and unconfirmed orphan groups cannot authorize signals or workspace deletion. |
| B-final through actual case child and batch | test_controller_delivery.py, test_workflow_handoffs.py | Actual Lean fixture, qualified partial/full synthetic review, real incident-bound operator decision, case summary and batch all preserve incomplete coverage and original-goal failure. Recheck, deadline during user wait and changed findings have explicit controls. |
| Qualified first-pass blockers | test_controller_classification.py | Actual interface/case callers classify substantive nonpass and whole-case expiry as workflow blockers while preserving real execution faults and external timeout distinctions. |

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

## Automatic concurrency from phase nodes

An omitted worker count and explicit `auto` now use the current R-node count for
local Audit A review/repair and the frozen T-node count for local Lean proofs.
The controls below check actual overlap, not only a recorded configuration.

| Boundary | Controls | Required behavior |
| --- | --- | --- |
| Public invocation | test_job_entry.py | Omitted/auto workers prepare every applicable track and dispatch a frozen auto job without confirmation; invalid limits fail before output; explicit N and model-profile requirements remain valid. |
| Phase resolution and accounting | test_concurrency.py | Pending resolution has no fixed fallback; zero/one/large node counts, actual R=3/T=5 peaks, distinct role records, revision history, active-resize rejection and explicit caps. |
| Audit A queues | test_phase_concurrency.py | Three actual concurrent review slots after the global barrier; serial explicit override, single-packet scope, global nonpass and an empty queue with no executor. |
| Native Audit A and fixture isolation | test_native_review_pipeline.py, test_offline_guard.py | Three real native client requests overlap against one loopback fixture; global test replacements are restored before live-call/notification guard checks. |
| Normal review/repair controller | test_nl0_review_loop.py | Three simultaneous reviewer/repair-author pairs share the phase limit; nested packet dispatch cannot reduce it to one; global removal recomputes R from two to one. |
| Lean queues | test_phase_concurrency.py | Five real proof slots, including a shared lemma and representation bridge, followed by actual Lean assembly and fresh verification; direct scheduler defaults and explicit serial override. |
| Frozen workflow | test_source_preparation.py | Freeze resolves from the actual T plan, seals that configuration and still rejects later mutation. |

The existing phase-exclusion, diagnostic slot lending, shared-job deduplication,
cache/native rechecks, cancellation and deadline controls remain in full discovery.
Model replies and reviewer judgments are synthetic; no live model or production
owner notification is used. Run the focused controls with
`PYTHONPATH=tests python3 -B -m unittest -v test_concurrency test_job_entry test_parallel_audit test_nl0_review_loop test_phase_concurrency`,
then run the complete discovery command at the top of this file.

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

## Strict declarations and reviewed internal revisions (2026-10-31)

Canonical main passed all 898 tests in 734.289 seconds after this repair. This
includes six actual Lean signature controls, seven retained-role controls,
reviewed internal revision/assembly/native acceptance, and actual native-carrier
fault injection with a real 60-second retry wait. Reviewer verdicts and provider
replies in software controls remain synthetic; no remote model was called.
The legacy smoke-runner negative control deliberately prints graph-check FAILED;
its asserted failure is distinct from the successful unittest suite.

## Retained proof work and resource repair

The new controls exercise the real native Codex process against a loopback
fixture: a failed Lean check, obstruction request, separate diagnostic task,
returned tool feedback and successful submission from the original author
thread. The diagnostic judgments are synthetic and do not certify mathematics.
Concurrent all-slot requests, parent cancellation, repeated evidence, source
allegation requirements and notification deduplication have separate controls.

Actual Lean tests compose two checked helpers, inspect their bodies in final
kernel dependencies, reject altered context/receipts and retain modular drafts
for an authorized continuation. Resource controls read the real configured
Lean option and force a short wall timeout. The existing fault-injection suite
continues to cover mid-response disconnects, retries and retained errors.

That repair checkpoint passed **921 tests** in 786.436 seconds, with no skipped
tests. Two record-aliasing regressions were first reproduced as failures and
then passed after the fixes. The complete suite was rerun on the final fixed
tree without intervening source edits. Skill validation, environment checks
and whitespace validation passed separately. The current validation record also
retains this historical checkpoint. See
[controller-repair-validation.json](controller-repair-validation.json).

## Shared controller hardening (2026-11-01)

The linked delivery control starts four real Python case children under the
actual batch controller. Each uses a real compiled Lean fixture and the actual
B-final collector, operator decision and case aggregation. It covers incomplete
review, complete nonpass, expiry while awaiting the user, and explicit recheck
followed by delivery. Upstream proof/reviewer artifacts and semantic judgments
are prepared synthetic fixtures; this is not a fresh full mathematical run.
No complete review receipt is fabricated for partial delivery, and the batch
does not count delivery of a different result as original-goal acceptance.

The deadline controls use genuine native clients against deterministic loopback
services, including global Audit A, two concurrent local Audit A workers,
a checked Lean proof draft and concurrent proof workers. A separate actual case-controller path exercises the retained
pause and explicit cancellation. Cold and queued stages, initialization,
provider retry, interrupted Lean checks, failed interruption, evidence mutation,
role reuse, reset and cancellation races have dedicated negative controls.
These compose longer production paths while retaining explicit fixture
boundaries; they do not claim that every possible interleaving was enumerated.

The same process-family ownership checks govern automatic and operator cleanup.
Tests deliberately retain unknown orphan groups until their test-owned teardown
can safely remove them. No existing tests were deleted for this repair.
Final discovery counts, timing, runtime bindings and the independent benchmark
preparation checks are recorded in
[controller-repair-validation.json](controller-repair-validation.json).

Final fixed-tree discovery passed **958 tests** in **909.713 seconds**, with
zero skipped tests. Runtime and test-source fingerprints were unchanged before
and after the full run. This adds 37 regressions to the 921-test checkpoint and
retains all existing tests. A final OS process/cwd inspection found no live case
or delivery controllers and no native clients in Yui stage workspaces.
The independent benchmark's 14 startup tests also passed; its installed-skill
preflight remained metadata-only, with no model or proof job started.

## Proof-round handoff validation (2026-11-14)

The task-only Git export passed 1,262 parent tests with no failures or
skips and confirmed owned-resource cleanup. The 25 new parent controls cover
all four graph statuses, real selector/reader/preparation handoffs, retained
local-body reuse and basis revision, malformed or stale selection evidence,
and actual Lean whole-file failure followed by checked connection repair and
final acceptance. The original failed report remains unchanged. A missing body
or successful-looking timed-out native record still cannot pass acceptance.

Builder audit registers 19 independent cases against the same portable
state/reader operation used by production, with distinct default and selected
origins. The cases reject deliberate old-whitelist, partial-admission and
ignored-digest mutations. All 89 executable lines were observed during a
standard-library line trace; this does not establish exhaustive branch or
semantic coverage. All 15 saved pre-change offline protocol scenarios replayed
successfully, and the public routing plan stayed unchanged. These traces and
review judgments are synthetic software controls; actual pinned Lean is used,
without live model inference or a research-theorem benchmark rerun.


## Per-run environment and private worker settings (2026-11-14)

The new stable environment was installed alongside existing toolchains: Lean
4.35.0 and Mathlib v4.35.0 (56a005855ea17e0b0958f73ec801ae140b0a1679).
Before running changed-code regressions, an actual isolated import/proof verified
selection, a frozen job, nested/thread and subprocess propagation, incompatible
pairs, ambiguity and a Lean-free NL0 context. Existing pinned projects were not
upgraded. Historical controls still explicitly select their original 4.32.2 pair.

The focused suite passed 110 tests, including actual 4.35.0 conditional and
unconditional public-entry delivery, independent readback after owned cleanup,
and requested Max/xhigh worker profiles. Provider replies and semantic review
judgments are loopback fixtures, not new live-model mathematical acceptance.

All 1,276 discovered parent tests then ran exactly once in three owned-cleanup
processes, with unchanged source during the run. One existing standalone prompt
preparation test failed because explicit environment paths unnecessarily invoked
module discovery. After restoring those defaults, its complete 14-test component
passed. All three full-suite processes and the component reported CLEANED.
No active patch was excluded from the full run.

Builder retains its 15 business cases, 28 edges, three entries and seven exits.
The new eight-case portable environment suite rejects ambiguous selection,
version mismatches and incomplete native compatibility records; deliberate
arbitrary-selection and timeout-acceptance mutations were rejected. Private-role
and profile mutations were also rejected. All eight Builder audit gates and
15 saved offline protocol replays passed; replay does not repeat theorem work.


## Native cleanup, recovery delivery and imported Lean (2026-11-14)

Owned native scratch now survives unconfirmed group shutdown, including a child
launched before OS identity capture fails. The sibling checks cover IR, helpers,
interfaces, Audit B assembly and shared modules. Process-table adapters share
three fresh attempts for actual query timeouts; malformed/exhausted snapshots
remain uncertainty and cannot authorize signals or source removal.

Final-only basis recovery uses the ordinary export and delivery verifier before
completion. Native proof acceptance survives packaging-only retry/cancellation.
Historical jobs retain actual Audit A evidence and explicitly label an absent
pre-local global freeze. Successful recovery delivery remains readable after
owned cleanup. The software controls use real Lean and synthetic review records.

New internal V4 jobs freeze their external-library scope; V2/V3 readers remain.
Public Job@1 and Delivery@1 still carry the same path/hash and inventory contracts.
Explicit source/compiler manifests include module-system companion artifacts.
Library identities bind native checks, helper/shared caches, recovery and public
source exports without treating availability as semantic approval.

The imported-code tool checks original source in the current pair first, checks
a declared original environment and import context only after failure, and
requires a completed current recheck of any port. Source boundaries, native
timeout/cancellation, failed ports, cache mutation and pre-freeze publication
have independent controls. The actual native-client public entry also uses a
checked imported module through private proof work, Audit B, final closure and
delivery on 4.35.0, followed by cleanup and a fresh public-source Lake build.
Provider responses and semantic judgments are local fixtures, not a new live
model run or a rerun of the research theorem.

All eight deliberately incorrect process/library/import rules were rejected
after tightening a shadowing example that previously failed for another reason.
The first complete regression found a minimal scientific-environment caller
incorrectly requiring a job root, plus a native routing fixture exhausting its
30-second allowance under concurrency. The exporter again accepts that caller
and clears unrelated inherited import roots. Routing fixtures now allow 120
seconds without changing production limits or timeout/cancellation rejection.
All 18 affected-component checks passed before the complete rerun.

Final frozen-tree discovery passed **1,326 tests** in **1,890.075 seconds**, with
zero failures or skips. Each test was assigned once to one of three independent
owned-cleanup processes; all three reported CLEANED. A fresh file enumeration
and source fingerprints matched the complete tested checkout. No active patch
was excluded. A 5.5 MB imported document also passed actual native checking and
exact range selection; its padding tests input-size handling, not theorem-scale
elaboration performance. The larger assembly/inspection optimizations remain
separate work.

The final registered Builder audit passed all eight gates, retained all 15
independent business cases and replayed all 15 saved protocol histories. Its
accepted checkpoint is
`d65963a96ee414582dfb7393e4b02012f9f143b7638565d23f28dc8c552ad45e`.
The public definition remains unchanged. Protocol replay checks compatibility
without repeating external proof actions.

## Cross-version strategy references (2026-11-14)

The scoped requirement and behavioral witnesses are recorded in
[the reference policy](../nl02lean/references/strategy-reference.md). All 22
cards are readable at any current version and before Lean selection. Catalogs
and complete cards disclose paired historical Lean/Mathlib context and require
actual checking in the selected task environment; advice grants no proof status.
Historical contexts are not relabeled as completed native verification.

Independent cases first reproduced the old version filtering and missing
disclosure. After correcting an unknown-ID error-reply mismatch, all **35
affected host tests passed in 5.387 seconds**, with CLEANED owned-resource
cleanup. The eight new portable contract/provenance cases also passed. Three
deliberately weakened provenance/authority rules were rejected by those cases.

The actual selected-environment public-entry control passed both conditional
and unconditional paths in **261.076 seconds**. It explicitly reads old-context
references through native clients while retaining the selected Lean/Mathlib
4.35.0 identity through compilation, Audit B and delivery. Unconditional delivery
also uses an external library and a checked imported module, followed by cleanup
and a fresh public-source build. Provider replies and semantic judgments remain
local software fixtures; Lean compilation is real.

This native run explicitly supplied `YUI_TEST_ALTERNATE_ENVIRONMENT` with the
4.35.0 descriptor. Without that selection, the existing public-entry control
uses its default pair and does not establish native coverage of another version.

The complete tested file set and hashes were unchanged during these checks.
This iteration used scoped bank/direct-consumer checks, not complete parent
test discovery. An extra earlier-repair run was stopped at the user's request
and cleaned; it is not reported as a passing suite. The timing observer is
task-local and does not alter production test behavior. Cross-version theorem
metadata cache handling and generic test-environment portability remain outside
this bank change; item 5 is not established as fully complete by these results.

The registered Builder audit passed all eight gates and 15 retained offline
protocol replays in 4.575 seconds, recording checkpoint
`ea1482eaec9cb5ffdd3b727254679d8c7084f92312a04c0c5a24a21f34360a09`.
The three public entries, 28 edges and seven exits retain their existing routes.
