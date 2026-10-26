import Mathlib
noncomputable section
namespace LR
abbrev Idx (l : ℕ) := Fin (l + 1)
def R (p : ℕ) : Subring ℚ := Subring.closure {q | ∃ a b : ℤ, ¬ (p : ℤ) ∣ b ∧ q = (a : ℚ) / (b : ℚ)}
instance rModule (p : ℕ) (V : Type*) [AddCommGroup V] [Module ℂ V] : Module (R p) V := Module.compHom V (algebraMap (R p) ℂ)
def MR (p : ℕ) {V : Type*} [AddCommGroup V] [Module ℂ V] (M : Submodule ℤ V) : Submodule (R p) V := Submodule.span (R p) (M : Set V)
def DP {V : Type*} [AddCommGroup V] [Module ℂ V] (f : Module.End ℂ V) (r : ℕ) : Module.End ℂ V := (r.factorial : ℂ)⁻¹ • f^r
def e {V : Type*} [AddCommGroup V] [Module ℂ V] (y : Module.End ℂ V) (v : V) (i : ℕ) : V := DP y i v
def Inv {F U : Type*} [Field F] [AddCommGroup U] [Module F U] (W : Submodule F U) (f : Module.End F U) : Prop := ∀ u ∈ W, f u ∈ W
def Brackets {F U : Type*} [Field F] [AddCommGroup U] [Module F U] (x y h : Module.End F U) : Prop := h*x-x*h = (2:F) • x ∧ h*y-y*h = (-2:F) • y ∧ x*y-y*x = h
def ext {F U : Type*} [Field F] [AddCommGroup U] [Module F U] {l : ℕ} (B : Module.Basis (Idx l) F U) (i : ℕ) : U := if hi : i < l+1 then B ⟨i,hi⟩ else 0
def MU {F U : Type*} [Field F] [AddCommGroup U] [Module F U] {l : ℕ} (B : Module.Basis (Idx l) F U) (i j : Idx l) : Module.End F U := (B.coord j).smulRight (B i)
def Actions {F U : Type*} [Field F] [AddCommGroup U] [Module F U] (l : ℕ) (a : ℕ → U) (x y h : Module.End F U) (X Y : ℕ → Module.End F U) : Prop :=
 x (a 0) = 0 ∧ (∀ i, 1 ≤ i → i ≤ l → x (a i) = ((l-i+1 : ℕ):F) • a (i-1)) ∧ (∀ i, i ≤ l → y (a i) = ((i+1:ℕ):F) • a (i+1)) ∧ (∀ i, i ≤ l → h (a i) = (((l:ℤ)-2*(i:ℤ):ℤ):F) • a i) ∧ (∀ r i, i ≤ l → X r (a i) = if r ≤ i then (((l-i+r).choose r : ℕ):F) • a (i-r) else 0) ∧ (∀ r i, i ≤ l → Y r (a i) = if i+r ≤ l then (((i+r).choose r : ℕ):F) • a (i+r) else 0)
def IsStringBasis {V : Type*} [AddCommGroup V] [Module ℂ V] (l : ℕ) (y : Module.End ℂ V) (v : V) (B : Module.Basis (Idx l) ℂ V) : Prop := ∀ i, B i = e y v i.val
structure IntegralOps {V : Type*} [AddCommGroup V] [Module ℂ V] (M : Submodule ℤ V) (x y h : Module.End ℂ V) where
 xz : Module.End ℤ M
 yz : Module.End ℤ M
 hz : Module.End ℤ M
 Xz : ℕ → Module.End ℤ M
 Yz : ℕ → Module.End ℤ M
 x_agree : ∀ m, (xz m : V) = x m
 y_agree : ∀ m, (yz m : V) = y m
 h_agree : ∀ m, (hz m : V) = h m
 X_agree : ∀ r m, (Xz r m : V) = DP x r m
 Y_agree : ∀ r m, (Yz r m : V) = DP y r m
abbrev VK (K : Type*) [Field K] {V : Type*} [AddCommGroup V] [Module ℂ V] (M : Submodule ℤ V) := K ⊗[ℤ] M
def Jc (p : ℕ) {V : Type*} [AddCommGroup V] [Module ℂ V] (M : Submodule ℤ V) (w : V) : Submodule (R p) ℂ := Submodule.span (R p) {c | c • w ∈ MR p M}
def pMR (p : ℕ) {V : Type*} [AddCommGroup V] [Module ℂ V] (M : Submodule ℤ V) : Submodule (R p) (MR p M) := LinearMap.range ((p : R p) • (LinearMap.id : MR p M →ₗ[R p] MR p M))
abbrev QMR (p : ℕ) {V : Type*} [AddCommGroup V] [Module ℂ V] (M : Submodule ℤ V) := (MR p M) ⧸ (pMR p M)
end LR
set_option autoImplicit false
#check (fun (p : ℕ) (K : Type) [instK : Field K] (lam : ℤ) (V : Type) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) => LR.QMR p M)
#check (fun (p : ℕ) (K : Type) [instK : Field K] (lam : ℤ) (V : Type) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) => ∀ o : LR.IntegralOps M x y h, LR.Brackets (o.xz.baseChange K) (o.yz.baseChange K) (o.hz.baseChange K))
#check (fun (p : ℕ) (K : Type) [instK : Field K] (lam : ℤ) (V : Type) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) => Nontrivial (LR.VK K M) ∧ ∃ o : LR.IntegralOps M x y h, ∀ W : Submodule K (LR.VK K M), LR.Inv W (o.xz.baseChange K) → LR.Inv W (o.yz.baseChange K) → LR.Inv W (o.hz.baseChange K) → W = ⊥ ∨ W = ⊤)
