import Mathlib
noncomputable section
namespace LR
 def R (p : ℕ) : Subring ℚ := Subring.closure {q | ∃ a b : ℤ, ¬ (p : ℤ) ∣ b ∧ q = (a : ℚ) / (b : ℚ)}
 def MR (p : ℕ) {V : Type*} [AddCommGroup V] [Module ℂ V] (M : Submodule ℤ V) : Submodule (R p) V := Submodule.span (R p) (M : Set V)
end LR
set_option autoImplicit false
#check (∀ p : ℕ, Algebra (LR.R p) ℚ)
#check (∀ p : ℕ, Algebra (LR.R p) ℂ)
