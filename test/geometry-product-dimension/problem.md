# Hausdorff dimension of a product with an interval

## Original exercise

Elias M. Stein and Rami Shakarchi, *Real Analysis: Measure Theory,
Integration, and Hilbert Spaces*, Princeton Lectures in Analysis III,
Chapter 7, Problems, exercise 9, printed page 388.
Book DOI: [10.1515/9781400835560](https://doi.org/10.1515/9781400835560).

> 9. Let \(E\) be a compact set in \(\mathbb R^{d-1}\). Show that
> \(\dim(E\times I)=\dim(E)+1\), where \(I\) is the unit interval in
> \(\mathbb R\).

## Fixed interpretation and complete target

Here dimension means **Hausdorff dimension**. As approved by the user on
2026-10-23, assume explicitly that \(E\) is nonempty. With the convention
\(\dim_H\varnothing=0\), the printed equality would otherwise fail for
the empty set. This is a disclosed addition to the printed exercise.

Let \(n\geq0\) be an integer, let \(E\subset\mathbb R^n\) be a nonempty
compact set, and put \(I=[0,1]\). Identify \(\mathbb R^n\times\mathbb R\)
with \(\mathbb R^{n+1}\) and use its Euclidean metric. Prove

\[
\dim_H(E\times[0,1])=\dim_H E+1.
\]

The zero-dimensional ambient space \(\mathbb R^0\) is included. A later
formalization using a different product norm must justify the metric change.

## Fixed natural-language proof

For a Euclidean set \(A\), exponent \(s>0\), and scale \(\delta>0\), put

\[
H^s_\delta(A)=\inf\left\{\sum_i(\operatorname{diam}U_i)^s:
 A\subseteq\bigcup_iU_i,\quad\operatorname{diam}U_i\leq\delta\right\},
\qquad H^s(A)=\sup_{\delta>0}H^s_\delta(A).
\]

Covers are countable, with empty members contributing zero. This
unnormalized Hausdorff measure gives the usual Hausdorff dimension. We use
its critical-exponent characterization: \(H^s(A)=0\) if
\(s>\dim_H A\), and \(H^s(A)=\infty\) if \(0<s<\dim_H A\).
Conversely, zero measure implies \(\dim_H A\leq s\), and infinite
measure implies \(\dim_H A\geq s\).

Write \(D=\dim_H E\) and \(F=E\times[0,1]\). First \(0\leq D\leq n\).
Indeed, compactness makes \(E\) bounded. When \(n>0\), a box containing
it admits a cover by at most \(Ch^{-n}\) cubes of side at most \(h\),
for \(0<h\leq1\). Here \(C\) depends only on that box. Each cube has
diameter at most \(\sqrt n h\). For any \(s>n\), the total \(s\)-cost
is at most \(C n^{s/2}h^{s-n}\to0\). These arbitrarily fine covers
give \(H^s(E)=0\) and hence \(D\leq n\). If \(n=0\), nonemptiness
makes \(E=\mathbb R^0\), a singleton of zero \(s\)-cost for every
\(s>0\); thus \(D=0\).

### Upper bound

When \(n=0\), \(F\) is isometric to \([0,1]\). Dividing this interval
into \(N\) equal pieces gives total \(a\)-cost \(N^{1-a}\to0\) for
every \(a>1\), proving \(\dim_H F\leq1=D+1\).
For this upper-bound argument now assume \(n\geq1\).

Fix \(q>D\). Since \(q>0\) and \(H^q(E)=0\), for every
\(0<r\leq1\) and \(\varepsilon>0\) there is a countable cover
\((U_i)\) of \(E\) with nonempty-member diameters
\(0<r_i\leq r\) and \(\sum_i r_i^q<\varepsilon\).
The positive-diameter requirement costs nothing: start with a cover of
cost below \(\varepsilon/2\); replace each zero-diameter singleton by
a ball of diameter at most \(r\), choosing the \(i\)-th replacement
to have \(q\)-cost less than \(\varepsilon2^{-i-2}\). The added cost
is less than \(\varepsilon/2\). Discard empty members.

Let \(N_i=\lceil1/r_i\rceil\). Partition \([0,1]\) into \(N_i\)
closed intervals of length \(1/N_i\leq r_i\). Because \(r_i\leq1\),
\(N_i\leq2/r_i\). The corresponding products with \(U_i\) form a
countable cover of \(F\). Each has Euclidean diameter at most
\(\sqrt2 r_i\), and their total \((q+1)\)-cost is at most

\[
\sum_iN_i(\sqrt2 r_i)^{q+1}
\leq2(\sqrt2)^{q+1}\sum_i r_i^q
<2(\sqrt2)^{q+1}\varepsilon.
\]

For any target scale \(\delta>0\), choose
\(r\leq\min(1,\delta/\sqrt2)\), then let \(\varepsilon\downarrow0\).
Thus \(H^{q+1}_\delta(F)=0\) for every scale, so
\(H^{q+1}(F)=0\) and \(\dim_H F\leq q+1\). Letting \(q\downarrow D\)
gives \(\dim_H F\leq D+1\).

### Lower bound when \(D>0\)

Fix \(0<s<D\). Then \(H^s(E)=\infty\), so
\(H^s_\delta(E)\) becomes arbitrarily large as \(\delta\downarrow0\).
We claim that, for every \(\delta>0\),

\[
H^s_\delta(E)\leq H^{s+1}_\delta(F).                 \tag{1}
\]

Take an arbitrary countable \(\delta\)-cover \((V_i)_{i\geq0}\) of
\(F\), discarding empty members. Define
\(\rho_i=\operatorname{diam}V_i\),
\(A_i=\pi_{\mathbb R^n}(V_i)\), and
\(B_i=\pi_{\mathbb R}(V_i)\). Coordinate projections are 1-Lipschitz,
so both projected diameters are at most \(\rho_i\leq\delta\).
For \(\varepsilon>0\), put

\[
\eta_i=\frac{\varepsilon2^{-i-1}}{1+\rho_i^s}>0.
\]

Enclose \(B_i\) in an open interval \(J_i\) of length at most
\(\rho_i+\eta_i\): its supremum minus infimum is at most \(\rho_i\),
and an enlargement of total width \(\eta_i\) suffices. This avoids
assuming that the arbitrary covering sets or their projections are measurable.

For each \(t\in[0,1]\), the sets \(A_i\) for which \(t\in J_i\)
cover \(E\). Indeed, a point \((x,t)\in F\) belongs to some \(V_i\),
giving \(x\in A_i\) and \(t\in B_i\subset J_i\). Their diameters
are at most \(\rho_i\). Consequently, with \(c=H^s_\delta(E)\),

\[
c\leq\sum_i\rho_i^s\mathbf1_{J_i}(t)\quad(t\in[0,1]).
\]

The constant \(c\) is finite: compactness gives a finite cover of \(E\)
by balls of diameter at most \(\delta\), with finite \(s\)-cost.
Each summand is nonnegative and measurable since \(J_i\) is open.
Integrate over \([0,1]\), of Lebesgue measure one, and use Tonelli's
theorem for this nonnegative series. Since
\(|J_i\cap[0,1]|\leq\rho_i+\eta_i\),

\[
\begin{aligned}
c&\leq\sum_i\rho_i^s|J_i\cap[0,1]|\\
 &\leq\sum_i\rho_i^{s+1}+\sum_i\eta_i\rho_i^s
 \leq\sum_i\rho_i^{s+1}+\varepsilon.
\end{aligned}
\]

If the first series is infinite the desired inequality is immediate;
otherwise let \(\varepsilon\downarrow0\). Take the infimum over the
arbitrary covers to obtain (1). As its left side is unbounded at small
scales, \(H^{s+1}(F)=\infty\), giving \(\dim_H F\geq s+1\).
Letting \(s\uparrow D\) proves \(\dim_H F\geq D+1\).

### Lower bound when \(D=0\)

Choose \(x_0\in E\). The map \(t\mapsto(x_0,t)\) is an isometric
embedding of \([0,1]\) into \(F\), so dimension monotonicity gives
\(\dim_H F\geq\dim_H[0,1]\). This interval has dimension one:
equal-length covers gave the upper bound above. For \(0<s<1\), any
\(\delta\)-cover with diameters \(\rho_i\leq\delta\) satisfies
\(\sum_i\rho_i\geq1\). To see this, enclose its nonempty members
in open intervals of lengths at most \(\rho_i+\varepsilon2^{-i-1}\),
use countable subadditivity of length to get
\(1\leq\sum_i\rho_i+\varepsilon\), and let \(\varepsilon\downarrow0\).
Hence \(\sum_i\rho_i^s\geq\delta^{s-1}\sum_i\rho_i
\geq\delta^{s-1}\to\infty\) as \(\delta\downarrow0\).
This proves the lower bound one. Thus \(\dim_H F\geq1=D+1\),
including when \(n=0\).

Together the bounds establish the required equality.

## Input status

This file fixes the problem, conventions and supplied proof route for future
tests. It is a natural-language input, not an NL0 artifact, an Audit A receipt,
a Lean proof, or a passing test result. Future runs must independently produce
and check those artifacts. The basic Hausdorff-measure and integration facts
used here must be registered by that future NL0/Audit A workflow.
