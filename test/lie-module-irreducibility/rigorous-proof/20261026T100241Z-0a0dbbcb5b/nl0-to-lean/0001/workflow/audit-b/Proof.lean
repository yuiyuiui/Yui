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

namespace Translation
set_option autoImplicit false

theorem T001 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H003 : 0 ≤ lam ∧ lam < (p : ℤ)) (h_H004 : Module.Finite ℂ V ∧ Module.finrank ℂ V = lam.toNat+1 ∧ LR.Brackets x y h ∧ Nontrivial V ∧ ∀ W : Submodule ℂ V, LR.Inv W x → LR.Inv W y → LR.Inv W h → W = ⊥ ∨ W = ⊤) (h_H005 : v ≠ 0 ∧ x v = 0 ∧ h v = (lam : ℂ) • v) :
    LR.Strings lam x y h v := by
  rcases h_H004.2.2.1 with ⟨hhx, hhy, hxy⟩
  have hy (w : V) : h (y w) = y (h w) - (2 : ℂ) • y w := by
    have hh := congrArg (fun f : Module.End ℂ V => f w) hhy
    change h (y w) - y (h w) = (-2 : ℂ) • y w at hh
    rw [sub_eq_iff_eq_add] at hh
    rw [hh]
    module
  have xy (w : V) : x (y w) = y (x w) + h w := by
    have hh := congrArg (fun f : Module.End ℂ V => f w) hxy
    change x (y w) - y (x w) = h w at hh
    exact (sub_eq_iff_eq_add.mp hh).trans (add_comm _ _)
  change (∀ m : ℕ, _) ∧ (∀ m : ℕ, _)
  have hp (m : ℕ) : (y ^ (m+1)) v = y ((y^m) v) := by
    rw [pow_succ']; rfl
  have both : ∀ m : ℕ,
      h ((y^m) v) = (((lam - 2*(m:ℤ) : ℤ) : ℂ)) • ((y^m) v) ∧
      x ((y^(m+1)) v) = (((((m+1:ℕ):ℤ)*(lam-(m:ℤ)) : ℤ) : ℂ)) • ((y^m) v) := by
    intro m
    induction m with
    | zero =>
      constructor
      · simpa using h_H005.2.2
      · rw [hp, xy]
        simp [h_H005.2.1, h_H005.2.2]
    | succ m ih =>
      constructor
      · rw [hp, hy, ih.1, map_smul]
        push_cast
        module
      · rw [hp (m+1), xy, ih.2, map_smul, ← hp m]
        rw [hp, hy, ih.1, map_smul]
        push_cast
        module
  exact ⟨fun m => (both m).1, fun m => (both m).2⟩

theorem T002 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H003 : 0 ≤ lam ∧ lam < (p : ℤ)) (h_H005 : v ≠ 0 ∧ x v = 0 ∧ h v = (lam : ℂ) • v) (h_T001 : LR.Strings lam x y h v) :
    (∀ i : LR.Idx lam.toNat, LR.e y v i.val ≠ 0) ∧ LinearIndependent ℂ (fun i : LR.Idx lam.toNat => LR.e y v i.val) := by
  classical
  have hy : ∀ n : ℕ, n ≤ lam.toNat → (y^n) v ≠ 0 := by
    intro n
    induction n with
    | zero => simpa using h_H005.1
    | succ n ih =>
      intro hn hz
      have hnlam : (n : ℤ) < lam := by
        have := Int.toNat_of_nonneg h_H003.1
        omega
      have hc : (((((n+1:ℕ):ℤ) * (lam-(n:ℤ)) : ℤ) : ℂ)) ≠ 0 := by
        exact_mod_cast (ne_of_gt (mul_pos (by omega : (0:ℤ) < (n+1:ℕ)) (by omega : (0:ℤ) < lam-n)))
      have hh := h_T001.2 n
      rw [hz, map_zero] at hh
      exact (smul_ne_zero hc (ih (by omega))) hh.symm
  have he : ∀ i : LR.Idx lam.toNat, LR.e y v i.val ≠ 0 := by
    intro i
    have hf : (i.val.factorial : ℂ) ≠ 0 := by exact_mod_cast Nat.factorial_ne_zero i.val
    simpa [LR.e, LR.DP] using smul_ne_zero (inv_ne_zero hf) (hy i.val (by have := i.isLt; omega))
  have hw : ∀ i : LR.Idx lam.toNat, h (LR.e y v i.val) = (((lam - 2*(i.val:ℤ):ℤ):ℂ)) • LR.e y v i.val := by
    intro i
    simp only [LR.e, LR.DP, LinearMap.smul_apply, map_smul, h_T001.1]
    rw [smul_comm]
  let w : LR.Idx lam.toNat → ℂ := fun i => ((lam - 2*(i.val:ℤ):ℤ):ℂ)
  have hinj : Function.Injective w := by
    intro i j hij
    change ((lam - 2*(i.val:ℤ):ℤ):ℂ) = ((lam - 2*(j.val:ℤ):ℤ):ℂ) at hij
    have hij' : lam - 2*(i.val:ℤ) = lam - 2*(j.val:ℤ) := by exact_mod_cast hij
    apply Fin.ext
    omega
  refine ⟨he, Fintype.linearIndependent_iff.mpr ?_⟩
  intro c hc j
  let q : Polynomial ℂ := ∏ k ∈ (Finset.univ.erase j), (Polynomial.X - Polynomial.C (w k))
  have hq (i : LR.Idx lam.toNat) : q.eval (w i) = ∏ k ∈ (Finset.univ.erase j), (w i - w k) := by
    simp [q, Polynomial.eval_prod]
  have hz (i : LR.Idx lam.toNat) (hij : i ≠ j) : q.eval (w i) = 0 := by
    rw [hq]
    apply Finset.prod_eq_zero (Finset.mem_erase.mpr ⟨hij, Finset.mem_univ _⟩)
    simp
  have hn : q.eval (w j) ≠ 0 := by
    rw [hq]
    apply Finset.prod_ne_zero_iff.mpr
    intro k hk
    exact sub_ne_zero.mpr (fun hh => (Finset.mem_erase.mp hk).1 (hinj hh).symm)
  have ht := congrArg (fun z : V => (Polynomial.aeval h q) z) hc
  simp only [map_sum, map_smul, map_zero] at ht
  simp_rw [Module.End.aeval_apply_of_mem_apply_eq_smul (hw _)] at ht
  have hs : (∑ i, c i • (q.eval (w i) • LR.e y v i.val)) = c j • (q.eval (w j) • LR.e y v j.val) := by
    apply Finset.sum_eq_single j
    · intro i hi hij
      rw [hz i hij, zero_smul, smul_zero]
    · simp
  change (∑ i, c i • (q.eval (w i) • LR.e y v i.val)) = 0 at ht
  rw [hs, smul_smul] at ht
  exact (mul_eq_zero.mp ((smul_eq_zero.mp ht).resolve_right (he j))).resolve_right hn

theorem T003 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H003 : 0 ≤ lam ∧ lam < (p : ℤ)) (h_H004 : Module.Finite ℂ V ∧ Module.finrank ℂ V = lam.toNat+1 ∧ LR.Brackets x y h ∧ Nontrivial V ∧ ∀ W : Submodule ℂ V, LR.Inv W x → LR.Inv W y → LR.Inv W h → W = ⊥ ∨ W = ⊤) (h_T001 : LR.Strings lam x y h v) (h_T002 : (∀ i : LR.Idx lam.toNat, LR.e y v i.val ≠ 0) ∧ LinearIndependent ℂ (fun i : LR.Idx lam.toNat => LR.e y v i.val)) :
    (∃ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B) ∧ (∀ m : ℕ, lam.toNat < m → (y^m) v = 0) := by
  classical
  letI : Module.Finite ℂ V := h_H004.1
  let B : Module.Basis (LR.Idx lam.toNat) ℂ V :=
    basisOfLinearIndependentOfCardEqFinrank h_T002.2 (by simpa [LR.Idx] using h_H004.2.1.symm)
  have hB : ∀ i, B i = LR.e y v i.val := by
    intro i
    exact congrFun (coe_basisOfLinearIndependentOfCardEqFinrank _ _) i
  have heig : ∀ i, h (B i) = (((lam - 2 * (i.val : ℤ) : ℤ) : ℂ)) • B i := by
    intro i
    rw [hB]
    simp only [LR.e, LR.DP, LinearMap.smul_apply, map_smul]
    rw [h_T001.1]
    exact smul_comm _ _ _
  have hc : ∀ (u : V) (i : LR.Idx lam.toNat),
      B.repr (h u) i = (((lam - 2 * (i.val : ℤ) : ℤ) : ℂ)) * B.repr u i := by
    intro u i
    change B.coord i (h u) = _
    calc
      B.coord i (h u) = B.coord i (h (∑ j, B.repr u j • B j)) := by rw [B.sum_repr]
      _ = _ := by
        simp only [map_sum, map_smul, heig]
        simp [Module.Basis.coord_apply, Finsupp.single_apply, mul_comm]
  constructor
  · exact ⟨B, hB⟩
  · intro m hm
    have hz : (y ^ (lam.toNat + 1)) v = 0 := by
      apply B.repr.injective
      ext i
      have hh := congrArg (fun u => B.repr u i) (h_T001.1 (lam.toNat + 1))
      rw [hc] at hh
      simp only [map_smul, Finsupp.smul_apply, smul_eq_mul] at hh
      have hn : (((lam - 2 * (i.val : ℤ) : ℤ) : ℂ)) ≠
          (((lam - 2 * ((lam.toNat + 1 : ℕ) : ℤ) : ℤ) : ℂ)) := by
        intro he
        have he' : lam - 2 * (i.val : ℤ) = lam - 2 * ((lam.toNat + 1 : ℕ) : ℤ) := by exact_mod_cast he
        have hi := i.isLt
        omega
      have hz' := (mul_eq_mul_right_iff).mp hh
      simp only [map_zero, Finsupp.zero_apply]
      exact hz'.resolve_left hn
    obtain ⟨k, hk⟩ := Nat.exists_eq_add_of_le (show lam.toNat + 1 ≤ m by omega)
    rw [hk, Nat.add_comm (lam.toNat + 1) k, pow_add, Module.End.mul_apply, hz, map_zero]

