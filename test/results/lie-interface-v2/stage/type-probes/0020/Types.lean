import Mathlib
open scoped TensorProduct
noncomputable def dividedPower (V : Type*) [AddCommGroup V] [Module ℂ V]
    (f : V →ₗ[ℂ] V) (r : ℕ) : V →ₗ[ℂ] V := ((Nat.factorial r : ℂ)⁻¹) • (f ^ r)
noncomputable def tensorAction {K : Type*} [Field K] {M : Type*} [AddCommGroup M]
    [Module ℤ M] (f : M →ₗ[ℤ] M) : K ⊗[ℤ] M →ₗ[K] K ⊗[ℤ] M :=
  TensorProduct.AlgebraTensorModule.lTensor K K f
structure LieLatticeData (lam : ℤ) (M : Type*) [AddCommGroup M] [Module ℤ M] where
  V : Type
  [vAdd : AddCommGroup V]
  [vMod : Module ℂ V]
  basisV : Module.Basis (Fin (lam.toNat + 1)) ℂ V
  basisM : Module.Basis (Fin (lam.toNat + 1)) ℤ M
  embed : M →ₗ[ℤ] V
  x : V →ₗ[ℂ] V
  y : V →ₗ[ℂ] V
  z : V →ₗ[ℂ] V
  xM : M →ₗ[ℤ] M
  yM : M →ₗ[ℤ] M
  zM : M →ₗ[ℤ] M
  v : V
  basisCompat : ∀ i, basisV i = embed (basisM i)
  embedInjective : Function.Injective embed
  bracket_hx : ∀ w, z (x w) - x (z w) = (2:ℂ) • x w
  bracket_hy : ∀ w, z (y w) - y (z w) = (-2:ℂ) • y w
  bracket_xy : ∀ w, x (y w) - y (x w) = z w
  highest_ne : v ≠ 0
  highest_x : x v = 0
  highest_h : z v = (lam : ℂ) • v
  x_compat : ∀ m, embed (xM m) = x (embed m)
  y_compat : ∀ m, embed (yM m) = y (embed m)
  z_compat : ∀ m, embed (zM m) = z (embed m)
  dividedX_stable : ∀ r m, ∃ m', embed m' = dividedPower V x r (embed m)
  dividedY_stable : ∀ r m, ∃ m', embed m' = dividedPower V y r (embed m)

set_option autoImplicit false
#check (∀ (K : Type*) [fK : Field K] (p : ℕ) (hp : Nat.Prime p) (lam : ℤ) (M : Type*) [aM : AddCommGroup M] [mM : Module ℤ M] (D : LieLatticeData lam M), D.basisCompat)
#check (∀ (K : Type*) [fK : Field K] (p : ℕ) (hp : Nat.Prime p) (lam : ℤ) (M : Type*) [aM : AddCommGroup M] [mM : Module ℤ M] (D : LieLatticeData lam M), LieIrreducible K (K ⊗[ℤ] M) (tensorAction D.xM) (tensorAction D.yM) (tensorAction D.zM))
