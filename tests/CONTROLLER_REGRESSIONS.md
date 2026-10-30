# Python controller repair record

These are software-control defects reproduced with synthetic inputs and local
services. They do not establish the cause of a historical upstream disconnect
or the correctness of any mathematical proof.

| Confirmed defect | Observable regression | Correction |
| --- | --- | --- |
| The relay appended a second HTTP error response after committing a successful SSE response | One raw connection contained both `200 OK` and `502 Bad Gateway`; disk failures had the same effect | Track the header boundary, retain the original error and close the connection without new status/headers or synthetic provider events |
| Successful provider subresponses did not reset consecutive retries until a whole native turn completed | A long tool-using turn exhausted old failures despite intervening completed responses | Bind clean response completion to its own request/native-turn generation; keep lifetime and consecutive counts separate |
| Exception class was used without the failing operation's origin | Downstream broken pipes and local bookkeeping timeouts became remote network retries | Classify upstream operations separately from local validation/evidence and downstream operations; preserve exact registered controller cancellation |
| Native stdout reader faults did not reach the main message loop | A log-write exception killed only the reader thread; invalid JSON was skipped while a live carrier could leave the controller waiting | Retain a structured local fault, wake the inbox and use the existing retained-error pause |
| Retained-role reassignment discarded state still required by the live relay | The first real HTTP submission returned 200; the same role's second assignment returned a local 502 | Drain the prior response evidence, preserve the relay lock and initialize its next assignment's stream registry |
| Owner summaries preferred a populated dictionary of all-zero proof counts over NL0 task counts | Active or paused review tasks appeared as zero running/paused tasks | Report all-task counts and proof-only counts as separate fields |
| Local model-catalog errors were uncaught by the relay | Missing/corrupt cache closed the connection without structured evidence or a main-controller error | Apply the same one-response boundary and retained local-fault reporting to `/models`; local pre-header failures use 500, distinct from upstream connection failures using 502 |
| Opaque native errors lost their actual rejected HTTP status | A real HTTP 400 was wrapped as `codexErrorInfo=other` and mislabeled `harness_bug` even though it paused correctly | Bind the relay's observed numeric status to its exact current request; use it for classification without parsing arbitrary error prose or using another request's status |

An additional test-isolation defect allowed a missed notifier mock to enqueue a
real front-end alert. Software tests now fail before that side effect unless
the notifier or local queue command is explicitly mocked. Production alerts are
unchanged.

The recognized-transient policy is now exactly one retry per 60 seconds, at most
30 retries following the original failed attempt. Exhaustion and permanent,
unknown or local faults retain the same task/workspace in `PAUSED_ERROR`; they
never authorize a workflow restart, task shutdown or cleanup. Mathematical
profiles, task numbering, frozen E/P, reviewers and accepted closure boundaries
are unchanged.

Tests are grouped by observable responsibility in [README.md](README.md). Red
regressions were run before their production fixes. Loopback wire tests and the
actual local native-client handoff complement state-machine unit tests; the
complete unified suite still includes the existing native Lean/acceptance checks.
No remote model or new mathematical benchmark is part of this repair validation.

The later native fault-injection suite exercises a task that has already saved a
real tool checkpoint before failure. It checks socket cuts, unavailable service,
read timeout, capacity/auth/balance/quota/request errors, local evidence failure,
30-retry pause, manual resume and cancellation through the actual client and
controller. Clock and notification-test boundaries are explicit in README.md.
