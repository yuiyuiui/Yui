# Clean execution boundary

The developer/controller process may inspect the implementation and user inputs.
It is not itself a clean experimental model. Every measured model stage uses a
new carrier session with a temporary home, state and working directory. Only
subscription authentication and the selected model catalog are copied into that
state; authentication files are removed when the stage ends and never logged.

The local carrier is restricted by an OS sandbox to its own state and one
loopback relay. Lean runs offline, can read only the pinned toolchain/library
and its task workspace, and cannot read the developer's project tree. The model
has no shell, arbitrary filesystem, browser, memory or personal-skill tool.

The relay constructs a semantic request allowlist: exact model and reasoning,
explicit Yui or bare instructions, exact authorized user messages, verified
within-stage model history, actual tool results and explicit tool schemas.
Developer/system additions, other user messages, server-conversation references
and unrelated provider metadata are removed or rejected before transmission.
No automatic inherited compaction context or model fallback is allowed.
An opaque native compaction summary is still discarded. An NL0 author instead
receives a small machine checkpoint naming only its own immutable current-stage
candidate, actual structural-check result, last structurally valid candidate and
remaining stage budget. Its source files and transmitted text are hash-bound
and independently checked during exposure readback. `read_draft` retrieves that
same-stage artifact. This restores working state after truncation without
importing a summary, other conversation, new theorem or mathematical judgment.
Outgoing HTTP headers also use an allowlist: authentication/account routing,
protocol identity and content negotiation only. Carrier session/conversation
state and premium-speed headers are omitted. Header names are logged; credential
values are never logged.

The controller scans actual function-argument deltas for pathological JSON
whitespace outside quoted strings. Its versioned policy and fixed threshold
are recorded in each stage manifest. A protective stop interrupts only the
exact active turn, preserves the unfinished attempt and never executes partial
arguments. It does not inspect mathematical correctness or call another model.
The same policy applies to both comparison arms. A provider output-token cap
is recorded from its actual incomplete-response event, separately from network
and controller health; no unsupported subscription parameter is injected.

Allowed mathematical information consists of the frozen problem, definitions,
permitted statements, supplied proof, selected Yui rules in the Yui arm, and
explicit tool results. External primary text must be explicitly staged with its
identity and hash before use. It is not obtained from arbitrary local files.
The direct arm has no Yui strategy/plan/reference-answer material.

Audit both what the carrier attempted to send and what the relay actually sent.
Retain payload hashes, tools, real replies, faults and denied-access controls.
Yui NL0 authors and Audit A receive the same shared mathematical requirements
extracted from the frozen Audit A document in their transmitted instructions.
The manifest binds its version and section/document hashes. Exposure readback
checks the archived source and actual instructions. Author notes stay outside
fresh review packets; a common standard does not create a common context.
Model self-report is supplementary; it is not proof of isolation. Provider-side
pretraining, undisclosed server state and account infrastructure are outside
this local verification boundary. "Clean" refers to the observable execution
and transmitted-input contract, not an untrained or provably stateless provider.

For long NL0 author stages, `own-stage-state-2` restores only bounded facts
from this same attempt: the latest draft pointer, real returned self-check
progress/issue IDs and an index of actual successful native source probes.
Immutable snapshot hashes, exact tool-result origins, source receipts and
candidate/authority match flags are checked in transmitted-input readback.
It does not admit an unbound carrier summary, another attempt's material,
personal memory or independent audit feedback. Old progress cannot grant
current readiness, and an index grants no theorem/application permission.
This reminder adds measured input tokens but makes no extra model call; raw
history is retained and no new history-pruning algorithm is applied.

The Standard policy removes premium-speed request/header hints. Requested and
observed tier metadata must be retained; an incompatible actual tier is a
configuration failure. A missing reported tier remains explicitly unverified.

## Clean text stages

Run `python3 nl0/scripts/yui.py stage PROMPT --phase PHASE --inputs MANIFEST --out RUN`.
The manifest explicitly lists `{id,path,sha256}` documents below its own
directory. They are frozen in memory before dispatch. `read_task_input` cannot
open any unlisted local file. Yui stages receive a rule-path catalog and the
`SKILL.md` entry; direct stages have no Yui reader or rule catalog.

`--kind nl0 --case-id ID` enables the structural authoring contract and the
restricted `probe_library` tool. Its submission is `{spec,graph}`. The controller
binds task hashes, toolchain locators and spec hash without editing mathematical
content. Successful submission means `NL0_STRUCTURE_ONLY`, never Audit A.
Release also requires complete bound author inspection, a reported no-known-
issue state and no outstanding located author issue. This is readiness, not a
mathematical verdict. Unfinished states preserve the draft without advancing
to an ordinary first-acceptance audit.
The default JSON contract means `JSON_ARTIFACT_ONLY`, including for review drafts.
The later dedicated A/B gates must still validate the actual review evidence.
`report_obstacle` preserves an explicit blocked result without granting proof
acceptance. A model's substantive-gap judgment can receive an actual bounded
review; keep both judgments and never silently relabel or erase the first.

Each stage snapshots its runtime/rules, records actual requests and responses,
and independently reads back exposure and usage. `measurement_valid` requires
the requested observed model, confirmed Standard tier, complete token ledger,
and no recorded execution fault. It does not imply mathematical acceptance.

The `delivered-tool-terminal-wait-2` policy records real tool-result delivery
without a default idle timeout. Silence alone does not exhaust a mathematical
budget. Explicit opt-in finite protocol limits remain available for controlled
experiments; if triggered, record `PROVIDER_TERMINAL_WAIT_EXCEEDED` with cause
`UNVERIFIED`, never a mathematical gap. Actual dead sockets/process exits remain
execution failures. No synthetic terminal/usage or partial-call execution is
permitted. This Python observer makes no model calls.

Case-local execution snapshots/control files are controller material, not
worker inputs. Their updates and heartbeats make no model calls. Independent
case workflows share only immutable toolchain/rule material. See
[the execution protocol](../../nl02lean/references/execution-protocol.md) for
scoped stops and the explicit limitation of the desktop main-chat Stop button.
