# Yui

<p align="center"><img src="assets/yui-guitar.png" alt="Anime-style sunburst electric guitar" width="320"></p>

Yui is a multi-agent harness designed to make natural-language mathematical proofs rigorous. Its core workflow has two parts, with an optional unconditional formalization route.

## Public workflow

[Explore the illustrated workflow](workflow-guide/README.md) to follow each entry through its proof stages and exits. Open the [interactive HTML guide](workflow-guide/index.html) in a local checkout to navigate between diagrams and contracts.

| Request | Command options | Accepted delivery |
| --- | --- | --- |
| Natural-language audit | `--track nl0` | Frozen graph, local proofs and actual Audit A |
| Conditional Lean | `--track full --formalization conditional` | Audit B and the exported theorem under the listed external premises |
| Unconditional Lean | `--track full --formalization unconditional` | Checked discharge, or the conditional result explicitly selected for retained foundations |

Use these options with `python nl0/scripts/yui.py run PROOF --target 'FULL STATEMENT' --use-config-profiles`. Create the Python environment once from the repository root with `python3 -m venv .venv` and `.venv/bin/python -m pip install -r workflow/requirements.txt`. Run the CLI with that interpreter. The workflow definition drives execution, diagrams and generated tests. The [operator instructions](workflow/SKILL.md) describe the shared graph, checkpoints, output and maintenance checks.

The public result is in `RUN/delivery/`. It contains `formalization/`, `theorem_formalization_statement.json`, `nl0/` and `run.json`. A natural-language audit leaves the Lean directory and statement list empty. Use `yui.py verify-delivery RUN/delivery` for readback, and add `--comparator /path/to/comparator` for native proof comparison. Explicit `yui.py cleanup RUN --apply` preserves the delivery and checks it again after releasing owned resources.

## 1. How it works

### Natural-language auditing

Yui organizes the original proof into a proof graph, **NL0**, with explicit external theorems and reviewed background mathematics. Each proof node has a prescribed format, inputs and outputs. Its argument is rewritten and audited for hidden dependencies, using only its available inputs and justified routine background facts. A fixed Mathlib version is used in the formalization stage; exact Mathlib bindings for routine background steps are resolved there.

The completed NL0 is reviewed under **Audit A**. A pass produces an acceptance record and an NL0 proof considered rigorous within this natural-language auditing system. Audit A is model-based mathematical review, rather than a machine-checked proof.

### Conditional formalization

Yui freezes the global proof structure before local authoring, independently reviews and freezes the formal statements of the external theorems and target, and supplies the global information needed for formalization. This forms the intermediate layer.

The resulting proof nodes are then formalized concurrently. Workers can use NL0, the intermediate layer's global information, the optional [Mathlib library](library/README.md) and the [Lean strategy bank](nl02lean/bank/rule.md) to help with their proofs.

Once all nodes are complete, the Python controller assembles the proof, runs Lean and performs **Audit B**. It checks proof closure and that the actual external premises, target and relevant definitions agree with the reviewed, frozen intermediate layer. The result is a conditional Lean proof whose literature theorems remain explicit assumptions.

## 2. Efficiency and advantages

### Optional unconditional formalization

An explicit unconditional request uses
`2basis → the same NL0/Audit A → the same nl02lean/Audit B → b2lean`.
2basis rewrites the proof toward actual Mathlib/public Lean-library results and
concrete internal derivations, preparing the used Lean proofs and version
adapters. Before release, a separate reviewer compares the prepared statements
with their actual Lean propositions, sources and intended uses in one batch.
The shared Audit A checks both the original target and rewritten proof.
b2lean applies the prepared proofs, then compiles and inspects the actual final
export with only the original hypotheses. Unresolved textbook dependencies need
an explicit user choice; accepting them produces a conditional result.
See [the basis workflow](nl0/references/basis.md) for stages, records and errors.
This route is under development; existing benchmark numbers concern the
conditional workflow, not unconditional performance.

### Fast conditional formalization

