import Mathlib
open scoped TensorProduct

set_option autoImplicit false
#check (fun (K : Type*) [instK : Field K] (p : ℕ) [instChar : CharP K p] (M : Type*) [instM : AddCommGroup M] [instZM : Module ℤ M] => M ⊗[ℤ] K)
#check (fun (K : Type*) [instK : Field K] (p : ℕ) [instChar : CharP K p] (M : Type*) [instM : AddCommGroup M] [instZM : Module ℤ M] => K ⊗[ℤ] M)
#check (fun (K : Type*) [instK : Field K] (p : ℕ) [instChar : CharP K p] (M : Type*) [instM : AddCommGroup M] [instZM : Module ℤ M] => Submodule K (M ⊗[ℤ] K))
#check (fun (K : Type*) [instK : Field K] (p : ℕ) [instChar : CharP K p] (M : Type*) [instM : AddCommGroup M] [instZM : Module ℤ M] => Module.Free ℤ M)
#check (fun (K : Type*) [instK : Field K] (p : ℕ) [instChar : CharP K p] (M : Type*) [instM : AddCommGroup M] [instZM : Module ℤ M] => Module.Finite ℤ M)
