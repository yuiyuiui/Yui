# Paper-scale benchmark

No papers have been selected and no benchmark scores are available.

The comparison arms are direct Lean translation, Yui with a single model stage at a time, and Yui with default resolved parallelism. All arms must use the same frozen original proof, mathematical inputs, permitted external results, model profile, tools and final acceptance standard.

Report success and healthy budget exhaustion separately from execution faults. Record repetitions, wall time, phase costs, all-agent input/cached/output/reasoning/total tokens, failed attempts, measured usage coverage, model/toolchain versions and requested/observed concurrency. Preparation and audits belong to whole-workflow cost. A fixed-NL0 translation-only comparison is an additional separately labelled experiment.

The default selected model is gpt-6-luna / high / Standard. A different model requires an explicit separately recorded configuration; there is no automatic upgrade. See ../rigorous-proof/references/measurement.md.

Use `result.schema.json` for eventual records. Counts must additionally satisfy
the runtime ledger invariants: total=input+output, cached<=input, reasoning<=output.
The schema does not authenticate semantic acceptance or measurements. Preserve
failed attempts and their raw ledgers beside successful ones.

The current `run_graph.py --arm direct` is a control on an already supplied
frozen Lean obligation. It is not an original-paper direct baseline: reusing
Yui's decomposition or typed preparation there would change the comparison.
The eventual original-proof direct arm must author its own implementation from
the same source material, with the same final acceptance review. Its preparation
is counted. No full three-arm paper campaign runner or benchmark result is
claimed by the present configuration file.
