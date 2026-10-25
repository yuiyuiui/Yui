# Test reflections and regression reminders

Updated: 2026-10-25. Repair baseline: `997689c`.

This is a short **controller/developer record**, not a model prompt, a proof
source, or an additional audit. Keep it outside all measured author, worker and
reviewer input manifests, including the direct-model arm. Read it before a new
campaign and compare it with the actual evidence afterwards.

The old run artifacts were deliberately removed during the reset. The lessons
below summarize observed development problems; they do not replace a new run's
logs. Software checks cover repaired contracts, but a successful fresh
mathematical workflow and any speedup remain to be demonstrated. Detailed
implementation/validation history is in [MAINTENANCE.md](support/MAINTENANCE.md).

## Mistakes to avoid repeating

| ID | What went wrong | What to check next time |
| --- | --- | --- |
| R01 | The proof-worker budget was also used in preparation/Audit A, so reported parallel activity was not Lean proof-node parallelism. | Each case has its own serial NL0/preparation/review lane and separate `auto\|N` proof budget. Check actual activity by role, not just the aggregate peak. Fresh audit contexts are allowed; parallel Audit A workers are not. |
| R02 | Source acceptance, interface elaboration, semantic review and final proof completion were conflated in progress reports. A downstream rejection could make an accepted source appear to have failed again. | Report NL0, A, interface, proof assembly and B separately. Checked types or library probes are not completed proofs. Preserve valid upstream acceptance when a later stage fails. |
| R03 | Mechanical contract errors, repeated restarts and loss of accumulated edits contributed to many candidate versions and wasted work. Version counts were then hard to interpret. | Bind routine metadata mechanically, aggregate format feedback, and continue from the latest own draft. Repair the affected part. Explain why a new attempt is needed; do not automatically rewrite the entire NL0 or weaken the target to obtain a pass. |
| R04 | Interface reviews included disputed claims about missing source assumptions and treated some planned Lean bridges as if their proofs had to be finished already. | A blocking mismatch must quote resolving source and formal locations and state the actual difference. Planned obligations still need real proofs later. A disputed verdict needs evidence-based resolution, not repeated judging until PASS; the permitted targeted adjudication is disclosed and bounded. Judge accuracy itself still needs real-model verification. |
| R05 | Incomplete review coverage, unavailable source evidence and actual mathematical failure were not always handled distinctly; review could stop before completing unrelated checks. | Save per-item coverage and verdicts. Distinguish unread/unassessed, UNVERIFIED and a located FAIL. A template or saved partial review cannot grant acceptance. A genuine blocker may stop with explicit incomplete coverage; do not erase it or invent remaining judgments. |
| R06 | Unchanged work was unnecessarily repeated, and comparison of an original file's path with its staged copy's path rejected legitimate copies. | Verify exact bytes/hashes and the applicable context. Reuse only qualified unchanged acceptance; invalidate affected evidence after a semantic change. Same-case repair or inherited evidence must be disclosed and is not an independent cold repetition. |
| R07 | CLI workers were hard to observe, main-chat Stop was not wired to them, and generated directories accumulated. | Inspect case execution records and exact process ownership. Use scoped cancellation/cleanup, confirm exit, then remove outputs. Do not infer termination from the chat UI. Keep each exercise directory input-only and put generated work under the documented disposable roots. |
| R08 | Deadline/early-stop/fault attribution and token coverage could be confused, obscuring both model failures and measurements. | Healthy exhaustion without an accepted result is MODEL_BUDGET_EXHAUSTED for that attempt. An external early stop is not exhaustion. Report transport/tool/controller faults separately. Count all stages/agents, deduplicate terminal usage, and retain unknown/partial accounting instead of reporting zero or a complete total. |
| R09 | In the 2026-10-24 rerun, an actual PDE packet review treated analysis results listed in the author's `logic.calculations` as permitted premises and passed dependency accounting without E/M roots. Other global defects still blocked whole-proof acceptance. | The author's calculation description cannot extend the fixed foundation. Check theorems used in the actual argument even when named in that field. Add a policy-only unlisted-theorem negative control before claiming coverage of this failure mode; the five simpler controls did not cover it. This issue is observed, not yet established as fixed. |

