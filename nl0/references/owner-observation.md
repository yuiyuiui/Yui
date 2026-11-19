# Monitoring a detached run from its owning chat

This protocol applies only to the invoking owner. Proof, author, preparation
and review stages continue their assigned work in their isolated contexts.
Ending an owner turn does not stop those processes, pause a goal or establish
mathematical acceptance.

## Dispatch and verify ownership

1. Collect the target/configuration and dispatch with `--detach`. When an entry
   wraps this command, follow its procedure for preparation and launch.
2. Verify the run paths, PID, start time and process group. Retain observation
   and cancellation commands. Report the initial phase separately from any
   mathematical outcome.
3. End the foreground turn after the initial report. For `CONTROLLER_REPORTS`,
   the controller submits each snapshot to the bound owner through the local
   Codex queue and requests a wakeup. The report is already in the local log
   before the request goes to Codex. An accepted queue receipt records local
   submission. The owner can interpret the report when its model is reachable.

The controller writes `logs/owner-progress.jsonl` under each run at the interval
in its frozen project settings (ten minutes by default), even with unchanged
progress. Detached runs with no recorded chat owner keep the same local log
under `LOCAL_LOG_ONLY`.

## Read a report or observe on demand

Summarize the pushed snapshot in the user's requested language, then end the
foreground turn. Include its phase, plan, local passes and ten-minute change,
current activities, most recent target check/model event and helper result, and
the longest blocker. State any observation gap.

Use the handoff's `yui.py observe RUN...` command. It reads owned status/result
metadata and one OS process table, and returns only concise stages, counts,
recorded outcomes, usage and PID/start/PGID checks. It starts no model, Lean
compiler, probe, repair or workflow and changes no scientific files.

Compare the snapshot with the saved monitor state. Inspect bounded new fault
metadata only as needed. Do not read unfinished arguments to steer construction,
send hints, import other proof skills, resample mathematical nonpasses or restart
a live/waiting case. Follow the existing guarded recovery boundary only with
actual authorization; update the current run map after any authorized change.

The reporting interval and the five-second controller liveness heartbeat cover
different observations. Read the latest model event separately from the
controller heartbeat when assessing progress.

`PAUSED_ERROR` is nonterminal. The local Python error controller separately
queues immediate fixed-text owner alerts and preserves its context/workspace.
Read `paused_errors` and its outbox status; do not restart a paused run, declare
it finished, or close its monitor. Operator controls and the only allowed
cleanup boundaries are in [error lifecycle](error-lifecycle.md).

At each case termination, read its actual result and linked gate reports. A
recorded PASS is not new verification; validate existing bound artifacts using
the Yui validators without starting another model or Lean run. Keep partial or
unknown usage and every execution qualification visible.

The detached controller sends a terminal update after writing the batch record.
Confirm its exit as well as the case exits before final validation. Once every
tracked case is terminal, the owned process groups have exited and
authorized recovery is complete, validate and save the final reports and run
the entry's authorized cleanup. Mark the owner monitor complete and end the
turn.
