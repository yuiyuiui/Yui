import Mathlib
open scoped TensorProduct
noncomputable instance sourceTensorModule (K : Type*) [Field K] (M : Type*) [AddCommGroup M] [Module ℤ M] : Module K (M ⊗[ℤ] K) where
  smul k z := (LinearMap.mulLeft ℤ k).lTensor M z
  one_smul z := by
    change (LinearMap.mulLeft ℤ (1:K)).lTensor M z = z
    ext m t
    simp [LinearMap.lTensor_tmul]
  mul_smul k l z := by
    change (LinearMap.mulLeft ℤ (k*l)).lTensor M z = (LinearMap.mulLeft ℤ k).lTensor M ((LinearMap.mulLeft ℤ l).lTensor M z)
    ext m t
    simp [LinearMap.lTensor_tmul, mul_assoc]
  smul_zero k := by simp
  smul_add k a b := by simp
  add_smul k l z := by
    change (LinearMap.mulLeft ℤ (k+l)).lTensor M z = (LinearMap.mulLeft ℤ k).lTensor M z + (LinearMap.mulLeft ℤ l).lTensor M z
    ext m t
    simp [LinearMap.lTensor_tmul, add_mul]
  zero_smul z := by
    change (LinearMap.mulLeft ℤ (0:K)).lTensor M z = 0
    ext m t
    simp [LinearMap.lTensor_tmul]

set_option autoImplicit false
#check (fun {K : Type*} [instK : Field K] {M : Type*} [instM : AddCommGroup M] [instZ : Module ℤ M] => Module K (M ⊗[ℤ] K))
