import Mathlib

namespace Translation
set_option autoImplicit false

#check (∀ (K : Type*) [instK : Field K] (p : ℕ) [instChar : CharP K p] (hp : Nat.Prime p) (lam : ℤ) (hLam : (0:ℤ) ≤ lam ∧ lam < (p:ℤ)) (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (h_H001 : Nat.Prime p) (h_H002 : CharP K p) (h_H003 : (0:ℤ) ≤ lam ∧ lam < (p:ℤ)) (h_H004 : True), True)

end Translation
