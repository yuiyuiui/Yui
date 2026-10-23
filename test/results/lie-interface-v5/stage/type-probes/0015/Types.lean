import Mathlib
open scoped TensorProduct
noncomputable def commAddEquiv {K : Type*} [Field K] (M : Type*) [AddCommGroup M] [Module ℤ M] : M ⊗[ℤ] K ≃+ K ⊗[ℤ] M := by
  letI : Module ℤ (M ⊗[ℤ] K) := TensorProduct.instModule
  letI : Module ℤ (K ⊗[ℤ] M) := TensorProduct.instModule
  exact (TensorProduct.comm ℤ M K).toAddEquiv
noncomputable def sourceTensorModule {K : Type*} [Field K] (M : Type*) [AddCommGroup M] [Module ℤ M] : Module K (M ⊗[ℤ] K) := AddEquiv.module K (@commAddEquiv K _ M _ _)

set_option autoImplicit false
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instMod : Module ℤ M] => Module K (M ⊗[ℤ] K))
