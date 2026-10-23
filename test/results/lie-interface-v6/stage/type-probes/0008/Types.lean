import Mathlib
open scoped TensorProduct
noncomputable instance sourceTensorModule (K : Type*) [Field K] (M : Type*) [AddCommGroup M] [Module ℤ M] : Module K (M ⊗[ℤ] K) where
  smul k z := (LinearMap.mulLeft ℤ k).lTensor M z
  one_smul z := by
    induction z using TensorProduct.induction_on with
    | zero => simp
    | tmul m t => simp [LinearMap.lTensor_tmul]
    | add a b ha hb => simp [ha, hb]
  mul_smul k l z := by
    induction z using TensorProduct.induction_on with
    | zero => simp
    | tmul m t => simp [LinearMap.lTensor_tmul, mul_assoc]
    | add a b ha hb => simp [ha, hb]
  smul_zero k := by simp
  smul_add k a b := by simp
  add_smul k l z := by
    induction z using TensorProduct.induction_on with
    | zero => simp
    | tmul m t => simp [LinearMap.lTensor_tmul, add_mul]
    | add a b ha hb => simp [ha, hb]
  zero_smul z := by
    induction z using TensorProduct.induction_on with
    | zero => simp
    | tmul m t => simp [LinearMap.lTensor_tmul]
    | add a b ha hb => simp [ha, hb]

set_option autoImplicit false
#check (fun {K : Type*} [instK : Field K] {M : Type*} [instM : AddCommGroup M] [instZ : Module ℤ M] => Module K (M ⊗[ℤ] K))