Useful existing software controls: [workflow policy](support/test_workflow_policy.py),
[review contracts](support/test_review_controllers.py),
[independent case scheduling](support/test_queue_controller.py),
[cleanup](support/test_cleanup_tests.py), and
[qualified audit reuse](support/test_audit_reuse.py).
Rerun relevant controls when their implementation changes; this document adds
no new automatic test suite or model calls.

## Questions still requiring actual testing

- **Semantic reliability:** a better review contract does not prove that an
  LLM's mathematical judgment is right. Check located false positives and
  missed defects; retain unresolved disagreements honestly.
- **Useful parallelism:** five available workers do not imply five independent
  ready jobs. A large local obligation or dependency chain can dominate. Record
  the ready queue, actual proof concurrency and bottleneck before claiming a
  scheduler failure or a speedup.
- **Formalization difficulty:** representation choices, missing bridges and
  mathlib interface search remain real costs. Measure where time is spent;
  do not assume the harness removes them, and do not turn a formalization stall
  or a long run into a claim that the original mathematics is wrong.

## Lightweight use in the next run

Before starting, confirm the fixed `problem.md` hashes, model/reasoning/speed,
requested/resolved concurrency, clean declared inputs/tools, and output root.
The controller must also verify that the actual transmitted inputs exclude
history, this reflection and other cases; model self-report alone is insufficient.
Reuse neither deleted historical controls nor missing audit receipts.

After the run, add a short paragraph to its ordinary report: which R-items
recurred, which relevant checks were observed to hold, and what was not checked.
Point to actual status/log locations. Preserve a concise lesson here **before**
clearing disposable results. New problems need only this one-line format:

> Date / commit / run — existing R-ID or NEW — observation and evidence —
> confirmed cause (or suspected cause) — action and next regression check.

Append or refine a lesson only when there is new evidence. Keep IDs stable,
avoid duplicate entries, and never mark an issue resolved merely because a
rule was written or software controls passed. No extra dashboard, schema or
mandatory model review is introduced.

2026-10-24 / baseline `997689c` plus recorded stage-one adapter changes /
`fresh-nl0-a-20261024-033230`: R03 recurred in both author metadata edits and
global-review serialization. The latter accumulated 32 rejected output calls
per affected case before an explicit operator stop after saved FAIL items.
Those stops are external early stops, not deadline exhaustion. Subsequent
same-case local repairs retain the old attempts/costs and use explicit
stage-specific output examples. They are not independent cold repetitions.
R09 evidence is retained in that run's `wave-policy-finding.json`; source
registration and fresh review are still being tested. These observations do
not establish an error in the original textbook theorems.

The same rerun also provides these narrower regression observations:

- **R03:** a local Lie-proof expansion was followed by indexed JSON edits that
  placed the `F_p` definition in the `M_R` record and the tensor-module text in
  the coefficient-set record. Actual audit rejected both. Existing JSON `test`
  operations on record IDs were then explicitly requested before indexed edits.
  This procedural reminder is not an implemented cure for fragile editing.
  Repeated manual entry of already-known library names/modules also recurred;
  an owner-written experimental adapter later re-queried unchanged selectors
  natively with zero model calls (about 28--31 seconds for 11--12 selectors).
  Its actual cost is separate from model-stage wall time. This is not yet a
  promoted core feature or evidence that semantic source review can be skipped.
- **R04/R09:** an initially passed Lie receipt missed a local `n` escaping its
  declared scope and was explicitly reopened. A repair later introduced a wrong
  matrix-unit coefficient; actual packet replay gave a counterexample, while
  the fixed `problem.md` formula remained correct. Model PASS/FAIL judgments
  must therefore be interpreted against the exact text and evidence.
- **R04/R06:** the geometry proof received opposing packet judgments on its
  finite grid-count expansion after only source-signature metadata changed.
  `geometry-review-disagreement.json` records the paired judgments and an exact
  mathematical-content equality check. Neither verdict is erased. Separately,
  a catalog probe reused under M005 retained an original M001 display marker;
  an auditor marked its evidence UNVERIFIED. An uncached native requery repaired
  that evidence without changing the proof. Do not confuse either issue with a
  counterexample to the original dimension theorem.
- **R01/R08:** observed case preparation/review peaks remained one model stage
  per case and proof-worker counts remained zero. The original geometry author
  recorded a connection reset at request 45 and incomplete usage; its source
  was recovered explicitly in a new session. Owner startup/preparation script
  mistakes and explicit early cancellations are retained separately. None is
  classified as healthy model-budget exhaustion.

