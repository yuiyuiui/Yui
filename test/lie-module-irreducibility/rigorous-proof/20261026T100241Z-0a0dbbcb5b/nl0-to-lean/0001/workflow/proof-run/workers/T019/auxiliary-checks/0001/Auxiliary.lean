import Mathlib
open scoped TensorProduct
noncomputable section
namespace LR
abbrev Idx (l : ℕ) := Fin (l + 1)
def R (p : ℕ) : Subring ℚ := Subring.closure {q | ∃ a b : ℤ, ¬ (p : ℤ) ∣ b ∧ q = (a : ℚ) / (b : ℚ)}
instance rModule (p : ℕ) (V : Type*) [AddCommGroup V] [Module ℂ V] : Module (R p) V := Module.compHom V (algebraMap (R p) ℂ)
def MR (p : ℕ) {V : Type*} [AddCommGroup V] [Module ℂ V] (M : Submodule ℤ V) : Submodule (R p) V := Submodule.span (R p) (M : Set V)
def DP {V : Type*} [AddCommGroup V] [Module ℂ V] (f : Module.End ℂ V) (r : ℕ) : Module.End ℂ V := (r.factorial : ℂ)⁻¹ • f^r
def e {V : Type*} [AddCommGroup V] [Module ℂ V] (y : Module.End ℂ V) (v : V) (i : ℕ) : V := DP y i v
def Inv {F U : Type*} [Field F] [AddCommGroup U] [Module F U] (W : Submodule F U) (f : Module.End F U) : Prop := ∀ u ∈ W, f u ∈ W
def Brackets {F U : Type*} [CommRing F] [AddCommGroup U] [Module F U] (x y h : Module.End F U) : Prop := h*x-x*h = (2:F) • x ∧ h*y-y*h = (-2:F) • y ∧ x*y-y*x = h
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
 brackets : Brackets xz yz hz
abbrev VK (K : Type*) [Field K] {V : Type*} [AddCommGroup V] [Module ℂ V] (M : Submodule ℤ V) := K ⊗[ℤ] M
def Jc (p : ℕ) {V : Type*} [AddCommGroup V] [Module ℂ V] (M : Submodule ℤ V) (w : V) : Submodule (R p) ℂ := Submodule.span (R p) {c | c • w ∈ MR p M}
def pMR (p : ℕ) {V : Type*} [AddCommGroup V] [Module ℂ V] (M : Submodule ℤ V) : Submodule (R p) (MR p M) := LinearMap.range ((p : R p) • (LinearMap.id : MR p M →ₗ[R p] MR p M))
abbrev QMR (p : ℕ) {V : Type*} [AddCommGroup V] [Module ℂ V] (M : Submodule ℤ V) := (MR p M) ⧸ (pMR p M)
section Complex
variable {V : Type*} [AddCommGroup V] [Module ℂ V]
def Strings (lam : ℤ) (x y h : Module.End ℂ V) (v : V) : Prop :=
 (∀ m : ℕ, h ((y^m) v) = ((lam-2*(m:ℤ):ℤ):ℂ) • ((y^m) v)) ∧ (∀ m : ℕ, x ((y^(m+1)) v) = ((((m+1:ℕ):ℤ)*(lam-(m:ℤ)):ℤ):ℂ) • ((y^m) v))
def StringResult (lam : ℤ) (x y h : Module.End ℂ V) (v : V) : Prop :=
 0 < lam.toNat+1 ∧ Fintype.card (Idx lam.toNat) = lam.toNat+1 ∧ Strings lam x y h v ∧ e y v 0 = v ∧ (∃ B : Module.Basis (Idx lam.toNat) ℂ V, IsStringBasis lam.toNat y v B) ∧ (∀ m : ℕ, lam.toNat < m → (y^m) v = 0) ∧ Actions lam.toNat (e y v) x y h (DP x) (DP y)
