# Frozen test target: wave-map energy with compactly supported perturbation

Approved by the user on 2026-10-23 (Asia/Shanghai). The support condition below
is an explicit nontrivial interpretation of Evans, second edition, section
12.6, exercise 14. The original screenshot and transcription are unchanged.

Let n,m be positive integers. Let u:R^n times (0,infinity) -> R^m be jointly
smooth, and let q in R^m have Euclidean norm one. Assume:

1. For every x and t>0, the Euclidean norm of u(x,t) is one.
2. At each (x,t), the acceleration u_tt(x,t)-Delta_x u(x,t) is normal to the
   unit sphere at u(x,t). Explicitly, there exists a real scalar a(x,t) for
   which u_tt(x,t)-Delta_x u(x,t)=a(x,t)u(x,t). No regularity of a is assumed.
3. For every finite closed interval [s,t] contained in (0,infinity), there is
   a compact set C_[s,t] in R^n such that u(x,r)=q whenever x is outside that
   set and r belongs to [s,t]. The compact set may depend on the time window.

For r>0 define the scalar energy density and energy by

    e(x,r) = ||u_t(x,r)||^2 + sum_(j=1)^n ||partial_(x_j) u(x,r)||^2,
    E(r) = integral_(R^n) e(x,r) dx,

where dx is Lebesgue measure, all vector norms are Euclidean, and Delta_x is
the sum of the second spatial partial derivatives, component by component.
Thus the spatial-gradient square is the Frobenius/Hilbert--Schmidt square,
not the operator norm of the Jacobian.

Prove that e(.,r) is Lebesgue integrable for every r>0, that E is differentiable
at every such r, and that E'(r)=0 there. Integrability and differentiability
make the displayed conservation law well defined; a totalized nonintegrable
integral returning zero is not an accepted solution. No assertion at the
endpoint r=0 is part of this test.

The scalar-multiple condition explicitly spells out the sphere normal used in
exercise 13. If the familiar wave-map PDE is used instead, justify it from
these hypotheses; do not silently add it as a stronger hypothesis. The fixed
vector q is independent of x and time. Compact support of u itself is not
assumed.

The problem supplies no proof or auxiliary calculus theorems. First author a
candidate proof, then complete NL0/Audit A and Lean/Audit B with every actual
source registered. This file contains no proof or acceptance verdict.
