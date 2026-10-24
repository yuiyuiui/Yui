# Execution terminology

Use these terms in Yui documentation, scheduling discussions and run reports.
Qualify `task` and `worker`: neither word alone identifies a conversation, a
mathematical obligation, a model context or an operating-system process.

## Terms

| Term | Meaning in Yui discussions |
| --- | --- |
| Codex conversation / chat / task / thread | A conversation container with an identity and history. Prefer `conversation` in prose and retain the actual backend `thread_id` in records. Starting a fresh CLI conversation creates a new conversation; opening another terminal window alone does not, and resuming continues an existing conversation. |
| Agent | A model-driven executor with instructions, context, tools and an execution loop. An agent can make many model requests and perform multiple work items. An agent is not a model name, a single request or a PID. |
| Main agent | The agent interacting with the user in the parent conversation. It may coordinate work, perform work itself, or invoke a controller. |
| Subagent | An agent delegated through the parent runtime's native agent-coordination mechanism. It has its own context and a parent/child relationship. It may have a backing thread, but it is not thereby another independent user-created top-level conversation. Separate context does not guarantee separate files, permissions or a clean experiment. |
| Case | One fixed mathematical problem and its supplied proof, inputs and acceptance requirements. A case can require several stages and attempts. |
| Stage | A workflow phase, such as NL0 authoring, global Audit A review, packet replay, interface preparation, Lean proof work or Audit B. A stage is not necessarily an agent or a process. |
| Job / work item | A scheduled unit of work. A Lean proof job targets a frozen local obligation; an authoring or review job has its own explicit scope. Use `proof job` rather than the unqualified `task` for a theorem obligation. |
| Attempt | One execution of a job under recorded inputs and configuration. A retry is another attempt; it does not erase the previous result. |
| Worker | A logical responsibility unit in Yui's workflow. It may contain several stages, model threads and program actions. Use the phase names below. Within a worker, identify the actual `NL0 author`, `Audit A reviewer`, interface author or other session role separately. A worker is not necessarily one agent, one thread or one PID. |
| Worker slot | A capacity position in the formalization queue, called a `formalization worker` in user-facing scheduling descriptions. Reusing a slot does not mean reusing a model context. Yui's Lean queue creates a fresh context/workspace for each node attempt. |
| Controller | The scheduling and bookkeeping program. Yui's Python controllers dispatch jobs, collect results, maintain state and handle cancellation. They make no model requests merely by updating records; a separately invoked planning/model stage does consume model usage. |
| Carrier / process | The runtime transport and its operating-system processes, such as a Codex app-server process. One process can support multiple requests or threads; a PID is not a mathematical result or a universal agent identifier. |
| Run / batch | A recorded execution containing cases, stages and attempts. A finite batch may terminate with failed or incomplete cases. |

Codex also documents a built-in agent profile named `worker`. That profile is
distinct from Yui's general use of the word for an execution role. Do not claim
that Yui selected the Codex `worker` profile without an actual configuration
record.

## Canonical worker names

Use the following four names for one mathematical case. These are logical
workflow units; grouping activities under one name does not merge their model
histories, remove review independence or create an additional model agent.

| Name | Responsibility and completion boundary |
| --- | --- |
| **NL0 worker** | Produce NL0 from the supplied proof, execute Audit A, and handle authorized local corrections and review. It completes successfully only with complete actual Audit A acceptance. The author and reviewer use separate sessions; global and packet reviews may require more than one reviewer thread. |
| **Preprocessing worker** | Enter translation from an accepted NL0; inspect shared derivations; propose bounded extraction and NL0 patches when useful; obtain the required local reviews and freeze the selected source; choose representations and shared Lean interfaces; construct the IR, local plans and task packets; obtain interface review and type elaboration; freeze the proof queue. It is ready only when the accepted source and interfaces/plans are frozen. |
| **Formalization workers (N slots)** | Execute the frozen local Lean proof queue with at most N simultaneous proof jobs. A free slot claims the next job. Each model-backed attempt creates a fresh thread; compatible checked reuse may avoid creating one. Shared Lean lemma and representation-conversion proof bodies belong in this queue. Local Lean acceptance does not by itself establish whole-case Audit B acceptance. |
| **Postprocessing worker** | Assemble actual local proofs and discharge internal dependencies; perform Lean builds; complete the Audit B source/formal mapping and permitted mathlib instantiations; obtain a fresh semantic Audit B review; validate the final receipt and preserve the report and process-exit evidence. It completes successfully only after full Audit B acceptance. |

The ordinary full-workflow order is:

```text
NL0 worker
  -> Preprocessing worker
  -> Formalization workers (up to N concurrent proof jobs)
  -> Postprocessing worker
```

An NL0-only run stops at accepted Audit A. A translation-only run starts from
an already accepted source and enters preprocessing. Within one case,
preprocessing and postprocessing use the serial preparation/review lane and
do not overlap its formalization queue. Multiple independent cases may execute
different phases concurrently under their separate case budgets.

