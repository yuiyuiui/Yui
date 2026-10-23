import Mathlib
structure X where
  M : Type
  [a : AddCommGroup M]
  [m : Module ℤ M]

set_option autoImplicit false
#check (∀ (K : Type*) [fK : Field K] (D : X), TensorProduct ℤ D.M K)
#check (∀ (K : Type*) [fK : Field K] (D : X), Module K (TensorProduct ℤ D.M K))
