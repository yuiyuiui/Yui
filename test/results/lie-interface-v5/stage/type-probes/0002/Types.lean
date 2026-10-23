import Mathlib
open scoped TensorProduct

set_option autoImplicit false
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instZM : Module ℤ M] [instKM : Module K (M ⊗[ℤ] K)] => Submodule K (M ⊗[ℤ] K))
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instZM : Module ℤ M] [instKM : Module K (M ⊗[ℤ] K)] => Module.Free ℤ M)
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instZM : Module ℤ M] [instKM : Module K (M ⊗[ℤ] K)] => Module.Finite ℤ M)
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instZM : Module ℤ M] [instKM : Module K (M ⊗[ℤ] K)] => Module.Free ℂ (Fin 2))
