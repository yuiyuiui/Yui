import Mathlib
open scoped TensorProduct
noncomputable def dividedPower (V : Type*) [AddCommGroup V] [Module ℂ V] (f : V →ₗ[ℂ] V) (r : ℕ) : V →ₗ[ℂ] V := ((Nat.factorial r : ℂ)⁻¹) • (f ^ r)
noncomputable def tensorAction {K : Type*} [Field K] {M : Type*} [AddCommGroup M] [Module ℤ M] (f : M →ₗ[ℤ] M) : K ⊗[ℤ] M →ₗ[K] K ⊗[ℤ] M := TensorProduct.AlgebraTensorModule.lTensor K K f
def InvariantUnder (K : Type*) [Field K] (E : Type*) [AddCommGroup E] [Module K E] (f : E →ₗ[K] E) (W : Submodule K E) : Prop := ∀ z ∈ W, f z ∈ W
def LieIrreducible (K : Type*) [Field K] (E : Type*) [AddCommGroup E] [Module K E] (x y z : E →ₗ[K] E) : Prop := Nontrivial E ∧ ∀ W : Submodule K E, InvariantUnder K E x W → InvariantUnder K E y W → InvariantUnder K E z W → W = ⊥ ∨ W = ⊤
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
noncomputable def LieLatticeData.H004 {lam : ℤ} {M : Type*} [AddCommGroup M] [Module ℤ M] (D : LieLatticeData lam M) : Prop := by
  letI := D.vAdd
  letI := D.vMod
  exact (∀ i, D.basisV i = D.embed (D.basisM i)) ∧ Function.Injective D.embed ∧
    (∀ w, D.z (D.x w) - D.x (D.z w) = (2:ℂ) • D.x w) ∧
    (∀ w, D.z (D.y w) - D.y (D.z w) = (-2:ℂ) • D.y w) ∧
    (∀ w, D.x (D.y w) - D.y (D.x w) = D.z w) ∧ D.v ≠ 0 ∧ D.x D.v = 0 ∧ D.z D.v = (lam:ℂ) • D.v ∧
    (∀ m, D.embed (D.xM m) = D.x (D.embed m)) ∧ (∀ m, D.embed (D.yM m) = D.y (D.embed m)) ∧
    (∀ m, D.embed (D.zM m) = D.z (D.embed m)) ∧
    (∀ r m, ∃ m', D.embed m' = dividedPower D.V D.x r (D.embed m)) ∧
    (∀ r m, ∃ m', D.embed m' = dividedPower D.V D.y r (D.embed m)) ∧
    LieIrreducible ℂ D.V D.x D.y D.z

namespace Translation
set_option autoImplicit false

#check (∀ (K : Type*) [instK : Field K] (p : ℕ) (lam : ℤ) (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (D : LieLatticeData lam M) (h_H003 : (0 : ℤ) ≤ lam ∧ lam < (p : ℤ)) (h_H004 : LieLatticeData.H004 D), ∀ i : Fin (lam.toNat + 1), True)
#check (∀ (K : Type*) [instK : Field K] (p : ℕ) (lam : ℤ) (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (D : LieLatticeData lam M) (h_H001 : Nat.Prime p) (h_H003 : (0 : ℤ) ≤ lam ∧ lam < (p : ℤ)) (h_H004 : LieLatticeData.H004 D) (h_T001 : ∀ i : Fin (lam.toNat + 1), True), ∀ i j : Fin (lam.toNat + 1), True)
#check (∀ (K : Type*) [instK : Field K] (p : ℕ) (lam : ℤ) (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (D : LieLatticeData lam M) (h_H001 : Nat.Prime p) (h_H003 : (0 : ℤ) ≤ lam ∧ lam < (p : ℤ)) (h_H004 : LieLatticeData.H004 D) (h_T002 : ∀ i j : Fin (lam.toNat + 1), True), True)
#check (∀ (K : Type*) [instK : Field K] (p : ℕ) (lam : ℤ) (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (D : LieLatticeData lam M) (h_H002 : CharP K p) (h_H003 : (0 : ℤ) ≤ lam ∧ lam < (p : ℤ)) (h_H004 : LieLatticeData.H004 D) (h_T003 : True), True)
#check (∀ (K : Type*) [instK : Field K] (p : ℕ) (lam : ℤ) (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (D : LieLatticeData lam M) (h_H001 : Nat.Prime p) (h_H002 : CharP K p) (h_H003 : (0 : ℤ) ≤ lam ∧ lam < (p : ℤ)) (h_H004 : LieLatticeData.H004 D) (h_T002 : ∀ i j : Fin (lam.toNat + 1), True) (h_T004 : True), True)
#check (∀ (K : Type*) [instK : Field K] (p : ℕ) (lam : ℤ) (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (D : LieLatticeData lam M) (h_H002 : CharP K p) (h_H003 : (0 : ℤ) ≤ lam ∧ lam < (p : ℤ)) (h_H004 : LieLatticeData.H004 D) (h_T005 : True), True)
#check (∀ (K : Type*) [instK : Field K] (p : ℕ) (lam : ℤ) (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (D : LieLatticeData lam M) (h_H002 : CharP K p) (h_H003 : (0 : ℤ) ≤ lam ∧ lam < (p : ℤ)) (h_H004 : LieLatticeData.H004 D) (h_T005 : True) (h_T006 : True), True)
#check (∀ (K : Type*) [instK : Field K] (p : ℕ) (lam : ℤ) (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (D : LieLatticeData lam M) (h_H001 : Nat.Prime p) (h_H002 : CharP K p) (h_H003 : (0 : ℤ) ≤ lam ∧ lam < (p : ℤ)) (h_H004 : LieLatticeData.H004 D) (h_T001 : ∀ i : Fin (lam.toNat + 1), True) (h_T002 : ∀ i j : Fin (lam.toNat + 1), True) (h_T003 : True) (h_T004 : True) (h_T005 : True) (h_T006 : True) (h_T007 : True), LieIrreducible K (K ⊗[ℤ] M) (tensorAction D.xM) (tensorAction D.yM) (tensorAction D.zM))

end Translation
