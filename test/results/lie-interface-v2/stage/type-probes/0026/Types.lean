import Mathlib
open scoped TensorProduct

set_option autoImplicit false
#check (∀ (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] (modM : Module ℤ M), Module K (M ⊗[ℤ] K))
