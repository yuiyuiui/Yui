# Foreground handoff and scheduled owner observation

This protocol applies only to the invoking owner. Proof, author, preparation
and review stages continue their assigned work in their isolated contexts.
Ending an owner turn does not stop those processes, pause a goal or establish
mathematical acceptance.

## Dispatch, register, then end the foreground turn

1. Finish target/configuration collection and dispatch with `--detach`.
2. Verify the returned run paths and PID/start-time/PGID records. Retain usable
   observation and cancellation commands. Do not start another mathematical run.
3. Read the returned `owner_observation` handoff. Its initial registration is
   `HOST_REGISTRATION_REQUIRED`; it is not an actual schedule. Use the host's
   automation tool to create or update one heartbeat in this same chat, every
   ten minutes, covering all cases in the invocation. Reuse an existing matching
   monitor rather than creating duplicates. The handoff supplies the exact run
   map, a bounded observation command and a durable observer-only prompt.
4. Save the actual returned automation ID and exact current run map in
   `OWNER_MONITOR_STATE.json` in the selected run; keep monitor metadata separate
   from mathematical inputs, receipts and worker token accounting. Report that
   work is running and monitoring is registered, then finish the foreground turn.

Never replace a host heartbeat with repeated sleeps, status reads, long waits
or an idle foreground agent loop. The Python controller cannot finish a chat
turn or register a desktop schedule itself. A detached launch alone does not
establish either action. If the host has no scheduling capability, say so,
return the concrete manual commands and end the turn; do not silently install a
cron job, background model observer or alternative scheduler.

The default policy is explicit in `config.json` under `owner_observation`:
`end_turn_after_handoff`, a 600-second interval, `host_heartbeat`, and
`meaningful_changes_only` notifications. A manual synchronous terminal command
can still wait for its program to finish without repeated model calls; the
policy governs the invoking conversational owner.

## One bounded check per scheduled wake

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
it finished, or delete its heartbeat. Operator controls and the only allowed
cleanup boundaries are in [error lifecycle](error-lifecycle.md).

At each case termination, read its actual result and linked gate reports. A
recorded PASS is not new verification; validate existing bound artifacts using
the Yui validators without starting another model or Lean run. Keep partial or
unknown usage and every execution qualification visible.

After all current cases are terminal, exact owned processes and groups have
exited and no authorized recovery is pending, preserve the final report and
delete the completed host heartbeat using its actual ID. End the scheduled turn.
Do not keep waking an already-completed workflow.

The host integration follows [scheduled tasks](https://learn.chatgpt.com/docs/automations).
Use the host's current tool schema rather than editing scheduler files.
