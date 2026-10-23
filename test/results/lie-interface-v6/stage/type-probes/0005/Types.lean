import Mathlib
open scoped TensorProduct
set_option autoImplicit false
#check (fun (K : Type*) [instK : Field K] (M : Type*) [instM : AddCommGroup M] [instZ : Module ℤ M] (k : K) => TensorProduct.lTensor M (LinearMap.mulLeft ℤ k))
