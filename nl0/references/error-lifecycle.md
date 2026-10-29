# Fault treatment, retained pause, and authorized exit

Classification describes what failed. Treatment decides whether to retry or
wait for an operator. Neither decision authorizes ending a workflow or deleting
its workspace. The local Python controllers own these transitions even when
the network and model service are unavailable.

| Fault | Category | Automatic treatment |
| --- | --- | --- |
| HTTP 401/403 or model/account authorization | `model_auth` | Pause immediately |
| HTTP 402 or depleted credit balance | `model_balance` | Pause immediately |
| Explicit exhausted usage/quota, including quota-related 429 | `model_quota` | Pause immediately |
| Transient 429/503 or recognized server overload | `model_capacity` | Retry at60-second intervals, at most 10 times |
| Recognized remote connection failure | `model_transport` | Same bounded retries |
| Remote request timeout | `model_timeout` | Same bounded retries |
| Interrupted response stream | `model_stream_interrupted` | Same bounded retries |
| HTTP 400/404/413/422, unsupported request/context/output settings | `model_request_rejected` | Pause immediately |
| Local controller/tool/provenance fault or unknown cause | `harness_bug` | Pause immediately; require verified repair |
| A remaining mathematical/source obstacle without a supported automatic repair | `workflow_blocked` | Pause with its original GAP/nonpass; do not misattribute it to software or service failure |

Explicit quota/auth/rejection evidence takes priority over a generic capacity
code. A mathematical nonpass is ordinary located repair, never a remote retry.
The native Lean 300-second limit remains a separate candidate-check policy.

## Retry and pause

The original failed attempt is followed by at most 10 additional attempts, each
after 60seconds, in the exact same isolated carrier/thread with the same profile,
drafts and tool receipts. Native provider retries are disabled so they cannot
multiply the controller's limit. A successfully completed turn ends the current
incident; manual resume explicitly authorizes a new bounded incident. Counters,
original faults, elapsed time and usage remain in the evidence.

Nonretryable faults and exhausted retries enter `PAUSED_ERROR`. The controller
waits locally without model calls or automatic phase replay. It retains its
carrier, temporary workspace, candidates and checkpoints. Successfully submitted
NL0/A-review carriers are also retained until the actual Audit A gate and its
finalization; Lean-stage carriers remain retained until final Audit B/workflow
finalization. Artifact submission alone is insufficient to release these resources.

Each pause saves `error-state.json` and a per-incident record under the affected
stage's `error-incidents/`. These include category, HTTP/code evidence, original
diagnostics/traceback with credentials redacted, retry count, process identity,
checkpoint and exact control commands. Original transport/tool logs remain
available. A local pending notification stays recorded if the front end cannot
be reached.

## Offline front-end report

Dispatch captures the owner task from `YUI_OWNER_THREAD_ID`, or `CODEX_THREAD_ID`
in a Codex task, in owner-only `owner-context.json`. This identity is never part
of mathematical model input. Outside Codex, explicitly set `YUI_OWNER_THREAD_ID`
to a real receiving task if desktop delivery is wanted.

Python calls the installed local `codex queue --thread ID --message TEXT` with
fixed diagnostic text. It requires a compatible local CLI and the desktop task
to exist; notification generation itself needs neither internet nor an LLM.
The script uses `YUI_CODEX_BINARY`/normal runtime discovery, never a developer's
absolute home path. One successful notification per incident is sufficient.
Failed delivery remains a local outbox with at most three bounded delivery
attempts 60seconds apart; it never abandons the paused task. The owner heartbeat
also reports pending error metadata and must not mark a pause terminal.

## Inspect, resume, cancel

```sh
python3 -B nl0/scripts/yui.py errors /absolute/path/to/RUN
python3 -B nl0/scripts/yui.py resume-error /absolute/path/to/RUN --incident INCIDENT_ID
python3 -B nl0/scripts/yui.py cancel /absolute/path/to/RUN
```

Fix the reported account/network/request issue before explicit resume. Resume
is bound to one current incident and the exact live owner PID/start/PGID; it
continues the same thread and never starts a replacement attempt. Restored
credentials may refresh only the same account; changing model/account identity
is not an implicit recovery. Completed tool-call IDs retain their original
results and cannot execute their side effects twice.

Unknown/local software faults and ambiguous protocol checkpoints stay paused
when a safe replay boundary is unavailable. `resume-error` refuses those cases;
the operator must inspect/verify the repair and select a supported checkpoint.
An installation edit does not silently change a running job's frozen runtime.
Legacy `resume` commands exist only for already-exited historical attempts and
retain their original guards; never use them instead of a live error pause.

## Exit and cleanup

Resource termination/deletion is authorized only by:

1. Actual requested acceptance and finalization: NL0 plus Audit A for its phase,
   or final assembly/native inspection plus independent Audit B for translation
   and the whole workflow. Previously authorized conditional-source outcomes
   retain their warnings and are never relabeled ordinary full PASS.
2. An explicit user cancellation, including a user-requested `cleanup --apply`.

Faults, retry exhaustion, a stage directory, a model's normal reply, a submitted
draft, elapsed time or a child-process exit cannot grant this authorization.
Parent controllers retain and report an abnormal child exit instead of declaring
the task finished. Existing scientific outputs and error evidence are retained;
automatic successful finalization removes only owned ephemeral resources.
Deleting an entire selected scientific run remains an explicit cleanup action.

Stage resource retention and authorized release are separate owner receipts, so
deferred cleanup does not rewrite hash-bound judgments/results. The existing
source, target, independent-review, interface, kernel and A/B validators remain
mandatory; an operational resume never grants mathematical acceptance or
fault-free benchmark timing.
