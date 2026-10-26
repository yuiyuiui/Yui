# Conservation of energy for a sphere-valued wave map

## Original exercise

Lawrence C. Evans, *Partial Differential Equations*, second edition,
Graduate Studies in Mathematics 19, AMS, 2010, section 12.6, exercise 14,
printed page 694. The preceding exercise 13 defines the sphere-valued
wave map. ISBN: 978-0-8218-4974-3.

> 14. Prove that if \(\mathbf u\) is a wave map into the unit sphere,
> with compact support in space, we have conservation of energy:
> \[
> \frac{d}{dt}\int_{\mathbb R^n}
>       |\mathbf u_t|^2+|D\mathbf u|^2\,dx=0.
> \]

## Fixed interpretation and complete target

A sphere-valued map cannot vanish outside a compact set. As approved by
the user on 2026-10-23, interpret spatial compact support as compact support
of a perturbation from a **fixed unit vector**, locally uniformly in time.
This is a disclosed nontrivial interpretation, not a claimed author-issued
correction.

Let \(n,m\geq1\) be integers and let
\(u:\mathbb R^n\times(0,\infty)\to\mathbb R^m\) be jointly smooth.
Fix \(q\in\mathbb R^m\) with \(|q|=1\). Assume:

1. \(|u(x,t)|=1\) for all \(x\) and \(t>0\).
2. The acceleration \(u_{tt}-\Delta_xu\) is normal to the sphere at
   \(u\): at each point there is a real scalar \(a(x,t)\) with
   \(u_{tt}-\Delta_xu=a u\). No regularity of the selected scalar is
   assumed.
3. For every \(0<s<t<\infty\), a compact set
   \(C_{[s,t]}\subset\mathbb R^n\) exists such that \(u(x,r)=q\) for
   \(x\notin C_{[s,t]}\), \(r\in[s,t]\).

With Euclidean norms and Lebesgue measure, define

\[
e(x,t)=|u_t(x,t)|^2+\sum_{j=1}^n|\partial_{x_j}u(x,t)|^2,
\qquad E(t)=\int_{\mathbb R^n}e(x,t)\,dx.
\]

The spatial gradient square is the Frobenius square, and
\(\Delta_xu=\sum_j\partial_{x_jx_j}u\) component by component.
Prove integrability of \(e(\cdot,t)\), differentiability of \(E\),
and \(E'(t)=0\) for every \(t>0\). No assertion at time zero is required.

## Fixed natural-language proof

### 1. Tangency and the wave-map equation

Differentiate \(u\cdot u=1\) in time. The product rule gives
\(2u\cdot u_t=0\), so

\[
u\cdot u_t=0,\qquad
u_t\cdot(u_{tt}-\Delta_xu)=a(u_t\cdot u)=0.          \tag{1}
\]

No derivative of \(a\) is needed. The familiar explicit equation also
follows from the assumptions: twice differentiating the unit constraint
gives \(u\cdot u_{tt}=-|u_t|^2\) and
\(u\cdot\partial_{x_jx_j}u=-|\partial_{x_j}u|^2\).
Dotting the normality equation with \(u\), using \(|u|^2=1\), yields
\(a=\sum_j|\partial_{x_j}u|^2-|u_t|^2\). This is a consequence,
not an additional PDE assumption.

### 2. Common compact support and integrability

Fix \(t_0>0\), put \(J=[t_0/2,3t_0/2]\), and choose its compact
spatial set \(C\) from assumption 3. Since \(C\) is bounded, choose
\(R>0\) with \(C\subset(-R,R)^n\) and set \(Q=[-R,R]^n\).
The box has finite Lebesgue measure \((2R)^n\).

On the open set \((\mathbb R^n\setminus C)\times\operatorname{int}J\),
the map equals the constant \(q\), so all its positive-order
derivatives vanish. At interior times, \(e\), \(e_t\), and the
derivative products used below consequently vanish outside \(C\).
They are continuous by smoothness; their spatial sections are measurable,
bounded on \(Q\), and supported there. Their absolute integrals are
bounded by a finite constant times \(|Q|\). This proves integrability
of \(e(\cdot,t_0)\) and of all later terms. Since \(t_0\) was arbitrary,
the energy is a finite, well-defined integral at every positive time.

### 3. Differentiate the energy integral

The product rule and equality of mixed derivatives give

\[
e_t=2u_t\cdot u_{tt}
   +2\sum_{j=1}^n\partial_{x_j}u\cdot\partial_{x_j}u_t.           \tag{2}
\]

Choose \(\eta>0\) so that
\([t_0-\eta,t_0+\eta]\subset\operatorname{int}J\).
Continuity of (2) on the compact box
\(Q\times[t_0-\eta,t_0+\eta]\) gives a finite bound \(|e_t|\leq B\).
For \(0<|h|<\eta\), the one-variable mean value theorem at fixed
\(x\) therefore gives

\[
\left|\frac{e(x,t_0+h)-e(x,t_0)}h\right|
\leq B\mathbf1_Q(x).
\]

Outside \(Q\), both densities vanish, so the bound holds throughout
\(\mathbb R^n\). The right side is integrable. The difference
quotients converge pointwise to \(e_t(x,t_0)\). Dominated convergence
and linearity for these integrable functions now prove

\[
E'(t_0)=\int_{\mathbb R^n}e_t(x,t_0)\,dx.            \tag{3}
\]

This establishes differentiability of the actual finite integral.

### 4. Integration by parts and cancellation

For each spatial index \(j\), at time \(t_0\) put
\(g_j(x)=u_t(x,t_0)\cdot\partial_{x_j}u(x,t_0)\).
It is smooth and vanishes on a neighborhood of the boundary of \(Q\),
because \(C\subset\operatorname{int}Q\). The product rule gives

\[
\partial_{x_j}g_j
=\partial_{x_j}u_t\cdot\partial_{x_j}u
 +u_t\cdot\partial_{x_jx_j}u.
\]

Integrate first over \(x_j\in[-R,R]\) at fixed remaining coordinates.
The fundamental theorem of calculus gives zero because both endpoint
values of \(g_j\) are zero. Fubini applies on \(Q\) because the
derivative and its two summands are continuous and bounded on a
finite-measure box. Thus \(\int_Q\partial_{x_j}g_j=0\).
All these terms vanish outside \(Q\), so

\[
\int_{\mathbb R^n}\partial_{x_j}u\cdot\partial_{x_j}u_t\,dx
=-\int_{\mathbb R^n}u_t\cdot\partial_{x_jx_j}u\,dx.              \tag{4}
\]

Every integral is finite by step 2. Sum (4) over the finitely many
spatial indices and substitute (2) into (3):

\[
\begin{aligned}
E'(t_0)
&=2\int_{\mathbb R^n}u_t\cdot u_{tt}\,dx
 -2\sum_{j=1}^n\int_{\mathbb R^n}u_t\cdot\partial_{x_jx_j}u\,dx\\
&=2\int_{\mathbb R^n}u_t\cdot(u_{tt}-\Delta_xu)\,dx=0,
\end{aligned}
\]

by (1). This holds at every \(t_0>0\). Hence \(E\) is differentiable
with zero derivative on \((0,\infty)\), and is constant there by the
mean value theorem. This is conservation of energy with exactly the
normalization in the exercise.

## Input status

This file fixes the exercise, the approved support interpretation and the
supplied proof. It is not an NL0 artifact, an Audit A receipt, a Lean proof,
or a passing test result. Future runs must construct and check those
artifacts from this input, explicitly registering the calculus and
integration sources they use.
