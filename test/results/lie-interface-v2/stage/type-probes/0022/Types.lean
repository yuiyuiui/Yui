import Mathlib
open scoped TensorProduct
noncomputable def dividedPower (V : Type*) [AddCommGroup V] [Module ℂ V]
    (f : V →ₗ[ℂ] V) (r : ℕ) : V →ₗ[ℂ] V := ((Nat.factorial r : ℂ)⁻¹) • (f ^ r)
noncomputable def tensorAction {K : Type*} [Field K] {M : Type*} [AddCommGroup M]
    [Module ℤ M] (f : M →ₗ[ℤ] M) : K ⊗[ℤ] M →ₗ[K] K ⊗[ℤ] M :=
  TensorProduct.AlgebraTensorModule.lTensor K K f
def InvariantUnder (K : Type*) [Field K] (E : Type*) [AddCommGroup E] [Module K E]
    (f : E →ₗ[K] E) (W : Submodule K E) : Prop := ∀ z ∈ W, f z ∈ W
def LieIrreducible (K : Type*) [Field K] (E : Type*) [AddCommGroup E] [Module K E]
    (x y z : E →ₗ[K] E) : Prop := Nontrivial E ∧ ∀ W : Submodule K E,
    InvariantUnder K E x W → InvariantUnder K E y W → InvariantUnder K E z W → W = ⊥ ∨ W = ⊤
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
def LieLatticeData.H004 {lam : ℤ} {M : Type*} [AddCommGroup M] [Module ℤ M]
  (D : LieLatticeData lam M) : Prop := by
  letI := D.vAdd
  letI := D.vMod
  exact (∀ i, D.basisV i = D.embed (D.basisM i)) ∧ Function.Injective D.embed ∧
  (∀ w, D.z (D.x w) - D.x (D.z w) = (2:ℂ) • D.x w) ∧
  (∀ w, D.z (D.y w) - D.y (D.z w) = (-2:ℂ) • D.y w) ∧
  (∀ w, D.x (D.y w) - D.y (D.x w) = D.z w) ∧ D.v ≠ 0 ∧ D.x D.v = 0 ∧
  D.z D.v = (lam:ℂ) • D.v ∧
  (∀ m, D.embed (D.xM m) = D.x (D.embed m)) ∧
  (∀ m, D.embed (D.yM m) = D.y (D.embed m)) ∧
  (∀ m, D.embed (D.zM m) = D.z (D.embed m)) ∧
  (∀ r m, ∃ m', D.embed m' = dividedPower D.V D.x r (D.embed m)) ∧
  (∀ r m, ∃ m', D.embed m' = dividedPower D.V D.y r (D.embed m)) ∧
  LieIrreducible ℂ D.V D.x D.y D.z

set_option autoImplicit false
#check (∀ (K : Type*) [fK : Field K] (p : ℕ) (hp : Nat.Prime p) (lam : ℤ) (M : Type*) [aM : AddCommGroup M] [mM : Module ℤ M] (D : LieLatticeData lam M), D.H004)
