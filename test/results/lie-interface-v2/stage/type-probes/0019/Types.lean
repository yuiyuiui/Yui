import Mathlib
open scoped TensorProduct

noncomputable def dividedPower (V : Type*) [AddCommGroup V] [Module ℂ V]
    (f : V →ₗ[ℂ] V) (r : ℕ) : V →ₗ[ℂ] V :=
  ((Nat.factorial r : ℂ)⁻¹) • (f ^ r)

noncomputable def tensorAction {K : Type*} [Field K] {M : Type*} [AddCommGroup M]
    [Module ℤ M] (f : M →ₗ[ℤ] M) : K ⊗[ℤ] M →ₗ[K] K ⊗[ℤ] M :=
  TensorProduct.AlgebraTensorModule.lTensor K K f

def InvariantUnder (K : Type*) [Field K] (E : Type*) [AddCommGroup E] [Module K E]
    (f : E →ₗ[K] E) (W : Submodule K E) : Prop := ∀ z ∈ W, f z ∈ W

def LieIrreducible (K : Type*) [Field K] (E : Type*) [AddCommGroup E] [Module K E]
    (x y h : E →ₗ[K] E) : Prop :=
  Nontrivial E ∧ ∀ W : Submodule K E,
    InvariantUnder K E x W → InvariantUnder K E y W → InvariantUnder K E h W →
      W = ⊥ ∨ W = ⊤

structure LieLatticeData (lam : ℤ) (M : Type*) [AddCommGroup M] [Module ℤ M] where
  V : Type
  [vAdd : AddCommGroup V]
  [vMod : Module ℂ V]
  basisV : Module.Basis (Fin (lam.toNat + 1)) ℂ V
  basisM : Module.Basis (Fin (lam.toNat + 1)) ℤ M
  embed : M →ₗ[ℤ] V
  x y h : V →ₗ[ℂ] V
  xM yM hM : M →ₗ[ℤ] M
  v : V
  valid : Prop := True
  basisCompat : ∀ i, basisV i = embed (basisM i)
  embedInjective : Function.Injective embed
  bracket_hx : ∀ z, h (x z) - x (h z) = (2:ℂ) • x z
  bracket_hy : ∀ z, h (y z) - y (h z) = (-2:ℂ) • y z
  bracket_xy : ∀ z, x (y z) - y (x z) = h z
  highest_ne : v ≠ 0
  highest_x : x v = 0
  highest_h : h v = (lam : ℂ) • v
  x_compat : ∀ m, embed (xM m) = x (embed m)
  y_compat : ∀ m, embed (yM m) = y (embed m)
  h_compat : ∀ m, embed (hM m) = h (embed m)
  dividedX_stable : ∀ r m, ∃ m', embed m' = dividedPower V x r (embed m)
  dividedY_stable : ∀ r m, ∃ m', embed m' = dividedPower V y r (embed m)

set_option autoImplicit false
#check (∀ (K : Type*) [fK : Field K] (p : ℕ) (hp : Nat.Prime p) (lam : ℤ) (M : Type*) [aM : AddCommGroup M] [mM : Module ℤ M] (D : LieLatticeData lam M), D.valid)
#check (∀ (K : Type*) [fK : Field K] (p : ℕ) (hp : Nat.Prime p) (lam : ℤ) (M : Type*) [aM : AddCommGroup M] [mM : Module ℤ M] (D : LieLatticeData lam M), LieIrreducible K (K ⊗[ℤ] M) (tensorAction D.xM) (tensorAction D.yM) (tensorAction D.hM))