Detailed tests and benchmark results are in [Yui-results](https://github.com/yuiyuiui/Yui-results). On a complete natural-language proof from a real research problem, the recorded end-to-end results were:

| Method | Elapsed time | Observed tokens |
| --- | ---: | ---: |
| Yui | 4 h 9 min | 282,760,473 |
| Pure model, including repair and acceptance review | 11 h 6 min | 248,548,201 |

In this benchmark, Yui completed the task **2.67 times as fast**, using **1.14 times as many observed tokens**. Both were configured for **gpt-6.1-sol / high / Standard**. Yui allowed 20 local workers; pure-model construction used one author session per run. The figures include the recorded repairs and reviews, and usage accounting is partial.

### Fast natural-language assurance

On the same input, NL0 writing and Audit A, including local repair, used:

| Stage | Elapsed time | Observed tokens |
| --- | ---: | ---: |
| Yui: NL0 + Audit A | About 34 min | 12,402,106 |

This stage took about **1/19.6 of the elapsed time** and **0.05 times the tokens** of the pure model's complete Lean formalization above. It produces audited NL0; there is no measured pure-model NL0-only baseline here.

If you do not want to spend as much effort on conditional formalization but are concerned about a proof's correctness, Yui's natural-language auditing system provides a quicker way to improve confidence in it.

### Preserving external-theorem and target interfaces

The benchmark showed that, for a long natural-language proof, a pure model can deliver substantially different external-theorem statements even when a strong model is explicitly asked to formalize the original external theorems with strict equivalence. In the author's experience, this has been a recurring problem, was more pronounced with GPT-5.6, and was not resolved simply by setting a goal. These are the author's observations, rather than a controlled comparison across models.

Yui's approach is to review and freeze the formal external theorems and target during intermediate-layer construction, when the workload is smaller and the model can focus on those statements. Final machine checks compare the delivered proof against the frozen interfaces, so downstream drift is surfaced rather than silently accepted. Fidelity to the original natural-language statements still depends on the independent semantic review before freezing.

## 3. Library and bank

[library](library/README.md) stores entries, each linked to a theorem in a particular Mathlib version. If your formalization work focuses on a specific field, you can collect frequently used Mathlib theorems there after repeated conditional formalization runs with Yui, to speed up retrieval. We have not yet demonstrated that a larger library produces a substantial speedup.

[bank](nl02lean/bank/rule.md) stores general strategies for writing Lean proofs and fixing errors. In the author's experience, some of these strategies have provided substantial speedups, but there is no guarantee that they will remain useful as models become stronger. After using Yui, users can try collecting the writing and repair strategies that the model spent time developing. So far, the author has curated only a small selection of broadly applicable strategies.

## 4. Installation and requirements

Install the complete repository as the **rigorous-proof** skill, keeping its runtime files beside `SKILL.md`:

```sh
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/yuiyuiui/Yui.git "$HOME/.agents/skills/rigorous-proof"
```

If you already have Yui installed under this skill name, use that installation instead of creating a duplicate. Restart Codex if the skill is not detected.

### Runtime

The current runtime requires:

- macOS, with its `sandbox-exec` isolation mechanism.
- An authenticated, compatible Codex CLI with its matching Code Mode helper.
- Python and ripgrep; reading PDFs also requires `pdftotext` or Python's `pypdf` package.
- Lean **4.32.2** and the matching pinned Mathlib environment described in [the toolchain configuration](toolchain/lock.json), installed separately.

Set `YUI_LEAN_ROOT` and `YUI_MATHLIB_ROOT` if these tools are installed outside the default locations under your home directory. `YUI_CODEX_BINARY` can select a Codex executable outside the normal search locations. Check the installation with:

```sh
python3 -B "$HOME/.agents/skills/rigorous-proof/nl0/scripts/yui.py" doctor
```

For first-time Codex and pinned Lean/Mathlib installation, follow the [local setup guide](docs/setup.md).

### Use

Open your proof's folder in local Codex and ask, for example:

```text
Use $rigorous-proof on proof.pdf through NL0/Audit A and Lean/Audit B.
Use gpt-6.1-sol/high/Standard for both phases, with 20 local workers.
```

For natural-language auditing alone, request **NL0 and Audit A only** and provide the model profile. When no worker count is specified, Yui uses one slot per R node for local Audit A review/repair, then one slot per T node for local Lean proofs, including shared lemmas and representation conversions. An explicit positive worker count caps each phase instead. Global authoring/review, preprocessing and postprocessing remain serial within a case; deduplication or checked reuse may reduce actual worker calls. Results are saved beside the input under `rigorous-proof/<run-id>/`. See the [operator guide](nl0/references/operation.md) for detailed configuration and controls, and [Yui-results](https://github.com/yuiyuiui/Yui-results) for test and benchmark reproduction prompts.

## 5. Limitations and next steps

1. **Unconditional formalization performance.** The optional basis/discharge route has software controls and native Lean regression fixtures. Its mathematical route selection, success rate and speed on substantial research proofs still require model-driven evaluation.

2. **Evaluating the division into proof nodes.** There is not yet a suitable evaluator for how a proof should be split. In observed runs, much of the parallel formalization time is spent on one particularly difficult node. Building a stable evaluator-optimizer for this division is a next step.

3. **Possible redundancy in NL0 and Audit A.** Strong models may not need all the information supplied by NL0. The older [nl0-detail branch](https://github.com/yuiyuiui/Yui/tree/nl0-detail) wrote a much more detailed NL0. In the author's development runs, substantially reducing the work spent on NL0 and Audit A was accompanied by a large reduction in intermediate-layer construction time, a small increase in node-formalization time, and a large decrease in total time. It may be possible to simplify NL0 and Audit A further. However, supplying less natural-language information could sharply increase the burden on weaker models. We do not yet have a good way to match model capability to the amount of natural-language detail it needs.

4. **A lightweight natural-language auditing system.** Much of the current NL0 work supplies information for formalization. A lighter system could audit complete natural-language proofs and also serve as a skill invoked periodically while a model is reasoning, checking local progress and reducing hallucinations.

## 6. References

Workflow design was informed by Anthropic's [Building effective agents](https://www.anthropic.com/research/building-effective-agents).

The logo and project name are inspired by Yui Hirasawa from *K-On!*.

The [MIT license](LICENSE) applies to original Yui code, documentation, strategy descriptions and other original project content. It does not grant rights to third-party material.

Lean, Mathlib, Codex and other external tools retain their own licenses and terms. They are not relicensed by Yui. Mathlib source excerpts and theorem-query output retain the applicable upstream attribution and license; see [Mathlib's license](https://github.com/leanprover-community/mathlib4/blob/master/LICENSE).

Original Yui metadata and strategy advice do not grant additional rights to the external material they describe. A source citation or a successful proof check is not a redistribution license.

### Final closure and recovery

Final basis discharge inspects the actual Lean declaration. It preserves levels
in the remaining parameters, hypotheses, approved residual assumptions and
conclusion, and instantiates only dependency-private levels at zero. Named
public levels, including composite `max`/`imax` levels, remain named; inferred
`Type*` levels are constrained by the actual arguments. The final standalone
proof still requires native compilation, full-signature comparison and
transitive axiom inspection. The v2 closure receipt uses this renderer; v1
receipts are revalidated with their original renderer.

After a verified software repair, an explicitly cancelled, exited, unlimited
normal-policy unconditional run whose only remaining failure is
`BASIS_FINAL_CLOSURE_FAILED` can reuse its accepted basis and Audit B:

```sh
python3 -B nl0/scripts/yui.py resume OLD_RUN --repair-basis-closure --prepare-only
python3 -B nl0/scripts/yui.py execute NEW_RUN --detach
```

Preparation checks the original documents, target, prepared proofs, frozen
interface, accepted Audit B and prior failure. It rejects live owners, pending
incidents and changed evidence. Execution uses a fresh immutable runtime and
only reruns the final native closure; no author or reviewer is called. It
preserves the old run and its costs, records recovery provenance, and rechecks
the authority before publishing. Source qualifications and approved residual
assumptions remain conditional. Each fresh run can execute only once; an
existing output is never overwritten. Use ordinary cancellation and owned
cleanup for the new run.
