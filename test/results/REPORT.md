# Mathematical test status

**Full-workflow acceptance: 0/3.** The private repository is a development
candidate; the selected exercises have not passed NL0/Audit A/Lean/Audit B.
Software regressions and source-signature probes are separate checks.

| Case | Frozen target | NL0 structure | Actual Audit A | Final Lean / Audit B |
| --- | --- | --- | --- | --- |
| Geometry: product Hausdorff dimension | User-approved nonempty compact E | Not accepted | Not run | Not run |
| Lie module: Humphreys GTM 9 §27 exercise 7 | Arbitrary admissible lattice, including p=2 and lambda=0 | Not accepted | Not run | Not run |
| Wave-map energy | User-approved locally uniform compact support of u-q | Accepted, revision v6 | Not passed | Not run; gate correctly blocked |

Read the [detailed continuation report](context-confirmation-v1/REPORT.md) and
[current machine status](status.json). The [initial report](REPORT.initial.md)
is retained as a historical snapshot; its then-pending target questions have
now been answered. Every failed attempt and its actual source/prompt/log/usage
remains in its own directory.

These are development iterations, not a three-arm benchmark or independent cold
repetitions. No acceleration, reliable success rate, or completed mathematical
case is claimed.
