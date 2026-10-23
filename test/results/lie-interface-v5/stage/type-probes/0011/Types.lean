import Mathlib
open scoped TensorProduct
noncomputable def srcComm {K : Type*} [Field K] (M : Type*) [AddCommGroup M] [Module ℤ M] : (M ⊗[ℤ] K) ≃+ (K ⊗[ℤ] M) := (TensorProduct.comm ℤ M K).toAddEquiv
noncomputable def sourceTensorModule (K : Type*) [Field K] (M : Type*) [AddCommGroup M] [Module ℤ M] : Module K (M ⊗[ℤ] K) := AddEquiv.module K (srcComm K M)
noncomputable def sourceTensorAction {K : Type*} [Field K] {M : Type*} [AddCommGroup M] [Module ℤ M] (f : M →ₗ[ℤ] M) : M ⊗[ℤ] K →ₗ[K] M ⊗[ℤ] K := by
  letI := sourceTensorModule K M
  let e : M ⊗[ℤ] K ≃ₗ[K] K ⊗[ℤ] M := (srcComm K M).linearEquiv K
  exact e.symm.toLinearMap.comp ((TensorProduct.AlgebraTensorModule.lTensor K K f).comp e.toLinearMap)

set_option autoImplicit false
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instMod : Module ℤ M] => sourceTensorModule K M)
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instMod : Module ℤ M] => sourceTensorAction (0 : M →ₗ[ℤ] M))
