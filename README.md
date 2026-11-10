# Yui

<p align="center"><img src="assets/yui-guitar.png" alt="Sunburst electric guitar" width="320"></p>

Yui is a multi-agent harness for formalizing mathematical proofs in Lean 4. Give it a theorem and its natural-language proof, then choose unconditional formalization, fast conditional formalization or a natural-language audit. [Illustrated workflow](workflow-guide/README.md)

## 1. Unconditional formalization

Use this workflow when you want a Lean proof under the theorem’s original hypotheses. Yui first identifies the mathematical results it needs to establish the target.

- **Reusable strategy banks.** Authors can consult techniques from earlier formalizations when a problem calls for them. For example, to bound the cost of two successive subroutines, the proof may need a bound on the size of the first subroutine’s output, since that is the second subroutine’s input. The foundation bank covers proof choices like this. The Lean bank covers implementation techniques such as controlling expensive unfolding. [Foundation strategies](nl0/basis-bank/README.md) · [Lean strategies](nl02lean/bank/rule.md)
- **Use classical textbook theorems to find a simpler proof.** While planning in natural language, Yui can look for a standard theorem that simplifies the main argument, even if the original proof never cites it. For example, a long estimate for exchanging a limit and an integral may give way to an application of the dominated convergence theorem. For a sequence of measurable functions, this route calls for almost-everywhere convergence and a common integrable bound. Yui then looks for Lean proofs of the results it uses in Mathlib or other public Lean libraries, or builds them from simpler lemmas. [Foundation planning](nl0/references/basis-planning.md)

The proof route can change while the target and its original hypotheses stay fixed. Independent reviewers check that the Lean statements express the intended mathematics. Before accepting an unconditional result, Yui compares the actual exported theorem with the reviewed target, checks that every extra premise has been discharged, and inspects the axioms the proof uses. If a cited theorem is still needed as an extra premise, you can ask Yui to keep working, stop, or explicitly accept a conditional result.

## 2. Fast conditional formalization

Use this workflow when you are willing to assume named results from the literature. Yui reviews their Lean statements, fixes the inputs and output of each proof step, and assigns independent steps to parallel Lean authors. It then assembles the proof and checks the exported theorem against the reviewed statements in **Audit B**. The delivery lists the external theorems that remain as premises.

## 3. Natural-language audit

Use this workflow to review a proof before investing in Lean formalization. Yui builds a proof graph (**NL0**) that records what each step assumes and what it establishes. In **Audit A**, independent reviewers check the overall argument and each local deduction. You receive the graph and the review outcome.

## 4. Installation and requirements

Yui runs on macOS and uses an authenticated Codex CLI with its matching Code Mode helper, Python, ripgrep, and a pinned Lean and Mathlib toolchain. Install the complete repository as the `rigorous-proof` skill and check the environment. The setup guide covers the required tools and PDF support. [Local setup](docs/setup.md)

```sh
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/yuiyuiui/Yui.git "$HOME/.agents/skills/rigorous-proof"
cd "$HOME/.agents/skills/rigorous-proof"
python3 -m venv .venv
.venv/bin/python -m pip install -r workflow/requirements.txt
.venv/bin/python -B nl0/scripts/yui.py doctor
```

### Use

Open the folder containing your proof in Codex and ask, for example, `Use $rigorous-proof to formalize Theorem 1 in proof.pdf unconditionally.` You can also start the workflow from the repository root using the CLI.

```sh
.venv/bin/python -B nl0/scripts/yui.py run /path/to/proof.pdf \
  --target 'Full statement of the theorem' --use-config-profiles \
  --track full --formalization unconditional
```

For conditional formalization, use `--track full --formalization conditional`. For a natural-language audit alone, use `--track nl0`. The accepted artifacts and the recorded outcome are in `RUN/delivery/`. Use `yui.py verify-delivery RUN/delivery` to check them. [Operator guide](workflow/SKILL.md)

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
