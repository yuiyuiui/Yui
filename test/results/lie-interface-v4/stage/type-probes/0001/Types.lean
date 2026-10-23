import Mathlib
open scoped TensorProduct
noncomputable def dividedPower (V : Type*) [AddCommGroup V] [Module ℂ V] (f : V →ₗ[ℂ] V) (r : ℕ) : V →ₗ[ℂ] V := ((Nat.factorial r : ℂ)⁻¹) • (f ^ r)

set_option autoImplicit false
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (f : M →ₗ[ℤ] M) => M ⊗[ℤ] K)
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (f : M →ₗ[ℤ] M) => (M ⊗[ℤ] K) →ₗ[K] (M ⊗[ℤ] K))
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (f : M →ₗ[ℤ] M) => TensorProduct.AlgebraTensorModule.lTensor K M f)
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instModM : Module ℤ M] (f : M →ₗ[ℤ] M) => TensorProduct.AlgebraTensorModule.rTensor K K f)
