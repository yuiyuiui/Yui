# Frozen test target: nonempty compact product dimension

Approved by the user on 2026-10-23 (Asia/Shanghai). This explicitly adds
nonemptiness to the supplied Stein--Shakarchi exercise; the original screenshot
and literal transcription remain unchanged.

Let n be a nonnegative integer and let E be a nonempty compact subset of
Euclidean R^n. Put I=[0,1] in R. Equip E times I with the metric induced from
Euclidean R^(n+1), identifying (x,t) with its concatenated coordinate vector.
Prove

    dim_H(E times I) = dim_H(E) + 1.

Here dim_H is Hausdorff dimension. The pinned mathlib convention gives
dim_H(empty)=0; no empty-set exception is hidden in the theorem. The case
n=0 is included. A product/max-metric Lean representation is allowed only
with a justified correspondence to the displayed Euclidean metric.

The problem supplies no proof. First author a candidate natural-language proof,
then construct an independent complete NL0 relative to its explicitly declared
H/E/M sources, perform fresh Audit A, translate and assemble Lean, and perform
Audit B. No source theorem, formalization or acceptance result is assumed here.
