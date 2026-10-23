import Mathlib

noncomputable def dividedPower (V : Type*) [AddCommGroup V] [Module ℂ V]
    (x : V →ₗ[ℂ] V) (r : ℕ) : V →ₗ[ℂ] V :=
  ((Nat.factorial r : ℂ)⁻¹) • (x ^ r)

structure LatticeData (n : ℕ) where
  M : Type
  [mAdd : AddCommGroup M]
  [mMod : Module ℤ M]
  mBasis : Module.Basis (Fin n) ℤ M
  V : Type
  [vAdd : AddCommGroup V]
  [vMod : Module ℂ V]
  vBasis : Module.Basis (Fin n) ℂ V
  incl : M →ₗ[ℤ] V
  incl_injective : Function.Injective incl
  basis_agrees : ∀ i, vBasis i = incl (mBasis i)
  x : V →ₗ[ℂ] V
  y : V →ₗ[ℂ] V
  h : V →ₗ[ℂ] V
  highest : V
  highest_ne : highest ≠ 0
  x_highest : x highest = 0
  h_highest : h highest = (n - 1 : ℂ) • highest
  stableX : ∀ r m, ∃ m', incl m' = dividedPower V x r (incl m)
  stableY : ∀ r m, ∃ m', incl m' = dividedPower V y r (incl m)

set_option autoImplicit false
#check (∀ (n : ℕ), LatticeData n)
