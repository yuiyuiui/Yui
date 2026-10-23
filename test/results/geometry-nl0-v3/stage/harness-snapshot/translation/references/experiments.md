# Functional development experiment

Use gpt-5.6-luna, reasoning high, through the existing subscription relay.
Do not substitute a model if it is unavailable. Pin the existing CLI, Lean
4.32.2 and mathlib revision. New instructions/tools define a new harness version;
these results must not be pooled with earlier four/five-tool baselines.

Each model stage gets a fresh carrier directory, ephemeral thread, empty
personal context and only explicit source/contract/plan text plus whitelisted
tools. Reuse the existing audited relay normalization, OS sandbox and offline
Lean checker. Archive prompts, sent requests, tool outputs, model outputs,
configuration and input hashes. Do not archive auth files or authorization
headers. Log whether skills were exposed and whether transport faults occurred.

The interface author sees NL, parameter/premise identifiers and representation
conventions, without the expected Lean signatures. A withheld owner-reviewed
development oracle checks exact port correspondence. Accepted proposed types
are then used by the planner, which sees the NL and frozen typed contract.
The local proof author sees its one conditional obligation and permitted premises. The owner
can inspect reference code for retrospective design, but measured workers
cannot. These development fragments are selected with reference exposure and
are not held-out benchmarks. Automatic NL-to-type proposal is tested on these
three prepared extracts; automatic verification of arbitrary NL semantic
equivalence and discovery of all shared global definitions are not tested.

Keep a no-IR direct fragment translation control when practical. Match model,
source, formal target, allowed facts, budget and tools as far as possible;
disclose differences rather than claiming a controlled speed result. Count
planning and all local proof calls in the IR arm. Do not omit failed attempts.

Run at least two development rounds and preserve failed logs before changing
the implementation. Distinguish an unchanged repeat from a revised design.
Tiny cases can expose overhead and correctness failures; they cannot establish
large-case parallel speedup or statistical significance.

Record separately:

- owner preparation and semantic-review time (UNMEASURED if not instrumented);
- model-stage remote wall time, which includes server/network time;
- tool/compiler time nested inside that stage (do not add it twice);
- controller/interface checking and final assembly/verification time;
- accepted results, failed transitions, proof-check count, source/route review;
- actual parallel work versus merely parallel-ready interfaces.

For an exhausted valid healthy attempt use MODEL_BUDGET_EXHAUSTED. For a
transport/environment/controller fault record unfinished task outcome and that
fault separately. Incomplete execution evidence leaves attribution UNVERIFIED.
Do not label a kernel counterexample or rejected candidate as a service fault.

End-to-end acceleration is a later question. Report functional behavior and
observed costs; no p-values, significant gains, or pure internal LLM reasoning
time can be inferred from a handful of these pilot runs.

## Shared-source and graph concurrency revision

Use contract/plan v2 only in new directories. Preserve the old examples,
experiments and NL0/Audit A bytes. Archive changed maintained code before editing
it, and record the old-path/hash to archive-path map for historical manifests.

The revised runner has explicit proof/case/global model concurrency limits.
Show actual overlap, not only the setting. Compare serial cold, parallel cold
and parallel warm separately on an intentionally repeated development workload.
Warm inputs must list their seeds and prior acquisition costs. Cold cost includes
first production, store registration, module/local checks, lookup, all model work
and final fresh assembly. Include preprocessing or mark uninstrumented owner
design/semantic review UNMEASURED. No total inference cost may be mistaken for
parallel makespan or for pure model reasoning.

Before a complete case rerun, reject wrong guards/targets/representations,
stale artifacts, invalid proof receipts, an unfinished shared producer and hidden
non-input uses. Check that exact duplicate jobs have one producer and that a
cache miss follows the normal proof path. Track actual duplicated lookup/proof
work; usage counts in historical Lean sources alone are not a time baseline.

## Candidate 0.4 integrated functional checks

Use the current source_preparation/workflow adapters only in new directories.
Exercise ordinary accepted source without extraction and accepted local revision
with one real producer/substitution review chain. Preserve the actual baseline
audit, new packets, canonical patch, inherited coverage, typed interface review,
isolated proof logs, complete assembly, source/kernel evidence and final B review.
Synthetic unit receipts test format only; never use them in the actual model run.

Record controller faults, rejected review artifacts, owner corrections and
review-scope clarification separately from healthy model deadline exhaustion.
Reusing unchanged actual review/proof artifacts requires exact binding and
disclosure of their original cost. Never delete failed attempts to describe the
final corrected path as a clean first attempt. Metadata-only fixes need no new
mathematics, but actual verdicts must not be silently changed.

An owner-prepared IR and author-exposed toy source are functional controls, not
held-out end-to-end translation or speed evidence. Include a graph-valid wrong
substitution to exercise actual semantic rejection without giving its expected
defect to the reviewing model. One detection is not a reviewer reliability rate.