structure LatticeEmbedding (p l : ℕ) (M : Submodule ℤ V) where
 basis : Module.Basis (Idx l) (R p) (MR p M)
 tensorEquiv : (R p ⊗[ℤ] M) ≃ₗ[R p] MR p M
 tensor_value : ∀ r m, (tensorEquiv (r ⊗ₜ[ℤ] m) : V) = (((r : R p) : ℚ) : ℂ) • (m : V)
 complex_span : Submodule.span ℂ (MR p M : Set V) = ⊤
def Preserves (p l : ℕ) (M : Submodule ℤ V) (x y h : Module.End ℂ V) : Prop :=
 Nonempty (IntegralOps M x y h) ∧ (∀ r m, m ∈ MR p M → DP x r m ∈ MR p M) ∧ (∀ r m, m ∈ MR p M → DP y r m ∈ MR p M) ∧ (∀ t, t ≤ l → IsUnit (t.factorial : R p)) ∧ (∀ j, j ≤ l → IsUnit (l.choose j : R p))
def MatrixControl (p l : ℕ) (M : Submodule ℤ V) (x y : Module.End ℂ V) (B : Module.Basis (Idx l) ℂ V) : Prop :=
 (DP y l * DP x l = MU B ⟨l,Nat.lt_succ_self l⟩ ⟨l,Nat.lt_succ_self l⟩) ∧
 (∀ i : Idx l, DP x (l-i.val) * MU B ⟨l,Nat.lt_succ_self l⟩ ⟨l,Nat.lt_succ_self l⟩ = MU B i ⟨l,Nat.lt_succ_self l⟩) ∧
 (∀ j : Idx l, MU B ⟨l,Nat.lt_succ_self l⟩ ⟨l,Nat.lt_succ_self l⟩ * DP y (l-j.val) = ((l.choose j.val : ℕ):ℂ) • MU B ⟨l,Nat.lt_succ_self l⟩ j) ∧
 (∀ i j : Idx l, MU B i j = (((l.choose j.val : ℕ):ℂ)⁻¹) • (DP x (l-i.val) * DP y l * DP x l * DP y (l-j.val))) ∧
 (∀ i j : Idx l, ∀ m, m ∈ MR p M → MU B i j m ∈ MR p M)
def LocalResult (p l : ℕ) (M : Submodule ℤ V) (x y h : Module.End ℂ V) (B : Module.Basis (Idx l) ℂ V) : Prop := Nonempty (LatticeEmbedding p l M) ∧ Preserves p l M x y h ∧ MatrixControl p l M x y B
structure Decomposition (p l : ℕ) (M : Submodule ℤ V) (v : V) (B : Module.Basis (Idx l) ℂ V) where
 exact_J : ∀ c : ℂ, c ∈ Jc p M v ↔ c • v ∈ MR p M
 exact_coord : ∀ i : Idx l, ∀ c : ℂ, c ∈ Jc p M (B i) ↔ c • B i ∈ MR p M
 common : ∀ i : Idx l, Jc p M (B i) = Jc p M v
 fg : (Jc p M v).FG
 nonzero : Jc p M v ≠ ⊥
 coordEquiv : (Idx l → Jc p M v) ≃ₗ[R p] MR p M
 coord_value : ∀ c, (coordEquiv c : V) = ∑ i, (c i : ℂ) • B i
abbrev T (p : ℕ) (M : Submodule ℤ V) (v : V) := ℚ ⊗[R p] Jc p M v
def RationalEmbedding (p : ℕ) (M : Submodule ℤ V) (v : V) : Prop :=
 ∃ mu : T p M v →ₗ[ℚ] ℂ, (∀ q c, mu (q ⊗ₜ[R p] c) = (q : ℂ) * (c : ℂ)) ∧ Function.Injective mu ∧ Module.Finite ℚ (T p M v)
def CoordinateResult (p l : ℕ) (M : Submodule ℤ V) (v : V) (B : Module.Basis (Idx l) ℂ V) : Prop :=
 0 < l+1 ∧ Nonempty (Decomposition p l M v B) ∧ RationalEmbedding p M v ∧ Module.finrank ℚ (T p M v) = 1 ∧ (∀ a c : ℂ, a ∈ Jc p M v → a ≠ 0 → c ∈ Jc p M v → ∃ q : ℚ, c = (q : ℂ) * a)