- **R03/R04:** a geometry repair changed the proof paragraph but left already
  reported symbol/declaration mismatches untouched. A later packet caught the
  same defect again. Guarding the parent inference ID alone is insufficient:
  local records also need symbol-and-scope guards and actual edited-record
  readback. A successful structural submission does not establish that the
  requested semantic repair was made.
- **R08:** later stages recorded TLS EOF, HTTP 502 and a remotely closed
  connection. Valid saved artifacts were preserved, but their author/reviewer
  measurements remained faulted or partial. Read-only reachability checks
  subsequently succeeded through the unchanged proxy; the transport root
  cause remains UNVERIFIED. Artifact recovery is not a healthy cold rerun.
- **R03/R06:** a PDE author found and proposed an integral-transport source,
  but wrong index guards rejected the edits. Its eventual tests-only submission
  was structurally accepted and triggered another review of the unchanged
  known-defective proof. Next checks: generate record pointers from the actual
  source, preserve own attempted edits, and reject an exact-no-op repair before
  launching review. An experimental guard passed a no-model check; it has not
  yet been verified in a real model run or promoted to the core harness.

The same campaign was subsequently transport-blocked. Eight paired default-TLS
and TLS-1.2 HEAD checks had six TLS EOF failures; neither protocol choice was a
demonstrated remedy. New model calls were stopped, and ownership-based process
inspection found no residual owned test processes. The run report preserves
one accepted source and two unfinished cases, all failures and partial usage;
it does not claim a successful three-case cold rerun.

On the attempted resumption, four anonymous HEAD checks passed, but actual
authenticated model requests again produced nine PDE and two geometry relay
faults. Both stages were stopped before submitting any new edited artifact;
ownership inspection again found no residual test processes. Anonymous endpoint
reachability is insufficient to declare the model transport restored. Await an
explicit adjustment-complete notice before launching another recovery, and keep
this attempt's faults and partial costs. The exact-no-op repair guard remains
untested by real model submission.

### 2026-10-24: cold first-pass rounds 7--9

- A written rule is insufficient if the author does not actually receive the
  same frozen acceptance text as the auditor. Audit A is now the single
  authority, injected and hash-bound for both roles; author instructions are
  its construction guide. Completed self-check notes are not readiness when
  the author reports an unresolved obligation.
- In `cold-first-pass-r8-20261024`, repeated escaped-string and numeric-path
  edit failures consumed many author turns. Numbered own-string views,
  hash-guarded line edits and actual record-identity diagnostics were added
  before round 9. Their software checks pass; actual efficiency remains to be
  measured. Internal candidate counts must remain visible even if first A passes.
- The same round's Lie request 121 generated extensive JSON whitespace until
  the provider's output-token cap. This was not a recorded network failure.
  The old wrapper incorrectly classified the incomplete response as an
  execution fault. The new controller distinguishes output limits and observed
  serialization stalls, preserves unfinished attempts, and executes no partial
  JSON. A protective stop is not exhaustion of the full stage time budget.
- Definition guards and exact source conclusions need explicit construction
  attention. A later proof cannot silently justify a currently partial global
  object, and a conclusion on a restricted domain does not automatically
  supply its whole-domain counterpart. These conversion defects do not by
  themselves refute the supplied mathematical proof.
- Review findings need inspection too. Supplied definitions and actual local
  derivations can establish a named consequence without another theorem root;
  merely naming a theorem still supplies no proof. Matched neutral definition
  controls were added without including these exercise answers. Never resample
  an unchanged failed review until PASS or lower the proof standard for the goal.

### Later cold-round controller and construction lessons

- A conditional packet assumes its explicitly supplied N statements; the
  global review checks their producers. Requiring ancestor proof bodies in a
  local packet is a scope error. The shared Audit A section now states both
  roles explicitly; no missing N may be invented.
- Round 11 exposed rejected drafts overwriting the canonical pair, followed
  by a fatal readable-render error. Candidates remain immutable evidence, but
  only a fully validated pair is now published; a failed view must not erase
  the round's outcomes/costs. Publication and rollback have direct controls.
- Author tool feedback now names the exact expired local facts/objects and
  provides concrete own-check actions. Source discovery accepts ordinary
  query terms while retaining exact native provenance checks. These changes
  need fresh model validation; unit checks alone are not a speed claim.
