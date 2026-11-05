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
3. Prefer a ten-minute scheduled wakeup when host rules permit it. Reuse a
   verified matching schedule or make one registration attempt with the host
   tool. Record the actual ID and current run paths before ending the owner
   turn. The generic `HOST_REGISTRATION_REQUIRED` handoff is a proposal whose
   registration must still be confirmed.
4. If scheduling is restricted, unavailable, unsuccessful or unconfirmed,
   report the reason once and continue the same run in the owning turn.
   Use an interruptible ten-minute wait, observe once and report in the
   requested language. Repeat while the run is live. This fallback records
   `OWNER_CHAT_WAIT` and uses no automation ID. Honor user interruptions.
5. Follow the entry's `OWNER_MONITOR_STATE.json` for ongoing observation.
   An unavailable scheduler selects the in-chat fallback and must not prevent
   an otherwise valid, authorized run from starting. Return concrete manual
   status/cancel commands only if neither observation mode is available.

Keep owner metadata separate from the frozen mathematical inputs, receipts and
worker usage. The scheduled proposal's defaults live in `config.json`. Entries
can request an update at every interval through their own monitor settings.

## One bounded observation per interval

Use the handoff's `yui.py observe RUN...` command. It reads owned status/result
metadata and one OS process table, and returns only concise stages, counts,
recorded outcomes, usage and PID/start/PGID checks. It starts no model, Lean
compiler, probe, repair or workflow and changes no scientific files.

Compare the snapshot with the saved monitor state. Inspect bounded new fault
metadata only as needed. Do not read unfinished arguments to steer construction,
send hints, import other proof skills, resample mathematical nonpasses or restart
a live/waiting case. Follow the existing guarded recovery boundary only with
actual authorization; update the current run map after any authorized change.

Notify on a meaningful stage/coverage change, fault, completion or required user
action. Stay quiet on unchanged routine checks unless the user expressly asked
for a report at every check. Use the user's requested language. An interval is
not a native-check deadline or a case/token budget. Five-second program liveness
heartbeats remain separate from these ten-minute owner checks.

`PAUSED_ERROR` is nonterminal. The local Python error controller separately
queues immediate fixed-text owner alerts and preserves its context/workspace.
Read `paused_errors` and its outbox status; do not restart a paused run, declare
it finished, or close its monitor. Operator controls and the only allowed
cleanup boundaries are in [error lifecycle](error-lifecycle.md).

At each case termination, read its actual result and linked gate reports. A
recorded PASS is not new verification; validate existing bound artifacts using
the Yui validators without starting another model or Lean run. Keep partial or
unknown usage and every execution qualification visible.

After every tracked case is terminal, the owned process groups have exited and
authorized recovery is complete, validate and save the final reports and run
the entry's authorized cleanup. Mark the owner monitor complete and end the
turn. For a run with a permitted host schedule, retire it using its recorded
ID. Use the host tool for that operation.
