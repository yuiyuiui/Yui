# Native execution boundary

Yui controls the workflow through the official Codex app-server stdio interface.
Codex connects directly to the model service using its own networking and login.
Production Yui does not host a model HTTP endpoint, forward responses, parse SSE,
rewrite model request bodies/headers, or renew bearer tokens.

Each role uses its own temporary home, CODEX_HOME and input directory. The native
configuration disables personal memories, plugins, project-document discovery,
shell/browser/computer tools and native delegation. Approved Yui dynamic tools
read only declared inputs, frozen rule files or the pinned Mathlib. Python never
executes model-generated Python or shell commands. Lean remains separately
sandboxed offline with its configured single-call limit.

The native Codex process may make outbound service connections, but cannot read
unrelated project files or launch arbitrary executables. Its approved dynamic
tools execute in the Python controller under their own path/schema checks.
System proxy environment variables may be inherited; Yui adds no network proxy.
Codex's own local Code Mode helper executes tool-calling JavaScript. Its path
comes from the selected installation's package manifest, or its adjacent
standalone helper; no second PATH installation is substituted. Jobs and native
receipts bind the main executable, helper and package manifest hashes. Each new
role checks this binding before dispatch. The process sandbox permits only the
main executable and this helper, with their required local read/IPC access.
Dynamic Yui calls still pass through the same Python schema and path checks.
The named `yui-native` provider uses Codex's OpenAI-authenticated default endpoint
selection, with no Yui base URL override. Native request/stream retries are set
to zero so Python owns the explicit 60-second, 30-retry failed-work policy.

Native Codex built-in instructions and context compaction are retained. Yui
supplies explicit role instructions and frozen task inputs through the native
API; it does not strip system instructions or replace compression summaries on
the wire. An unchanged role retains only its own conversation. Distinct authors,
reviewers and cases keep separate sessions and tool/receipt namespaces.

`native-client.json`, effective-config.toml, client.jsonl, events.jsonl and actual
tool/hand-off records describe this boundary. Readback checks configuration,
model/effort/tier requests, controller-supplied messages, tool schemas and file
hashes. It is not byte-level inspection of provider HTTP payloads. Actual model
routing/service tier and per-response usage are reported only when exposed by
the native client; otherwise they remain UNVERIFIED. A passed native-context
receipt is not a mathematical review, a provider-isolation proof or a complete
benchmark measurement.

Execution status counts actually completed tool RPCs separately from automatic
continuations. Rejection feedback is still a completed tool call, not a proof
success; replaying an already delivered call does not increment that counter.

Tool RPCs must match the active role thread/turn, allowed tool catalog and exact
call ID. Exact repeats return the immutable previous result without reexecution;
changed arguments, foreign identities and unsupported tools are rejected. After
submission, persist the artifact, stop only the current generation via the native
API, confirm its matching completion and retain the role until the specified
successful workflow boundary. Never manipulate HTTP connections to implement
this handoff.

Historical snapshots and archived raw-wire logs retain their original meanings.
Legacy read-only exposure/usage readers remain for those records; new production
runs cannot launch the removed relay. Provider-side state and account scheduling
remain outside the locally observable boundary.

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

Each stage snapshots its runtime/rules and native configuration, records stdio
work/tool events and reads back native context and usage. Cumulative usage
snapshots are differenced, never summed. Unknown per-response coverage or actual
service tier prevents a claim of complete benchmark measurement; it does not
turn an otherwise valid mathematical submission into an automatic failure.

The native completion policy has no controller-imposed model idle cutoff.
Silence alone does not exhaust a mathematical budget. Codex stdio does not expose
partial provider argument/SSE events, so the former consecutive-whitespace and
raw-provider-terminal observers are not installed or claimed for native runs.
Complete tool arguments are validated before execution. Native-reported errors
and process/reader failures follow the retained fault lifecycle; no synthetic
terminal/usage or partial-call execution is permitted. Historical event-classification
tests do not establish protection of an unobservable native stream.

Case-local execution snapshots/control files are controller material, not
worker inputs. Their updates and heartbeats make no model calls. Independent
case workflows share only immutable toolchain/rule material. See
[the execution protocol](../../nl02lean/references/execution-protocol.md) for
scoped stops and the explicit limitation of the desktop main-chat Stop button.
