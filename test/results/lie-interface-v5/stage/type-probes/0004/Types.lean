import Mathlib
noncomputable def testH4 (V : Type*) [AddCommGroup V] [Module ℂ V] (x y h : V →ₗ[ℂ] V) (v : V) (lam : ℤ) : Prop := (∀ w, h (x w) - x (h w) = (2:ℂ) • x w) ∧ (∀ w, h (y w) - y (h w) = (-2:ℂ) • y w) ∧ (∀ w, x (y w) - y (x w) = h w) ∧ v ≠ 0 ∧ x v = 0 ∧ h v = (lam:ℂ) • v

set_option autoImplicit false
#check (fun (p : ℕ) (K : Type*) [instK : Field K] [instChar : CharP K p] (M : Type*) [instM : AddCommGroup M] [instMod : Module ℤ M] => testH4 (Fin 3) (0 : Fin 3 →ₗ[ℂ] Fin 3) (0 : Fin 3 →ₗ[ℂ] Fin 3) (0 : Fin 3 →ₗ[ℂ] Fin 3) 0 2)
#check (fun (p : ℕ) (K : Type*) [instK : Field K] [instChar : CharP K p] (M : Type*) [instM : AddCommGroup M] [instMod : Module ℤ M] => Module.Free ℤ M)
#check (fun (p : ℕ) (K : Type*) [instK : Field K] [instChar : CharP K p] (M : Type*) [instM : AddCommGroup M] [instMod : Module ℤ M] => M ⊗[ℤ] K)