theorem T004 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H003 : 0 ≤ lam ∧ lam < (p : ℤ)) (h_H005 : v ≠ 0 ∧ x v = 0 ∧ h v = (lam : ℂ) • v) (h_T001 : LR.Strings lam x y h v) (h_T002 : (∀ i : LR.Idx lam.toNat, LR.e y v i.val ≠ 0) ∧ LinearIndependent ℂ (fun i : LR.Idx lam.toNat => LR.e y v i.val)) (h_T003 : (∃ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B) ∧ (∀ m : ℕ, lam.toNat < m → (y^m) v = 0)) :
    LR.StringResult lam x y h v := by
  have fac (i : ℕ) : (i.factorial : ℂ) ≠ 0 := by exact_mod_cast Nat.factorial_ne_zero i
  have e0 : LR.e y v 0 = v := by simp [LR.e, LR.DP]
  have ya (i : ℕ) : y (LR.e y v i) = ((i+1 : ℕ) : ℂ) • LR.e y v (i+1) := by
    simp only [LR.e, LR.DP, LinearMap.smul_apply, map_smul]
    rw [pow_succ', Module.End.mul_apply]
    rw [Nat.factorial_succ, Nat.cast_mul, smul_smul]
    congr 1
    have hi : ((i+1:ℕ):ℂ) ≠ 0 := by exact_mod_cast Nat.succ_ne_zero i
    field_simp
  have xa (i : ℕ) (hi : 1 ≤ i) (hil : i ≤ lam.toNat) : x (LR.e y v i) = ((lam.toNat-i+1 : ℕ):ℂ) • LR.e y v (i-1) := by
    obtain ⟨j, rfl⟩ := Nat.exists_eq_succ_of_ne_zero (by omega : i ≠ 0)
    simp only [LR.e, LR.DP, LinearMap.smul_apply, map_smul, h_T001.2, Nat.succ_sub_one]
    have hl : (lam : ℂ) = (lam.toNat : ℂ) := by rw [← Int.cast_natCast, Int.toNat_of_nonneg h_H003.1]
    have hj : ((j+1:ℕ):ℂ) ≠ 0 := by exact_mod_cast Nat.succ_ne_zero j
    have hsub : ((lam.toNat-(j+1)+1 : ℕ):ℂ) = (lam.toNat : ℂ) - j := by
      push_cast [Nat.cast_sub (show j+1 ≤ lam.toNat from hil)]
      ring
    simp only [Int.cast_mul, Int.cast_natCast, Int.cast_sub, Nat.factorial_succ, Nat.cast_mul, smul_smul]
    rw [hl, hsub]
    congr 1
    field_simp
    <;> ring
  have ha (i : ℕ) (hi : i ≤ lam.toNat) : h (LR.e y v i) = (((lam.toNat:ℤ)-2*(i:ℤ):ℤ):ℂ) • LR.e y v i := by
    rw [Int.toNat_of_nonneg h_H003.1]
    simp only [LR.e, LR.DP, LinearMap.smul_apply, map_smul, h_T001.1, smul_smul]
    congr 1
    ring
  have xzero : x (LR.e y v 0) = 0 := by rw [e0]; exact h_H005.2.1
  have xp : ∀ r i : ℕ, i ≤ lam.toNat → (x^r) (LR.e y v i) = if r ≤ i then (((lam.toNat-i+1).ascFactorial r : ℕ):ℂ) • LR.e y v (i-r) else 0 := by
    intro r
    induction r with
    | zero => intro i hi; simp
    | succ r ih =>
      intro i hi
      rw [pow_succ', Module.End.mul_apply, ih i hi]
      by_cases hr : r ≤ i
      · rw [if_pos hr, map_smul]
        by_cases hs : r+1 ≤ i
        · rw [if_pos hs, xa (i-r) (by omega) (by omega), smul_smul, Nat.ascFactorial_succ]
          have he : lam.toNat - (i-r) + 1 = lam.toNat-i+1+r := by omega
          have he' : i-r-1 = i-(r+1) := by omega
          rw [he, he', Nat.cast_mul]
          congr 1
          ring
        · have he : r = i := by omega
          subst r
          simp [Nat.sub_self, xzero, show ¬ i+1 ≤ i by omega]
      · rw [if_neg hr, map_zero, if_neg (by omega : ¬ r+1 ≤ i)]
  have yp : ∀ r i : ℕ, (y^r) (LR.e y v i) = (((i+1).ascFactorial r : ℕ):ℂ) • LR.e y v (i+r) := by
    intro r
    induction r with
    | zero => intro i; simp
    | succ r ih =>
      intro i
      rw [pow_succ', Module.End.mul_apply, ih, map_smul, ya, smul_smul, Nat.ascFactorial_succ, Nat.cast_mul]
      have he : i+r+1 = i+(r+1) := by omega
      rw [he]
      congr 1
      push_cast
      ring
  refine ⟨by omega, by simp [LR.Idx], h_T001, e0, h_T003.1, h_T003.2, ?_⟩
  refine ⟨xzero, xa, (fun i hi => ya i), ha, ?_, ?_⟩
  · intro r i hi
    simp only [LR.DP, LinearMap.smul_apply, xp r i hi]
    by_cases hr : r ≤ i
    · rw [if_pos hr, if_pos hr, smul_smul, Nat.ascFactorial_eq_factorial_mul_choose, Nat.cast_mul]
      rw [← mul_assoc, inv_mul_cancel₀ (fac r), one_mul]
    · simp [hr]
  · intro r i hi
    simp only [LR.DP, LinearMap.smul_apply, yp r i]
    rw [Nat.ascFactorial_eq_factorial_mul_choose, Nat.cast_mul, smul_smul]
    rw [← mul_assoc, inv_mul_cancel₀ (fac r), one_mul]
    by_cases hr : i+r ≤ lam.toNat
    · rw [if_pos hr]
    · rw [if_neg hr]
      have hz : LR.e y v (i+r) = 0 := by
        simp [LR.e, LR.DP, h_T003.2 (i+r) (by omega)]
      rw [hz, smul_zero]

theorem T005 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) :
    ∀ q : ℚ, q ∈ LR.R p ↔ ∃ a b : ℤ, b ≠ 0 ∧ ¬ (p : ℤ) ∣ b ∧ q = (a : ℚ)/(b : ℚ) := by
  have hp : Prime (p : ℤ) := Nat.prime_iff_prime_int.mp h_H001
  let S : Subring ℚ :=
    { carrier := {q | ∃ a b : ℤ, b ≠ 0 ∧ ¬ (p : ℤ) ∣ b ∧ q = (a : ℚ) / (b : ℚ)}
      zero_mem' := by
        exact ⟨0, 1, one_ne_zero, hp.not_dvd_one, by norm_num⟩
      one_mem' := by
        exact ⟨1, 1, one_ne_zero, hp.not_dvd_one, by norm_num⟩
      add_mem' := by
        rintro u w ⟨a, b, hb, hpb, rfl⟩ ⟨c, d, hd, hpd, rfl⟩
        refine ⟨a*d+c*b, b*d, mul_ne_zero hb hd, hp.not_dvd_mul hpb hpd, ?_⟩
        push_cast
        simpa only [mul_comm] using
          (div_add_div (b := (b : ℚ)) (d := (d : ℚ)) (a : ℚ) (c : ℚ)
            (by exact_mod_cast hb) (by exact_mod_cast hd))
      mul_mem' := by
        rintro u w ⟨a, b, hb, hpb, rfl⟩ ⟨c, d, hd, hpd, rfl⟩
        refine ⟨a*c, b*d, mul_ne_zero hb hd, hp.not_dvd_mul hpb hpd, ?_⟩
        push_cast
        exact div_mul_div_comm _ _ _ _
      neg_mem' := by
        rintro u ⟨a, b, hb, hpb, rfl⟩
        refine ⟨-a, b, hb, hpb, ?_⟩
        simp only [Int.cast_neg, neg_div] }
  have hRS : LR.R p ≤ S := by
    apply Subring.closure_le.mpr
    rintro q ⟨a, b, hpb, hq⟩
    exact ⟨a, b, fun hb => hpb (hb ▸ dvd_zero _), hpb, hq⟩
  intro q
  constructor
  · exact fun hq => hRS hq
  · rintro ⟨a, b, hb, hpb, hq⟩
    exact Subring.subset_closure ⟨a, b, hpb, hq⟩

theorem T006 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_H004 : Module.Finite ℂ V ∧ Module.finrank ℂ V = lam.toNat+1 ∧ LR.Brackets x y h ∧ Nontrivial V ∧ ∀ W : Submodule ℂ V, LR.Inv W x → LR.Inv W y → LR.Inv W h → W = ⊥ ∨ W = ⊤) (h_H006 : (∃ f : Module.Basis (LR.Idx lam.toNat) ℤ M, ∃ c : Module.Basis (LR.Idx lam.toNat) ℂ V, ∀ i, (f i : V) = c i) ∧ (∀ r m, m ∈ M → LR.DP x r m ∈ M) ∧ (∀ r m, m ∈ M → LR.DP y r m ∈ M)) (h_T004 : LR.StringResult lam x y h v) (h_T005 : ∀ q : ℚ, q ∈ LR.R p ↔ ∃ a b : ℤ, b ≠ 0 ∧ ¬ (p : ℤ) ∣ b ∧ q = (a : ℚ)/(b : ℚ)) :
    Nonempty (LR.LatticeEmbedding p lam.toNat M) := by
  classical
  letI : IsScalarTower (LR.R p) ℂ V := IsScalarTower.of_compHom (LR.R p) ℂ V
  rcases h_H006.1 with ⟨f, c, hfc⟩
  have hs : Submodule.span (LR.R p) (Set.range c) = LR.MR p M := by
    apply le_antisymm
    · apply Submodule.span_le.mpr
      rintro _ ⟨i, rfl⟩
      rw [← hfc]
      exact Submodule.subset_span (f i).property
    · apply Submodule.span_le.mpr
      intro m hm
      have he := congrArg (fun z : M => (z : V)) (f.sum_repr ⟨m, hm⟩)
      simp only [Submodule.coe_sum, Submodule.coe_smul] at he
      rw [← he]
      apply Submodule.sum_mem
      intro i hi
      apply (Submodule.span (LR.R p) (Set.range c)).toAddSubgroup.zsmul_mem
      exact Submodule.subset_span ⟨i, (hfc i).symm⟩
  let g := (c.restrictScalars (LR.R p)).map (LinearEquiv.ofEq _ _ hs)
  have hg : ∀ i, (g i : V) = c i := by
    intro i
    simp [g]
  let E := (f.baseChange (LR.R p)).equiv g (Equiv.refl _)
  have hE : ∀ i, E (1 ⊗ₜ[ℤ] f i) = g i := by
    intro i
    simpa only [Module.Basis.baseChange_apply, Equiv.refl_apply] using
      (f.baseChange (LR.R p)).equiv_apply i g (Equiv.refl _)
  have hval : ((LR.MR p M).subtype.restrictScalars ℤ).comp
      ((E.toLinearMap.restrictScalars ℤ).comp ((TensorProduct.mk ℤ (LR.R p) M) 1)) = M.subtype := by
    apply f.ext
    intro i
    change (E (1 ⊗ₜ[ℤ] f i) : V) = (f i : V)
    rw [hE, hg, hfc]
  refine ⟨{ basis := g, tensorEquiv := E, tensor_value := ?_, complex_span := ?_ }⟩
  · intro r m
    have hm : (E (1 ⊗ₜ[ℤ] m) : V) = (m : V) := LinearMap.congr_fun hval m
    have ht : r ⊗ₜ[ℤ] m = r • (1 ⊗ₜ[ℤ] m) := by
      rw [TensorProduct.smul_tmul', smul_eq_mul, mul_one]
    rw [ht, map_smul, Submodule.coe_smul, hm]
    rfl
  · apply top_unique
    rw [← c.span_eq]
    apply Submodule.span_mono
    rintro _ ⟨i, rfl⟩
    rw [← hfc]
    exact Submodule.subset_span (f i).property

theorem T007 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_H003 : 0 ≤ lam ∧ lam < (p : ℤ)) (h_H004 : Module.Finite ℂ V ∧ Module.finrank ℂ V = lam.toNat+1 ∧ LR.Brackets x y h ∧ Nontrivial V ∧ ∀ W : Submodule ℂ V, LR.Inv W x → LR.Inv W y → LR.Inv W h → W = ⊥ ∨ W = ⊤) (h_H006 : (∃ f : Module.Basis (LR.Idx lam.toNat) ℤ M, ∃ c : Module.Basis (LR.Idx lam.toNat) ℂ V, ∀ i, (f i : V) = c i) ∧ (∀ r m, m ∈ M → LR.DP x r m ∈ M) ∧ (∀ r m, m ∈ M → LR.DP y r m ∈ M)) (h_T004 : LR.StringResult lam x y h v) (h_T005 : ∀ q : ℚ, q ∈ LR.R p ↔ ∃ a b : ℤ, b ≠ 0 ∧ ¬ (p : ℤ) ∣ b ∧ q = (a : ℚ)/(b : ℚ)) :
    LR.Preserves p lam.toNat M x y h := by
  have hxM : ∀ m ∈ M, x m ∈ M := by
    intro m hm
    simpa [LR.DP] using h_H006.2.1 1 m hm
  have hyM : ∀ m ∈ M, y m ∈ M := by
    intro m hm
    simpa [LR.DP] using h_H006.2.2 1 m hm
  have hhM : ∀ m ∈ M, h m ∈ M := by
    intro m hm
    rw [← h_H004.2.2.1.2.2]
    exact M.sub_mem (hxM _ (hyM _ hm)) (hyM _ (hxM _ hm))
  let xz : Module.End ℤ M := (x.restrictScalars ℤ).restrict hxM
  let yz : Module.End ℤ M := (y.restrictScalars ℤ).restrict hyM
  let hz : Module.End ℤ M := (h.restrictScalars ℤ).restrict hhM
  have bx : LR.Brackets xz yz hz := by
    rcases h_H004.2.2.1 with ⟨h1,h2,h3⟩
    refine ⟨?_, ?_, ?_⟩
    · ext m
      simpa [xz, yz, hz, two_smul] using congrArg (fun f : Module.End ℂ V => f m) h1
    · ext m
      simpa [xz, yz, hz, two_smul] using congrArg (fun f : Module.End ℂ V => f m) h2
    · ext m
      simpa [xz, yz, hz] using congrArg (fun f : Module.End ℂ V => f m) h3
  have ops : Nonempty (LR.IntegralOps M x y h) := by
    refine ⟨{
      xz := xz
      yz := yz
      hz := hz
      Xz := fun r => ((LR.DP x r).restrictScalars ℤ).restrict (h_H006.2.1 r)
      Yz := fun r => ((LR.DP y r).restrictScalars ℤ).restrict (h_H006.2.2 r)
      x_agree := fun _ => rfl
      y_agree := fun _ => rfl
      h_agree := fun _ => rfl
      X_agree := fun _ _ => rfl
      Y_agree := fun _ _ => rfl
      brackets := bx }⟩
  have span_pres (f : Module.End ℂ V) (hf : ∀ m ∈ M, f m ∈ M) :
      ∀ m ∈ LR.MR p M, f m ∈ LR.MR p M := by
    intro m hm
    induction hm using Submodule.span_induction with
    | mem m hm => exact Submodule.subset_span (hf m hm)
    | zero => simpa using (LR.MR p M).zero_mem
    | add a b ha hb ia ib => simpa using (LR.MR p M).add_mem ia ib
    | smul a b hb ib =>
      change f (algebraMap (LR.R p) ℂ a • b) ∈ LR.MR p M
      rw [map_smul]
      exact (LR.MR p M).smul_mem a ib
  have hlp : lam.toNat < p := by omega
  have units : ∀ t, t ≤ lam.toNat → IsUnit (t.factorial : LR.R p) := by
    intro t ht
    have hnd : ¬ p ∣ t.factorial := h_H001.coprime_iff_not_dvd.mp
      (h_H001.coprime_factorial_of_lt (lt_of_le_of_lt ht hlp))
    have hndi : ¬ (p : ℤ) ∣ (t.factorial : ℤ) := by exact_mod_cast hnd
    have hmem : (1 / (t.factorial : ℚ)) ∈ LR.R p :=
      (h_T005 _).mpr ⟨1, (t.factorial : ℤ), by exact_mod_cast Nat.factorial_ne_zero t,
        hndi, by simp⟩
    apply isUnit_iff_exists_inv.mpr
    refine ⟨⟨_, hmem⟩, ?_⟩
    apply Subtype.ext
    change (t.factorial : ℚ) * (1 / (t.factorial : ℚ)) = 1
    simp [Nat.factorial_ne_zero]
  refine ⟨ops, (fun r => span_pres _ (h_H006.2.1 r)),
    (fun r => span_pres _ (h_H006.2.2 r)), units, ?_⟩
  intro j hj
  have hid : (lam.toNat.choose j : LR.R p) * (j.factorial : LR.R p) *
      ((lam.toNat-j).factorial : LR.R p) = (lam.toNat.factorial : LR.R p) := by
    exact_mod_cast Nat.choose_mul_factorial_mul_factorial hj
  have hu := units lam.toNat le_rfl
  rw [← hid] at hu
  exact isUnit_of_mul_isUnit_left (isUnit_of_mul_isUnit_left hu)

theorem T008 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_T004 : LR.StringResult lam x y h v) (h_T005 : ∀ q : ℚ, q ∈ LR.R p ↔ ∃ a b : ℤ, b ≠ 0 ∧ ¬ (p : ℤ) ∣ b ∧ q = (a : ℚ)/(b : ℚ)) (h_T006 : Nonempty (LR.LatticeEmbedding p lam.toNat M)) (h_T007 : LR.Preserves p lam.toNat M x y h) :
    ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.LocalResult p lam.toNat M x y h B := by
  classical
  intro B hB
  refine ⟨h_T006, h_T007, ?_⟩
  let l := lam.toNat
  let t : LR.Idx l := ⟨l, Nat.lt_succ_self l⟩
  let z : LR.Idx l := ⟨0, by omega⟩
  have hb (i : LR.Idx l) : LR.e y v i.val = B i := (hB i).symm
  have acts := h_T004.2.2.2.2.2.2
  have hx (r : ℕ) (k : LR.Idx l) : LR.DP x r (B k) = if hr : r ≤ k.val then (((l-k.val+r).choose r : ℕ) : ℂ) • B ⟨k.val-r, by omega⟩ else 0 := by
    rw [hB k, acts.2.2.2.2.1 r k.val (by omega)]
    split_ifs with hr
    · rw [hb ⟨k.val-r, by omega⟩]
    · rfl
  have hy (r : ℕ) (k : LR.Idx l) : LR.DP y r (B k) = if hr : k.val+r ≤ l then (((k.val+r).choose r : ℕ) : ℂ) • B ⟨k.val+r, by omega⟩ else 0 := by
    rw [hB k, acts.2.2.2.2.2 r k.val (by omega)]
    split_ifs with hr
    · rw [hb ⟨k.val+r, by omega⟩]
    · rfl
  have mu (i j k : LR.Idx l) : LR.MU B i j (B k) = if j = k then B i else 0 := by
    by_cases he : j = k <;> simp_all [LR.MU, Module.Basis.coord_apply]
  have xl (k : LR.Idx l) : LR.DP x l (B k) = if t = k then B z else 0 := by
    by_cases he : t = k
    · subst k; simp [hx, t, z]
    · have hk : ¬ l ≤ k.val := by
        intro hk
        apply he
        apply Fin.ext
        dsimp [t]
        omega
      simp [hx, hk, he]
  have yl : LR.DP y l (B z) = B t := by simp [hy, z, t]
  have xlast (i : LR.Idx l) : LR.DP x (l-i.val) (B t) = B i := by
    have hi : l - (l - i.val) = i.val := by omega
    simp [hx, t, hi]
  have H1 : LR.DP y l * LR.DP x l = LR.MU B t t := by
    apply B.ext
    intro k
    simp only [Module.End.mul_apply, xl, mu]
    split_ifs <;> simp_all
  have comp (i j : LR.Idx l) : LR.DP x (l-i.val) * LR.MU B t j = LR.MU B i j := by
    apply B.ext
    intro k
    simp only [Module.End.mul_apply, mu]
    split_ifs <;> simp_all
  have H2 (i : LR.Idx l) : LR.DP x (l-i.val) * LR.MU B t t = LR.MU B i t := comp i t
  have H3 (j : LR.Idx l) : LR.MU B t t * LR.DP y (l-j.val) = ((l.choose j.val : ℕ):ℂ) • LR.MU B t j := by
    apply B.ext
    intro k
    simp only [Module.End.mul_apply, LinearMap.smul_apply, mu]
    rw [hy]
    by_cases he : j = k
    · subst k
      have hj : j.val + (l-j.val) = l := by omega
      simp [hj, Nat.choose_symm (show j.val ≤ l by omega), t, mu]
    · by_cases hk : k.val + (l-j.val) ≤ l
      · rw [dif_pos hk, map_smul, mu, if_neg he]
        have hn : t ≠ (⟨k.val + (l-j.val), by omega⟩ : LR.Idx l) := by
          intro hn
          have hv := congrArg Fin.val hn
          apply he
          apply Fin.ext
          dsimp [t] at hv
          omega
        simp [hn]
      · simp [hk, he]
  have prod (i j : LR.Idx l) : LR.DP x (l-i.val) * LR.DP y l * LR.DP x l * LR.DP y (l-j.val) = ((l.choose j.val : ℕ):ℂ) • LR.MU B i j := by
    rw [mul_assoc (LR.DP x (l-i.val)), H1, mul_assoc, H3, mul_smul_comm, comp]
  have H4 (i j : LR.Idx l) : LR.MU B i j = (((l.choose j.val : ℕ):ℂ)⁻¹) • (LR.DP x (l-i.val) * LR.DP y l * LR.DP x l * LR.DP y (l-j.val)) := by
    have hc : ((l.choose j.val : ℕ):ℂ) ≠ 0 := by exact_mod_cast (Nat.choose_pos (show j.val ≤ l by omega)).ne'
    rw [prod, smul_smul, inv_mul_cancel₀ hc, one_smul]
  refine ⟨H1, H2, H3, H4, ?_⟩
  intro i j m hm
  rw [H4]
  have hm' : (LR.DP x (l-i.val) * LR.DP y l * LR.DP x l * LR.DP y (l-j.val)) m ∈ LR.MR p M := by
    exact h_T007.2.1 _ _ (h_T007.2.2.1 _ _ (h_T007.2.1 _ _ (h_T007.2.2.1 _ _ hm)))
  let hu := h_T007.2.2.2.2 j.val (show j.val ≤ lam.toNat by omega)
  have hr : algebraMap (LR.R p) ℂ (↑(hu.unit⁻¹) : LR.R p) = ((l.choose j.val : ℕ):ℂ)⁻¹ := by
    apply eq_inv_of_mul_eq_one_left
    have hh := congrArg (algebraMap (LR.R p) ℂ) (Units.inv_mul hu.unit)
    simpa only [map_mul, map_one, hu.unit_spec, map_natCast] using hh
  have hs := (LR.MR p M).smul_mem (↑(hu.unit⁻¹) : LR.R p) hm'
  change (algebraMap (LR.R p) ℂ (↑(hu.unit⁻¹) : LR.R p)) • _ ∈ LR.MR p M at hs
  simpa only [hr, LinearMap.smul_apply] using hs

theorem T009 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_T004 : LR.StringResult lam x y h v) (h_T008 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.LocalResult p lam.toNat M x y h B) :
    ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → Nonempty (LR.Decomposition p lam.toNat M v B) := by
  classical
  intro B hB
  rcases h_T008 B hB with ⟨⟨emb⟩, hp, hc⟩
  let S := LR.MR p M
  let L (w : V) : ℂ →ₗ[LR.R p] V :=
    { toFun := fun c => c • w
      map_add' := fun a b => add_smul a b w
      map_smul' := by
        intro r c
        change ((algebraMap (LR.R p) ℂ r) * c) • w = (algebraMap (LR.R p) ℂ r) • (c • w)
        exact mul_smul _ _ _ }
  have exactJ (w : V) (c : ℂ) : c ∈ LR.Jc p M w ↔ c • w ∈ S := by
    change c ∈ Submodule.span (LR.R p) {c | c • w ∈ S} ↔ _
    have he : {c : ℂ | c • w ∈ S} = (S.comap (L w) : Set ℂ) := rfl
    rw [he, Submodule.span_eq]
    rfl
  let z : LR.Idx lam.toNat := ⟨0, Nat.zero_lt_succ _⟩
  have hz : B z = v := (hB z).trans h_T004.2.2.2.1
  have mu (i j : LR.Idx lam.toNat) (w : V) : LR.MU B i j w = B.repr w j • B i := rfl
  have common (i : LR.Idx lam.toNat) : LR.Jc p M (B i) = LR.Jc p M v := by
    rw [← hz]
    apply le_antisymm
    · intro c hc'
      apply (exactJ _ _).mpr
      have hh := hc.2.2.2.2 z i (c • B i) ((exactJ _ _).mp hc')
      simpa [mu] using hh
    · intro c hc'
      apply (exactJ _ _).mpr
      have hh := hc.2.2.2.2 i z (c • B z) ((exactJ _ _).mp hc')
      simpa [mu] using hh
  let C (i : LR.Idx lam.toNat) : S →ₗ[LR.R p] ℂ :=
    { toFun := fun m => B.repr (m : V) i
      map_add' := by intros; simp
      map_smul' := by
        intro r m
        change B.repr ((algebraMap (LR.R p) ℂ r) • (m : V)) i = (algebraMap (LR.R p) ℂ r) * B.repr (m : V) i
        simp }
  have coord_mem (i : LR.Idx lam.toNat) (m : S) : B.repr (m : V) i ∈ LR.Jc p M v := by
    rw [← common i]
    apply (exactJ _ _).mpr
    exact hc.2.2.2.2 i i m m.property
  have rangeC : LinearMap.range (C z) = LR.Jc p M v := by
    ext c
    constructor
    · rintro ⟨m, rfl⟩
      exact coord_mem z m
    · intro hc'
      refine ⟨⟨c • v, (exactJ _ _).mp hc'⟩, ?_⟩
      change B.repr (c • v) z = c
      simp [← hz]
  have fg : (LR.Jc p M v).FG := by
    letI : Module.Finite (LR.R p) S := Module.Finite.of_basis emb.basis
    rw [← rangeC, ← Submodule.map_top]
    exact Module.Finite.fg_top.map _
  have nonzero : LR.Jc p M v ≠ ⊥ := by
    intro hj
    have hs : ∀ m : S, (m : V) = 0 := by
      intro m
      apply B.repr.injective
      ext i
      have hm := coord_mem i m
      rw [hj] at hm
      simpa using hm
    have hspan : Submodule.span ℂ (S : Set V) ≤ ⊥ := by
      apply Submodule.span_le.mpr
      intro w hw
      exact hs ⟨w, hw⟩
    rw [emb.complex_span] at hspan
    have hb : B z = 0 := hspan (Submodule.mem_top)
    exact B.ne_zero z hb
  let J := LR.Jc p M v
  let F : (LR.Idx lam.toNat → J) →ₗ[LR.R p] V :=
    { toFun := fun c => ∑ i, (c i : ℂ) • B i
      map_add' := by intro a b; simp [add_smul, Finset.sum_add_distrib]
      map_smul' := by
        intro r c
        change (∑ i, ((algebraMap (LR.R p) ℂ r) * (c i : ℂ)) • B i) = (algebraMap (LR.R p) ℂ r) • ∑ i, (c i : ℂ) • B i
        simp only [mul_smul, Finset.smul_sum] }
  have Fmem (c : LR.Idx lam.toNat → J) : F c ∈ S := by
    change (∑ i, (c i : ℂ) • B i) ∈ S
    apply Submodule.sum_mem
    intro i hi
    apply (exactJ _ _).mp
    rw [common i]
    exact (c i).property
  let f : (LR.Idx lam.toNat → J) →ₗ[LR.R p] S := F.codRestrict S Fmem
  have fval (c : LR.Idx lam.toNat → J) : (f c : V) = ∑ i, (c i : ℂ) • B i := rfl
  have coord_sum (c : LR.Idx lam.toNat → J) (j : LR.Idx lam.toNat) : B.repr (f c : V) j = (c j : ℂ) := by
    rw [fval]
    simp [Finsupp.single_apply]
  have finj : Function.Injective f := by
    intro a b hab
    funext i
    apply Subtype.ext
    have hh := congrArg (fun m : S => B.repr (m : V) i) hab
    simpa only [coord_sum] using hh
  have fsurj : Function.Surjective f := by
    intro m
    let c : LR.Idx lam.toNat → J := fun i => ⟨B.repr (m : V) i, coord_mem i m⟩
    refine ⟨c, ?_⟩
    apply Subtype.ext
    rw [fval]
    exact B.sum_repr (m : V)
  exact ⟨{ exact_J := exactJ v, exact_coord := fun i => exactJ (B i), common := common, fg := fg, nonzero := nonzero, coordEquiv := LinearEquiv.ofBijective f ⟨finj, fsurj⟩, coord_value := fval }⟩

theorem T010 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_T009 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → Nonempty (LR.Decomposition p lam.toNat M v B)) :
    ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.RationalEmbedding p M v := by
  intro B hB
  obtain ⟨D⟩ := h_T009 B hB
  let J := LR.Jc p M v
  let f : ℚ →ₗ[LR.R p] J →ₗ[LR.R p] ℂ :=
    { toFun := fun q =>
        { toFun := fun c => (q : ℂ) * (c : ℂ)
          map_add' := by intros; simp [mul_add]
          map_smul' := by
            intro r c
            change (q : ℂ) * (((r : ℚ) : ℂ) * (c : ℂ)) = ((r : ℚ) : ℂ) * ((q : ℂ) * (c : ℂ))
            ring }
      map_add' := by intros; ext; simp [add_mul]
      map_smul' := by
        intro r q
        ext c
        change (((r : ℚ) * q : ℚ) : ℂ) * (c : ℂ) = ((r : ℚ) : ℂ) * ((q : ℂ) * (c : ℂ))
        simp [mul_assoc] }
  let mu0 := TensorProduct.lift f
  let mu : LR.T p M v →ₗ[ℚ] ℂ :=
    { toFun := mu0
      map_add' := mu0.map_add
      map_smul' := by
        intro q t
        induction t using TensorProduct.induction_on with
        | zero => simp
        | tmul a c =>
          change mu0 (q • (a ⊗ₜ[LR.R p] c)) = q • mu0 (a ⊗ₜ[LR.R p] c)
          simp [mu0, TensorProduct.smul_tmul', f, Algebra.smul_def, mul_assoc]
        | add a b ha hb => simpa [smul_add, map_add] using congrArg₂ (· + ·) ha hb }
  have hmu (q : ℚ) (c : J) : mu (q ⊗ₜ[LR.R p] c) = (q : ℂ) * (c : ℂ) := rfl
  letI : Module.Finite (LR.R p) J := Module.Finite.of_fg D.fg
  have hfin : Module.Finite ℚ (LR.T p M v) := by infer_instance
  change ∃ mu : LR.T p M v →ₗ[ℚ] ℂ, _
  refine ⟨mu, hmu, ?_, hfin⟩
  apply (LinearMap.ker_eq_bot).mp
  apply le_antisymm ?_ bot_le
  intro t ht
  change t = 0
  have hz : mu t = 0 := ht
  have clear : ∀ t : LR.T p M v, ∃ d : ℕ, d ≠ 0 ∧ ∃ c : J, (d : ℚ) • t = (1 : ℚ) ⊗ₜ[LR.R p] c := by
    intro t
    induction t using TensorProduct.induction_on with
    | zero => exact ⟨1, by decide, 0, by simp⟩
    | tmul q c =>
      refine ⟨q.den, q.den_nz, (q.num : LR.R p) • c, ?_⟩
      rw [TensorProduct.smul_tmul']
      have hq : (q.den : ℚ) • q = (q.num : ℚ) := by
        simpa [smul_eq_mul, mul_comm] using Rat.mul_den_eq_num q
      rw [hq]
      calc
        _ = ((q.num : LR.R p) • (1 : ℚ)) ⊗ₜ[LR.R p] c := by
          congr 1
          change (q.num : ℚ) = (q.num : ℚ) * 1
          simp
        _ = _ := by rw [TensorProduct.tmul_smul, TensorProduct.smul_tmul']
    | add a b ha hb =>
      obtain ⟨d, hd, c, hc⟩ := ha
      obtain ⟨e, he, g, hg⟩ := hb
      refine ⟨d*e, Nat.mul_ne_zero hd he, (e : LR.R p) • c + (d : LR.R p) • g, ?_⟩
      rw [Nat.cast_mul, smul_add, mul_comm (d : ℚ), mul_smul, hc, mul_comm (e : ℚ), mul_smul, hg]
      simp only [TensorProduct.tmul_add, TensorProduct.smul_tmul', TensorProduct.tmul_smul]
      simp [Algebra.smul_def]
  obtain ⟨d, hd, c, hc⟩ := clear t
  have hcz : (c : ℂ) = 0 := by
    have hh := congrArg mu hc
    simpa [map_smul, hz, hmu] using hh.symm
  have : c = 0 := Subtype.ext hcz
  rw [this, TensorProduct.tmul_zero] at hc
  exact (smul_eq_zero.mp hc).resolve_left (by exact_mod_cast hd)

theorem T011 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_T009 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → Nonempty (LR.Decomposition p lam.toNat M v B)) :
    ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → ∀ d : LR.Decomposition p lam.toNat M v B, ∃ Phi : (ℚ ⊗[LR.R p] LR.MR p M) ≃ₗ[ℚ] (LR.Idx lam.toNat → LR.T p M v), ∀ q c, Phi (q ⊗ₜ[LR.R p] d.coordEquiv c) = fun i => q ⊗ₜ[LR.R p] c i := by
  classical
  intro B hB d
  refine ⟨(d.coordEquiv.symm.baseChange (LR.R p) ℚ).trans
    (TensorProduct.piRight (LR.R p) ℚ ℚ (fun _ : LR.Idx lam.toNat => LR.Jc p M v)), ?_⟩
  intro q c
  simp

theorem T012 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_T004 : LR.StringResult lam x y h v) (h_T008 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.LocalResult p lam.toNat M x y h B) (h_T009 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → Nonempty (LR.Decomposition p lam.toNat M v B)) (h_T010 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.RationalEmbedding p M v) (h_T011 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → ∀ d : LR.Decomposition p lam.toNat M v B, ∃ Phi : (ℚ ⊗[LR.R p] LR.MR p M) ≃ₗ[ℚ] (LR.Idx lam.toNat → LR.T p M v), ∀ q c, Phi (q ⊗ₜ[LR.R p] d.coordEquiv c) = fun i => q ⊗ₜ[LR.R p] c i) :
    ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → Module.finrank ℚ (LR.T p M v) = 1 := by
  intro B hB
  obtain ⟨d⟩ := h_T009 B hB
  obtain ⟨Phi, hPhi⟩ := h_T011 B hB d
  obtain ⟨emb⟩ := (h_T008 B hB).1
  obtain ⟨mu, hmu, hinj, hfin⟩ := h_T010 B hB
  letI : Module.Finite ℚ (LR.T p M v) := hfin
  have hleft : Module.finrank ℚ (ℚ ⊗[LR.R p] LR.MR p M) = lam.toNat + 1 := by
    simpa [LR.Idx] using Module.finrank_eq_card_basis (emb.basis.baseChange ℚ)
  have hright : Module.finrank ℚ (LR.Idx lam.toNat → LR.T p M v) =
      (lam.toNat + 1) * Module.finrank ℚ (LR.T p M v) := by
    rw [Module.finrank_pi_fintype]
    simp [LR.Idx]
  have heq := Phi.finrank_eq
  rw [hleft, hright] at heq
  nlinarith

theorem T013 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_T004 : LR.StringResult lam x y h v) (h_T009 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → Nonempty (LR.Decomposition p lam.toNat M v B)) (h_T010 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.RationalEmbedding p M v) (h_T012 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → Module.finrank ℚ (LR.T p M v) = 1) :
    ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.CoordinateResult p lam.toNat M v B := by
  intro B hB
  have hrat := h_T010 B hB
  have hdim := h_T012 B hB
  refine ⟨h_T004.1, h_T009 B hB, hrat, hdim, ?_⟩
  intro a c ha hane hc
  obtain ⟨mu, hmu, hinj, hfin⟩ := hrat
  let ta : LR.T p M v := (1 : ℚ) ⊗ₜ[LR.R p] (⟨a, ha⟩ : LR.Jc p M v)
  let tc : LR.T p M v := (1 : ℚ) ⊗ₜ[LR.R p] (⟨c, hc⟩ : LR.Jc p M v)
  have hma : mu ta = a := by simpa [ta] using hmu 1 (⟨a, ha⟩ : LR.Jc p M v)
  have hmc : mu tc = c := by simpa [tc] using hmu 1 (⟨c, hc⟩ : LR.Jc p M v)
  have hta : ta ≠ 0 := by
    intro he
    apply hane
    rw [← hma, he, map_zero]
  have hli : LinearIndependent ℚ (fun _ : Unit => ta) :=
    linearIndependent_unique_iff.mpr hta
  have hspan : Submodule.span ℚ ({ta} : Set (LR.T p M v)) = ⊤ := by
    have hs := hli.span_eq_top_of_card_eq_finrank (by simpa using hdim.symm)
    simpa using hs
  have hmem : tc ∈ Submodule.span ℚ ({ta} : Set (LR.T p M v)) := by
    rw [hspan]
    trivial
  obtain ⟨q, hq⟩ := Submodule.mem_span_singleton.mp hmem
  refine ⟨q, ?_⟩
  have he := congrArg mu hq
  rw [map_smul, hma, hmc] at he
  simpa only [Rat.smul_def] using he.symm

theorem T014 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_T013 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.CoordinateResult p lam.toNat M v B) :
    ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → ∃ k : ℕ, 0 < k ∧ ∃ g : Fin k → ℂ, (∀ j, g j ∈ LR.Jc p M v ∧ g j ≠ 0) ∧ LR.Jc p M v = Submodule.span (LR.R p) (Set.range g) := by
  classical
  intro B hB
  obtain ⟨_, ⟨d⟩, _⟩ := h_T013 B hB
  obtain ⟨s, hs, hspan⟩ := Submodule.fg_def.mp d.fg
  let t : Set ℂ := {c ∈ s | c ≠ 0}
  have ht : t.Finite := hs.subset (by intro c hc; exact hc.1)
  have htspan : Submodule.span (LR.R p) t = LR.Jc p M v := by
    rw [← hspan]
    apply le_antisymm
    · exact Submodule.span_mono (by intro c hc; exact hc.1)
    · apply Submodule.span_le.mpr
      intro c hc
      by_cases hz : c = 0
      · simpa [hz] using (Submodule.zero_mem (Submodule.span (LR.R p) t))
      · exact Submodule.subset_span ⟨hc, hz⟩
  have htne : t.Nonempty := by
    by_contra hn
    have he : t = ∅ := Set.not_nonempty_iff_eq_empty.mp hn
    apply d.nonzero
    rw [← htspan, he, Submodule.span_empty]
  obtain ⟨k, g, _, hg⟩ := ht.fin_param
  have hk : 0 < k := by
    obtain ⟨c, hc⟩ := htne
    rw [← hg] at hc
    obtain ⟨j, _⟩ := hc
    exact Nat.zero_lt_of_lt j.isLt
  refine ⟨k, hk, g, ?_, ?_⟩
  · intro j
    have hj : g j ∈ t := by rw [← hg]; exact Set.mem_range_self j
    exact ⟨hspan ▸ Submodule.subset_span hj.1, hj.2⟩
  · rw [hg, htspan]

theorem T015 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_T013 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.CoordinateResult p lam.toNat M v B) :
    ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → ∀ (k : ℕ) (g : Fin k → ℂ), 0 < k → (∀ j, g j ∈ LR.Jc p M v ∧ g j ≠ 0) → ∃ a : ℂ, a ∈ LR.Jc p M v ∧ a ≠ 0 ∧ ∃ nu : Fin k → ℤ, ∃ u : Fin k → (LR.R p)ˣ, (∀ j, g j = ((((p : ℚ) ^ nu j) * ((u j : LR.R p) : ℚ) : ℚ) : ℂ) * a) ∧ ∃ j0 : Fin k, ∀ j, nu j0 ≤ nu j := by
  classical
  have factor : ∀ q : ℚ, q ≠ 0 → ∃ n : ℤ, ∃ u : (LR.R p)ˣ, q = (p : ℚ) ^ n * ((u : LR.R p) : ℚ) := by
   intro q hq
   have hp : (p : ℚ) ≠ 0 := by exact_mod_cast h_H001.ne_zero
   have hn : q.num ≠ 0 := Rat.num_ne_zero.mpr hq
   have hd : (q.den : ℤ) ≠ 0 := by exact_mod_cast q.den_ne_zero
   obtain ⟨a, ha, hpa⟩ := (Int.finiteMultiplicity_iff.mpr ⟨by simpa using h_H001.ne_one, hn⟩ : FiniteMultiplicity (p : ℤ) q.num).exists_eq_pow_mul_and_not_dvd
   obtain ⟨b, hb, hpb⟩ := (Int.finiteMultiplicity_iff.mpr ⟨by simpa using h_H001.ne_one, hd⟩ : FiniteMultiplicity (p : ℤ) (q.den : ℤ)).exists_eq_pow_mul_and_not_dvd
   have ha0 : a ≠ 0 := by rintro rfl; exact hpa (dvd_zero _)
   have hb0 : b ≠ 0 := by rintro rfl; exact hpb (dvd_zero _)
   have haQ : (a : ℚ) ≠ 0 := by exact_mod_cast ha0
   have hbQ : (b : ℚ) ≠ 0 := by exact_mod_cast hb0
   have hab : (a : ℚ) / (b : ℚ) ∈ LR.R p := Subring.subset_closure ⟨a, b, hpb, rfl⟩
   have hba : (b : ℚ) / (a : ℚ) ∈ LR.R p := Subring.subset_closure ⟨b, a, hpa, rfl⟩
   let u : (LR.R p)ˣ := ⟨⟨(a : ℚ) / b, hab⟩, ⟨(b : ℚ) / a, hba⟩, by ext; dsimp; field_simp, by ext; dsimp; field_simp⟩
   refine ⟨(multiplicity (p : ℤ) q.num : ℤ) - (multiplicity (p : ℤ) (q.den : ℤ) : ℤ), u, ?_⟩
   change q = (p : ℚ) ^ ((multiplicity (p : ℤ) q.num : ℤ) - (multiplicity (p : ℤ) (q.den : ℤ) : ℤ)) * ((a : ℚ) / b)
   rw [zpow_sub₀ hp, zpow_natCast, zpow_natCast]
   have ha' : (q.num : ℚ) = (p : ℚ) ^ multiplicity (p : ℤ) q.num * a := by exact_mod_cast ha
   have hb' : (q.den : ℚ) = (p : ℚ) ^ multiplicity (p : ℤ) (q.den : ℤ) * b := by exact_mod_cast hb
   calc
    q = (q.num : ℚ) / q.den := (Rat.num_div_den q).symm
    _ = _ := by rw [ha', hb']; ring
  intro B hB k g hk hg
  let jbase : Fin k := ⟨0, hk⟩
  let a : ℂ := g jbase
  have ha : a ∈ LR.Jc p M v := (hg jbase).1
  have ha0 : a ≠ 0 := (hg jbase).2
  have hline := (h_T013 B hB).2.2.2.2
  have hq : ∀ j, ∃ q : ℚ, g j = (q : ℂ) * a := fun j => hline a (g j) ha ha0 (hg j).1
  choose q hq using hq
  have hq0 : ∀ j, q j ≠ 0 := by
   intro j hj
   have := hq j
   rw [hj, Rat.cast_zero, zero_mul] at this
   exact (hg j).2 this
  choose nu u hu using fun j => factor (q j) (hq0 j)
  refine ⟨a, ha, ha0, nu, u, ?_, ?_⟩
  · intro j
    rw [hq j, hu j]
  · obtain ⟨j0, _, hj0⟩ := Finset.exists_min_image (Finset.univ : Finset (Fin k)) nu ⟨jbase, Finset.mem_univ _⟩
    exact ⟨j0, fun j => hj0 j (Finset.mem_univ _)⟩

