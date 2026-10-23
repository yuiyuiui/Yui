import Mathlib
open scoped TensorProduct
noncomputable instance sourceTensorModule (K : Type*) [Field K] (M : Type*) [AddCommGroup M] [Module ℤ M] : Module K (M ⊗[ℤ] K) where
  smul k z := (TensorProduct.comm ℤ K M) (k • (TensorProduct.comm ℤ K M).symm z)
  one_smul z := by
    apply (TensorProduct.comm ℤ K M).injective
    simp
  mul_smul k l z := by
    apply (TensorProduct.comm ℤ K M).injective
    simp [mul_smul]
  smul_zero k := by simp
  smul_add k a b := by simp
  add_smul k l z := by
    apply (TensorProduct.comm ℤ K M).injective
    simp [add_smul]
  zero_smul z := by
    apply (TensorProduct.comm ℤ K M).injective
    simp

set_option autoImplicit false
#check (fun {K : Type*} [instK : Field K] {M : Type*} [instM : AddCommGroup M] [instZ : Module ℤ M] => Module K (M ⊗[ℤ] K))