- A real construction guard must precede use in the proof graph, even if its
  definition is written near the top of the file. The neutral guarded-object
  example illustrates this without a test answer. Optional independent prose
  may be omitted; every retained or target-needed claim still requires proof.
- Diagnostic first audits of two unchanged submitted round-11 sources remain
  failures, separate from their authors' transport faults. One reviewer also
  overstated a prerequisite: finite generation is preserved by linear images
  without Noetherian/PID assumptions. Exact fixed-library evidence and the
  other genuine omissions are recorded separately in the owner report.

## Cold-round R12: actual omissions and avoidable author overhead

- Preserve the first mathematical failure separately from execution health. R12 had healthy author/review transport. Two accepted author artifacts failed first A; the third author had a recorded malformed output protective stop, not a proof judgment.
- Do not mistake a feasible value for an extremum or reverse the direction of a monotone-limit definition. Original definitions should be copied exactly when already adequate; an unsupported gap allegation does not authorize changing the supplied mathematics.
- Familiar algebraic/number-theoretic existence and measurability closure claims still need declared inputs or actual local proofs under the frozen elementary profile. Do not count a displayed desired formula or a source's named premise as its proof.
- Local reference diagnostics must show exact application/local indices and actual S/input IDs. Return independent reference mistakes together rather than forcing many one-error edit cycles.
- Read-only line requests may return the remaining existing lines; line edits must keep exact ranges/hash/newline requirements. Obstacle tools should publish their actual typed fields, not require guessing a nested JSON schema from “five fields”.
- Same-author packet READ credit should depend on the exact complete displayed mathematical view and shared authority, not unrelated proof bodies. R12 recorded identical views repeatedly across candidate edits. Current whole-proof readiness notes and known-issue resolution remain mandatory; read credit is not a mathematical verdict and never transfers to independent A.
- R13 implements these bounded changes and verifies general native-source metadata. The more invasive same-author history-window proposal is deferred: first measure the smaller fixes. No old-case answer, prior audit or case-specific repair instruction is supplied to cold authors.

## R14 control-oracle localization false rejections

All 14 actual mathematical verdicts were correct and healthy. Two valid findings pointed to the exact proof step using an opaque input or choosing an unjustified witness, while the owner key allowed only the declaration/input statement. Preserve those raw records; do not misreport this as mathematical reviewer unreliability. Controlled defects now have owner-only origin/record/use-site locations derived from actual packet references. Exact verdict matching remains mandatory, and unrelated locations or broad inference/list ancestors do not qualify. Retrospective replay checks the software fix without new model calls; it is not a new cold-round success. Expected labels/locations remain absent from all reviewer inputs.

## R16--R17: standalone inputs, progress evidence and outcome separation

- A root statement saying an object is “as specified in the target” is not a closed premise. R16 Lie's actual first A found a proof-critical omitted given condition. R17 adds narrow standalone-content rejection and literal selected-GIVEN copying; copying never grants a new assumption or mathematical acceptance.
- Exact edit/schema feedback matters: missing replace_lines hashes and ambiguous same-start local declarations caused avoidable repeated wrong-field edits. R17 gives missing/unexpected fields and actual local-record paths without inferring a hash, scope or mathematical correction.
- A transport keepalive is not proof progress. R16 Wave had a genuine tool result followed by 496 seconds without a response terminal/next request. Its scoped external cancellation and unknown cause remain preserved. R17 adds a frozen 120s post-delivery uncertainty guard and distinguishes substantive activity, with no model call or hidden retry. This guards/labels the observation; it does not establish or fix its upstream cause.
- A placeholder graph lacking a derivation/source is not by itself evidence of a substantive mathematical gap. R17 Geometry stopped early on that basis; retain its report and distinguish unperformed routine completion from a genuinely obstructed implication. A clearer operational guide is planned after this frozen round.
- Do not conflate complete-artifact eligibility for mathematical review with healthy timing eligibility. The current controller rejects even a later complete author solely for a recovered transport fault. Separation is planned after R17; faults, missing usage and unqualified benchmark timing must remain visible. Partial drafts, false identity/input boundaries and isolation/controller/tool faults remain blocked.
- The R17 software batch passed 208 checks. This is software evidence, not three-case success, a speed measurement or a guarantee of mathematical correctness. R17 remains a fresh frozen experiment.