theorem T016 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_T013 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.CoordinateResult p lam.toNat M v B) (h_T014 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → ∃ k : ℕ, 0 < k ∧ ∃ g : Fin k → ℂ, (∀ j, g j ∈ LR.Jc p M v ∧ g j ≠ 0) ∧ LR.Jc p M v = Submodule.span (LR.R p) (Set.range g)) (h_T015 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → ∀ (k : ℕ) (g : Fin k → ℂ), 0 < k → (∀ j, g j ∈ LR.Jc p M v ∧ g j ≠ 0) → ∃ a : ℂ, a ∈ LR.Jc p M v ∧ a ≠ 0 ∧ ∃ nu : Fin k → ℤ, ∃ u : Fin k → (LR.R p)ˣ, (∀ j, g j = ((((p : ℚ) ^ nu j) * ((u j : LR.R p) : ℚ) : ℚ) : ℂ) * a) ∧ ∃ j0 : Fin k, ∀ j, nu j0 ≤ nu j) :
    ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.PrincipalResult p lam.toNat M v B := by
  classical
  intro B hB
  have hprincipal : ∃ b : ℂ, b ∈ LR.Jc p M v ∧ b ≠ 0 ∧ LR.Jc p M v = Submodule.span (LR.R p) {b} := by
    obtain ⟨k, hk, g, hg, hspan⟩ := h_T014 B hB
    obtain ⟨a, ha, ha0, nu, u, hgu, j0, hmin⟩ := h_T015 B hB k g hk hg
    let b : ℂ := (((p : ℚ) ^ nu j0 : ℚ) : ℂ) * a
    have hp : (p : ℚ) ≠ 0 := by exact_mod_cast h_H001.ne_zero
    have hpC : (p : ℂ) ≠ 0 := by exact_mod_cast h_H001.ne_zero
    have hb0 : b ≠ 0 := mul_ne_zero (by exact_mod_cast zpow_ne_zero _ hp) ha0
    have hbj : (u j0 : LR.R p) • b = g j0 := by
      change (((u j0 : LR.R p) : ℚ) : ℂ) * b = g j0
      rw [hgu j0]
      dsimp [b]
      push_cast
      ring
    have hbmem : b ∈ LR.Jc p M v := by
      have ht := (LR.Jc p M v).smul_mem (↑((u j0)⁻¹) : LR.R p) (hg j0).1
      rw [← hbj] at ht
      change (((↑((u j0)⁻¹) : LR.R p) : ℚ) : ℂ) * ((((u j0 : LR.R p) : ℚ) : ℂ) * b) ∈ LR.Jc p M v at ht
      have hu := congrArg (fun r : LR.R p => ((r : ℚ) : ℂ)) (Units.inv_mul (u j0))
      push_cast at hu
      rwa [← mul_assoc, hu, one_mul] at ht
    refine ⟨b, hbmem, hb0, le_antisymm ?_ ?_⟩
    · rw [hspan]
      apply Submodule.span_le.mpr
      rintro _ ⟨j, rfl⟩
      apply Submodule.mem_span_singleton.mpr
      refine ⟨(p : LR.R p) ^ (nu j - nu j0).toNat * (u j : LR.R p), ?_⟩
      change (((((p : LR.R p) ^ (nu j - nu j0).toNat * (u j : LR.R p)) : LR.R p) : ℚ) : ℂ) * b = g j
      rw [hgu j]
      dsimp [b]
      push_cast
      have he : (p : ℂ) ^ nu j = (p : ℂ) ^ (nu j - nu j0).toNat * (p : ℂ) ^ nu j0 := by
        rw [← zpow_natCast, Int.toNat_of_nonneg (sub_nonneg.mpr (hmin j)), ← zpow_add₀ hpC]
        congr 1
        omega
      rw [he]
      ring
    · exact Submodule.span_le.mpr (by simpa using hbmem)
  refine ⟨hprincipal, ?_, Nat.zero_lt_succ _, ?_⟩
  · intro b hb hb0 hgen
    obtain ⟨D⟩ := (h_T013 B hB).2.1
    let L : LR.R p →ₗ[LR.R p] LR.Jc p M v := LinearMap.toSpanSingleton _ _ ⟨b, hb⟩
    have hL : Function.Bijective L := by
      constructor
      · intro r s hrs
        apply Subtype.ext
        apply Rat.cast_injective (α := ℂ)
        apply mul_right_cancel₀ hb0
        exact congrArg (fun z : LR.Jc p M v => (z : ℂ)) hrs
      · intro c
        have hc : (c : ℂ) ∈ Submodule.span (LR.R p) {b} := hgen ▸ c.property
        obtain ⟨r, hr⟩ := Submodule.mem_span_singleton.mp hc
        exact ⟨r, Subtype.ext hr⟩
    let E : LR.R p ≃ₗ[LR.R p] LR.Jc p M v := LinearEquiv.ofBijective L hL
    let P : (LR.Idx lam.toNat → LR.R p) ≃ₗ[LR.R p] (LR.Idx lam.toNat → LR.Jc p M v) := LinearEquiv.piCongrRight (fun _ => E)
    let f := (Pi.basisFun (LR.R p) (LR.Idx lam.toNat)).map (P.trans D.coordEquiv)
    refine ⟨f, ?_⟩
    intro i
    change (D.coordEquiv (P ((Pi.basisFun (LR.R p) (LR.Idx lam.toNat)) i)) : V) = _
    rw [D.coord_value]
    have hval : ∀ r, (E r : ℂ) = (((r : LR.R p) : ℚ) : ℂ) * b := by intro r; rfl
    simp [P, LinearEquiv.piCongrRight_apply, Pi.basisFun_apply, hval, Pi.single_apply, apply_ite]
  · simp [LR.Idx]

