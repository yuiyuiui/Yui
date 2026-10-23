import Mathlib
open scoped TensorProduct
noncomputable def tensorActionRight {K : Type*} [Field K] {M : Type*} [AddCommGroup M]
 (modM : Module ℤ M) (f : M →ₗ[ℤ] M) : M ⊗[ℤ] K →ₗ[K] M ⊗[ℤ] K := by
  letI := modM
  exact { toFun := f.rTensor K
    map_add' := by intro a b; exact map_add (f.rTensor K) a b
    map_smul' := by
      intro c z
      induction z using TensorProduct.induction_on with
      | zero => simp
      | tmul m k => simp [TensorProduct.smul_tmul']
      | add a b ha hb => simp [ha, hb] }

set_option autoImplicit false
#check (∀ (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] (modM : Module ℤ M) (f : M →ₗ[ℤ] M), M ⊗[ℤ] K →ₗ[K] M ⊗[ℤ] K)