## R18 global calibration and exact inventory accounting

- Original H retention has an explicit unused-H exception to target reachability. A6 now says all retained non-H nodes lie in the target closure; original H stay present and unused H are reported. Do not invent uses or delete givens.
- A global view must expose the existing computed unused-H report as well as every actual H. R18's positive global calibration correctly stopped on the missing report; no exercise author started. The v2 overview now reports declared graph reachability without a mathematical verdict. Exact v1 projections remain verifiable as historical data.
- A matched negative verdict can include a false side allegation. R18 correctly detected an omitted original condition but also demanded a separate source for a fixed elementary additive law. Preserve this reviewer error separately and check the actual fixed calculation permission before endorsing every finding. The paired positive/global controls use the actual global prompt and contract.
- Same-author restoration reminders bind to real own-stage tool results and source receipts. They add measured input tokens, no extra model call; they do not grant current readiness, theorem permission or an independent mathematical verdict.

## R20 cold attempt and disclosed warm closeout

The original R20 first Audit A failed all three cases. Geometry and Lie later
obtained warm-repair acceptance; PDE did not. Geometry/PDE received owner
source locators, mathematical explanations and proposed patches during warm
closing. These are not independent cold-first-pass successes. This campaign
did not reach the Lean proof queue or Audit B.

- **R03 / source and scope fidelity:** Geometry added measurability conditions
  to the native `lintegral_mono` restatement; Lie omitted a tensor-basis/rank
  bridge and used local symbols before their declared scope. PDE omitted
  measure/topology and sequential-limit dependencies. These are NL0 closure
  defects, not evidence that the original exercises are false. Do not claim
  that author self-check notes guarantee mathematical completeness.
- **R04 / review evidence:** a Geometry factor-two allegation contradicted
  the exact hashed supplied source; the located dispute is retained. PDE also
  had a disputed witness demand on a universally quantified conditional.
  Preserve the actual reviews and distinguish textual contradictions from
  unresolved mathematical disagreements; never resample until PASS or alter
  a correct proof just to satisfy an unsupported allegation.
- **R05 / role ownership:** the final PDE global reviewer left source rows
  UNVERIFIED while awaiting application/sequence arguments also assigned to
  packet replay. The global prompt explicitly requests actual applications.
  Clarify ownership of provenance, local applicability and final composition
  without removing any required check. Empty definition rows/no new target
  row here are valid inheritance: target, D001 and D002 were inherited; the
  new global assignment was structure plus 28 sources. Do not report that
  omission as a new coverage bug.
- **R03 / tooling:** legitimate same-stage `bound-M...` source-index aliases
  are emitted but rejected by the own-state readback path pattern. This is an
  unresolved producer/verifier mismatch; do not waive origin checks. Final
  PDE also recorded sixteen read-only 250-line limit errors and one packet
  location correction. Pagination should eliminate avoidable read failures
  without weakening exact edit or source boundaries.
- **R03 / warm repair:** a previously identified compactness obligation was
  still absent from the final PDE delivery. Carry located unresolved issues
  across authorized repairs; a readiness assertion or unrelated change does
  not establish resolution. Cold authors must not receive this repair history.
- **R07 / termination:** the finite batch returned nonpass and exited. The
  owner also inserted a terminal-nonpass monitoring stop, which did not fulfill
  the user's requested all-case acceptance target. Keep session/process exit,
  finite-batch completion, case acceptance and required follow-up separate.
- **R08 / usage and faults:** the final PDE batch made 260 model requests with
  259 usage reports and 16,766,969 observed tokens, including cached/repeated
  inputs. Complete total is unknown. Its global request 10 had a recorded
  relay fault; R001/R002 had no recorded transport fault. Network failures
  are not proof defects. Earlier HTTP401 credential expiry is distinct from
  TLS/relay failure. Do not attribute this mixed outcome solely to capability.
- **Previously fixed:** the recorded tool-history output budget change passed
  a healthy actual readback with a 46,604-character tool output. It is not an
  outstanding unfixed truncation bug. Mathematical acceptance is separate.
- **Cleanup verified on 2026-10-24:** the read-only cleanup preview found no
  matching live processes, no owned temporary directories and no errors.
  Approximately 11 GB remained under `test/results`, including historical
  campaigns. Retained scientific output is disk evidence, not a live worker
  or model-memory leak. No purge occurred during this retrospective.

