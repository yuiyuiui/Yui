import Mathlib
open scoped TensorProduct
noncomputable def dividedPower (V : Type*) [AddCommGroup V] [Module ℂ V] (f : V →ₗ[ℂ] V) (r : ℕ) : V →ₗ[ℂ] V := ((Nat.factorial r : ℂ)⁻¹) • (f ^ r)
noncomputable def tensorAction {K : Type*} [Field K] {M : Type*} [AddCommGroup M] [Module ℤ M] (f : M →ₗ[ℤ] M) : K ⊗[ℤ] M →ₗ[K] K ⊗[ℤ] M := TensorProduct.AlgebraTensorModule.lTensor K K f
def InvariantUnder (K : Type*) [Field K] (E : Type*) [AddCommGroup E] [Module K E] (f : E →ₗ[K] E) (W : Submodule K E) : Prop := ∀ z ∈ W, f z ∈ W
def LieIrreducible (K : Type*) [Field K] (E : Type*) [AddCommGroup E] [Module K E] (x y z : E →ₗ[K] E) : Prop := Nontrivial E ∧ ∀ W : Submodule K E, InvariantUnder K E x W → InvariantUnder K E y W → InvariantUnder K E z W → W = ⊥ ∨ W = ⊤
noncomputable instance sourceTensorModule (K : Type*) [Field K] (M : Type*) [AddCommGroup M] [Module ℤ M] : Module K (M ⊗[ℤ] K) where
  smul k z := (TensorProduct.comm ℤ K M) (k • (TensorProduct.comm ℤ K M).symm z)
  one_smul z := by change (TensorProduct.comm ℤ K M) (1 • (TensorProduct.comm ℤ K M).symm z) = z; simp
  mul_smul k l z := by
    change (TensorProduct.comm ℤ K M) ((k*l) • (TensorProduct.comm ℤ K M).symm z) = (TensorProduct.comm ℤ K M) (k • (TensorProduct.comm ℤ K M).symm ((TensorProduct.comm ℤ K M) (l • (TensorProduct.comm ℤ K M).symm z)))
    simp [mul_smul]
  smul_zero k := by change (TensorProduct.comm ℤ K M) (k • (TensorProduct.comm ℤ K M).symm 0) = 0; simp
  smul_add k a b := by
    change (TensorProduct.comm ℤ K M) (k • (TensorProduct.comm ℤ K M).symm (a+b)) = (TensorProduct.comm ℤ K M) (k • (TensorProduct.comm ℤ K M).symm a) + (TensorProduct.comm ℤ K M) (k • (TensorProduct.comm ℤ K M).symm b)
    simp
  add_smul k l z := by
    change (TensorProduct.comm ℤ K M) ((k+l) • (TensorProduct.comm ℤ K M).symm z) = (TensorProduct.comm ℤ K M) (k • (TensorProduct.comm ℤ K M).symm z) + (TensorProduct.comm ℤ K M) (l • (TensorProduct.comm ℤ K M).symm z)
    simp [add_smul]
  zero_smul z := by change (TensorProduct.comm ℤ K M) (0 • (TensorProduct.comm ℤ K M).symm z) = 0; simp
noncomputable def sourceTensorAction {K : Type*} [Field K] {M : Type*} [AddCommGroup M] [Module ℤ M] (f : M →ₗ[ℤ] M) : M ⊗[ℤ] K →ₗ[K] M ⊗[ℤ] K := by
  let e := TensorProduct.comm ℤ K M
  let A := TensorProduct.AlgebraTensorModule.lTensor K K f
  refine { toFun := fun z => e (A (e.symm z)), map_add' := ?_, map_smul' := ?_ }
  · intro a b; simp [e, A]
  · intro k z
    change e (A (e.symm (e (k • e.symm z)))) = e (k • e.symm (e (A (e.symm z))))
    simp [A]
noncomputable def sourceTensorComm {K : Type*} [Field K] {M : Type*} [AddCommGroup M] [Module ℤ M] : (M ⊗[ℤ] K) ≃ₗ[K] (K ⊗[ℤ] M) where
  toFun := TensorProduct.comm ℤ M K
  invFun := TensorProduct.comm ℤ K M
  left_inv := by intro z; simp
  right_inv := by intro z; simp
  map_add' := by intro a b; simp
  map_smul' := by
    intro k z
    change (TensorProduct.comm ℤ M K) ((TensorProduct.comm ℤ K M) (k • (TensorProduct.comm ℤ M K) z)) = k • (TensorProduct.comm ℤ M K) z
    simp
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

#check (∀ (K : Type*) [instK : Field K] (p : ℕ) (lam : ℤ) (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (D : LieLatticeData lam M) (h_H001 : Nat.Prime p) (h_H002 : CharP K p) (h_H003 : (0 : ℤ) ≤ lam ∧ lam < (p : ℤ)) (h_H004 : D.H004), LieIrreducible K (K ⊗[ℤ] M) (tensorAction D.xM) (tensorAction D.yM) (tensorAction D.zM))
#check (∀ (K : Type*) [instK : Field K] (p : ℕ) (lam : ℤ) (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (D : LieLatticeData lam M) (h_T001 : LieIrreducible K (K ⊗[ℤ] M) (tensorAction D.xM) (tensorAction D.yM) (tensorAction D.zM)), LieIrreducible K (M ⊗[ℤ] K) (sourceTensorAction D.xM) (sourceTensorAction D.yM) (sourceTensorAction D.zM))

end Translation
