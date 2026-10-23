import Mathlib

set_option autoImplicit false
#check (∀ (V : Type*) (a : AddCommGroup V) (m : Module ℂ V) (x : V →ₗ[ℂ] V) (r : ℕ), ((Nat.factorial r : ℂ)⁻¹) • (x ^ r))
#check (∀ (V : Type*) (a : AddCommGroup V) (m : Module ℂ V) (x : V →ₗ[ℂ] V) (r : ℕ), Module.Basis (Fin 3) ℂ V)
