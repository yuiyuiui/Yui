import Mathlib
open scoped TensorProduct
noncomputable instance sourceTensorModule (K : Type*) [Field K] (M : Type*) [AddCommGroup M] [Module ℤ M] : Module K (M ⊗[ℤ] K) where
  smul k z := (TensorProduct.comm ℤ K M) (k • (TensorProduct.comm ℤ K M).symm z)
  one_smul z := by
    change (TensorProduct.comm ℤ K M) (1 • (TensorProduct.comm ℤ K M).symm z) = z
    simp
  mul_smul k l z := by
    change (TensorProduct.comm ℤ K M) ((k*l) • (TensorProduct.comm ℤ K M).symm z) = (TensorProduct.comm ℤ K M) (k • (TensorProduct.comm ℤ K M).symm ((TensorProduct.comm ℤ K M) (l • (TensorProduct.comm ℤ K M).symm z)))
    simp [mul_smul]
  smul_zero k := by
    change (TensorProduct.comm ℤ K M) (k • (TensorProduct.comm ℤ K M).symm 0) = 0
    simp
  smul_add k a b := by
    change (TensorProduct.comm ℤ K M) (k • (TensorProduct.comm ℤ K M).symm (a+b)) = (TensorProduct.comm ℤ K M) (k • (TensorProduct.comm ℤ K M).symm a) + (TensorProduct.comm ℤ K M) (k • (TensorProduct.comm ℤ K M).symm b)
    simp
  add_smul k l z := by
    change (TensorProduct.comm ℤ K M) ((k+l) • (TensorProduct.comm ℤ K M).symm z) = (TensorProduct.comm ℤ K M) (k • (TensorProduct.comm ℤ K M).symm z) + (TensorProduct.comm ℤ K M) (l • (TensorProduct.comm ℤ K M).symm z)
    simp [add_smul]
  zero_smul z := by
    change (TensorProduct.comm ℤ K M) (0 • (TensorProduct.comm ℤ K M).symm z) = 0
    simp

set_option autoImplicit false
#check (fun {K : Type*} [instK : Field K] {M : Type*} [instM : AddCommGroup M] [instZ : Module ℤ M] => Module K (M ⊗[ℤ] K))
