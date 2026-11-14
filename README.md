# Yui

<p align="center"><img src="assets/yui-guitar.png" alt="Sunburst electric guitar" width="320"></p>

Yui is a multi-agent harness for formalizing mathematical proofs in Lean 4. Give it a theorem and its natural-language proof, then choose unconditional formalization, fast conditional formalization or a natural-language audit. [Illustrated workflow](workflow-guide/README.md)

## 1. Unconditional formalization

Use this workflow when you want a Lean proof under the theorem’s original hypotheses. Yui has two special features.

- **Reusable strategy banks.** Authors can consult techniques from earlier formalizations when a problem calls for them. One bank is for searching for proof graphs. Some difficult tasks like computational complexity theorem may benefit from it. Another bank is for translating to Lean code. [Foundation strategies](nl0/basis-bank/README.md) · [Lean strategies](nl02lean/bank/rule.md)
- **Use classical textbook theorems to find a basis proof.** Yui first directly finds proof paths not rooted in mathlib but foundation theorems in classical textbooks to shorten the paths length and lower the difficulty of searching for a proof graph. Then it finds Lean proofs for these theorems. [Foundation planning](nl0/references/basis-planning.md)

The proof route can change while the target and its original hypotheses stay fixed. The formalization author explains how the Lean expression matches the original theorem, and independent reviewers check that correspondence.

## 2. Fast conditional formalization

Use this workflow when you are willing to assume named results from the literature. Yui reviews their Lean statements, fixes the inputs and output of each proof step, and assigns independent steps to parallel Lean authors. It then assembles the proof and checks the exported theorem against the reviewed statements in **Audit B**. The delivery lists the external theorems that remain as premises.

The benchmark compares both methods on the complete natural-language proof of Theorem 1 in the paper on the Li–Wu KdV integrator (AIM problem 518). Both proofs keep the cited literature theorems as explicit assumptions.

| Method | Elapsed time (hh:mm:ss) | Observed input + output tokens |
| --- | ---: | ---: |
| Yui | 04:09:26 | 282,760,473 |
| Pure model, including repair and acceptance review | 11:06:03 | 248,548,201 |

Yui completed this benchmark **2.67 times as fast**, using **13.8% more observed tokens**. Both methods requested **gpt-6.1-sol / high / Standard**. In this benchmark, Yui allowed up to 20 local workers, while pure-model construction used one author session per run. Token accounting was partial.

## 3. Natural-language audit

You can use this workflow to review a proof just in natural language level with low time and tokens cost. Yui builds a proof graph (**NL0**) that records what each step assumes and what it establishes. In **Audit A**, independent reviewers check the overall argument and each local deduction. You receive the graph and the review outcome.

## 4. Installation and requirements

After downloading Yui, ask Codex to execute [the local adaptation entry](setup/README.md), then start using the skill.

### Use

Open the folder containing your proof in Codex and ask, for example, `Use $rigorous-proof to formalize Theorem 1 in proof.pdf unconditionally.` You can also start the workflow from the repository root using the CLI.

```sh
.venv/bin/python -B nl0/scripts/yui.py run /path/to/proof.pdf \
  --target 'Full statement of the theorem' --use-config-profiles \
  --track full --formalization unconditional
```

For conditional formalization, use `--track full --formalization conditional`. For a natural-language audit alone, use `--track nl0`. [Operator guide](workflow/SKILL.md)

Yui saves the outcome and its supporting files in the run’s `delivery/` directory. To check the files against the recorded outcome, run the following command from the root of your Yui installation. Replace the example path with your delivery directory.

```sh
.venv/bin/python -B nl0/scripts/yui.py verify-delivery "/path/to/your/run/delivery"
```

### Final closure and recovery

If a controller fault interrupted only the final discharge, Yui can reuse the checked foundations and Audit B after the fault has been fixed. For an explicitly cancelled, exited, unlimited normal-policy run with `BASIS_FINAL_CLOSURE_FAILED`, prepare a new run from that checkpoint and execute it.

```sh
.venv/bin/python -B nl0/scripts/yui.py resume OLD_RUN --repair-basis-closure --prepare-only
.venv/bin/python -B nl0/scripts/yui.py execute NEW_RUN --detach
```

## Tests and benchmarks

The three unconditional formalization tests, the three conditional formalization tests and the benchmarks are available at <https://github.com/yuiyuiui/Yui-results>.

## Credits and license

The name and guitar artwork are inspired by Yui Hirasawa from *K-On!*. Yui’s original code and documentation are available under the [MIT license](LICENSE).

## References

- The algorithm for pruning proof dependencies draws on [SHEAF](https://github.com/frenzymath/SHEAF).
- The workflow scheduling design draws on [MIPStarRE](https://github.com/LionSR/MIPStarRE).
- The agent workflow also draws on Anthropic’s [Building effective agents](https://www.anthropic.com/research/building-effective-agents).
