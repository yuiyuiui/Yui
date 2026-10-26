# Single-case execution and file-based control

This reference is for the run operator and Python controller. A proof worker
uses its frozen packet, not execution/control files or sibling proofs. Recording
and cancellation make no model requests and add no mathematical input.

Use the [canonical worker names](../../references/terminology.md#canonical-worker-names):
preprocessing worker, formalization workers (N slots), and postprocessing worker.
These group responsibilities across the translation stage. Each may use several
separate threads or program actions; a queue slot is not a persistent model
conversation. The upstream NL0 worker covers NL0 authoring and Audit A.

## Scope and queue

Keep concurrent cases separate from `max_concurrency=auto|N` inside one case.
The batch starts explicitly requested independent Python case owners, each with its
own serial preparation/review budget, proof Budget, output and mutable state. Three cases with N=2
can overlap six proof workers. Python coordinators consume no model slot.
Unknown CLI limits use the disclosed fallback two, not a claimed maximum.
Share immutable rules/toolchains, not cross-case prompts, drafts or proof stores.
Within each case, NL0 authoring, Audit A (including successive fresh packet
contexts), interface work and Audit B are serial. They never borrow the proof
worker limit or overlap that case's proof work. All roles share one usage ledger.

1. Retain source/Audit A and interface/plan freeze checks. All types must
   elaborate before model dispatch. Changes need a new accepted revision/run.
2. Materialize jobs in deterministic topological order. One node is one job;
   exact compatible shared-job groups have one producer and recorded consumers.
   Record IDs, direct inputs, hashes, attempts and result locations.
3. The existing executor queue supplies at most N slots. A free slot immediately
   takes another pending job. Distinguish slot ID from model session/attempt ID.
4. Every node attempt creates a fresh model context/workspace, even when its
   slot is reused. Supply only its target, direct inputs, definitions/views,
   NL argument and allowed tools. Conditional consumers may run before producer
   bodies finish; assembly must later discharge the actual dependencies.
5. Recheck returned proofs with Lean. Existing store locks serialize admission.
   Do not overwrite accepted results with late attempts. Preserve rejected code.
6. Ordinary unfinished work permits other queued conditional jobs to finish,
   but leaves the root incomplete. Continue local implementation work without a
   fixed time/token quota; do not silently restart failed experiments or escalate models. Source/interface changes return to
   their gate; a tactic failure does not automatically require rewriting NL0.
7. Assemble actual bodies, discharge every internal input, run fresh Lean and
   complete existing Audit B. Execution records never grant mathematical PASS.

A batch is finite: when all submitted jobs end and pending is empty, report
and exit, including on mathematical failures. Reject duplicate active case IDs
within a batch and existing output ownership. Do not wait indefinitely for all
mathematics to pass. No adaptive priority or expensive scheduling model is used.

Omitted or null `time_budget_seconds` means unlimited execution. Configuration
also leaves stage/native time limits and the total token budget null. The
runtime does not cap model-call count or stop a healthy task because tool-result
idle time exceeded a threshold. Native Lean runs with unlimited heartbeats and
without an artificial per-process heap quota. Explicit cancellation, completed
or rejected submissions, and actual execution failures still terminate work.

Only an explicit user request may enable a positive case deadline for a separate
bounded experiment. It starts with the case process and covers preparation,
model-slot waiting, proofs, assembly and Audit B without resetting at each
stage. Preserve outputs on expiry and distinguish it from external cancellation.
Transport handshakes, dead sockets, cleanup/reaping waits, and polling intervals
are operational controls, not allowances for mathematical work.

## One execution record

Read `<problem-directory>/rigorous-proof/<run-id>/execution-status.json` for
normal installed runs. Each translation attempt has a `workflow/` child under
`nl0-to-lean/<attempt>/` for its frozen artifacts.
Standalone `workflow.py run` records at its workflow root; `run_graph.py` records
at its own output. One thread-safe recorder writes pretty UTF-8 JSON atomically.
Volatile state is outside frozen inputs. Existing transcripts remain evidence;
native check results are under `native-checks/`.

Fields include case/run IDs and bindings; controller identity/phase; model and
concurrency; counts; task slot/attempt IDs, direct inputs, timings and activity;
actual latest Lean checks and log paths; owned processes; usage; cancellation;
and result/health qualifications. `LOCAL_CHECKED` is not Audit B. `FINISHED` for
a text/review stage is only stage completion. Waiting for a model slot differs
from actual `MODEL_RUNNING` or `LEAN_CHECKING` activity.
`concurrency.roles` separates preparation/review and proof peaks; `proof_counts`
counts only actual proof tasks. A total model-stage peak is not proof utilization.

- Events update memory; ordinary writes coalesce to at most once per second,
  with an intended healthy-host latency of about a second. Continuous events
  cannot postpone that flush indefinitely.
- A five-second heartbeat indicates controller liveness. Stop requests,
  finalization and cleanup confirmation force immediate writes.
- Each Lean check has an ID, code hash and log. Its active `CHECKING` record is
  separate from the previous completed result. Update when the compiler returns.
- Usage changes only on valid provider reports, deduplicated by response ID.
  In-flight/unreported use is unknown; exact per-token live counting is not
  promised. `usage_last_observed_at_utc` differs from heartbeat/file timestamps.
  Cached/reasoning are subsets, not extra tokens. Missing usage is never zero.
- Do not scan full transcripts on every refresh. Final stage ledgers reconcile
  counters after response logging drains; incomplete reports stay PARTIAL/UNKNOWN.

A file is a snapshot, not proof its writer lives. `workflow.py status` also
checks process identity. Missing owner/stale heartbeat means unknown cleanup.
`controller.state=FINALIZED` means recording ended, not that the host Python
process vanished. Child `EXITED` requires actual process reaping.

## Stop and retained results

```sh
python3 translation/scripts/workflow.py status /absolute/translation-output
python3 translation/scripts/workflow.py cancel /absolute/translation-output
python3 translation/scripts/workflow.py cancel /absolute/translation-output --task T003
```

Cancel writes an idempotent scoped request under `control/`, without editing
mathematical inputs. For one or several complete cases use
`python3 scripts/yui.py cancel /absolute/run-a /absolute/run-b`.

Stop affected pending claims; cancel waiting slot acquisitions without starting
a model. Interrupt the exact active model turn, wait boundedly for its event,
stop/reap registered CLI/Lean processes and retain evidence. SIGINT/SIGTERM use
the same cleanup. Match PID and process-start identity before escalation; never
use broad pkill. Separate external cancellation from model budget exhaustion,
execution faults and mathematical gaps. Unconfirmed cleanup remains UNKNOWN.

**The desktop main-chat Stop button is not wired to these independent CLI
sessions.** Supported control is the explicit file/CLI path and handled process
signals, not unverified UI propagation. Hard kill may prevent cleanup: inspect
stale ownership/residuals rather than assuming every child stopped.

Preserve attempts and reports. Explicit new runs may use the existing compatible
checked-proof store, re-elaborated by Lean with acquisition cost and warm reuse
disclosed. General node resume, model-session resurrection and automatic NL0/B
recovery are not implemented. An active/uncertain owner blocks output reuse.
