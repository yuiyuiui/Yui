# Formalize the complete Theorem 1

Use only the supplied paper, its cited external results, and the pinned Lean /
Mathlib installation. Do not inspect Yui's proof rules, strategy bank, other
benchmark arms, earlier answers, or the repository's `test/` proof archives.
Do not delegate to another model. Keep every output inside this directory.

Paper: `/Users/syyui/projects/Yui/benchmark/aim-518-kdv-log-loss.pdf`.
Target: **Theorem 1 (Logarithm-free convergence)**, including the precise fixed
unfiltered method defined in Section 2, equations (1) and (2). Read the entire
statement, its preceding definitions and standing assumptions, and its proof.

For each T > 0, 0 < gamma <= 1 and R > 0, the result is uniform over real,
mean-zero initial data in H^gamma(Torus) with norm at most R. The constants
C and tau_0 depend only on T, gamma and R. For every positive integer L with
tau = T/L <= tau_0, the maximum L2 error over all n = 0,...,L is at most
C * tau^gamma. Preserve this quantifier order and the paper's exact solution
concept, normalized measure, Fourier conventions, full update and spaces.
Do not replace the algorithm by a filtered method, impose a Fourier cutoff,
assume the desired stability/convergence estimate, restrict to smooth data,
or lose uniformity in the initial-data ball.

External theorems explicitly used by the paper may be formal assumptions, with
their complete hypotheses and conclusions faithfully stated. Verify primary
sources when accessible. If a primary text is inaccessible, use only a complete
statement actually present in the supplied material, retain it as an explicitly
unverified external assumption, and disclose the exact uncertainty in warn.json
and correspondence.md. Do not invent a missing external theorem from memory,
hide an internal missing lemma inside an external assumption, or discard a
known contradiction. Pinned Mathlib results may be used freely.

Lean installation:
`/Users/syyui/.elan/toolchains/leanprover--lean4---v4.32.2/bin/lean`.
Mathlib source and precompiled libraries:
`/Users/syyui/formalization-tools/lean-mathlib-v4.32.2/mathlib`.
Mathlib commit: `905b95818eb32af7874a58b427f50c1711a5e96c`.
Use the existing pinned environment; do not run `lake update` or change it.

Deliver:

1. `Proof.lean`: a complete compilable development whose exported theorem is
   named `theorem_1`. Every internal obligation must have an actual proof. No
   sorry, admit, new axiom declarations or unproved replacements are permitted;
   external results are explicit parameters with source-faithful types.
2. `correspondence.md`: explain the exact target correspondence, all hypotheses,
   the update and solution representations, and each external premise with its
   source, version, statement and verification status.
3. `result.json`: maintain a factual checkpoint with keys `status`
   (`in_progress`, `complete`, or `blocked`), `root_declaration` (`theorem_1`),
   `target_label` (`Theorem 1`), `remaining_obligations` (a list), and `blocker`
   (null, or an object with `kind`, `detail`, `evidence`). A complete report has
   no remaining obligations and is backed by the actual files and full build.
4. `warn.json` when source correspondence remains unverified. Never describe a
   conditional formal proof as independently certified primary-source fidelity.

Continue making concrete progress and repairing actual compiler errors until
the complete development is ready. Completing a preliminary lemma, compiling
a partial file, or writing a plan is not completion. Save useful partial work
and checkpoints during long runs. An ordinary unfinished subgoal or a difficult
proof is not a reason to mark the task complete or stop by choice.

There is no imposed total time, token, call or iteration budget. The supervisor
will resume this same session after an incomplete normal turn. If an actual
missing input, unavailable essential source statement, or broken tool requires
human intervention, record a concrete blocker with evidence and preserve all
work. User cancellation must be respected. A completed candidate still requires
independent semantic assessment; your self-report is not such an assessment.