Evidence index:
`test/results/nl0-first-pass-goal-20261024-065112/MONITOR_FINAL.json`,
`r20-closeout-execution-obstacles.json`,
`r20-geometry-factor-two-review-dispute.json`,
`r20-wave-universal-sequence-owner.json`, and the original
`test/results/cold-first-pass-r20-20261024/round-result.json`.
These historical result directories are disposable. Their essential findings
are retained above; the user authorized deleting their raw outputs before the
next run. They will not remain available as live evidence after that cleanup.

## 2026-10-25: bounded repairs before the Sol test

Implemented deterministic changes: shared same-stage source-origin validation
for native and bound metadata, bounded read pagination, located verbatim
blocking findings, immutable source-review context snapshots, and explicit
case acceptance separate from finite process termination. The carrier also
closes its parent stderr handle after spawning the child.

Audit A A7 assigns source identity/full-statement checks to global review and
actual applications/local arguments to packet review. Final acceptance still
requires both. Qualified unchanged source review no longer depends on every
consumer body; changed applications still invalidate their own packets. An
explicit warm-only repair-obligation input retains located issues and baseline
identity. Cold test inputs exclude that file and all earlier work.

The new profile is gpt-6.1-sol / high / Standard, without fallback. Its results
must remain separate from Luna runs. Each fresh author receives only its own
unchanged problem-and-proof input plus frozen Yui rules/tools. The owner may
dispatch and inspect execution health, but supplies no mathematical reasoning,
source locators, patches or review feedback. The campaign freezes this policy,
model, author prompt and runtime. It runs once and reports every actual result;
there is no automatic repair or resampling until PASS.

These are software/protocol repairs. They do not establish one-pass NL0
reliability, reviewer correctness, formalization speed or a successful cold
experiment. A disputed review still needs a separately disclosed adjudication;
this campaign does not run one. Network/credential faults remain distinct
execution observations. The old first-pass goal remains unachieved and paused.

- New admission policy: an already correct routine background step may receive
  a verified per-node Audit A note instead of an author rewrite. Retain all
  mathematical checks; missing hypotheses, source guesses and substantive
  gaps still block. Disclose PASS with notes separately from zero-note passes
  and historical stricter outcomes. No acceleration is established by this change.

2026-10-25 / R23 at `db385f2` / R03/R08 — all 18 calibration sessions finished,
but the matcher rejected one correct FAIL because it located missing continuous
addition at the inference rather than the Y parameter. The three exercises
never started. The owner repeated an unchanged run despite knowing this blocker,
adding avoidable calibration cost. Explicit owner-only defect use sites now
cover that exact inference without weakening verdict/location guards. The
27-test controller suite and an offline 18-record replay passed; these are
software checks, not fresh mathematical results. Resolve known deterministic
gate failures before spending on another model round. Report NOT_STARTED cases
and incomplete requested scope prominently when a prelaunch gate ends a run.

## 2026-10-25: R24 first independent Audit A passes and rule freeze

The single frozen R24 experiment used source commit
`fc71a02774ae8780980b5e2eb1f484e4466b9eca` and exactly
`gpt-6.1-sol / high / Standard`, with no fallback. Eighteen neutral controls
matched their expected classifications before three independent case processes
started. Each case used serial author, global-review and per-node review
contexts. The owner supplied no mathematical assistance, source locators,
patches or audit feedback; no post-audit author repair or resampling ran.

| Case | First complete independent Audit A | Background notes, by R001 onward | Author plus Audit A | Observed tokens | Usage coverage |
| --- | --- | --- | --- | --- | --- |
| Geometry | PASS with notes | 85: 10, 17, 16, 21, 17, 4 | 4361.881136 s | 21,749,431 | Partial: two review transport faults |
| Lie | PASS with notes | 13: 3, 4, 1, 3, 2 | 3629.495391 s | 16,909,896 | Partial: two review transport faults |
| PDE | PASS with notes | 83: 10, 27, 18, 24, 4 | 4471.458818 s | 31,751,811 | Complete; no recorded author/review execution fault |