theorem T017 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_H002 : CharP K p) (h_T005 : ∀ q : ℚ, q ∈ LR.R p ↔ ∃ a b : ℤ, b ≠ 0 ∧ ¬ (p : ℤ) ∣ b ∧ q = (a : ℚ)/(b : ℚ)) :
    Nonempty (LR.FirstChange p K M) := by
  classical
  letI : CharP K p := h_H002
  let S := (nonZeroDivisors K).comap (Int.castRingHom K)
  have hs (b : ℤ) : b ∈ S ↔ ¬ (p : ℤ) ∣ b := by
    simp [S, mem_nonZeroDivisors_iff_ne_zero, CharP.intCast_eq_zero_iff K p]
  have hb0 (b : S) : (b : ℤ) ≠ 0 := by
    intro hb
    have := (hs b).mp b.property
    exact this (hb ▸ dvd_zero _)
  letI : IsLocalization S (LR.R p) := by
    refine ⟨{ map_units := ?_, surj := ?_, exists_of_eq := ?_ }⟩
    · intro b
      have hi : (1 / (b : ℤ) : ℚ) ∈ LR.R p := (h_T005 _).mpr ⟨1, b, hb0 b, (hs b).mp b.property, by simp⟩
      apply isUnit_iff_exists_inv.mpr
      refine ⟨⟨_, hi⟩, ?_⟩
      apply Subtype.ext
      change (b : ℚ) * (1 / (b : ℤ) : ℚ) = 1
      simp [hb0 b]
    · intro r
      obtain ⟨a, b, hb, hpb, hr⟩ := (h_T005 r).mp r.property
      refine ⟨(a, ⟨b, (hs b).mpr hpb⟩), ?_⟩
      apply Subtype.ext
      change (r : ℚ) * (b : ℚ) = (a : ℚ)
      rw [hr]
      exact div_mul_cancel₀ _ (by exact_mod_cast hb)
    · intro a b hab
      refine ⟨1, ?_⟩
      have hh := congrArg (fun r : LR.R p => (r : ℚ)) hab
      have : a = b := by exact_mod_cast hh
      simpa using this
  have hunit (b : S) : IsUnit ((Int.castRingHom K) b) := by
    apply isUnit_iff_ne_zero.mpr
    exact fun h => (hs b).mp b.property ((CharP.intCast_eq_zero_iff K p b).mp h)
  let rho : LR.R p →+* K := IsLocalization.lift hunit
  letI : Algebra (LR.R p) K := rho.toAlgebra
  have hval : ∀ a b : ℤ, ∀ r : LR.R p, (r : ℚ) = (a : ℚ) / (b : ℚ) → ¬ (p : ℤ) ∣ b → algebraMap (LR.R p) K r = (a : K) / (b : K) := by
    intro a b r hr hb
    have hbQ : (b : ℚ) ≠ 0 := by
      exact_mod_cast (hb0 ⟨b, (hs b).mpr hb⟩)
    have hh : r * (b : LR.R p) = (a : LR.R p) := by
      apply Subtype.ext
      change (r : ℚ) * (b : ℚ) = (a : ℚ)
      rw [hr, div_mul_cancel₀ _ hbQ]
    have hbK : (b : K) ≠ 0 := fun h => hb ((CharP.intCast_eq_zero_iff K p b).mp h)
    apply (eq_div_iff hbK).mpr
    simpa using congrArg (algebraMap (LR.R p) K) hh
  letI : IsLocalizedModule S (LinearMap.id : V →ₗ[ℤ] V) := isLocalizedModule_id S V (LR.R p)
  have heq : M.localized' (LR.R p) S (LinearMap.id : V →ₗ[ℤ] V) = LR.MR p M := by
    rw [Submodule.localized'_eq_span]
    simp [LR.MR]
  let e := LinearEquiv.ofEq _ _ heq
  let inc : M →ₗ[ℤ] LR.MR p M := (e.restrictScalars ℤ).toLinearMap.comp (M.toLocalized' (LR.R p) S (LinearMap.id : V →ₗ[ℤ] V))
  letI : IsLocalizedModule S inc := IsLocalizedModule.of_linearEquiv S _ (e.restrictScalars ℤ)
  let bc := IsLocalizedModule.isBaseChange S (LR.R p) inc
  let A : LR.VK K M ≃ₗ[K] (K ⊗[LR.R p] LR.MR p M) :=
    (TensorProduct.AlgebraTensorModule.cancelBaseChange ℤ (LR.R p) K K M).symm.trans (TensorProduct.AlgebraTensorModule.congr (LinearEquiv.refl K K) bc.equiv)
  refine ⟨{ ak := inferInstance
            rho_value := hval
            inc := inc
            inc_value := ?_
            A := A
            A_value := ?_ }⟩
  · intro m
    rfl
  · intro c m
    simp [A, IsBaseChange.equiv_tmul]

theorem T018 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_H002 : CharP K p) (h_T005 : ∀ q : ℚ, q ∈ LR.R p ↔ ∃ a b : ℤ, b ≠ 0 ∧ ¬ (p : ℤ) ∣ b ∧ q = (a : ℚ)/(b : ℚ)) (h_T017 : Nonempty (LR.FirstChange p K M)) :
    Nonempty (LR.ScalarData p K M) := by
  classical
  letI : Fact p.Prime := ⟨h_H001⟩
  letI : CharP K p := h_H002
  obtain ⟨fc⟩ := h_T017
  letI := fc.ak
  let I : Ideal (LR.R p) := Ideal.span {(p : LR.R p)}
  have hI : I ≤ RingHom.ker (algebraMap (LR.R p) K) := by
    rw [Ideal.span_le]
    intro a ha
    rcases Set.mem_singleton_iff.mp ha with rfl
    simp [RingHom.mem_ker]
  let g : (LR.R p ⧸ I) →+* K := Ideal.Quotient.lift I (algebraMap (LR.R p) K) hI
  letI : Nontrivial (LR.R p ⧸ I) := g.domain_nontrivial
  have hp0 : (p : LR.R p ⧸ I) = 0 := by
    rw [← map_natCast (Ideal.Quotient.mk I), Ideal.Quotient.eq_zero_iff_mem]
    exact Ideal.subset_span (Set.mem_singleton _)
  letI : CharP (LR.R p ⧸ I) p := (CharP.charP_iff_prime_eq_zero h_H001).mpr hp0
  let f : ZMod p →+* (LR.R p ⧸ I) := ZMod.castHom (dvd_refl p) _
  have frac : ∀ a b : ℤ, ∀ r : LR.R p, (r : ℚ) = (a : ℚ)/(b : ℚ) → ¬ (p : ℤ) ∣ b → Ideal.Quotient.mk I r = f ((a : ZMod p) * (b : ZMod p)⁻¹) := by
    intro a b r hr hb
    have hb0 : b ≠ 0 := by intro he; apply hb; simp [he]
    have he : (b : LR.R p) * r = a := by
      apply Subtype.ext
      change (b : ℚ) * (r : ℚ) = (a : ℚ)
      rw [hr]
      field_simp
    have hbz : (b : ZMod p) ≠ 0 := by simpa [CharP.intCast_eq_zero_iff] using hb
    have he' := congrArg (Ideal.Quotient.mk I) he
    have hu : f (b : ZMod p) * f ((b : ZMod p)⁻¹) = 1 := by
      rw [← map_mul, mul_inv_cancel₀ hbz, map_one]
    have hfint (z : ℤ) : f (z : ZMod p) = (z : LR.R p ⧸ I) := map_intCast f z
    simp only [map_mul, map_intCast] at he'
    rw [map_mul]
    calc
      Ideal.Quotient.mk I r = (f (b : ZMod p) * f ((b : ZMod p)⁻¹)) * Ideal.Quotient.mk I r := by rw [hu, one_mul]
      _ = f (a : ZMod p) * f ((b : ZMod p)⁻¹) := by rw [mul_right_comm, hfint, he', hfint]
  have hsurj : Function.Surjective f := by
    intro q
    obtain ⟨r, rfl⟩ := Ideal.Quotient.mk_surjective q
    obtain ⟨a,b,hb,hpb,hr⟩ := (h_T005 r).mp r.property
    exact ⟨_, (frac a b r hr hpb).symm⟩
  let e := RingEquiv.ofBijective f ⟨f.injective, hsurj⟩
  have hres : ∀ a b : ℤ, ∀ r : LR.R p, (r : ℚ) = (a : ℚ)/(b : ℚ) → ¬ (p : ℤ) ∣ b → e.symm (Ideal.Quotient.mk I r) = (a : ZMod p) * (b : ZMod p)⁻¹ := by
    intro a b r hr hb
    apply e.injective
    simpa [e] using frac a b r hr hb
  let d : LR.MR p M →ₗ[LR.R p] LR.MR p M := (p : LR.R p) • LinearMap.id
  let q := (LR.pMR p M).mkQ
  let F : (K ⊗[LR.R p] LR.MR p M) →ₗ[K] (K ⊗[LR.R p] LR.QMR p M) := q.baseChange K
  have hd : d.lTensor K = 0 := by
    apply TensorProduct.ext'
    intro c u
    change c ⊗ₜ[LR.R p] ((p : LR.R p) • u) = 0
    rw [← TensorProduct.smul_tmul]
    simp [Algebra.smul_def]
  have hex : Function.Exact d q := by
    rw [LinearMap.exact_iff]
    exact Submodule.ker_mkQ _
  have hk : LinearMap.ker (q.lTensor K) = ⊥ := by
    rw [(lTensor_exact K hex (Submodule.mkQ_surjective _)).linearMap_ker_eq, hd, LinearMap.range_zero]
  have hinj : Function.Injective F := by
    change Function.Injective (q.lTensor K)
    exact LinearMap.ker_eq_bot.mp hk
  have hsur : Function.Surjective F := by
    change Function.Surjective (q.lTensor K)
    exact LinearMap.lTensor_surjective K (Submodule.mkQ_surjective _)
  let E := LinearEquiv.ofBijective F ⟨hinj, hsur⟩
  have ht : ∃ (af : Algebra (ZMod p) K) (mq : Module (ZMod p) (LR.QMR p M)), letI := af; letI := mq; ∃ D : (K ⊗[LR.R p] LR.QMR p M) ≃ₗ[K] (K ⊗[ZMod p] LR.QMR p M), ∀ c u, D (c ⊗ₜ[LR.R p] u) = c ⊗ₜ[ZMod p] u := by
    let af : Algebra (ZMod p) K := ZMod.algebra _ _
    letI := af
    have hkill : ∀ q : LR.QMR p M, p • q = 0 := by
      intro q
      obtain ⟨u, rfl⟩ := (LR.pMR p M).mkQ_surjective q
      rw [← map_nsmul, ← Nat.cast_smul_eq_nsmul (LR.R p), Submodule.mkQ_apply, Submodule.Quotient.mk_eq_zero]
      exact ⟨u, rfl⟩
    let mq : Module (ZMod p) (LR.QMR p M) := AddCommGroup.zmodModule hkill
    letI := mq
    have scalar (r : LR.R p) : ∃ z : ZMod p, (∀ c : K, r • c = z • c) ∧ (∀ q : LR.QMR p M, r • q = z • q) := by
      obtain ⟨a,b,hb0,hb,hr⟩ := (h_T005 r).mp r.property
      have hbz : (b : ZMod p) ≠ 0 := by simpa [CharP.intCast_eq_zero_iff] using hb
      have he : (b : LR.R p) * r = a := by
        apply Subtype.ext
        change (b : ℚ) * (r : ℚ) = (a : ℚ)
        rw [hr]
        field_simp
      refine ⟨(a : ZMod p) * (b : ZMod p)⁻¹, ?_, ?_⟩
      · intro c
        simp only [Algebra.smul_def, fc.rho_value a b r hr hb, map_mul, map_intCast, map_inv₀, div_eq_mul_inv]
      · intro q
        have hh : (b : ZMod p) • (r • q) = (a : ZMod p) • q := by
          rw [Int.cast_smul_eq_zsmul, ← Int.cast_smul_eq_zsmul (LR.R p), smul_smul, he]
          simp only [Int.cast_smul_eq_zsmul]
        calc
          r • q = (b : ZMod p)⁻¹ • ((b : ZMod p) • (r • q)) := by rw [inv_smul_smul₀ hbz]
          _ = (b : ZMod p)⁻¹ • ((a : ZMod p) • q) := congrArg (_ • ·) hh
          _ = ((a : ZMod p) * (b : ZMod p)⁻¹) • q := by rw [smul_smul, mul_comm]
    letI comm : SMulCommClass (LR.R p) (ZMod p) K := ⟨by intro r z c; simp only [Algebra.smul_def]; ring⟩
    letI hc1 : TensorProduct.CompatibleSMul (ZMod p) (LR.R p) K (LR.QMR p M) := ⟨by
      intro r c q
      obtain ⟨z,hk,hq⟩ := scalar r
      rw [hk, hq, TensorProduct.smul_tmul]⟩
    letI hc2 : TensorProduct.CompatibleSMul (LR.R p) (ZMod p) K (LR.QMR p M) := ⟨by
      intro z c q
      letI : Module (ZMod p) (K ⊗[LR.R p] LR.QMR p M) := Module.compHom _ (algebraMap (ZMod p) K)
      exact (ZMod.map_smul ((TensorProduct.mk (LR.R p) K (LR.QMR p M)).flip q).toAddMonoidHom z c).trans
        (ZMod.map_smul (TensorProduct.mk (LR.R p) K (LR.QMR p M) c).toAddMonoidHom z q).symm⟩
    let D := @TensorProduct.equivOfCompatibleSMul (ZMod p) inferInstance (LR.R p) K K (LR.QMR p M) inferInstance inferInstance (inferInstance : Module (ZMod p) K) mq inferInstance (inferInstance : Module (LR.R p) K) (inferInstance : Module (LR.R p) (LR.QMR p M)) inferInstance inferInstance (inferInstance : Module K K) inferInstance inferInstance hc1 hc2
    exact ⟨af, mq, D, fun c u => rfl⟩
  obtain ⟨af, mq, D, hD⟩ := ht
  letI := af
  letI := mq
  let C := E.trans D
  refine ⟨{ toFirstChange := fc, af := af, mq := mq, residue := e.symm, residue_value := hres, C := C, C_value := ?_ }⟩
  intro c u
  change D (E (c ⊗ₜ[LR.R p] u)) = c ⊗ₜ[ZMod p] (LR.pMR p M).mkQ u
  exact hD c ((LR.pMR p M).mkQ u)

theorem T019 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_H002 : CharP K p) (h_T004 : LR.StringResult lam x y h v) (h_T008 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.LocalResult p lam.toNat M x y h B) (h_T016 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.PrincipalResult p lam.toNat M v B) (h_T018 : Nonempty (LR.ScalarData p K M)) :
    ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → Nonempty (LR.ReducedBasis p K lam.toNat M v B) := by
  intro B hB
  classical
  obtain ⟨b, hb, hb0, hprincipal⟩ := (h_T016 B hB).1
  obtain ⟨f, hf⟩ := (h_T016 B hB).2.1 b hb hb0 hprincipal
  obtain ⟨s⟩ := h_T018
  letI := s.ak
  letI := s.mq
  let beta := (f.baseChange K).map s.A.symm
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
  have hg : ∀ i, Module.Basis.ofEquivFun E i = (LR.pMR p M).mkQ (f i) := by
    intro i
    apply E.injective
    rw [Module.Basis.coe_ofEquivFun, LinearEquiv.apply_symm_apply]
    change Pi.single i 1 = e₄ (fq.equivFun (1 ⊗ₜ[LR.R p] f i))
    have ht : fq.equivFun (1 ⊗ₜ[LR.R p] f i) = Pi.single i 1 := by
      ext j
      by_cases hij : i = j <;> simp [fq, Module.Basis.equivFun_apply, Pi.single_apply, Finsupp.single_apply, hij, eq_comm]
    rw [ht]
    ext j
    by_cases hij : i = j <;> simp [e₄, Pi.single_apply, hij, eq_comm]
  refine ⟨{ scalars := s, b := b, b_mem := hb, b_ne := hb0, principal := hprincipal, f := f, f_value := hf, beta := beta, transported := ?_, quotient_basis := ⟨Module.Basis.ofEquivFun E, hg⟩, dimension := ?_, positive := Nat.succ_pos _, cardinality := Fintype.card_fin _ }⟩
  · intro i
    simp [beta, Module.Basis.baseChange_apply]
  · simpa [LR.Idx] using Module.finrank_eq_card_basis beta

theorem T020 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_H002 : CharP K p) (h_T004 : LR.StringResult lam x y h v) (h_T008 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.LocalResult p lam.toNat M x y h B) :
    ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → ∀ rb : LR.ReducedBasis p K lam.toNat M v B, ∀ o : LR.IntegralOps M x y h, LR.ReducedAction K lam.toNat M x y h o rb.beta := by
  open LR in
    intro B hB rb o
    letI := rb.scalars.ak
    letI : IsScalarTower (R p) ℂ V := ⟨fun r c w => by change ((algebraMap (R p) ℂ r * c) • w) = _; exact mul_smul _ _ _⟩
    have bsmul (f : Module.End ℤ M) (z : ℤ) :
        (z • f).baseChange K = (z:K) • f.baseChange K := by
      rw [LinearMap.baseChange_smul]
      apply LinearMap.ext
      intro w
      exact (algebraMap_smul K z (f.baseChange K w)).symm
    have liftop (F : Module.End ℂ V) (fz : Module.End ℤ M)
        (hf : ∀ m, (fz m : V) = F m) :
        ∃ G : Module.End (R p) (MR p M), ∀ u, (G u : V) = F u := by
      have hs : ∀ u ∈ MR p M, F u ∈ MR p M := by
        intro u hu
        induction hu using Submodule.span_induction with
        | mem u hu => exact hf ⟨u,hu⟩ ▸ Submodule.subset_span (fz ⟨u,hu⟩).property
        | zero => simpa using (MR p M).zero_mem
        | add u w hu hw ihu ihw => simpa using (MR p M).add_mem ihu ihw
        | smul r u hu ihu => simpa using (MR p M).smul_mem r ihu
      exact ⟨(F.restrictScalars (R p)).restrict hs, fun _ => rfl⟩
    let ef : ℕ → MR p M := fun i => if hi : i < lam.toNat+1 then rb.f ⟨i,hi⟩ else 0
    have hfe (i : ℕ) : (ef i : V) = rb.b • ext B i := by
      unfold ef ext
      split_ifs with hi
      · exact rb.f_value _
      · simp
    have hae (i : ℕ) : rb.scalars.A (ext rb.beta i) = (1:K) ⊗ₜ[R p] ef i := by
      unfold ef ext
      split_ifs with hi
      · exact rb.transported _
      · simp
    have transfer (F : Module.End ℂ V) (fz : Module.End ℤ M)
        (hf : ∀ m, (fz m : V) = F m) (i j : ℕ) (z : ℤ)
        (he : F (ext B i) = (z:ℂ) • ext B j) :
        fz.baseChange K (ext rb.beta i) = (z:K) • ext rb.beta j := by
      obtain ⟨G,hG⟩ := liftop F fz hf
      have inter (w : VK K M) : rb.scalars.A (fz.baseChange K w) = G.baseChange K (rb.scalars.A w) := by
        induction w using TensorProduct.induction_on with
        | zero => simp
        | tmul c m =>
          simp only [LinearMap.baseChange_tmul, rb.scalars.A_value]
          congr 1
          apply Subtype.ext
          simp only [hG, rb.scalars.inc_value, hf]
        | add a b ha hb => simp [ha,hb]
      have hg : G (ef i) = z • ef j := by
        apply Subtype.ext
        rw [hG]
        change F (ef i : V) = z • (ef j : V)
        rw [hfe, hfe, map_smul, he, smul_comm, Int.cast_smul_eq_zsmul]
      apply rb.scalars.A.injective
      rw [inter, hae, LinearMap.baseChange_tmul, hg]
      simp [hae, Int.cast_smul_eq_zsmul]
    rcases h_T004 with ⟨_,_,_,_,_,hnil,ha⟩
    have he (i : ℕ) : ext B i = e y v i := by
      unfold ext
      split_ifs with hi
      · exact hB _
      · symm
        change (i.factorial:ℂ)⁻¹ • ((y^i) v) = 0
        rw [hnil i (by omega), smul_zero]
    have actB : Actions lam.toNat (ext B) x y h (DP x) (DP y) := by
      rw [show ext B = e y v from funext he]
      exact ha
    refine ⟨?_, ?_, ?_⟩
    · rcases o.brackets with ⟨hx,hy,hh⟩
      refine ⟨?_,?_,?_⟩
      · have hb := congrArg (LinearMap.baseChange K) hx
        rw [LinearMap.baseChange_sub, LinearMap.baseChange_mul, LinearMap.baseChange_mul, bsmul] at hb
        simpa only [Int.cast_ofNat] using hb
      · have hb := congrArg (LinearMap.baseChange K) hy
        rw [LinearMap.baseChange_sub, LinearMap.baseChange_mul, LinearMap.baseChange_mul, bsmul] at hb
        simpa only [Int.cast_neg, Int.cast_ofNat] using hb
      · simpa only [LinearMap.baseChange_sub, LinearMap.baseChange_mul] using congrArg (LinearMap.baseChange K) hh
    · rcases actB with ⟨ax0,ax,ay,ah,aX,aY⟩
      refine ⟨?_,?_,?_,?_,?_,?_⟩
      · simpa using transfer x o.xz o.x_agree 0 0 0 (by simpa using ax0)
      · intro i hi hil
        simpa using transfer x o.xz o.x_agree i (i-1) ((lam.toNat-i+1:ℕ):ℤ) (by simpa using ax i hi hil)
      · intro i hi
        simpa using transfer y o.yz o.y_agree i (i+1) (i+1) (by simpa using ay i hi)
      · intro i hi
        exact transfer h o.hz o.h_agree i i (lam.toNat-2*(i:ℤ)) (ah i hi)
      · intro r i hi
        by_cases hr : r ≤ i
        · simp only [if_pos hr]
          simpa using transfer (DP x r) (o.Xz r) (o.X_agree r) i (i-r) ((lam.toNat-i+r).choose r) (by simpa [hr] using aX r i hi)
        · simp only [if_neg hr]
          simpa using transfer (DP x r) (o.Xz r) (o.X_agree r) i 0 0 (by simpa [hr] using aX r i hi)
      · intro r i hi
        by_cases hr : i+r ≤ lam.toNat
        · simp only [if_pos hr]
          simpa using transfer (DP y r) (o.Yz r) (o.Y_agree r) i (i+r) ((i+r).choose r) (by simpa [hr] using aY r i hi)
        · simp only [if_neg hr]
          simpa using transfer (DP y r) (o.Yz r) (o.Y_agree r) i 0 0 (by simpa [hr] using aY r i hi)
    · intro r hr
      have hn : (r.factorial:K) ≠ 0 := by
        have hu := (h_T008 B hB).2.1.2.2.2.1 r hr
        simpa using (hu.map (algebraMap (R p) K)).ne_zero
      have powagree (F : Module.End ℂ V) (fz : Module.End ℤ M)
          (hf : ∀ m, (fz m : V) = F m) (n : ℕ) (m : M) :
          ((fz^n) m : V) = (F^n) m := by
        induction n with
        | zero => rfl
        | succ n ih => simp only [pow_succ', Module.End.mul_apply, hf, ih]
      have divided (F : Module.End ℂ V) (fz Zz : Module.End ℤ M)
          (hf : ∀ m, (fz m : V) = F m)
          (hZ : ∀ m, (Zz m : V) = DP F r m) :
          Zz.baseChange K = (r.factorial:K)⁻¹ • (fz.baseChange K)^r := by
        have hid : (r.factorial:ℤ) • Zz = fz^r := by
          ext m
          change (r.factorial:ℤ) • (Zz m : V) = ((fz^r) m : V)
          rw [hZ, powagree F fz hf, ← Int.cast_smul_eq_zsmul ℂ]
          simp [DP, smul_smul, Nat.factorial_ne_zero]
        have hb := congrArg (LinearMap.baseChange K) hid
        rw [bsmul, LinearMap.baseChange_pow] at hb
        have hb' : (r.factorial:K) • Zz.baseChange K = (fz.baseChange K)^r := by
          simpa only [Int.cast_natCast] using hb
        rw [← hb', smul_smul, inv_mul_cancel₀ hn, one_smul]
      exact ⟨hn, divided x o.xz (o.Xz r) o.x_agree (o.X_agree r), divided y o.yz (o.Yz r) o.y_agree (o.Y_agree r)⟩

theorem T021 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_T004 : LR.StringResult lam x y h v) (h_T008 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.LocalResult p lam.toNat M x y h B) (h_T020 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → ∀ rb : LR.ReducedBasis p K lam.toNat M v B, ∀ o : LR.IntegralOps M x y h, LR.ReducedAction K lam.toNat M x y h o rb.beta) :
    ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → ∀ rb : LR.ReducedBasis p K lam.toNat M v B, ∀ o : LR.IntegralOps M x y h, LR.ReducedControl K lam.toNat M x y h o rb.beta := by
  intro B hB rb o
  rcases h_T020 B hB rb o with ⟨hb, ha, hd⟩
  rcases ha with ⟨hx0, hx, hy, hh, hX, hY⟩
  have hu := (h_T008 B hB).2.1.2.2.2.2
  letI := rb.scalars.ak
  have hn (j : LR.Idx lam.toNat) : ((lam.toNat.choose j.val : ℕ) : K) ≠ 0 := by
    have ht := (hu j.val (Nat.le_of_lt_succ j.isLt)).map (algebraMap (LR.R p) K)
    simpa using ht.ne_zero
  have he (k : LR.Idx lam.toNat) : LR.ext rb.beta k.val = rb.beta k := by simp [LR.ext, k.isLt]
  have fx (i : LR.Idx lam.toNat) : (o.Xz (lam.toNat-i.val)).baseChange K (LR.ext rb.beta lam.toNat) = rb.beta i := by
    simpa [Nat.sub_sub_self (Nat.le_of_lt_succ i.isLt), he] using hX (lam.toNat-i.val) lam.toNat (le_refl _)
  have fx0 : (o.Xz lam.toNat).baseChange K (LR.ext rb.beta lam.toNat) = LR.ext rb.beta 0 := by
    simpa using hX lam.toNat lam.toNat (le_refl _)
  have fy0 : (o.Yz lam.toNat).baseChange K (LR.ext rb.beta 0) = LR.ext rb.beta lam.toNat := by
    simpa using hY lam.toNat 0 (Nat.zero_le _)
  have hid : ∀ i j : LR.Idx lam.toNat, LR.MU rb.beta i j = (((lam.toNat.choose j.val : ℕ):K)⁻¹) • ((o.Xz (lam.toNat-i.val)).baseChange K * (o.Yz lam.toNat).baseChange K * (o.Xz lam.toNat).baseChange K * (o.Yz (lam.toNat-j.val)).baseChange K) := by
    intro i j
    apply rb.beta.ext
    intro k
    simp only [LR.MU, LinearMap.smulRight_apply, Module.Basis.coord_apply, LinearMap.smul_apply, Module.End.mul_apply]
    rw [← he k, hY _ _ (Nat.le_of_lt_succ k.isLt)]
    by_cases hkj : k = j
    · subst k
      have hj : j.val + (lam.toNat - j.val) = lam.toNat := Nat.add_sub_of_le (Nat.le_of_lt_succ j.isLt)
      simp only [hj, le_refl, if_true, map_smul, fx0, fy0, fx]
      rw [Nat.choose_symm (Nat.le_of_lt_succ j.isLt)]
      simp [he, smul_smul, hn]
    · have hv : k.val ≠ j.val := fun hh => hkj (Fin.ext hh)
      by_cases hs : k.val + (lam.toNat-j.val) ≤ lam.toNat
      · have ht : ¬ lam.toNat ≤ k.val + (lam.toNat-j.val) := by omega
        rw [if_pos hs, map_smul, hX _ _ hs, if_neg ht]
        simp [he, Ne.symm hkj]
      · rw [if_neg hs]
        simp [he, Ne.symm hkj]
  constructor
  · exact hid
  · intro W hxW hyW i j
    have hp (f : Module.End K (LR.VK K M)) (hf : LR.Inv W f) (n : ℕ) : LR.Inv W (f^n) := by
      induction n with
      | zero => intro u hu; simpa using hu
      | succ n ih =>
        intro u hu
        simpa only [pow_succ, Module.End.mul_apply] using ih (f u) (hf u hu)
    have hDX (r : ℕ) (hr : r ≤ lam.toNat) : LR.Inv W ((o.Xz r).baseChange K) := by
      rw [(hd r hr).2.1]
      intro u hu
      exact W.smul_mem _ ((hp _ hxW r) u hu)
    have hDY (r : ℕ) (hr : r ≤ lam.toNat) : LR.Inv W ((o.Yz r).baseChange K) := by
      rw [(hd r hr).2.2]
      intro u hu
      exact W.smul_mem _ ((hp _ hyW r) u hu)
    rw [hid i j]
    intro u hu
    apply W.smul_mem
    apply hDX _ (Nat.sub_le _ _)
    apply hDY _ (le_refl _)
    apply hDX _ (le_refl _)
    exact hDY _ (Nat.sub_le _ _) u hu

theorem T022 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_T004 : LR.StringResult lam x y h v) (h_T008 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.LocalResult p lam.toNat M x y h B) (h_T019 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → Nonempty (LR.ReducedBasis p K lam.toNat M v B)) (h_T020 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → ∀ rb : LR.ReducedBasis p K lam.toNat M v B, ∀ o : LR.IntegralOps M x y h, LR.ReducedAction K lam.toNat M x y h o rb.beta) (h_T021 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → ∀ rb : LR.ReducedBasis p K lam.toNat M v B, ∀ o : LR.IntegralOps M x y h, LR.ReducedControl K lam.toNat M x y h o rb.beta) :
    ∃ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B ∧ LR.ReductionResult p K lam.toNat M x y h v B := by
  rcases h_T004.2.2.2.2.1 with ⟨B, hB⟩
  rcases h_T019 B hB with ⟨rb⟩
  rcases (h_T008 B hB).2.1.1 with ⟨o⟩
  exact ⟨B, hB, rb, o, h_T020 B hB rb o, h_T021 B hB rb o⟩

