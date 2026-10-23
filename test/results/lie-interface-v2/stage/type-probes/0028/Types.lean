import Mathlib
open scoped TensorProduct

set_option autoImplicit false
#check (∀ (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] (modM : Module ℤ M), ∃ e : M ⊗[ℤ] K ≃ₗ[K] K ⊗[ℤ] M, ∀ m k, e (m ⊗ₜ[ℤ] k) = k ⊗ₜ[ℤ] m)
