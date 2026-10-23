import Mathlib
open scoped TensorProduct

set_option autoImplicit false
#check (∀ (M : Type*) [aM : AddCommGroup M] [mM : Module ℤ M] (K : Type*) [fK : Field K] (f : M →ₗ[ℤ] M), f.rTensor K)
#check (∀ (M : Type*) [aM : AddCommGroup M] [mM : Module ℤ M] (K : Type*) [fK : Field K] (f : M →ₗ[ℤ] M), LinearMap.restrictScalars K (f.rTensor K))
