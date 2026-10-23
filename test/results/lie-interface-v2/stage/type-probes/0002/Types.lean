import Mathlib

set_option autoImplicit false
#check (∀ (K : Type*) [instK : Field K] (n : ℕ) (W : Submodule K (Fin n → K)), ∀ (i j : Fin n), ∀ f : Fin n → K, (fun t => if t = i then f j else 0) ∈ W)
#check (∀ (K : Type*) [instK : Field K] (n : ℕ) (W : Submodule K (Fin n → K)), (∃ f : Fin n → K, f ∈ W ∧ f ≠ 0) → W = ⊥ ∨ W = ⊤)
