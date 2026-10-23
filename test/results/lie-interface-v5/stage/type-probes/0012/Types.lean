import Mathlib
open scoped TensorProduct

set_option autoImplicit false
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instZM : Module ℤ M] => TensorProduct.comm ℤ M K)
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instZM : Module ℤ M] => (TensorProduct.comm ℤ M K).toAddEquiv)
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instZM : Module ℤ M] => TensorProduct.comm ℤ M K |>.toLinearMap)
