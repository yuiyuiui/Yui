# Mathematical full-workflow tests

Each fixed exercise directory contains exactly one tracked input, `problem.md`:

| Case | Fixed input |
| --- | --- |
| Geometry / measure | [Hausdorff product dimension](geometry-product-dimension/problem.md) |
| Lie algebras / representation | [Admissible-lattice reduction](lie-module-irreducibility/problem.md) |
| PDE | [Sphere-valued wave-map energy](wave-map-energy/problem.md) |

Each input contains the literal original problem, bibliographic context, the
approved interpretation with all hypotheses, and a detailed natural-language
proof. These are supplied proofs to translate and audit. Test workers must not
solve a different problem, replace the supplied route, or silently drop edge
cases. Freeze the input bytes in each future run's input manifest and record
its Git commit/hash. Only explicitly staged inputs and, in the Yui arm, the
harness are model-visible. Developer history and other cases are withheld.

The original screenshots and separate context/target metadata were consolidated
into the problem files. Generated runs carry their own versioned receipts and
status; the input dataset itself claims no result. The accepted R24 NL0/Audit A
artifacts remain local under `test/results/` and may be reused only after their
actual bindings are checked. Stage-two cleanup is selective and must preserve
those stage-one files and source evidence. A supplied natural-language proof
is not an Audit A pass or a Lean verification result.

## Future runs

The controller should read [REFLECTIONS.md](REFLECTIONS.md) before a campaign
and compare its lessons with the actual run evidence afterwards. This brief
record is maintained source documentation and survives cleanup. It must not
enter any measured model's task inputs, including reviewer and direct-model
inputs; do not add an extra model review just to maintain it.

Use the phase profiles in [config.json](../rigorous-proof/config.json):

| Phase | Model | Reasoning | Speed |
| --- | --- | --- | --- |
| NL0 authoring and Audit A, including its calibration | `gpt-6.1-sol` | `high` | Standard |
| NL0-to-Lean preprocessing, interface authoring, local proof workers and Audit B mapping/review | `gpt-6.1-sol` | `high` | Standard |

There is no automatic fallback or stronger-model rescue. Python coordination,
Lean compilation and assembly make no model calls. The carrier selects and
freezes a profile **per model stage**, including when a full case crosses the
phase boundary in one controller process. Its configuration hash, actual model
identity, reasoning and tier are retained in stage records. Reviews use fresh
contexts; Audit B has the same Sol profile as the formalization workers.
An accepted Sol NL0/Audit A receipt can be reused unchanged for a new Sol
translation run. That is inherited stage-one acceptance, not a fresh NL0 test.
Keep phase costs and model identities separate; this continuation alone is
not a measured speedup comparison. Owner reasoning and personal context never enter measured stages.
A batch consists of independent case processes. Each case has a separate
serial author/preparation/review lane and its own `auto|N` Lean proof-worker
budget. The Python controller does not consume a proof-worker slot. Report
requested/resolved/observed concurrency, actual stage time, execution health,
and usage coverage. Clean boundary details are in
[isolation.md](../rigorous-proof/references/isolation.md).

Place all generated mathematical test runs, queues, NL0s, audit controls,
Lean drafts, snapshots and reports under `test/results/`. This directory is
ignored by Git. Core software-control outputs belong under
`rigorous-proof/tests/results/` or `rigorous-proof/translation/tests/results/`,
which are also disposable and ignored. Runtime code, regression tests/fixtures,
`test/support/`, and the fixed `problem.md` inputs are maintained source files.

The support adapters operate on explicitly prepared inputs/jobs. Actual reviewer
behavioral controls must be freshly prepared and run before their acceptance
is used. The old controls were removed with the old results; do not fabricate
a passing summary or rely on a deleted historical receipt. An NL0-only run may
finish `DRAFT-AUDIT-PASSED`; full formalization acceptance additionally requires
assembled kernel-checked Lean and actual Audit B under the same exact target.

## Current stage-two default

- Reuse the accepted source and Audit A after local integrity checks. Do not
  repeat model Audit A for unchanged mathematics.
- Use the [minimal translation procedure](../rigorous-proof/translation/references/minimal-translation.md):
  original H/E project ports, optional M discharge ports, node-local notes on
  demand, incremental saved interfaces and concise E/P correspondence explanations,
  and a mechanical type/source-boundary freeze. Semantic interface review is
  deferred to actual final Audit B; no pre-proof review PASS is manufactured.
- Run three independent cases, each with five proof slots when requested. Only
  proof nodes use those slots; preparation/review within a case is serial.
- Omit `time_budget_seconds`, or set it to `null`, for unlimited execution.
  There is no default case/stage/native-check deadline, token quota, call quota,
  or post-tool idle cutoff. Stop a run explicitly when required. Only a user-requested positive case limit still covers all its stages and queue waiting;
  no later stage resets it.
- Save partial artifacts; routine `TASK_INCOMPLETE` reports are not a tool.
  Short continuation prompts follow only an unfinished model turn. State and
  usage recording do not call a model.
