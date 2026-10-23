import Mathlib
open scoped TensorProduct
noncomputable def commAddEquiv {K : Type*} [Field K] (M : Type*) [AddCommGroup M] [Module ℤ M] : M ⊗[ℤ] K ≃+ K ⊗[ℤ] M := by
  letI : Module ℤ (M ⊗[ℤ] K) := TensorProduct.instModule
  letI : Module ℤ (K ⊗[ℤ] M) := TensorProduct.instModule
  exact (TensorProduct.comm ℤ M K).toAddEquiv
noncomputable def sourceTensorAction {K : Type*} [Field K] {M : Type*} [AddCommGroup M] [Module ℤ M] (f : M →ₗ[ℤ] M) : M ⊗[ℤ] K →ₗ[K] M ⊗[ℤ] K := by
  letI : Module K (M ⊗[ℤ] K) := AddEquiv.module K (@commAddEquiv K _ M _ _)
  let e : M ⊗[ℤ] K ≃ₗ[K] K ⊗[ℤ] M := (@commAddEquiv K _ M _ _).linearEquiv K
  exact e.symm.toLinearMap.comp ((TensorProduct.AlgebraTensorModule.lTensor K K f).comp e.toLinearMap)

set_option autoImplicit false
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instMod : Module ℤ M] => sourceTensorAction (0 : M →ₗ[ℤ] M))
