# Time, token and outcome accounting

One record is identified by problem, arm, model profile, repetition, phase,
stage and response ID. Arms are direct, Yui sequential and Yui parallel. The
main comparison holds mathematical inputs, allowed theorems, checker, model,
reasoning and service-speed policy fixed. Sequential means a model-stage cap
of one; parallel records the requested/default resolved cap and observed peak.

Record root/controller, author, plan, worker, review, diagnostic, repair and
retry calls. Sum actual provider usage over distinct responses, not repeated
copies of a cumulative event or the final assistant message alone. Cached input
is included in input; reasoning output is included in output. Preserve both
subcategories without adding them to totals again. Missing/partial usage is
unknown and reduces coverage; character estimates are never exact usage.

Report each phase and end-to-end totals, successful and unsuccessful attempts,
wall time, model-stage intervals, queue/compiler/tool time and overlap. Summed
worker durations are work, not elapsed wall time or pure model inference.
Whole-workflow accounting includes source preparation and audits. A separate
fixed-NL0 translation comparison may be useful but has a different scope.
Shared-source/store reuse must record the initial artifact and its acquisition
cost; cold and warm runs do not silently share results.

Use the same final semantic/Lean acceptance standard for all arms. No numeric
speedup is inferred when the baseline did not finish. Healthy budget exhaustion
is MODEL_BUDGET_EXHAUSTED under the recorded configuration. Transport, sandbox,
tool-service and controller faults are reported separately. Missing health or
usage evidence remains UNVERIFIED. Never drop failed attempts from the report.
