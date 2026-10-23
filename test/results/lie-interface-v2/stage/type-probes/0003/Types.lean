import Mathlib
structure LieLatticeData (n : ℕ) where
  V : Type
  [addV : AddCommGroup V]
  [moduleV : Module ℂ V]
  basisZ : Basis (Fin n) ℤ (Fin n → ℤ)
  basisC : Basis (Fin n) ℂ V
  basis_agree : ∀ i, basisC i = (basisZ i : Fin n → ℤ)

set_option autoImplicit false
#check (∀ (n : ℕ), LieLatticeData n)
