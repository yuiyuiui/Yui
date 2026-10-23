import Mathlib
open scoped TensorProduct
noncomputable def tensorAction {K : Type*} [Field K] {M : Type*} [AddCommGroup M] [Module ℤ M] [Module K (M ⊗[ℤ] K)] (f : M →ₗ[ℤ] M) : M ⊗[ℤ] K →ₗ[K] M ⊗[ℤ] K :=
  { TensorProduct.map f (LinearMap.id : K →ₗ[ℤ] K) with
    map_smul' := by
      intro c z
      induction z using TensorProduct.induction_on with
      | zero => simp
      | tmul m k => simp [TensorProduct.map_tmul]
      | add z₁ z₂ ih₁ ih₂ => simp [ih₁, ih₂] }

set_option autoImplicit false
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instMod : Module ℤ M] [instTensor : Module K (M ⊗[ℤ] K)] => tensorAction (0 : M →ₗ[ℤ] M))