The owner read the actual saved judgments and revalidated all three final
receipts with the existing `nl0.validate(graph, spec, audit)` function. Every
recorded owned process identity and process group had exited; the completed
monitor automation was deleted. Scientific artifacts were preserved locally
under ignored `test/results/`. This source repository carries a summary, not
the original proof/audit evidence bundle.

This is acceptance under `verified-background-1`, including 181 positively
checked routine background notes. It is not zero-note or old strict-policy
success, held-out reliability evidence, Lean/Audit B acceptance or measured
speedup. Author self-checks included local revisions before the definitive
submission; a first independent Audit A PASS does not mean no internal edits.
Whole-experiment usage, including calibration, is partial: 74,003,059 observed
tokens across 1,475 requests, with 1,451 usage reports. Calibration also had
transport faults. Cached inputs and reasoning outputs are subsets, repeated
contexts count again, and owner monitoring is outside these totals.

The user then froze NL0 authoring and Audit A without changing their normative
contents. See [`NL0_AUDIT_A_FREEZE.json`](../rigorous-proof/NL0_AUDIT_A_FREEZE.json)
and Git tag `nl0-audit-a-2026-10-25`. Continue translation work against this
baseline. No further model experiment or Lean translation is authorized by
this freeze alone. Background notes provide source/application guidance, not
ready-made Lean proofs; their time benefit remains unmeasured.

## 2026-10-26: stage-two simplification before a new Sol run

The first Luna stage-two attempt spent its allowance in interface construction;
it did not reach proof workers or Audit B. Repeated ordinary incomplete reports,
long continuation instructions and mandatory pre-typing of the background-note
inventory added work before any proof could begin. Partial type probes did not
provide a persistent, incrementally editable complete-interface draft.

The user requested removal of that attempt's stage-two outputs and owned
processes while retaining all accepted R24 NL0/Audit A sources and evidence.
The cleanup was scoped to those four stage-two output directories. It found no
remaining matching live process. New translation contracts keep the original
H/E/M ports and carry verified notes as node-local references; they no longer
promote every note into a typed M input. Incomplete interface JSON is preserved
before validation; normal work does not require an obstacle report. A separate
interface semantic review is deferred to final Audit B, with its pending status
made explicit rather than filled with PASS values.

An actual continuous-addition control also exposed a dependency-classification
issue: implicit typeclass evidence was counted as undeclared independent
mathematics. The inspector now records actual instance-argument uses and
requires final semantic review of that support. It does not exempt an instance
used as an ordinary proof, extra hypotheses, or arbitrary library theorems.

The next run uses Sol / high / Standard, five proof slots per independent case,
and one three-hour second-stage wall budget per case. Preserve original source
acceptance and separate pre-processing, proof and Audit B results. These changes
and software controls do not by themselves demonstrate success or acceleration.

## 2026-10-26: separate postprocessing assembly from Audit B judgment

The Sol R2 stage-two run checked 23/23 geometry, 19/24 Lie and 16/16 PDE local
conditional proofs. No independent semantic Audit B review started. All five
unfinished Lie jobs ended with recorded TLS EOF/HTTP 502 faults. Geometry and
PDE original attempts also had transport faults; their separately authorized
warm continuations exposed additional engineering blockers. These results do
not establish model incapability, a mathematical error, whole-proof closure
or a speed advantage.

- Geometry's exact pinned `MeasureTheory.lintegral_indicator_const₀` existed,
  but an ASCII-only name filter rejected its subscript. The error did not name
  the source entry. Declaration components now preserve Unicode/quoted names,
  and malformed-name diagnostics identify the source ID and field. Pinned
  resolution, general-type and dependency checks remain required.
- PDE's generated source-facing export left library-only universe levels
  unresolved. The assembly generator now reads actual elaborated level use,
  infers levels retained in the exported interface, and instantiates only
  implementation-only levels at the final application. General M signatures
  and original H/E remain unchanged. A native generic-interface control guards
  against specializing user-visible type parameters to level zero.
- Short compiler excerpts hid the actual error behind large signatures. The
  postprocessing author now gets error-first feedback and a registered,
  paginated own-candidate reader. Both tool schema and dispatch registration
  are checked. Identical checked submissions reuse exact unchanged native
  evidence; no semantic review is manufactured by that reuse.
- Fragment assembly, standalone `Proof.lean`, kernel inspection and actual
  independent Audit B now have separate completion states. The inspector
  avoids unnecessary weak-head normalization and has a bounded disclosed
  heartbeat allowance; exhaustion blocks inspection without falsely calling
  the mathematical proof wrong.

