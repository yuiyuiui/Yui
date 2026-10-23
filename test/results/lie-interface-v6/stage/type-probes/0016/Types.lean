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
  · intro a b
    simp [e, A]
  · intro k z
    change e (A (e.symm (e (k • e.symm z)))) = e (k • e.symm (e (A (e.symm z))))
    simp [A]
noncomputable def sourceTensorComm {K : Type*} [Field K] {M : Type*} [AddCommGroup M] [Module ℤ M] : (M ⊗[ℤ] K) ≃ₗ[K] (K ⊗[ℤ] M) where
  toFun := TensorProduct.comm ℤ K M
  invFun := (TensorProduct.comm ℤ K M).symm
  left_inv := by intro z; simp
  right_inv := by intro z; simp
  map_add' := by intro a b; simp
  map_smul' := by intro k z; rfl

set_option autoImplicit false
#check (fun {K : Type*} [instK : Field K] {M : Type*} [instM : AddCommGroup M] [instZ : Module ℤ M] => sourceTensorComm)
#check (fun {K : Type*} [instK : Field K] {M : Type*} [instM : AddCommGroup M] [instZ : Module ℤ M] => sourceTensorAction (LinearMap.id : M →ₗ[ℤ] M))