theorem T023 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V)  :
    ∀ beta : Module.Basis (LR.Idx lam.toNat) K (LR.VK K M), Nontrivial (LR.VK K M) ∧ ∀ W : Submodule K (LR.VK K M), W ≠ ⊥ → ∃ w : LR.VK K M, w ∈ W ∧ w ≠ 0 ∧ ∃ j : LR.Idx lam.toNat, beta.repr w j ≠ 0 := by
  intro beta
  constructor
  · exact ⟨⟨beta ⟨0, Nat.zero_lt_succ _⟩, 0, beta.ne_zero _⟩⟩
  · intro W hW
    obtain ⟨w, hwW, hw⟩ := Submodule.exists_mem_ne_zero_of_ne_bot hW
    refine ⟨w, hwW, hw, ?_⟩
    by_contra hc
    push_neg at hc
    apply hw
    apply beta.repr.injective
    ext j
    simpa using hc j

theorem T024 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_T023 : ∀ beta : Module.Basis (LR.Idx lam.toNat) K (LR.VK K M), Nontrivial (LR.VK K M) ∧ ∀ W : Submodule K (LR.VK K M), W ≠ ⊥ → ∃ w : LR.VK K M, w ∈ W ∧ w ≠ 0 ∧ ∃ j : LR.Idx lam.toNat, beta.repr w j ≠ 0) :
    ∀ beta : Module.Basis (LR.Idx lam.toNat) K (LR.VK K M), ∀ W : Submodule K (LR.VK K M), (∀ i j, LR.Inv W (LR.MU beta i j)) → W = ⊥ ∨ W = ⊤ := by
  intro beta W hW
  by_cases hzero : W = ⊥
  · exact Or.inl hzero
  · right
    obtain ⟨w, hw, hwne, j, hj⟩ := (h_T023 beta).2 W hzero
    have hb : ∀ i, beta i ∈ W := by
      intro i
      have hi := hW i j w hw
      change (beta.coord j w) • beta i ∈ W at hi
      have hc : beta.coord j w ≠ 0 := by simpa using hj
      have hs := W.smul_mem (beta.coord j w)⁻¹ hi
      simpa only [smul_smul, inv_mul_cancel₀ hc, one_smul] using hs
    apply top_unique
    rw [← beta.span_eq]
    exact Submodule.span_le.mpr (by rintro _ ⟨i, rfl⟩; exact hb i)

