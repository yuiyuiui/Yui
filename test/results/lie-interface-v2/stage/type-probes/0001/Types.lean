import Mathlib

set_option autoImplicit false
#check (∀ (K : Type*) [inst : Field K] (p : ℕ) (hp : Nat.Prime p), Submodule K (Fin 3 → K))
#check (∀ (K : Type*) [inst : Field K] (p : ℕ) (hp : Nat.Prime p), (Fin 3 → K) → Prop)
