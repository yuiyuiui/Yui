# Mathematical full-workflow tests

The three user-selected exercises are geometry-product-dimension, lie-module-irreducibility and wave-map-energy. Each retains the supplied screenshot, literal transcription and explicit source context. They are not substituted by easier propositional examples.

Current mathematical status: no full case pass. The geometry/PDE cases now use
the user-approved nonempty-set and sphere-relative-support conventions. Their
complete statements and hashes are frozen in each case directory. The Lie
exercise is Humphreys GTM 9, section 27, exercise 7; isolated proof/NL0 attempts
ran, but its author stopped before acceptance. The wave-map revision reached
structural validity and then failed actual Audit A; final Lean/B were blocked. See
[the detailed report](results/REPORT.md) and [machine status](results/status.json).
No altered interpretation is counted as the original exercise.

After context is frozen, use clean model stages for a supplied proof, NL0, actual Audit A, source preparation, typed Lean interfaces, proof workers, assembly and actual Audit B. Reference solutions and developer history are withheld. Structural controls and partial Lean fragments are reported separately from full-workflow success.

Selected model: gpt-6-luna / high / Standard. Concurrency: default auto, with the resolved bound and actual peak recorded.

## Acceptance

A full case pass requires the exact approved target, a structurally complete
NL0, an actually completed current Audit A, assembled Lean proofs, and an
actually completed Audit B establishing source correspondence and kernel
closure. A candidate proof, valid JSON, checked local lemma, successful source
probe or model self-report is not a full pass. A failed or UNVERIFIED A review
blocks translation; an external theorem remains an explicit premise unless
its Lean proof is supplied separately.

Execution health and measurement validity are separate from mathematical
acceptance. Record clean transmitted inputs/tools/model, all actual stage
usage, failures and unresolved coverage. A normal healthy deadline without an
accepted result is MODEL_BUDGET_EXHAUSTED for that attempt/configuration. An
early model stop is not budget exhaustion or proof that the exercise is wrong.
Source/format completion failures must not be presented as substantive gaps.

The current records are development iterations. Fresh model contexts may
receive explicit earlier candidate artifacts and actual review feedback from
the same case. Those repairs are disclosed warm continuations, not independent
cold repetitions or a performance comparison.
