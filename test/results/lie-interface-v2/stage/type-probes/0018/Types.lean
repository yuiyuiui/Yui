import Mathlib
open scoped TensorProduct

def InvariantUnder (K : Type*) [Field K] (E : Type*) [AddCommGroup E] [Module K E]
    (f : E →ₗ[K] E) (W : Submodule K E) : Prop :=
  ∀ z ∈ W, f z ∈ W

def LieIrreducible (K : Type*) [Field K] (E : Type*) [AddCommGroup E] [Module K E]
    (x y h : E →ₗ[K] E) : Prop :=
  Nontrivial E ∧ ∀ W : Submodule K E,
    InvariantUnder K E x W → InvariantUnder K E y W → InvariantUnder K E h W →
      W = ⊥ ∨ W = ⊤
noncomputable def tensorAction {K : Type*} [Field K] {M : Type*} [AddCommGroup M]
    [Module ℤ M] (f : M →ₗ[ℤ] M) : K ⊗[ℤ] M →ₗ[K] K ⊗[ℤ] M :=
  TensorProduct.AlgebraTensorModule.lTensor K K f

set_option autoImplicit false
#check (∀ (K : Type*) [fK : Field K] (M : Type*) [aM : AddCommGroup M] [mM : Module ℤ M] (x : M →ₗ[ℤ] M) (y : M →ₗ[ℤ] M) (h : M →ₗ[ℤ] M), LieIrreducible K (K ⊗[ℤ] M) (tensorAction x) (tensorAction y) (tensorAction h))
#check (∀ (K : Type*) [fK : Field K] (M : Type*) [aM : AddCommGroup M] [mM : Module ℤ M] (x : M →ₗ[ℤ] M) (y : M →ₗ[ℤ] M) (h : M →ₗ[ℤ] M), ∀ W : Submodule K (K ⊗[ℤ] M), InvariantUnder K (K ⊗[ℤ] M) (tensorAction x) W → InvariantUnder K (K ⊗[ℤ] M) (tensorAction y) W → InvariantUnder K (K ⊗[ℤ] M) (tensorAction h) W → W = ⊥ ∨ W = ⊤)
