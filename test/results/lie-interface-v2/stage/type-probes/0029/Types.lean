import Mathlib
open scoped TensorProduct

set_option autoImplicit false
#check (∀ (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M], Module K (M ⊗[ℤ] K))
#check (∀ (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M], Module K (K ⊗[ℤ] M))