theorem T025 (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_H003 : 0 ≤ lam ∧ lam < (p : ℤ)) (h_H004 : Module.Finite ℂ V ∧ Module.finrank ℂ V = lam.toNat+1 ∧ LR.Brackets x y h ∧ Nontrivial V ∧ ∀ W : Submodule ℂ V, LR.Inv W x → LR.Inv W y → LR.Inv W h → W = ⊥ ∨ W = ⊤) (h_T022 : ∃ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B ∧ LR.ReductionResult p K lam.toNat M x y h v B) (h_T023 : ∀ beta : Module.Basis (LR.Idx lam.toNat) K (LR.VK K M), Nontrivial (LR.VK K M) ∧ ∀ W : Submodule K (LR.VK K M), W ≠ ⊥ → ∃ w : LR.VK K M, w ∈ W ∧ w ≠ 0 ∧ ∃ j : LR.Idx lam.toNat, beta.repr w j ≠ 0) (h_T024 : ∀ beta : Module.Basis (LR.Idx lam.toNat) K (LR.VK K M), ∀ W : Submodule K (LR.VK K M), (∀ i j, LR.Inv W (LR.MU beta i j)) → W = ⊥ ∨ W = ⊤) :
    Nontrivial (LR.VK K M) ∧ ∃ o : LR.IntegralOps M x y h, ∀ W : Submodule K (LR.VK K M), LR.Inv W (o.xz.baseChange K) → LR.Inv W (o.yz.baseChange K) → LR.Inv W (o.hz.baseChange K) → W = ⊥ ∨ W = ⊤ := by
  rcases h_T022 with ⟨B, hB, rb, o, ha, hc⟩
  refine ⟨(h_T023 rb.beta).1, o, ?_⟩
  intro W hx hy hh
  apply h_T024 rb.beta W
  exact hc.2 W hx hy