def PrincipalResult (p l : ℕ) (M : Submodule ℤ V) (v : V) (B : Module.Basis (Idx l) ℂ V) : Prop :=
 (∃ b : ℂ, b ∈ Jc p M v ∧ b ≠ 0 ∧ Jc p M v = Submodule.span (R p) {b}) ∧ (∀ b : ℂ, b ∈ Jc p M v → b ≠ 0 → Jc p M v = Submodule.span (R p) {b} → ∃ f : Module.Basis (Idx l) (R p) (MR p M), ∀ i, (f i : V) = b • B i) ∧ 0 < l+1 ∧ Fintype.card (Idx l) = l+1
structure FirstChange (p : ℕ) (K : Type*) [Field K] (M : Submodule ℤ V) where
 [ak : Algebra (R p) K]
 rho_value : ∀ a b : ℤ, ∀ r : R p, (r : ℚ) = (a : ℚ)/(b : ℚ) → ¬ (p : ℤ) ∣ b → algebraMap (R p) K r = (a : K)/(b : K)
 inc : M →ₗ[ℤ] MR p M
 inc_value : ∀ m, (inc m : V) = (m : V)
 A : VK K M ≃ₗ[K] (K ⊗[R p] MR p M)
 A_value : ∀ c m, A (c ⊗ₜ[ℤ] m) = c ⊗ₜ[R p] inc m
structure ScalarData (p : ℕ) (K : Type*) [Field K] (M : Submodule ℤ V) extends FirstChange p K M where
 [af : Algebra (ZMod p) K]
 [mq : Module (ZMod p) (QMR p M)]
 residue : (R p ⧸ Ideal.span {(p : R p)}) ≃+* ZMod p
 residue_value : ∀ a b : ℤ, ∀ r : R p, (r : ℚ) = (a : ℚ)/(b : ℚ) → ¬ (p : ℤ) ∣ b → residue (Ideal.Quotient.mk _ r) = (a : ZMod p) * (b : ZMod p)⁻¹
 C : (K ⊗[R p] MR p M) ≃ₗ[K] (K ⊗[ZMod p] QMR p M)
 C_value : ∀ c u, C (c ⊗ₜ[R p] u) = c ⊗ₜ[ZMod p] (pMR p M).mkQ u
structure ReducedBasis (p : ℕ) (K : Type*) [Field K] (l : ℕ) (M : Submodule ℤ V) (v : V) (B : Module.Basis (Idx l) ℂ V) where
 scalars : ScalarData p K M
 b : ℂ
 b_mem : b ∈ Jc p M v
 b_ne : b ≠ 0
 principal : Jc p M v = Submodule.span (R p) {b}
 f : Module.Basis (Idx l) (R p) (MR p M)
 f_value : ∀ i, (f i : V) = b • B i
 beta : Module.Basis (Idx l) K (VK K M)
 transported : letI := scalars.ak; ∀ i, scalars.A (beta i) = (1 : K) ⊗ₜ[R p] f i
 quotient_basis : letI := scalars.mq; ∃ gamma : Module.Basis (Idx l) (ZMod p) (QMR p M), ∀ i, gamma i = (pMR p M).mkQ (f i)
 dimension : Module.finrank K (VK K M) = l+1
 positive : 0 < l+1
 cardinality : Fintype.card (Idx l) = l+1
def ReducedAction (K : Type*) [Field K] (l : ℕ) (M : Submodule ℤ V) (x y h : Module.End ℂ V) (o : IntegralOps M x y h) (beta : Module.Basis (Idx l) K (VK K M)) : Prop :=
 Brackets (o.xz.baseChange K) (o.yz.baseChange K) (o.hz.baseChange K) ∧ Actions l (ext beta) (o.xz.baseChange K) (o.yz.baseChange K) (o.hz.baseChange K) (fun r => (o.Xz r).baseChange K) (fun r => (o.Yz r).baseChange K) ∧ (∀ r, r ≤ l → (r.factorial : K) ≠ 0 ∧ (o.Xz r).baseChange K = (r.factorial : K)⁻¹ • (o.xz.baseChange K)^r ∧ (o.Yz r).baseChange K = (r.factorial : K)⁻¹ • (o.yz.baseChange K)^r)
