import Mathlib
open scoped TensorProduct

set_option autoImplicit false
#check (∀ (K : Type*) [fK : Field K] (M : Type*) [aM : AddCommGroup M] [mM : Module ℤ M] (f : M →ₗ[ℤ] M), TensorProduct.AlgebraTensorModule.lTensor K K f)