Preprocessing chooses the statements and interfaces of shared Lean lemmas; it
does not silently prove them in a definition header or assume their conclusions.
Their actual proof obligations remain explicit formalization jobs. Postprocessing
mapping and library-instantiation work is genuine model work when performed by
a model, and must be included in the postprocessing time and token costs.

For example, `N=5` means five formalization slots. It does not mean that one
preprocessing thread, five proof threads and one postprocessing thread all run
at once. Across the full case there can be many more than five model threads,
because each authoring/review stage and each proof attempt has its own recorded
session. One logical worker may also include mechanical actions that make no
model requests. Count all actual model calls; do not charge a thread or token
cost merely because a logical worker exists.

Keep the logical worker name, stage, job/attempt identity, model thread identity
and process identity distinct in reports. These names are documentation/reporting
conventions, not new runtime schema fields. Retain existing CLI options, raw
`worker_id` slot labels, logs and old evidence without renaming or rewriting them.

Naming a phase does not implement its orchestration. The current test adapter
dispatches interface authoring/review, the proof queue, mapping and Audit B
review. Shared mathematical extraction and its local source-review dispatch
still require explicit operator orchestration around the preparation tools.
Do not describe that missing dispatch as automated merely because it belongs
to the preprocessing worker.

## Two different delegation mechanisms

Native delegation has a parent agent and its subagents:

```text
User-facing Codex conversation
  main agent
    native subagent A
    native subagent B
```

Yui's current isolated subscription carrier instead uses programmatic dispatch:

```text
User-facing main agent / run operator
  Python batch controller
    Python case controller
      isolated NL0 author session
      isolated Audit A reviewer sessions, successively
      later: isolated Lean proof sessions, up to the proof-worker budget
```

The second diagram describes workflow ownership and stage order, not a native
Codex subagent tree. In the current carrier, `scripts/run_pilot.py` starts
`codex app-server --stdio` with native `multi_agent` and `multi_agent_v2`
disabled. Its author/reviewer/proof sessions are therefore not native
subagents of the interactive main conversation. A stage's recorded
`model_thread_id`, attempt ID and process identity describe different objects.
This implementation fact must be rechecked if the carrier changes.

## Concurrency counts

- **Native subagent capacity:** report the limit supplied by the actual runtime
  and whether it includes the main agent. Do not describe three subagents as
  a universal Codex limit. For example, a runtime exposing four active-agent
  slots including the main agent leaves at most three active descendants
  across that tree, not three fresh slots for every descendant.
- **Concurrent cases:** the number of mathematical cases running at once.
- **Per-case proof concurrency:** `max_concurrency=auto|N` limits simultaneous
  Lean proof jobs in that case, exposed as N formalization worker slots. The
  Python controller occupies no proof slot.
  NL0 authoring, Audit A and other preparation/review work use the case's
  separate serial lane. The proof budget does not authorize concurrent Audit A
  reviewers within one case.
- **Observed concurrency:** the overlap actually measured, which can be below
  any configured bound. Three ready cases with five available proof slots each
  permit up to fifteen simultaneous proof jobs only when backend capacity and
  resource limits also allow it. This is not a claim that fifteen ran.

Independent carrier sessions are outside the interactive conversation's native
subagent tree. They still share applicable account/service limits and host
resources. Neither a new conversation nor a new subprocess establishes clean
isolation; use the input, tool and environment checks in
[isolation](isolation.md).

## Completion vocabulary

Keep the work item's outcome separate from its executor's lifecycle:

- `Model session/process exited`: the identified executor ended; say whether
  this was normal completion, cancellation, a fault or an unconfirmed stop.
  Older reports saying `worker exited` must identify the underlying session or
  process; exit does not establish completion of a logical worker's duties.
- `Stage finished`: the stage returned a result. This alone is not Audit A/B
  acceptance. An `ACCEPTED` JSON artifact may contain FAIL or UNVERIFIED
  mathematical judgments; state the acceptance scope.
- `Case passed Audit A`: complete current-standard actual review judgments and
  their receipt passed the required validation.
- `Batch finished with nonpass`: submitted work ended, but one or more cases
  did not meet acceptance. This does not fulfill an instruction to continue
  until those cases pass.

A controller's finite-batch termination policy and the user's overall stop
condition are separate. State both explicitly. Reducing monitoring frequency
does not authorize changing the overall stop condition. Preserve drafts and
logs when work ends without acceptance; do not report process exit as success.

## References

- [OpenAI: Codex app-server](https://learn.chatgpt.com/docs/app-server),
  conversation/thread creation, resumption and turns.
- [OpenAI: Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
  delegation, configuration, permissions and the named `worker` profile.
- [OpenAI: Responses multi-agent](https://developers.openai.com/api/docs/guides/responses-multi-agent),
  the active-descendant limit for that API's native agent tree. Do not transfer
  its configuration defaults to a different runtime.
- [Yui execution protocol](../translation/references/execution-protocol.md),
  queue slots, fresh attempts, file-based control and process ownership.
- [Yui review execution](review-execution.md), serial preparation/review lanes
  and mathematical acceptance boundaries.

Official documentation and the current carrier were checked on 2026-10-24.
