import Mathlib

set_option autoImplicit false
#check (∀ (K : Type*) [fK : Field K] (M : Type*) [aM : AddCommGroup M] [mM : Module ℤ M], TensorProduct ℤ M K)
#check (∀ (K : Type*) [fK : Field K] (M : Type*) [aM : AddCommGroup M] [mM : Module ℤ M], Module K (TensorProduct ℤ M K))
