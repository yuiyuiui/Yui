import Mathlib
open scoped TensorProduct
noncomputable section
namespace Test
structure S (R K T : Type*) [CommRing R] [Field K] [AddCommGroup T] [Module R T] (p : ℕ) where
 [ak : Algebra R K]
 [af : Algebra (ZMod p) K]
 [mt : Module (ZMod p) T]
 C : (K ⊗[R] T) ≃ₗ[K] (K ⊗[ZMod p] T)
end Test
set_option autoImplicit false
#check (Test.S)
