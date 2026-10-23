import Mathlib
open scoped TensorProduct
noncomputable def dividedPower (V : Type*) [AddCommGroup V] [Module ℂ V] (f : V →ₗ[ℂ] V) (r : ℕ) : V →ₗ[ℂ] V := ((Nat.factorial r : ℂ)⁻¹) • (f ^ r)
noncomputable def tensorAction {K : Type*} [Field K] {M : Type*} [AddCommGroup M] [Module ℤ M] (f : M →ₗ[ℤ] M) : K ⊗[ℤ] M →ₗ[K] K ⊗[ℤ] M := TensorProduct.AlgebraTensorModule.lTensor K K f

set_option autoImplicit false
#check (fun (K : Type*) [instK : Field K] (p : ℕ) (lam : ℤ) (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (D : LieLatticeData lam M) => Nat.Prime p)
#check (fun (K : Type*) [instK : Field K] (p : ℕ) (lam : ℤ) (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (D : LieLatticeData lam M) => CharP K p)
#check (fun (K : Type*) [instK : Field K] (p : ℕ) (lam : ℤ) (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (D : LieLatticeData lam M) => (0 : ℤ) ≤ lam ∧ lam < (p : ℤ))
#check (fun (K : Type*) [instK : Field K] (p : ℕ) (lam : ℤ) (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (D : LieLatticeData lam M) => LieLatticeData.H004 D)
#check (fun (K : Type*) [instK : Field K] (p : ℕ) (lam : ℤ) (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (D : LieLatticeData lam M) => LieIrreducible K (K ⊗[ℤ] M) (tensorAction D.xM) (tensorAction D.yM) (tensorAction D.zM))
