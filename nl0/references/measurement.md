# Native measurement and historical evidence

New runs use native Codex stdio events, not an intercepted HTTP stream. Preserve
selected model/effort/Standard configuration, native thread/turn identities,
actual tool results, errors, retry waits, role handoffs and final artifacts.

Native tokenUsage.total is cumulative for a thread. Use its latest nonregressing
snapshot minus the saved baseline at the beginning of a retained-role dispatch.
Do not add repeated snapshots, total and last, or reasoning/cached subsets.
A native stage ledger uses a record_id, not an invented provider response ID.
Keep distinct stages and exclude copied review/runtime evidence from aggregate
costs. Missing counters, request counts, response coverage and actual tier remain
unknown. Native totals are reported as partial observed usage, not full exact
per-provider-response accounting. Owner/controller overhead remains separate.

A native-context check validates the supplied configuration, role instructions,
inputs and tools. It does not certify exact provider HTTP payloads. Mathematical
acceptance, execution health and measurement completeness are distinct fields.
Known recovered native transport errors preserve their faults and costs; a
complete correctly bound review may proceed without pretending execution was
fault-free. Unknown native errors, reader/tool faults and unconfirmed handoffs
remain ineligible for automatic acceptance.

The old raw-wire format is supported only by read-only historical validators.
Its requests.jsonl/response-*.sse evidence must not be fabricated for new runs.
Historical benchmark results keep the runtime/profile that produced them.

Stage wall time includes tools, network/service waits and model work. Native
work-start/completion intervals are not pure model reasoning time. Retries and
pauses remain included in dispatch-to-terminal elapsed time, with their durations
reported separately when observable. Do not infer speedup from concurrent cases
or compare changed runtimes as an isolated causal experiment.