- After all local jobs pass, one fresh serial postprocessing author follows
  [assembly and export](../rigorous-proof/translation/references/assembly.md).
  It connects actual proofs, discharges retained M ports, compiles standalone
  `Proof.lean` and prepares actual inspection evidence. A subsequent fresh
  independent Audit B reviewer judges source fidelity. Record assembly,
  inspection and semantic review separately; a conditional fragment is not a
  complete proof and an inspector execution error is not a mathematical FAIL.
- Audit B version 2 checks every external E and the entire target P, including
  hypotheses, against actual Lean types. The author supplies a short direct or
  equivalent-encoding explanation; the independent reviewer verifies it. All
  pinned Mathlib results are available without matching an NL0 M use ledger.
  Earlier version-1 verdicts keep their historical scope; they are not converted
  into new-policy passes.

## Cold first-pass NL0 rounds

Prepare one fresh round, then execute its real model calls:

```sh
python3 -B test/support/first_pass_campaign.py prepare --out test/results/cold-first-pass-r1 --index 1
python3 -B test/support/first_pass_campaign.py run --out test/results/cold-first-pass-r1
```

Use a new output directory/index for each round. Preparation makes no model
call. Execution first runs neutral reviewer controls, then launches the three
cases concurrently with one serial author/Audit A lane per case. Each cold
author receives only its own identical `problem.md` plus frozen Yui rules and
allowed tools. There is no old NL0, inherited audit or case-specific repair
prompt, and no author repair after Audit A in that round.

`round-manifest.json` freezes runtime, rules, inputs and configuration;
`round-result.json` records actual outcomes and usage coverage. The criterion
is all three first complete Audit A results passing in the same round. Own
drafting/structural checks remain inside the one author attempt and their
rejections are retained. A failed calibration prevents the expensive case
launch. Do not edit frozen runtime files while a round is active. Repeated use
of these cases makes them development/regression data, not held-out evidence
of general reliability, Lean correctness or acceleration.

## Owner non-interference during measured runs

The interactive owner dispatches the frozen campaign and observes execution
health, process state, timing and usage only. It does not send messages,
mathematical reasoning, theorem/source locators, suggested lemmas, proof
patches, prior verdicts or another case's material to measured sessions.
Do not inspect unfinished mathematical arguments to steer their construction.
Author and reviewer threads receive only their declared staged inputs and
Yui rules. Let each complete author/first-A pipeline reach its own recorded
outcome; inspect the mathematical failures after the campaign finishes.

Do not change rules, prompts, source inputs or code while that frozen run is
active. The round manifest binds the no-help policy, original problem hashes,
author prompt and runtime snapshot. The frozen verifier checks them again at
collection. Neutral calibration is separate from the three exercise results.
No audit-driven author repair or repeated unchanged review occurs inside a
cold round. Report a nonpass honestly. A later explicitly authorized warm
repair is a separate run, with its own costs and disclosed input history.

Read-only monitoring cannot redefine the run's acceptance or stop policy.
For a requested single experiment, finish the finite pipelines and report all
three outcomes. For a separately requested continue-until-acceptance workflow,
batch termination leaves an unmet target for its outer coordinator. Network
and environment failures remain execution faults, not proof defects.

## Stop and clear a test

From the repository root, preview the cleanup:

```sh
python3 -B test/support/cleanup_tests.py
```

Then stop owned runs and remove their generated files/directories:

```sh
python3 -B test/support/cleanup_tests.py --apply
```

The script works from any current directory when invoked by absolute path.
It uses no LLM. It requests cancellation, allows ten seconds for normal
shutdown, then stops remaining matching owned processes, confirms exit, and
only then deletes generated output roots and registered temporary workspaces.
The grace period is configurable with `--grace-seconds 0..60`.

Ownership uses PID **and** OS start identity and process group, plus controller
records, descendants, and exact temporary-workspace bindings. It never calls
`killall` or signals an unrelated process group. An ownership inconsistency or
unconfirmed stop returns a nonzero status and preserves outputs for inspection.
New test stages cannot start while cleanup holds its lock. A second completed
cleanup is safe. Fixed problem files, support code, benchmarks, personal Codex
state and shared Lean/mathlib installations are preserved.

The desktop chat Stop button is not a cancellation hook for independent CLI
processes; use the batch cancel interface or this cleanup command. Temporary
folders from other repositories are outside this script's scope. Legacy Yui
carrier folders can be reclaimed only when exact archived/live ownership
material agrees; arbitrary same-prefix temporary directories are not deleted.

See [support/MAINTENANCE.md](support/MAINTENANCE.md) for the software changes
and their validation scope. Those controls are not mathematical test scores.

## Background-enabled Audit A policy

New-policy rounds may report PASS with verified background notes. Keep the
per-node notes, actual source evidence, note count and policy version beside
the outcome. This is disclosed routine completion during review, not an old
strict-policy or zero-note success. Important dependencies and substantive
mathematical obligations remain fully checked. Accepted notes accompany later
formalization; they are never additional original hypotheses.

Selective cleanup preserves accepted stage-one inputs. Use repeated absolute
`--output /absolute/path/to/results/child` arguments with
`python3 -B test/support/cleanup_tests.py --apply` to remove only specified
stage-two runs and their exact owned processes/resources. Omitting `--output`
cleans all generated outputs, including stage-one runs; do not use that mode
when retaining accepted NL0/Audit A evidence. Always inspect a preview first.
