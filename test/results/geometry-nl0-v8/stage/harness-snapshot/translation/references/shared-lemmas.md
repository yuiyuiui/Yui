# Explicit shared conditional lemmas

## Freeze authority and permissions

Perform mathematical extraction at translation entry under
[the local revision protocol](source-refactoring.md), before final IR freeze
and worker-packet generation. It is a patch to existing derivations, not a new
NL0 construction or an automatic full-case Audit A rerun. Use the
[revision record](../templates/source-refactoring.md); observe its explicit
incremental evidence-chain checks and current-v2/limited-patch scope.

Keep the original natural division of NL0. If a common mathematical lemma must
be introduced, create one N/R pair, update its consumers' direct inputs and
perform the scoped producer/substitution review in a new case version. Do not split every
consumer around that small lemma. Existing NL0 exports can be reused directly.
If complete local derivations are merely factored into Lean code, record that
classification and correspondence; do not conceal new mathematics as plumbing.

Contract v2 has `shared_obligations`: `id` (Lddd), full `statement`, ordered
direct `inputs`, complete `source_steps`, the fixed proof `route` and a `review`
with `classification`, `status`, `reviewer`, `basis`. Supported classifications
are `existing_nl0_lemma` and `implementation_extraction`. An upstream-audited
label requires an upstream-audited contract. Development owner review remains
development evidence. These reviews are declarations that need actual human or
model examination; validating their JSON does not perform that examination.

A plan step may set `shared_lemma: L001` only if its statement, inputs and source
mapping match the frozen export exactly. Its consumers list that T step as an
ordinary input. Their packets include the input type and shared ID/review, not
the producer proof. No shared fact becomes an ambient global definition.

## Physical project store

```text
shared-store/
  index.json
  Shared/L<typed-route-key>.lean
  objects/<typed-route-key>/entry.json
  objects/<typed-route-key>/verification.json
  objects/<typed-route-key>/module-verification.json
```

The index maps exact keys to immutable entry hashes. Each entry stores the full
conditional type, all parameters/direct conditions, proof source, declaration,
module/proof/check hashes, source/paragraph/review provenance and measured
verification cost. Registered entries are `VERIFIED_LEAN_CONDITIONAL`; they do
not inherit Audit A/B. Pending/running/failed work is kept in scheduler job
records, not published as a verified library entry.

The first implementation re-elaborates a closed local copy of the stored
conditional theorem and applies it to the current binders. The physical Lean
module is also compiled on admission. It is a source-proof store, not an
optimized compiled module cache. Compiler costs and any missed lookup are
included. Admission never accepts `sorry`, a custom axiom or an unproved input
disguised as a theorem. Conditions remain explicit proof binders.

## Matching and invalidation

Python matches the ordered typed interface, frozen header/definitions, pins,
representation records and fixed route. Parameter and input binder names may
be alpha-renamed; there is no approximate semantic matching, premise discharge
by metadata, arbitrary generalization or automatic representation optimization.
Conservative misses are acceptable. Lean rechecks the concrete instantiation.

Record the initial index and allowed export interfaces in every run. A changed
environment, definition, condition, target, representation or route has another
key. Changed module, metadata or check bytes invalidate a matching entry. A miss
returns to the ordinary worker; an invalid artifact is preserved for inspection,
and its slot is not silently overwritten. Failed/unfinished new proofs are not
admitted. Hashes protect recorded state, not against an owner rewriting every
artifact and hash together; the underlying source/correspondence audit remains.

## Concurrency

`scheduler.prove_graph` freezes all ports, typechecks representation expressions
and schedules independent conditional proof bodies with a bounded thread pool.
Compatible shared tasks within that graph are grouped by the typed-route key:
one worker produces the proof and checked instantiations serve the aliases.
This is single-controller coordination, not a distributed multi-controller lock
service. The index has a process-safe publication lock; it is not a cross-process
in-flight proof-job scheduler.

A downstream worker can prove `B -> P` while another proves B, using B as a
local proof parameter. Final assembly supplies actual proofs topologically.
Every local body, reused instantiation and final root must check. If B remains
unfinished, the root is unfinished. No placeholder module or internal axiom is
created. General dependent witness export still requires an explicit interface.

Cold runs start with an empty store. Warm runs enumerate their seeds and prior
construction costs. Never preload reference solutions and call this a fresh
formalization speed result. Frequent source use alone does not establish that
isolated workers duplicated construction; measure that behavior first.

## Run a frozen graph

From the translation candidate directory, with source paths staged locally
under the contract directory and a new output directory:

```sh
python3 scripts/run_graph.py /absolute/case/contract.json /absolute/case/plan.json \
  --out /absolute/new-run --shared-store /absolute/project/shared-store \
  --max-concurrency auto --timeout-seconds 180
```

The runner copies source/contract/plan bytes without changing their hashes,
freezes configuration and source snapshots, and uses fresh model stages. Omit
`--shared-store` for ordinary conditional proof work. `--bank` optionally exposes
the advice lookup. The stage budget starts after any model-stage queue; runner
makespan includes packaging, queue, proof work and verification. Source/port
authoring and their semantic review precede this frozen-port command and must
be counted separately in an end-to-end experiment.

Inspect or admit a single reviewed export without calling a model:

```sh
python3 scripts/shared_lemmas.py lookup /absolute/project/shared-store \
  /absolute/case/contract.json /absolute/case/plan.json --step T001
python3 scripts/shared_lemmas.py admit /absolute/project/shared-store \
  /absolute/case/contract.json /absolute/case/plan.json --step T001 \
  --proof /absolute/proof-tactic-body.txt
```
