import Mathlib
noncomputable def testH4 {V : Type*} [AddCommGroup V] [Module ℂ V] (x y h : V →ₗ[ℂ] V) (v : V) (lam : ℤ) : Prop := by
  let irreducible := True
  exact (∀ w : V, h (x w) - x (h w) = (2:ℂ) • x w) ∧ (∀ w : V, h (y w) - y (h w) = (-2:ℂ) • y w) ∧ (∀ w : V, x (y w) - y (x w) = h w) ∧ v ≠ 0 ∧ x v = 0 ∧ h v = (lam:ℂ) • v

set_option autoImplicit false
#check (fun (K : Type*) [instK : Field K] (p : ℕ) [instChar : CharP K p] (M : Type*) [instM : AddCommGroup M] [instZM : Module ℤ M] => M ⊗[ℤ] K)
#check (fun (K : Type*) [instK : Field K] (p : ℕ) [instChar : CharP K p] (M : Type*) [instM : AddCommGroup M] [instZM : Module ℤ M] => Module.Free ℤ M)
#check (fun (K : Type*) [instK : Field K] (p : ℕ) [instChar : CharP K p] (M : Type*) [instM : AddCommGroup M] [instZM : Module ℤ M] => Module.Finite ℤ M)
#check (fun (K : Type*) [instK : Field K] (p : ℕ) [instChar : CharP K p] (M : Type*) [instM : AddCommGroup M] [instZM : Module ℤ M] => ∀ i j : Fin 3, i = j ∨ i ≠ j)
