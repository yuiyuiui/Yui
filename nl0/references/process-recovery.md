# Process cleanup diagnosis for the owning AI

This is an operational recovery entry. It grants no mathematical acceptance.
The native caller retains its process handle, exact compiler result and frozen
inputs while the existing owner AI investigates. Do not start a new foreground
chat or restart the proof workflow merely because a process query failed.

Diagnostic notifications request `codex queue --resume` for the existing owner.
Queue success, including a zero exit with a resume warning, does not acknowledge
takeover. `owner_takeover` stays `AWAITING_ACKNOWLEDGEMENT` until a fresh bound
`process-diagnose` observation is actually received. If this is still missing
after sixty seconds and cleanup remains unconfirmed, one reminder requests
attention and records `UNACKNOWLEDGED`; delivery errors remain in the bounded
outbox. A later valid observation clears that takeover-specific attention flag.
These states never replace actual native identity/group exit checks.

1. Read the bound `error-state.json` and `native-checkpoint.json` from the
   notification. Confirm the incident is still `PAUSED_ERROR` before acting.
2. Execute the supplied `process-diagnose RUN --incident ID` command. It performs
   read-only self/target/table probes within thirty seconds total and retains
   their results. A nonzero exit or truncated display is not an empty table.
3. Inspect the parent's handle observation, actual native result, query attempts,
   failed probes and relevant implementation. Distinguish confirmed facts,
   hypotheses and unknowns. Later recovery does not prove the original cause.
4. Write a JSON diagnosis with these exact fields:

   - `incident`: the open incident ID;
   - `version`: `yui-process-diagnosis-1`;
   - `checkpoint_sha256`: the checkpoint binding from the state;
   - `observation_sha256`: the observation binding returned by the diagnostic;
   - `assessment`: `CONFIRMED`, `LIKELY` or `UNKNOWN`;
   - `observations`: nonempty located explanations of actual observations;
   - `unknowns`: evaluated uncertainties, nonempty for `UNKNOWN`;
   - `options`: nonempty concrete recovery/repair alternatives;
   - `action`: `recheck`, `wait` or `escalate`;
   - optional `delay_seconds`: an integer from zero to 300 (wait defaults to 60).

5. Submit it with `process-decision RUN --incident ID --report FILE` using the
   same frozen `yui.py` entry as the notification. `recheck` and `wait` only ask
   the live caller to repeat its ordinary identity/group cleanup checks. Advice
   never substitutes for those checks. One automatic recheck is scheduled after
   sixty seconds; subsequent failures require fresh owner investigation rather
   than an unlimited automatic loop. Normal queries use 5/15/30-second attempts.
6. Apply already-authorized safe operational remedies, then investigate/recheck.
   Prepare code fixes in an isolated copy and validate the actual failure path.
   Do not hot-edit the frozen runtime or task input, add hypotheses, signal
   unidentified processes or cancel the case. If a fix cannot safely attach to
   this live checkpoint, explain that limitation and prepare a retained-results
   continuation rather than claiming to have restored an unwound Python stack.
7. When judgment or authority is missing, choose `escalate` and present concrete
   options in the owning desktop chat. Relay only the user's authorized choice.
   If owner delivery is unavailable, leave explicit pending notification evidence
   and expose this same entry; never claim a diagnosis was performed.

After fresh cleanup confirmation the original native result returns, and its
remaining type/trust/acceptance checks still run. Existing successful compilation
is not rerun merely for cleanup. A timed-out compilation remains a nonpass.
Cancellation remains available through the ordinary explicit user control.