def ReducedControl (K : Type*) [Field K] (l : ℕ) (M : Submodule ℤ V) (x y h : Module.End ℂ V) (o : IntegralOps M x y h) (beta : Module.Basis (Idx l) K (VK K M)) : Prop :=
 (∀ i j : Idx l, MU beta i j = (((l.choose j.val : ℕ):K)⁻¹) • ((o.Xz (l-i.val)).baseChange K * (o.Yz l).baseChange K * (o.Xz l).baseChange K * (o.Yz (l-j.val)).baseChange K)) ∧ (∀ W : Submodule K (VK K M), Inv W (o.xz.baseChange K) → Inv W (o.yz.baseChange K) → ∀ i j, Inv W (MU beta i j))
def ReductionResult (p : ℕ) (K : Type*) [Field K] (l : ℕ) (M : Submodule ℤ V) (x y h : Module.End ℂ V) (v : V) (B : Module.Basis (Idx l) ℂ V) : Prop :=
 ∃ rb : ReducedBasis p K l M v B, ∃ o : IntegralOps M x y h, ReducedAction K l M x y h o rb.beta ∧ ReducedControl K l M x y h o rb.beta
end Complex
end LR

open Lean Elab Term
elab "yui_aux_type% " text:str : term => do
  let parsed ← ofExcept <| Parser.runParserCategory (← getEnv) `term text.getString
  Term.elabTerm parsed none

namespace YuiAuxiliary
set_option autoImplicit false
theorem checked (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_H002 : CharP K p) (h_T004 : LR.StringResult lam x y h v) (h_T008 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.LocalResult p lam.toNat M x y h B) (h_T016 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.PrincipalResult p lam.toNat M v B) (h_T018 : Nonempty (LR.ScalarData p K M)) : yui_aux_type% "∀ (s : LR.ScalarData p K M) (f : Module.Basis (LR.Idx lam.toNat) (LR.R p) (LR.MR p M)), letI := s.mq; ∃ gamma : Module.Basis (LR.Idx lam.toNat) (ZMod p) (LR.QMR p M), ∀ i, gamma i = (LR.pMR p M).mkQ (f i)" := by
  intro s f
  letI := s.mq
  have hp : LR.pMR p M = (Ideal.span {(p : LR.R p)}) • (⊤ : Submodule (LR.R p) (LR.MR p M)) := by
    rw [Submodule.ideal_span_singleton_smul]
    ext u
    simp [LR.pMR, Submodule.mem_smul_pointwise_iff_exists]
  let e₁ := Submodule.quotEquivOfEq (LR.pMR p M) _ hp
  let e₂ := TensorProduct.quotTensorEquivQuotSMul (LR.MR p M) (Ideal.span {(p : LR.R p)})
  let fq := f.baseChange (LR.R p ⧸ Ideal.span {(p : LR.R p)})
  let e₃ := fq.equivFun
  let e₄ := AddEquiv.piCongrRight (fun _ : LR.Idx lam.toNat => s.residue.toAddEquiv)
  let ea := e₁.toAddEquiv.trans (e₂.symm.toAddEquiv.trans (e₃.toAddEquiv.trans e₄))
  let E : LR.QMR p M ≃ₗ[ZMod p] (LR.Idx lam.toNat → ZMod p) :=
    { ea with map_smul' := ZMod.map_smul ea }
  refine ⟨Module.Basis.ofEquivFun E, ?_⟩
  intro i
  apply E.injective
  simp [E, ea, e₁, e₂, e₃, e₄, fq]
#check @checked
#print axioms checked
end YuiAuxiliary