set_option Elab.async false in
theorem P (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_H002 : CharP K p) (h_H003 : 0 ≤ lam ∧ lam < (p : ℤ)) (h_H004 : Module.Finite ℂ V ∧ Module.finrank ℂ V = lam.toNat+1 ∧ LR.Brackets x y h ∧ Nontrivial V ∧ ∀ W : Submodule ℂ V, LR.Inv W x → LR.Inv W y → LR.Inv W h → W = ⊥ ∨ W = ⊤) (h_H005 : v ≠ 0 ∧ x v = 0 ∧ h v = (lam : ℂ) • v) (h_H006 : (∃ f : Module.Basis (LR.Idx lam.toNat) ℤ M, ∃ c : Module.Basis (LR.Idx lam.toNat) ℂ V, ∀ i, (f i : V) = c i) ∧ (∀ r m, m ∈ M → LR.DP x r m ∈ M) ∧ (∀ r m, m ∈ M → LR.DP y r m ∈ M)) :
    Nontrivial (LR.VK K M) ∧ ∃ o : LR.IntegralOps M x y h, ∀ W : Submodule K (LR.VK K M), LR.Inv W (o.xz.baseChange K) → LR.Inv W (o.yz.baseChange K) → LR.Inv W (o.hz.baseChange K) → W = ⊥ ∨ W = ⊤ := by
  have h_T001 : LR.Strings lam x y h v := @T001 p K instK lam V instV instCV x y h v M h_H003 h_H004 h_H005
  have h_T002 : (∀ i : LR.Idx lam.toNat, LR.e y v i.val ≠ 0) ∧ LinearIndependent ℂ (fun i : LR.Idx lam.toNat => LR.e y v i.val) := @T002 p K instK lam V instV instCV x y h v M h_H003 h_H005 h_T001
  have h_T003 : (∃ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B) ∧ (∀ m : ℕ, lam.toNat < m → (y^m) v = 0) := @T003 p K instK lam V instV instCV x y h v M h_H003 h_H004 h_T001 h_T002
  have h_T004 : LR.StringResult lam x y h v := @T004 p K instK lam V instV instCV x y h v M h_H003 h_H005 h_T001 h_T002 h_T003
  have h_T005 : ∀ q : ℚ, q ∈ LR.R p ↔ ∃ a b : ℤ, b ≠ 0 ∧ ¬ (p : ℤ) ∣ b ∧ q = (a : ℚ)/(b : ℚ) := @T005 p K instK lam V instV instCV x y h v M h_H001
  have h_T006 : Nonempty (LR.LatticeEmbedding p lam.toNat M) := @T006 p K instK lam V instV instCV x y h v M h_H001 h_H004 h_H006 h_T004 h_T005
  have h_T007 : LR.Preserves p lam.toNat M x y h := @T007 p K instK lam V instV instCV x y h v M h_H001 h_H003 h_H004 h_H006 h_T004 h_T005
  have h_T008 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.LocalResult p lam.toNat M x y h B := @T008 p K instK lam V instV instCV x y h v M h_T004 h_T005 h_T006 h_T007
  have h_T009 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → Nonempty (LR.Decomposition p lam.toNat M v B) := @T009 p K instK lam V instV instCV x y h v M h_H001 h_T004 h_T008
  have h_T010 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.RationalEmbedding p M v := @T010 p K instK lam V instV instCV x y h v M h_H001 h_T009
  have h_T011 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → ∀ d : LR.Decomposition p lam.toNat M v B, ∃ Phi : (ℚ ⊗[LR.R p] LR.MR p M) ≃ₗ[ℚ] (LR.Idx lam.toNat → LR.T p M v), ∀ q c, Phi (q ⊗ₜ[LR.R p] d.coordEquiv c) = fun i => q ⊗ₜ[LR.R p] c i := @T011 p K instK lam V instV instCV x y h v M h_H001 h_T009
  have h_T012 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → Module.finrank ℚ (LR.T p M v) = 1 := @T012 p K instK lam V instV instCV x y h v M h_H001 h_T004 h_T008 h_T009 h_T010 h_T011
  have h_T013 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.CoordinateResult p lam.toNat M v B := @T013 p K instK lam V instV instCV x y h v M h_H001 h_T004 h_T009 h_T010 h_T012
  have h_T014 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → ∃ k : ℕ, 0 < k ∧ ∃ g : Fin k → ℂ, (∀ j, g j ∈ LR.Jc p M v ∧ g j ≠ 0) ∧ LR.Jc p M v = Submodule.span (LR.R p) (Set.range g) := @T014 p K instK lam V instV instCV x y h v M h_H001 h_T013
  have h_T015 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → ∀ (k : ℕ) (g : Fin k → ℂ), 0 < k → (∀ j, g j ∈ LR.Jc p M v ∧ g j ≠ 0) → ∃ a : ℂ, a ∈ LR.Jc p M v ∧ a ≠ 0 ∧ ∃ nu : Fin k → ℤ, ∃ u : Fin k → (LR.R p)ˣ, (∀ j, g j = ((((p : ℚ) ^ nu j) * ((u j : LR.R p) : ℚ) : ℚ) : ℂ) * a) ∧ ∃ j0 : Fin k, ∀ j, nu j0 ≤ nu j := @T015 p K instK lam V instV instCV x y h v M h_H001 h_T013
  have h_T016 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → LR.PrincipalResult p lam.toNat M v B := @T016 p K instK lam V instV instCV x y h v M h_H001 h_T013 h_T014 h_T015
  have h_T017 : Nonempty (LR.FirstChange p K M) := @T017 p K instK lam V instV instCV x y h v M h_H001 h_H002 h_T005
  have h_T018 : Nonempty (LR.ScalarData p K M) := @T018 p K instK lam V instV instCV x y h v M h_H001 h_H002 h_T005 h_T017
  have h_T019 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → Nonempty (LR.ReducedBasis p K lam.toNat M v B) := @T019 p K instK lam V instV instCV x y h v M h_H001 h_H002 h_T004 h_T008 h_T016 h_T018
  have h_T020 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → ∀ rb : LR.ReducedBasis p K lam.toNat M v B, ∀ o : LR.IntegralOps M x y h, LR.ReducedAction K lam.toNat M x y h o rb.beta := @T020 p K instK lam V instV instCV x y h v M h_H001 h_H002 h_T004 h_T008
  have h_T021 : ∀ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B → ∀ rb : LR.ReducedBasis p K lam.toNat M v B, ∀ o : LR.IntegralOps M x y h, LR.ReducedControl K lam.toNat M x y h o rb.beta := @T021 p K instK lam V instV instCV x y h v M h_H001 h_T004 h_T008 h_T020
  have h_T022 : ∃ B : Module.Basis (LR.Idx lam.toNat) ℂ V, LR.IsStringBasis lam.toNat y v B ∧ LR.ReductionResult p K lam.toNat M x y h v B := @T022 p K instK lam V instV instCV x y h v M h_T004 h_T008 h_T019 h_T020 h_T021
  have h_T023 : ∀ beta : Module.Basis (LR.Idx lam.toNat) K (LR.VK K M), Nontrivial (LR.VK K M) ∧ ∀ W : Submodule K (LR.VK K M), W ≠ ⊥ → ∃ w : LR.VK K M, w ∈ W ∧ w ≠ 0 ∧ ∃ j : LR.Idx lam.toNat, beta.repr w j ≠ 0 := @T023 p K instK lam V instV instCV x y h v M 
  have h_T024 : ∀ beta : Module.Basis (LR.Idx lam.toNat) K (LR.VK K M), ∀ W : Submodule K (LR.VK K M), (∀ i j, LR.Inv W (LR.MU beta i j)) → W = ⊥ ∨ W = ⊤ := @T024 p K instK lam V instV instCV x y h v M h_T023
  have h_T025 : Nontrivial (LR.VK K M) ∧ ∃ o : LR.IntegralOps M x y h, ∀ W : Submodule K (LR.VK K M), LR.Inv W (o.xz.baseChange K) → LR.Inv W (o.yz.baseChange K) → LR.Inv W (o.hz.baseChange K) → W = ⊥ ∨ W = ⊤ := @T025 p K instK lam V instV instCV x y h v M h_H001 h_H003 h_H004 h_T022 h_T023 h_T024
  exact h_T025

