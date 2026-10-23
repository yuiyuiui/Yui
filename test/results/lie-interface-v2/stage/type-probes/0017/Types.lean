import Mathlib
open scoped TensorProduct
noncomputable def act {K : Type*} [Field K] {M : Type*} [AddCommGroup M] [Module ℤ M]
    (f : M →ₗ[ℤ] M) : K ⊗[ℤ] M →ₗ[K] K ⊗[ℤ] M :=
  TensorProduct.AlgebraTensorModule.lTensor K K f

set_option autoImplicit false
#check (∀ (K : Type*) [fK : Field K] (M : Type*) [aM : AddCommGroup M] [mM : Module ℤ M] (f : M →ₗ[ℤ] M), K ⊗[ℤ] M →ₗ[K] K ⊗[ℤ] M)
