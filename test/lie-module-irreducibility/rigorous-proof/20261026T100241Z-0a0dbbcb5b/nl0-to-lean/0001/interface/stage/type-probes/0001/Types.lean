import Mathlib
noncomputable section
namespace LatticeReduction
 def R (p : ℕ) : Subring ℂ := Subring.closure {z | ∃ a b : ℤ, ¬ (p : ℤ) ∣ b ∧ z = (a : ℂ) / (b : ℂ)}
 def MR (p : ℕ) {V : Type*} [AddCommGroup V] [Module ℂ V] (M : Submodule ℤ V) : Submodule (R p) V := Submodule.span (R p) (M : Set V)
end LatticeReduction
set_option autoImplicit false
#check (∀ p : ℕ, Module (LatticeReduction.R p) ℂ)
#check (∀ (p : ℕ) (V : Type) [AddCommGroup V] [Module ℂ V] (M : Submodule ℤ V), Module (LatticeReduction.R p) (LatticeReduction.MR p M))