#check @P
#print axioms P

end Translation

namespace AuditBExport
set_option autoImplicit false
set_option Elab.async false in
theorem P (p : ℕ) (K : Type*) [instK : Field K] (lam : ℤ) (V : Type*) [instV : AddCommGroup V] [instCV : Module ℂ V] (x : Module.End ℂ V) (y : Module.End ℂ V) (h : Module.End ℂ V) (v : V) (M : Submodule ℤ V) (h_H001 : Nat.Prime p) (h_H002 : CharP K p) (h_H003 : 0 ≤ lam ∧ lam < (p : ℤ)) (h_H004 : Module.Finite ℂ V ∧ Module.finrank ℂ V = lam.toNat+1 ∧ LR.Brackets x y h ∧ Nontrivial V ∧ ∀ W : Submodule ℂ V, LR.Inv W x → LR.Inv W y → LR.Inv W h → W = ⊥ ∨ W = ⊤) (h_H005 : v ≠ 0 ∧ x v = 0 ∧ h v = (lam : ℂ) • v) (h_H006 : (∃ f : Module.Basis (LR.Idx lam.toNat) ℤ M, ∃ c : Module.Basis (LR.Idx lam.toNat) ℂ V, ∀ i, (f i : V) = c i) ∧ (∀ r m, m ∈ M → LR.DP x r m ∈ M) ∧ (∀ r m, m ∈ M → LR.DP y r m ∈ M)) : Nontrivial (LR.VK K M) ∧ ∃ o : LR.IntegralOps M x y h, ∀ W : Submodule K (LR.VK K M), LR.Inv W (o.xz.baseChange K) → LR.Inv W (o.yz.baseChange K) → LR.Inv W (o.hz.baseChange K) → W = ⊥ ∨ W = ⊤ := by
  exact @Translation.P.{_, _} p K instK lam V instV instCV x y h v M h_H001 h_H002 h_H003 h_H004 h_H005 h_H006

#check @P
#print axioms P
end AuditBExport
