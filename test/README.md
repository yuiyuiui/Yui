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

The original screenshots and separate context/target metadata have been
removed after consolidation into the problem files. Previous generated runs,
NL0s, audit receipts, drafts and logs have been intentionally cleared. There is
currently no test result or accepted NL0 in this reset dataset. A supplied
natural-language proof is not an Audit A pass or a Lean verification result.
No new model run was performed during the reset.

## Future runs

Selected model: `gpt-6-luna`, reasoning `high`, Standard speed; no fallback.
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

The support adapters operate on explicitly prepared inputs/jobs; they do not
constitute an automatic original-proof campaign launcher. Actual reviewer
behavioral controls must be freshly prepared and run before their acceptance
is used. The old controls were removed with the old results; do not fabricate
a passing summary or rely on a deleted historical receipt. Mathematical
acceptance still requires complete NL0, actual Audit A, assembled kernel-checked
Lean, and actual Audit B under the same exact target.

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
