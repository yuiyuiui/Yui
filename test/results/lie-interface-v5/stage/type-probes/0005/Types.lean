import Mathlib
noncomputable def dividedPower (V : Type*) [AddCommGroup V] [Module ℂ V] (f : V →ₗ[ℂ] V) (r : ℕ) : V →ₗ[ℂ] V := ((Nat.factorial r : ℂ)⁻¹) • (f ^ r)
def LieIrreducible (K : Type*) [Field K] (E : Type*) [AddCommGroup E] [Module K E] (x y h : E →ₗ[K] E) : Prop := Nontrivial E ∧ ∀ W : Submodule K E, (∀ z ∈ W, x z ∈ W) → (∀ z ∈ W, y z ∈ W) → (∀ z ∈ W, h z ∈ W) → W = ⊥ ∨ W = ⊤
structure DData (lam : ℤ) (M : Type*) [AddCommGroup M] [Module ℤ M] where
  V : Type*
  [vAdd : AddCommGroup V]
  [vMod : Module ℂ V]
  basisV : Module.Basis (Fin (lam.toNat + 1)) ℂ V
  basisM : Module.Basis (Fin (lam.toNat + 1)) ℤ M
  embed : M →ₗ[ℤ] V
  x : V →ₗ[ℂ] V
  y : V →ₗ[ℂ] V
  h : V →ₗ[ℂ] V
  xM : M →ₗ[ℤ] M
  yM : M →ₗ[ℤ] M
  hM : M →ₗ[ℤ] M
  v : V
  basis_compatible : ∀ i, basisV i = embed (basisM i)
  embed_injective : Function.Injective embed
  complex_irreducible : LieIrreducible ℂ V x y h
  x_compatible : ∀ m, embed (xM m) = x (embed m)
  y_compatible : ∀ m, embed (yM m) = y (embed m)
  h_compatible : ∀ m, embed (hM m) = h (embed m)
  divided_x_preserves : ∀ r m, ∃ m', embed m' = dividedPower V x r (embed m)
  divided_y_preserves : ∀ r m, ∃ m', embed m' = dividedPower V y r (embed m)

def DData.H004 {lam : ℤ} {M : Type*} [AddCommGroup M] [Module ℤ M] (D : DData lam M) : Prop := by
  letI := D.vAdd
  letI := D.vMod
  exact (∀ w, D.h (D.x w) - D.x (D.h w) = (2:ℂ) • D.x w) ∧ (∀ w, D.h (D.y w) - D.y (D.h w) = (-2:ℂ) • D.y w) ∧ (∀ w, D.x (D.y w) - D.y (D.x w) = D.h w) ∧ D.v ≠ 0 ∧ D.x D.v = 0 ∧ D.h D.v = (lam:ℂ) • D.v ∧ D.basis_compatible ∧ D.embed_injective ∧ D.complex_irreducible ∧ (∀ m, D.embed (D.xM m) = D.x (D.embed m)) ∧ (∀ m, D.embed (D.yM m) = D.y (D.embed m)) ∧ (∀ m, D.embed (D.hM m) = D.h (D.embed m)) ∧ (∀ r m, ∃ m', D.embed m' = dividedPower D.V D.x r (D.embed m)) ∧ (∀ r m, ∃ m', D.embed m' = dividedPower D.V D.y r (D.embed m))

set_option autoImplicit false
#check (fun (M : Type*) [instM : AddCommGroup M] [instMod : Module ℤ M] => ∀ (D : DData 0 M), DData.H004 D)
#check (fun (M : Type*) [instM : AddCommGroup M] [instMod : Module ℤ M] => Module.Free ℤ M)