One serial postprocessing author connects completed nodes and prepares the
actual audit handoff; a fresh independent reviewer remains separate. Read the
[assembly protocol](../rigorous-proof/translation/references/assembly.md).
The accepted R24 NL0/Audit A authority is preserved. Before selective removal
of active stage-two outputs, proof bundles, Lean sources, partial drafts and
actual audit/assembly errors were saved in a hash-verified small offline
archive outside this checkout. Raw carrier histories/caches are not required
to retain that curated evidence. This reset launches no new model experiment;
synthetic native/software controls are not the three exercises passing B.


## 2026-10-26: separate assembly, source fidelity and inspector failures

The R3 follow-up diagnosis was recorded before reset; its untracked detailed
report and generated proof/diagnostic files were deleted at the user's request
on 2026-10-26. The concise findings below remain. No new model test ran during
that diagnosis.

- Geometry's 23 checked jobs assembled into a root that triggered Lean's async
  universe-parameter commit error. The byte-identical source fails again;
  a diagnostic copy with async elaboration disabled compiles. Fix the root
  generator/gate rather than reauthoring all node proofs.
- PDE's eleven library-signature rejections disappear under bijective universe
  renaming. All five source input sets already match. Its 274 reported imported
  proof names mix foundational tactic machinery and genuine missing dependency
  correspondence; never report that count as 274 mathematical gaps.
- Lie's separate Yui-only review found missing bridges to the integral and
  tensor Lie-algebra objects despite a compiling operator proof. Native
  inspector heartbeat exhaustion is a different, additional execution defect.
- Ordinary runs now have no automatic time/token/call budget or post-tool idle
  cutoff. Explicit cancellation and resource ownership remain. Earlier finite
  manifests and original failed artifacts retain their historical meaning.


## 2026-10-26: endpoint correspondence and Mathlib policy revision

Audit B version 2 (`endpoint-fidelity-2`) reviews every external theorem E and
complete target P, including parameters, hypotheses and conclusion. Authors
supply a short direct/equivalent correspondence explanation; reviewers must
check it against original text, actual types and relevant definitions. A
missing literal Mathlib object or a missing redundant second representation is
not by itself evidence of a wrong translation. The earlier Lie bridge finding
remains an old-policy result, not proof that the operator encoding is
mathematically inequivalent. Its new-policy semantic verdict is still pending.

All pinned Mathlib theorems may now be used without per-M registration or
node-level library permission review. Optional intermediate M ports must still
be discharged by real Lean proofs. There is no per-M signature inventory,
calculation permission ledger or imported-proof whitelist in the new Audit B.
Unproved extra assumptions, local axioms and changed endpoint meanings remain
failures. Old measured outcomes are not relabeled.

The generated assembled root now elaborates synchronously to avoid missing
proof-only universe parameters at async commit. Signature comparisons allow
bijective universe renaming while preserving distinct levels and their
relations. Regression controls cover these changes, permitted direct library
use, wrong targets, stronger external assumptions, hidden proof fields, pending
reviews and explanation/evidence bindings. These are software/native checks;
this revision does not launch a new three-exercise model test or establish a
new mathematical Audit B pass or timing improvement.


## 2026-10-26: clean stage-two restart under endpoint-fidelity-2

The user requested deletion of previous stage-two processes, temporary resources,
Lean artifacts and audit/diagnostic drafts before another run. Exact-ownership
cleanup found no remaining live old model process or owned carrier workspace.
Stage-two outputs and their untracked diagnostic handoffs were removed. The
accepted R24 NL0/Audit A evidence and fixed problem inputs were hash-checked
before and after cleanup; those stage-one sources remain the new run's inputs.

Before reset, 296 core, 150 translation and 92 support controls passed (538
software tests), along with skill validation and whitespace checks. These are
software/native controls, not new mathematical Audit B verdicts. The next run
uses the pushed source commit and a new output directory, with no old Lean
proof, interface, verdict, repair hint or owner mathematical help supplied.
Each of the three cases has five independent proof slots and serial preparation
and review, using gpt-6.1-sol/high/Standard with no fallback and no imposed
case/stage/native/token budget. Reuse accepted Audit A by integrity checks only.
