import Mathlib
open scoped TensorProduct

set_option autoImplicit false
#check (∀ (K : Type*) [fK : Field K] (M : Type*) [aM : AddCommGroup M] [mM : Module ℤ M], TensorProduct ℤ K M)
#check (∀ (K : Type*) [fK : Field K] (M : Type*) [aM : AddCommGroup M] [mM : Module ℤ M], Module K (TensorProduct ℤ K M))
