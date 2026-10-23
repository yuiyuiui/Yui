import Mathlib
open scoped TensorProduct
noncomputable def commAddEquiv {K : Type*} [Field K] (M : Type*) [AddCommGroup M] [Module ℤ M] : M ⊗[ℤ] K ≃+ K ⊗[ℤ] M :=
  { toFun := TensorProduct.comm ℤ M K
    invFun := (TensorProduct.comm ℤ M K).symm
    left_inv := (TensorProduct.comm ℤ M K).left_inv
    right_inv := (TensorProduct.comm ℤ M K).right_inv
    map_add' := (TensorProduct.comm ℤ M K).map_add }

set_option autoImplicit false
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] (instMod : Module ℤ M) => commAddEquiv K M)
