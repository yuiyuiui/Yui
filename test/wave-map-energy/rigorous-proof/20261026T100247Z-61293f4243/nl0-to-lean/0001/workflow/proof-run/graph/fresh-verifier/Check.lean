import Mathlib

open scoped BigOperators Topology ContDiff
open MeasureTheory

namespace WM
abbrev X (n : ℕ) := Fin n → ℝ
abbrev Y (m : ℕ) := EuclideanSpace ℝ (Fin m)
def dom (n : ℕ) : Set (X n × ℝ) := {p | 0 < p.2}
noncomputable def dt {n : ℕ} {V : Type*} [NormedAddCommGroup V] [NormedSpace ℝ V] (f : X n × ℝ → V) (x : X n) (t : ℝ) : V := deriv (fun r => f (x,r)) t
noncomputable def dx {n : ℕ} {V : Type*} [NormedAddCommGroup V] [NormedSpace ℝ V] (f : X n × ℝ → V) (j : Fin n) (x : X n) (t : ℝ) : V := fderiv ℝ (fun y => f (y,t)) x (Pi.single j 1)
noncomputable def ut {n m : ℕ} (u : X n × ℝ → Y m) : X n × ℝ → Y m := fun p => dt u p.1 p.2
noncomputable def utt {n m : ℕ} (u : X n × ℝ → Y m) : X n × ℝ → Y m := fun p => dt (ut u) p.1 p.2
noncomputable def xu {n m : ℕ} (u : X n × ℝ → Y m) (j : Fin n) : X n × ℝ → Y m := fun p => dx u j p.1 p.2
noncomputable def lap {n m : ℕ} (u : X n × ℝ → Y m) (x : X n) (t : ℝ) : Y m := ∑ j, dx (xu u j) j x t
noncomputable def e {n m : ℕ} (u : X n × ℝ → Y m) : X n × ℝ → ℝ := fun p => ‖ut u p‖ ^ 2 + ∑ j, ‖xu u j p‖ ^ 2
noncomputable def et {n m : ℕ} (u : X n × ℝ → Y m) : X n × ℝ → ℝ := fun p => dt (e u) p.1 p.2
noncomputable def energy {n m : ℕ} (u : X n × ℝ → Y m) (t : ℝ) : ℝ := ∫ x, e u (x,t)
def box (n : ℕ) (R : ℝ) : Set (X n) := {x | ∀ j, x j ∈ Set.Icc (-R) R}
def openBox (n : ℕ) (R : ℝ) : Set (X n) := {x | ∀ j, x j ∈ Set.Ioo (-R) R}
noncomputable def aTerm {n m : ℕ} (u : X n × ℝ → Y m) : X n × ℝ → ℝ := fun p => inner ℝ (ut u p) (utt u p)
noncomputable def bTerm {n m : ℕ} (u : X n × ℝ → Y m) (j : Fin n) : X n × ℝ → ℝ := fun p => inner ℝ (xu u j p) (dx (ut u) j p.1 p.2)
noncomputable def cTerm {n m : ℕ} (u : X n × ℝ → Y m) (j : Fin n) : X n × ℝ → ℝ := fun p => inner ℝ (ut u p) (dx (xu u j) j p.1 p.2)
noncomputable def flux {n m : ℕ} (u : X n × ℝ → Y m) (j : Fin n) : X n × ℝ → ℝ := fun p => inner ℝ (ut u p) (xu u j p)
noncomputable def divFlux {n m : ℕ} (u : X n × ℝ → Y m) (j : Fin n) : X n × ℝ → ℝ := fun p => dx (flux u j) j p.1 p.2
def regular {n m : ℕ} (u : X n × ℝ → Y m) : Prop :=
  ContDiffOn ℝ ∞ (ut u) (dom n) ∧ ContDiffOn ℝ ∞ (utt u) (dom n) ∧ (∀ j, ContDiffOn ℝ ∞ (xu u j) (dom n)) ∧ ContDiffOn ℝ ∞ (e u) (dom n) ∧ ContDiffOn ℝ ∞ (et u) (dom n) ∧
  (∀ x t, 0 < t → et u (x,t) = 2 * aTerm u (x,t) + 2 * ∑ j, bTerm u j (x,t)) ∧
  (∀ j x t, 0 < t → dt (xu u j) x t = dx (ut u) j x t)
def good {n : ℕ} (C : Set (X n)) (R : ℝ) (f : X n → ℝ) : Prop :=
  Continuous f ∧ (∃ B : ℝ, 0 ≤ B ∧ ∀ x ∈ box n R, |f x| ≤ B) ∧ (∀ x, x ∉ C → f x = 0) ∧ Integrable f
noncomputable def quot {n m : ℕ} (u : X n × ℝ → Y m) (t h : ℝ) (x : X n) : ℝ := (e u (x,t+h) - e u (x,t)) / h
noncomputable def major {n : ℕ} (R B : ℝ) : X n → ℝ := (box n R).indicator (fun _ => B)
def geometry {n m : ℕ} (u : X n × ℝ → Y m) (q : Y m) (τ : ℝ) (C : Set (X n)) (R : ℝ) : Prop :=
  IsCompact C ∧ 0 < R ∧ C ⊆ openBox n R ∧ (∀ x, x ∉ C → ∀ r ∈ Set.Icc (τ/2) (3*τ/2), u (x,r) = q)
def localData {n m : ℕ} (u : X n × ℝ → Y m) (q : Y m) (τ : ℝ) (C : Set (X n)) (R : ℝ) : Prop :=
  geometry u q τ C R ∧ IsCompact (box n R) ∧ volume (box n R) = ENNReal.ofReal ((2*R)^n) ∧ volume (box n R) < ⊤ ∧
  (∀ x, x ∉ C → ∀ r ∈ Set.Ioo (τ/2) (3*τ/2), ∀ k : ℕ, 0 < k → iteratedFDeriv ℝ k u (x,r) = 0) ∧
  (∀ r ∈ Set.Ioo (τ/2) (3*τ/2), good C R (fun x => e u (x,r)) ∧ good C R (fun x => et u (x,r)) ∧ good C R (fun x => aTerm u (x,r)) ∧ ∀ j, good C R (fun x => bTerm u j (x,r)) ∧ good C R (fun x => cTerm u j (x,r)) ∧ good C R (fun x => divFlux u j (x,r)))
def supportAndRegularity {n m : ℕ} (u : X n × ℝ → Y m) (q : Y m) : Prop :=
  regular u ∧ (∀ t : ℝ, 0 < t → Integrable (fun x => e u (x,t))) ∧ ∀ τ : ℝ, 0 < τ → ∃ C R, localData u q τ C R
noncomputable def fluxData {n m : ℕ} (u : X n × ℝ → Y m) (q : Y m) (t : ℝ) (j : Fin n) (C : Set (X n)) (R : ℝ) : Prop :=
  localData u q t C R ∧ ContDiff ℝ ∞ (fun x => flux u j (x,t)) ∧ good C R (fun x => flux u j (x,t)) ∧
  (∀ x, divFlux u j (x,t) = bTerm u j (x,t) + cTerm u j (x,t))
end WM

namespace Translation
set_option autoImplicit false

theorem T001 (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_H002 : ContDiffOn ℝ ∞ u (WM.dom n)) (h_H004 : ∀ (x : WM.X n) (t : ℝ), 0 < t → ‖u (x,t)‖ = 1) (h_H005 : ∀ (x : WM.X n) (t : ℝ), 0 < t → ∃ a : ℝ, WM.utt u (x,t) - WM.lap u x t = a • u (x,t)) :
    ∀ (x : WM.X n) (t : ℝ), 0 < t → inner ℝ (u (x,t)) (WM.ut u (x,t)) = 0 ∧ inner ℝ (WM.ut u (x,t)) (WM.utt u (x,t) - WM.lap u x t) = 0 := by
  intro x t ht
  have hopen : IsOpen (WM.dom n) := isOpen_lt continuous_const continuous_snd
  have hj : DifferentiableAt ℝ u (x,t) :=
    (h_H002.contDiffAt (hopen.mem_nhds ht)).differentiableAt (by simp)
  have hs : DifferentiableAt ℝ (fun r : ℝ => u (x,r)) t :=
    hj.comp t ((differentiableAt_const x).prodMk differentiableAt_id)
  have hd : HasDerivAt (fun r : ℝ => u (x,r)) (WM.ut u (x,t)) t := hs.hasDerivAt
  let f : ℝ → WM.Y m := fun r => if 0 < r then u (x,r) else q
  have heq : f =ᶠ[nhds t] (fun r => u (x,r)) := by
    filter_upwards [isOpen_Ioi.mem_nhds ht] with r hr
    have hr' : 0 < r := hr
    simp [f, hr']
  have hf : HasDerivAt f (WM.ut u (x,t)) t := hd.congr_of_eventuallyEq heq
  have hsq : HasDerivAt (fun r => inner ℝ (f r) (f r)) 0 t := by
    apply (hasDerivAt_const t (1 : ℝ)).congr_of_eventuallyEq
    filter_upwards [isOpen_Ioi.mem_nhds ht] with r hr
    have hr' : 0 < r := hr
    simp [f, hr', inner_self_eq_norm_sq_to_K, h_H004 x r hr']
  have hval : f t = u (x,t) := by simp [f, ht]
  have hh := (hf.inner ℝ hf).unique hsq
  rw [hval, real_inner_comm (u (x,t)) (WM.ut u (x,t))] at hh
  have ho : inner ℝ (u (x,t)) (WM.ut u (x,t)) = 0 := by linarith
  refine ⟨ho, ?_⟩
  obtain ⟨a, ha⟩ := h_H005 x t ht
  rw [ha, inner_smul_right, real_inner_comm (u (x,t)) (WM.ut u (x,t)), ho, mul_zero]

theorem T002 (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_H002 : ContDiffOn ℝ ∞ u (WM.dom n)) :
    WM.regular u := by
  classical
  have ho : IsOpen (WM.dom n) := isOpen_lt continuous_const continuous_snd
  have bridge : ∀ {V : Type} [NormedAddCommGroup V] [NormedSpace ℝ V] (f : WM.X n × ℝ → V) (p : WM.X n × ℝ), DifferentiableAt ℝ f p → WM.dt f p.1 p.2 = fderiv ℝ f p (0,1) ∧ ∀ j, WM.dx f j p.1 p.2 = fderiv ℝ f p (Pi.single j 1,0) := by
    intro V _ _ f p hf
    constructor
    · exact ((hf.hasFDerivAt.comp p.2 (hasFDerivAt_prodMk_right p.1 p.2)).hasDerivAt).deriv
    · intro j
      have H : HasFDerivAt (fun y => f (y,p.2)) ((fderiv ℝ f p).comp (ContinuousLinearMap.inl ℝ (WM.X n) ℝ)) p.1 := hf.hasFDerivAt.comp p.1 (hasFDerivAt_prodMk_left p.1 p.2)
      dsimp [WM.dx]
      rw [H.fderiv]
      simp
  have smooth : ∀ {V : Type} [NormedAddCommGroup V] [NormedSpace ℝ V] (f : WM.X n × ℝ → V), ContDiffOn ℝ ∞ f (WM.dom n) → ContDiffOn ℝ ∞ (fun p => WM.dt f p.1 p.2) (WM.dom n) ∧ ∀ j, ContDiffOn ℝ ∞ (fun p => WM.dx f j p.1 p.2) (WM.dom n) := by
    intro V _ _ f hf
    have hd := hf.fderiv_of_isOpen ho (show (∞ : ℕ∞ω) + 1 ≤ ∞ by simp)
    have diff : ∀ p ∈ WM.dom n, DifferentiableAt ℝ f p := fun p hp => (hf.contDiffAt (ho.mem_nhds hp)).differentiableAt (by simp)
    constructor
    · exact (hd.clm_apply contDiffOn_const).congr (fun p hp => (bridge f p (diff p hp)).1)
    · intro j
      exact (hd.clm_apply contDiffOn_const).congr (fun p hp => (bridge f p (diff p hp)).2 j)
  have hut : ContDiffOn ℝ ∞ (WM.ut u) (WM.dom n) := (smooth u h_H002).1
  have hutt : ContDiffOn ℝ ∞ (WM.utt u) (WM.dom n) := (smooth (WM.ut u) hut).1
  have hxu : ∀ j, ContDiffOn ℝ ∞ (WM.xu u j) (WM.dom n) := (smooth u h_H002).2
  have he : ContDiffOn ℝ ∞ (WM.e u) (WM.dom n) := by
    unfold WM.e
    exact (hut.norm_sq ℝ).add (ContDiffOn.sum fun j _ => (hxu j).norm_sq ℝ)
  have het : ContDiffOn ℝ ∞ (WM.et u) (WM.dom n) := (smooth (WM.e u) he).1
  have mixed : ∀ j x t, 0 < t → WM.dt (WM.xu u j) x t = WM.dx (WM.ut u) j x t := by
    intro j x t ht
    let p : WM.X n × ℝ := (x,t)
    have hp : p ∈ WM.dom n := ht
    have H := h_H002.contDiffAt (ho.mem_nhds hp)
    have hd := (h_H002.fderiv_of_isOpen ho (show (∞ : ℕ∞ω) + 1 ≤ ∞ by simp)).contDiffAt (ho.mem_nhds hp)
    have ev (v w : WM.X n × ℝ) : fderiv ℝ (fun z => fderiv ℝ u z v) p w = fderiv ℝ (fderiv ℝ u) p w v := by
      have hh := (hd.differentiableAt (by simp)).hasFDerivAt.clm_apply (hasFDerivAt_const v p)
      simpa using congrArg (fun L => L w) hh.fderiv
    have eu : WM.ut u =ᶠ[𝓝 p] (fun z => fderiv ℝ u z (0,1)) := by
      filter_upwards [ho.mem_nhds hp] with z hz
      exact (bridge u z ((h_H002.contDiffAt (ho.mem_nhds hz)).differentiableAt (by simp))).1
    have ex : WM.xu u j =ᶠ[𝓝 p] (fun z => fderiv ℝ u z (Pi.single j 1,0)) := by
      filter_upwards [ho.mem_nhds hp] with z hz
      exact (bridge u z ((h_H002.contDiffAt (ho.mem_nhds hz)).differentiableAt (by simp))).2 j
    rw [(bridge (WM.xu u j) p (((hxu j).contDiffAt (ho.mem_nhds hp)).differentiableAt (by simp))).1,
        (bridge (WM.ut u) p ((hut.contDiffAt (ho.mem_nhds hp)).differentiableAt (by simp))).2 j,
        ex.fderiv_eq, eu.fderiv_eq, ev, ev]
    exact H.isSymmSndFDerivAt (by
      simp only [minSmoothness_of_isRCLikeNormedField]
      exact ENat.natCast_le_of_coe_top_le_withTop le_rfl 2) _ _
  refine ⟨hut, hutt, hxu, he, het, ?_, mixed⟩
  intro x t ht
  have timeRule (f : WM.X n × ℝ → WM.Y m) (hf : ContDiffOn ℝ ∞ f (WM.dom n)) : HasDerivAt (fun r => f (x,r)) (WM.dt f x t) t := by
    exact (((hf.contDiffAt (ho.mem_nhds ht)).differentiableAt (by simp)).hasFDerivAt.comp t (hasFDerivAt_prodMk_right x t)).differentiableAt.hasDerivAt
  have hE := (timeRule (WM.ut u) hut).norm_sq.add (HasDerivAt.sum (u := Finset.univ) (fun j _ => (timeRule (WM.xu u j) (hxu j)).norm_sq))
  calc
    WM.et u (x,t) = 2 * inner ℝ (WM.ut u (x,t)) (WM.utt u (x,t)) + ∑ j, 2 * inner ℝ (WM.xu u j (x,t)) (WM.dt (WM.xu u j) x t) := by
      simpa only [WM.et, WM.dt, WM.e, WM.utt, Finset.sum_fn, Pi.add_def] using hE.deriv
    _ = _ := by simp only [mixed _ _ _ ht, ← Finset.mul_sum, WM.aTerm, WM.bTerm]

theorem T003 (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_H006 : ∀ (s t : ℝ), 0 < s → s < t → ∃ C : Set (WM.X n), IsCompact C ∧ ∀ x, x ∉ C → ∀ r ∈ Set.Icc s t, u (x,r) = q) :
    ∀ τ : ℝ, 0 < τ → ∃ (C : Set (WM.X n)) (R : ℝ), WM.geometry u q τ C R := by
  intro τ hτ
  obtain ⟨C, hC, hu⟩ := h_H006 (τ / 2) (3 * τ / 2) (by linarith) (by linarith)
  obtain ⟨L, hL⟩ := hC.exists_bound_of_continuousOn (continuous_id.continuousOn : ContinuousOn (fun x : WM.X n => x) C)
  refine ⟨C, 1 + max L 0, hC, ?_, ?_, hu⟩
  · have := le_max_right L 0
    linarith
  · intro x hx j
    have hnorm : |x j| ≤ L := by
      simpa only [Real.norm_eq_abs] using (norm_le_pi_norm x j).trans (hL x hx)
    have hlt : L < 1 + max L 0 := by
      have := le_max_left L 0
      linarith
    exact abs_lt.mp (lt_of_le_of_lt hnorm hlt)

theorem T004 (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_H001 : 1 ≤ n ∧ 1 ≤ m) (h_H002 : ContDiffOn ℝ ∞ u (WM.dom n)) (h_T002 : WM.regular u) (h_T003 : ∀ τ : ℝ, 0 < τ → ∃ (C : Set (WM.X n)) (R : ℝ), WM.geometry u q τ C R) :
    WM.supportAndRegularity u q := by
  classical
  have dx_smooth : ∀ {V : Type} [NormedAddCommGroup V] [NormedSpace ℝ V] (f : WM.X n × ℝ → V), ContDiffOn ℝ ∞ f (WM.dom n) → ∀ j : Fin n, ContDiffOn ℝ ∞ (fun p : WM.X n × ℝ => WM.dx f j p.1 p.2) (WM.dom n) := by
    intro V _ _ f hf j
    have hopen : IsOpen (WM.dom n) := isOpen_lt continuous_const continuous_snd
    intro p hp
    have hfp : ContDiffAt ℝ ∞ (Function.uncurry (fun (p : WM.X n × ℝ) (y : WM.X n) => f (y,p.2))) (p,p.1) := (hf.contDiffAt (hopen.mem_nhds hp)).comp _ (contDiffAt_snd.prodMk (contDiffAt_fst.snd))
    have hd := ContDiffAt.fderiv (f := fun (p : WM.X n × ℝ) (y : WM.X n) => f (y,p.2)) (g := fun p => p.1) hfp contDiffAt_fst (m := (∞ : WithTop ℕ∞)) (by simp)
    exact (hd.clm_apply contDiffAt_const).contDiffWithinAt
  have const_derivs : ∀ {V : Type} [NormedAddCommGroup V] [NormedSpace ℝ V] (O : Set (WM.X n × ℝ)), IsOpen O → ∀ (f : WM.X n × ℝ → V) (v : V), Set.EqOn f (fun _ => v) O → ∀ p ∈ O, WM.dt f p.1 p.2 = 0 ∧ ∀ j, WM.dx f j p.1 p.2 = 0 := by
    intro V _ _ O hO f v hf p hp
    have he : f =ᶠ[𝓝 p] (fun _ => v) := Filter.eventually_of_mem (hO.mem_nhds hp) hf
    constructor
    · have ht : (fun r => f (p.1,r)) =ᶠ[𝓝 p.2] (fun _ => v) := he.comp_tendsto (continuous_const.prodMk continuous_id).continuousAt
      simpa [WM.dt] using ht.deriv_eq
    · intro j
      have hx : (fun y => f (y,p.2)) =ᶠ[𝓝 p.1] (fun _ => v) := he.comp_tendsto (continuous_id.prodMk continuous_const).continuousAt
      simp [WM.dx, hx.fderiv_eq]
  have make_good : ∀ (C : Set (WM.X n)) (R : ℝ), IsCompact C → IsCompact (WM.box n R) → ∀ f : WM.X n → ℝ, Continuous f → (∀ x, x ∉ C → f x = 0) → WM.good C R f := by
    intro C R hC hQ f hf hz
    have hs : HasCompactSupport f := HasCompactSupport.of_support_subset_isCompact hC (by
      intro x hx
      by_contra h
      exact hx (hz x h))
    obtain ⟨B,hB,hbound⟩ := (hQ.image hf).isBounded.exists_pos_norm_le
    refine ⟨hf, ⟨B, hB.le, ?_⟩, hz, hf.integrable_of_hasCompactSupport hs⟩
    intro x hx
    simpa only [Real.norm_eq_abs] using hbound (f x) (Set.mem_image_of_mem f hx)
  rcases h_T002 with ⟨hut, hutt, hxu, he, het, hident, hmixed⟩
  have ha : ContDiffOn ℝ ∞ (WM.aTerm u) (WM.dom n) := hut.inner ℝ hutt
  have hb : ∀ j, ContDiffOn ℝ ∞ (WM.bTerm u j) (WM.dom n) := fun j => (hxu j).inner ℝ (dx_smooth _ hut j)
  have hc : ∀ j, ContDiffOn ℝ ∞ (WM.cTerm u j) (WM.dom n) := fun j => hut.inner ℝ (dx_smooth _ (hxu j) j)
  have hf : ∀ j, ContDiffOn ℝ ∞ (WM.flux u j) (WM.dom n) := fun j => hut.inner ℝ (hxu j)
  have hd : ∀ j, ContDiffOn ℝ ∞ (WM.divFlux u j) (WM.dom n) := fun j => dx_smooth _ (hf j) j
  have local_all : ∀ τ : ℝ, 0 < τ → ∃ C R, WM.localData u q τ C R := by
    intro τ hτ
    obtain ⟨C,R,hgeom⟩ := h_T003 τ hτ
    obtain ⟨hC,hR,hCQ,hconst⟩ := hgeom
    have hboxeq : WM.box n R = Set.Icc (fun _ : Fin n => -R) (fun _ : Fin n => R) := by
      ext x
      simp [WM.box, Set.mem_Icc, Pi.le_def, forall_and]
    have hQ : IsCompact (WM.box n R) := hboxeq ▸ isCompact_Icc
    have hv : volume (WM.box n R) = ENNReal.ofReal ((2*R)^n) := by
      rw [hboxeq, Real.volume_Icc_pi]
      simp [sub_neg_eq_add, ← two_mul, ENNReal.ofReal_pow, le_of_lt hR]
    let O : Set (WM.X n × ℝ) := Cᶜ ×ˢ Set.Ioo (τ/2) (3*τ/2)
    have hO : IsOpen O := hC.isClosed.isOpen_compl.prod isOpen_Ioo
    have huO : Set.EqOn u (fun _ => q) O := by
      intro p hp
      exact hconst p.1 hp.1 p.2 ⟨hp.2.1.le, hp.2.2.le⟩
    have hutO : Set.EqOn (WM.ut u) (fun _ => 0) O := by
      intro p hp
      exact (const_derivs O hO u q huO p hp).1
    have hxuO : ∀ j, Set.EqOn (WM.xu u j) (fun _ => 0) O := by
      intro j p hp
      exact (const_derivs O hO u q huO p hp).2 j
    have heO : Set.EqOn (WM.e u) (fun _ => 0) O := by
      intro p hp
      simp [WM.e, hutO hp, fun j => hxuO j hp]
    have hetO : Set.EqOn (WM.et u) (fun _ => 0) O := by
      intro p hp
      exact (const_derivs O hO (WM.e u) 0 heO p hp).1
    have haO : Set.EqOn (WM.aTerm u) (fun _ => 0) O := by
      intro p hp
      simp [WM.aTerm, hutO hp]
    have hbO : ∀ j, Set.EqOn (WM.bTerm u j) (fun _ => 0) O := by
      intro j p hp
      simp [WM.bTerm, hxuO j hp]
    have hcO : ∀ j, Set.EqOn (WM.cTerm u j) (fun _ => 0) O := by
      intro j p hp
      simp [WM.cTerm, hutO hp]
    have hfO : ∀ j, Set.EqOn (WM.flux u j) (fun _ => 0) O := by
      intro j p hp
      simp [WM.flux, hutO hp]
    have hdO : ∀ j, Set.EqOn (WM.divFlux u j) (fun _ => 0) O := by
      intro j p hp
      exact (const_derivs O hO (WM.flux u j) 0 (hfO j) p hp).2 j
    refine ⟨C,R, ⟨hC,hR,hCQ,hconst⟩, hQ, hv, hv ▸ ENNReal.ofReal_lt_top, ?_, ?_⟩
    · intro x hx r hr k hk
      have hp : (x,r) ∈ O := ⟨hx,hr⟩
      have heq : u =ᶠ[𝓝 (x,r)] (fun _ => q) := Filter.eventually_of_mem (hO.mem_nhds hp) huO
      rw [(heq.iteratedFDeriv ℝ k).eq_of_nhds, iteratedFDeriv_const_of_ne (ne_of_gt hk)]
      rfl
    · intro r hr
      have hrpos : 0 < r := by linarith [hr.1]
      have section_good : ∀ (f : WM.X n × ℝ → ℝ), ContDiffOn ℝ ∞ f (WM.dom n) → Set.EqOn f (fun _ => 0) O → WM.good C R (fun x => f (x,r)) := by
        intro f hfs hz
        apply make_good C R hC hQ
        · exact hfs.continuousOn.comp_continuous (continuous_id.prodMk continuous_const) (fun x => hrpos)
        · intro x hx
          exact hz ⟨hx,hr⟩
      exact ⟨section_good _ he heO, section_good _ het hetO, section_good _ ha haO,
        fun j => ⟨section_good _ (hb j) (hbO j), section_good _ (hc j) (hcO j), section_good _ (hd j) (hdO j)⟩⟩
  refine ⟨⟨hut,hutt,hxu,he,het,hident,hmixed⟩, ?_, local_all⟩
  intro t ht
  obtain ⟨C,R,hlocal⟩ := local_all t ht
  have htI : t ∈ Set.Ioo (t/2) (3*t/2) := by constructor <;> linarith
  exact (hlocal.2.2.2.2.2 t htI).1.2.2.2

theorem T005 (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_T004 : WM.supportAndRegularity u q) :
    ∀ t : ℝ, 0 < t → ∃ (C : Set (WM.X n)) (R B : ℝ), WM.localData u q t C R ∧ 0 ≤ B ∧ ∀ x ∈ WM.box n R, ∀ r ∈ Set.Icc (t-t/4) (t+t/4), |WM.et u (x,r)| ≤ B := by
  intro t ht
  obtain ⟨C, R, hlocal⟩ := h_T004.2.2 t ht
  have hcompact : IsCompact (WM.box n R ×ˢ Set.Icc (t - t / 4) (t + t / 4)) :=
    hlocal.2.1.prod isCompact_Icc
  have hsub : WM.box n R ×ˢ Set.Icc (t - t / 4) (t + t / 4) ⊆ WM.dom n := by
    intro p hp
    change 0 < p.2
    have hp' := hp.2.1
    linarith
  have hcont : ContinuousOn (WM.et u) (WM.box n R ×ˢ Set.Icc (t - t / 4) (t + t / 4)) :=
    h_T004.1.2.2.2.2.1.continuousOn.mono hsub
  obtain ⟨B, hB⟩ := hcompact.exists_bound_of_continuousOn hcont
  refine ⟨C, R, max B 0, hlocal, le_max_right _ _, ?_⟩
  intro x hx r hr
  have hb := hB (x, r) ⟨hx, hr⟩
  exact le_trans (by simpa only [Real.norm_eq_abs] using hb) (le_max_left _ _)

theorem T006 (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_T004 : WM.supportAndRegularity u q) :
    ∀ (t : ℝ), 0 < t → ∀ (C : Set (WM.X n)) (R B : ℝ), WM.localData u q t C R → 0 ≤ B → (∀ x ∈ WM.box n R, ∀ r ∈ Set.Icc (t-t/4) (t+t/4), |WM.et u (x,r)| ≤ B) → ((∀ h : ℝ, 0 < |h| → |h| < t/4 → Integrable (WM.quot u t h) ∧ AEStronglyMeasurable (WM.quot u t h) ∧ ∀ x, |WM.quot u t h x| ≤ WM.major R B x) ∧ (∀ x, Filter.Tendsto (fun h => WM.quot u t h x) (nhdsWithin 0 ({0}ᶜ)) (nhds (WM.et u (x,t))))) := by
  intro t ht C R B hloc hB hbound
  have hopen : IsOpen (WM.dom n) := isOpen_lt continuous_const continuous_snd
  have hd (x : WM.X n) (r : ℝ) (hr : 0 < r) :
      HasDerivAt (fun s => WM.e u (x,s)) (WM.et u (x,r)) r := by
    have he := (h_T004.1.2.2.2.1.differentiableOn (by simp)).differentiableAt
      (hopen.mem_nhds (show (x,r) ∈ WM.dom n from hr))
    have hc : DifferentiableAt ℝ (fun s : ℝ => (x,s)) r :=
      (differentiableAt_const x).prodMk differentiableAt_id
    exact (he.comp r hc).hasDerivAt
  have htI : t ∈ Set.Ioo (t/2) (3*t/2) := by constructor <;> linarith
  have hg := hloc.2.2.2.2.2 t htI
  constructor
  · intro h hh hsmall
    have hlow : - (t/4) < h := (abs_lt.mp hsmall).1
    have hupp : h < t/4 := (abs_lt.mp hsmall).2
    have hpos : 0 < t+h := by linarith
    have htime : t+h ∈ Set.Ioo (t/2) (3*t/2) := by constructor <;> linarith
    have hgh := hloc.2.2.2.2.2 (t+h) htime
    have hi : Integrable (WM.quot u t h) :=
      (hgh.1.2.2.2.sub hg.1.2.2.2).div_const h
    refine ⟨hi, hi.aestronglyMeasurable, ?_⟩
    intro x
    by_cases hx : x ∈ WM.box n R
    · have hm (a b : ℝ) (ha : t-t/4 ≤ a) (hb : b ≤ t+t/4) (hab : a ≤ b) :
          |WM.e u (x,b) - WM.e u (x,a)| ≤ B * (b-a) := by
        have H := norm_image_sub_le_of_norm_deriv_le_segment'
          (f := fun s => WM.e u (x,s)) (f' := fun s => WM.et u (x,s)) (C := B)
          (a := a) (b := b)
          (fun r hr => (hd x r (by have := hr.1; linarith)).hasDerivWithinAt)
          (fun r hr => by
            rw [Real.norm_eq_abs]
            exact hbound x hx r ⟨by linarith [hr.1], by linarith [hr.2]⟩)
          b ⟨hab, le_rfl⟩
        simpa only [Real.norm_eq_abs] using H
      have hdiff : |WM.e u (x,t+h) - WM.e u (x,t)| ≤ B * |h| := by
        by_cases hh0 : 0 ≤ h
        · simpa [abs_of_nonneg hh0] using hm t (t+h) (by linarith) (by linarith) (by linarith)
        · have H := hm (t+h) t (by linarith) (by linarith) (by linarith)
          rw [abs_sub_comm] at H
          simpa [abs_of_neg (lt_of_not_ge hh0)] using H
      rw [WM.major, Set.indicator_of_mem hx]
      change |(WM.e u (x,t+h) - WM.e u (x,t)) / h| ≤ B
      rw [abs_div]
      exact (div_le_iff₀ hh).2 hdiff
    · have hxc : x ∉ C := by
        intro hc
        apply hx
        exact fun j => ⟨(hloc.1.2.2.1 hc j).1.le, (hloc.1.2.2.1 hc j).2.le⟩
      have hz := hg.1.2.2.1 x hxc
      have hzh := hgh.1.2.2.1 x hxc
      simp [WM.quot, WM.major, hx, hz, hzh]
  · intro x
    simpa [WM.quot, smul_eq_mul, div_eq_mul_inv, mul_comm] using (hd x t ht).tendsto_slope_zero

theorem T007 (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_T004 : WM.supportAndRegularity u q) (h_T005 : ∀ t : ℝ, 0 < t → ∃ (C : Set (WM.X n)) (R B : ℝ), WM.localData u q t C R ∧ 0 ≤ B ∧ ∀ x ∈ WM.box n R, ∀ r ∈ Set.Icc (t-t/4) (t+t/4), |WM.et u (x,r)| ≤ B) (h_T006 : ∀ (t : ℝ), 0 < t → ∀ (C : Set (WM.X n)) (R B : ℝ), WM.localData u q t C R → 0 ≤ B → (∀ x ∈ WM.box n R, ∀ r ∈ Set.Icc (t-t/4) (t+t/4), |WM.et u (x,r)| ≤ B) → ((∀ h : ℝ, 0 < |h| → |h| < t/4 → Integrable (WM.quot u t h) ∧ AEStronglyMeasurable (WM.quot u t h) ∧ ∀ x, |WM.quot u t h x| ≤ WM.major R B x) ∧ (∀ x, Filter.Tendsto (fun h => WM.quot u t h x) (nhdsWithin 0 ({0}ᶜ)) (nhds (WM.et u (x,t)))))) :
    ∀ t : ℝ, 0 < t → Filter.Tendsto (fun h => ∫ x, WM.quot u t h x) (nhdsWithin 0 ({0}ᶜ)) (nhds (∫ x, WM.et u (x,t))) := by
  intro t ht
  obtain ⟨C, R, B, hdata, hB, hbound⟩ := h_T005 t ht
  obtain ⟨hquot, hlim⟩ := h_T006 t ht C R B hdata hB hbound
  have hmajor : Integrable (WM.major (n := n) R B) := by
    exact (integrableOn_const (C := B) hdata.2.2.2.1.ne).integrable_indicator hdata.2.1.measurableSet
  have hev : ∀ᶠ h : ℝ in nhdsWithin 0 ({0}ᶜ), 0 < |h| ∧ |h| < t / 4 := by
    have hsmall : ∀ᶠ h : ℝ in nhdsWithin 0 ({0}ᶜ), h ∈ Metric.ball 0 (t / 4) :=
      nhdsWithin_le_nhds (Metric.ball_mem_nhds 0 (by positivity))
    filter_upwards [hsmall, self_mem_nhdsWithin] with h hs hn
    have hne : h ≠ 0 := by simpa using hn
    exact ⟨abs_pos.mpr hne, by simpa [Real.dist_eq] using hs⟩
  apply tendsto_integral_filter_of_dominated_convergence (WM.major R B)
  · filter_upwards [hev] with h hh
    exact (hquot h hh.1 hh.2).2.1
  · filter_upwards [hev] with h hh
    exact Filter.Eventually.of_forall (fun x => by simpa only [Real.norm_eq_abs] using (hquot h hh.1 hh.2).2.2 x)
  · exact hmajor
  · exact Filter.Eventually.of_forall hlim

theorem T008 (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_T004 : WM.supportAndRegularity u q) (h_T007 : ∀ t : ℝ, 0 < t → Filter.Tendsto (fun h => ∫ x, WM.quot u t h x) (nhdsWithin 0 ({0}ᶜ)) (nhds (∫ x, WM.et u (x,t)))) :
    ∀ t : ℝ, 0 < t → DifferentiableAt ℝ (WM.energy u) t ∧ deriv (WM.energy u) t = ∫ x, WM.et u (x,t) := by
  intro t ht
  have hi := h_T004.2.1
  have hp : ∀ᶠ h : ℝ in nhds 0, 0 < t + h := by
    exact (isOpen_lt continuous_const (continuous_const.add continuous_id)).mem_nhds (by simpa using ht)
  have heq : (fun h : ℝ => ∫ x, WM.quot u t h x) =ᶠ[nhdsWithin 0 ({0}ᶜ)]
      (fun h => h⁻¹ • (WM.energy u (t+h) - WM.energy u t)) := by
    filter_upwards [hp.filter_mono nhdsWithin_le_nhds] with h hh
    change (∫ x, (WM.e u (x,t+h) - WM.e u (x,t)) / h) = _
    rw [integral_div, integral_sub (hi (t+h) hh) (hi t ht)]
    simp only [WM.energy, smul_eq_mul, div_eq_mul_inv, mul_comm]
  have hd : HasDerivAt (WM.energy u) (∫ x, WM.et u (x,t)) t := by
    apply hasDerivAt_iff_tendsto_slope_zero.mpr
    exact (h_T007 t ht).congr' heq
  exact ⟨hd.differentiableAt, hd.deriv⟩

theorem T009 (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_H001 : 1 ≤ n ∧ 1 ≤ m) (h_H002 : ContDiffOn ℝ ∞ u (WM.dom n)) (h_T004 : WM.supportAndRegularity u q) :
    ∀ (t : ℝ), 0 < t → ∀ j : Fin n, ∃ (C : Set (WM.X n)) (R : ℝ), WM.fluxData u q t j C R := by
  intro t ht j
  obtain ⟨C, R, hL⟩ := h_T004.2.2 t ht
  have hreg := h_T004.1
  have hs : ContDiff ℝ ∞ (fun x : WM.X n => (x,t)) := contDiff_id.prodMk contDiff_const
  have hU : ContDiff ℝ ∞ (fun x => WM.ut u (x,t)) :=
    hreg.1.comp_contDiff hs (fun _ => ht)
  have hX : ContDiff ℝ ∞ (fun x => WM.xu u j (x,t)) :=
    (hreg.2.2.1 j).comp_contDiff hs (fun _ => ht)
  have hF : ContDiff ℝ ∞ (fun x => WM.flux u j (x,t)) := hU.inner ℝ hX
  have hzero : ∀ x, x ∉ C → WM.flux u j (x,t) = 0 := by
    intro x hx
    have htI : t ∈ Set.Ioo (t/2) (3*t/2) := by constructor <;> linarith
    have he := (hL.2.2.2.2.2 t htI).1.2.2.1 x hx
    have hsum : 0 ≤ ∑ k : Fin n, ‖WM.xu u k (x,t)‖ ^ 2 := Finset.sum_nonneg (fun k _ => sq_nonneg _)
    have hu : WM.ut u (x,t) = 0 := by
      apply norm_eq_zero.mp
      dsimp [WM.e] at he
      nlinarith [norm_nonneg (WM.ut u (x,t))]
    simp [WM.flux, hu]
  have hcompact : HasCompactSupport (fun x => WM.flux u j (x,t)) := by
    apply HasCompactSupport.of_support_subset_isCompact hL.1.1
    intro x hx
    by_contra hn
    exact hx (hzero x hn)
  have hgood : WM.good C R (fun x => WM.flux u j (x,t)) := by
    refine ⟨hF.continuous, ?_, hzero, hF.continuous.integrable_of_hasCompactSupport hcompact⟩
    obtain ⟨B, hB⟩ := hL.2.1.exists_bound_of_continuousOn hF.continuous.continuousOn
    refine ⟨max B 0, le_max_right _ _, ?_⟩
    intro x hx
    have hb : |WM.flux u j (x,t)| ≤ B := by simpa only [Real.norm_eq_abs] using hB x hx
    exact hb.trans (le_max_left _ _)
  refine ⟨C, R, hL, hF, hgood, ?_⟩
  intro x
  have hdU := hU.differentiable (by simp) x
  have hdX := hX.differentiable (by simp) x
  have hp := fderiv_inner_apply ℝ hdU hdX (Pi.single j 1)
  change fderiv ℝ (fun x => inner ℝ (WM.ut u (x,t)) (WM.xu u j (x,t))) x (Pi.single j 1) = _
  rw [hp]
  simp only [WM.bTerm, WM.cTerm, WM.dx]
  rw [real_inner_comm (fderiv ℝ (fun y => WM.ut u (y,t)) x (Pi.single j 1)), add_comm]

theorem T010 (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m)  :
    ∀ (k : ℕ) (j : Fin (k+1)) (R : ℝ), 0 < R → MeasurePreserving (fun p : ℝ × WM.X k => (Fin.insertNth j p.1 p.2 : WM.X (k+1))) volume volume ∧ (Set.image (fun p : ℝ × WM.X k => (Fin.insertNth j p.1 p.2 : WM.X (k+1))) (Set.Icc (-R) R ×ˢ WM.box k R) = WM.box (k+1) R) ∧ (∀ d : WM.X (k+1) → ℝ, Continuous d → (∫ x in WM.box (k+1) R, d x) = ∫ z in WM.box k R, ∫ y in Set.Icc (-R) R, d (Fin.insertNth j y z)) := by
  intro k j R hR
  let E : (ℝ × WM.X k) ≃ᵐ WM.X (k+1) :=
    (MeasurableEquiv.piFinSuccAbove (fun _ : Fin (k+1) => ℝ) j).symm
  have hE : MeasurePreserving E volume volume :=
    (volume_preserving_piFinSuccAbove (fun _ : Fin (k+1) => ℝ) j).symm _
  have hpre : E ⁻¹' WM.box (k+1) R = Set.Icc (-R) R ×ˢ WM.box k R := by
    ext p
    simp only [Set.mem_preimage, WM.box, Set.mem_setOf_eq, Set.mem_prod,
      MeasurableEquiv.piFinSuccAbove_symm_apply, E]
    rw [j.forall_iff_succAbove]
    simp
  have himg : E '' (Set.Icc (-R) R ×ˢ WM.box k R) = WM.box (k+1) R := by
    rw [← hpre]
    exact E.image_preimage _
  refine ⟨hE, himg, ?_⟩
  intro d hd
  have hc : Continuous (fun p : ℝ × WM.X k => d (E p)) := by
    apply hd.comp
    change Continuous (fun p : ℝ × WM.X k => (Fin.insertNth j p.1 p.2 : WM.X (k+1)))
    exact Continuous.finInsertNth (A := fun _ => ℝ) j continuous_fst continuous_snd
  have hcompact : IsCompact (WM.box k R) := by
    simpa [WM.box, Set.pi] using
      (isCompact_univ_pi (fun _ : Fin k => (isCompact_Icc : IsCompact (Set.Icc (-R) R))))
  have hint : IntegrableOn (fun p : ℝ × WM.X k => d (E p))
      (Set.Icc (-R) R ×ˢ WM.box k R) volume :=
    hc.continuousOn.integrableOn_compact (isCompact_Icc.prod hcompact)
  calc
    (∫ x in WM.box (k+1) R, d x) =
        ∫ p in Set.Icc (-R) R ×ˢ WM.box k R, d (E p) := by
      rw [← himg]
      exact hE.setIntegral_image_emb E.measurableEmbedding d _
    _ = ∫ z in WM.box k R, ∫ y in Set.Icc (-R) R, d (Fin.insertNth j y z) := by
      rw [Measure.volume_eq_prod, ← Measure.prod_restrict]
      apply integral_prod_symm
      simpa only [IntegrableOn, Measure.volume_eq_prod, ← Measure.prod_restrict] using hint

theorem T011 (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_H001 : 1 ≤ n ∧ 1 ≤ m) (h_T009 : ∀ (t : ℝ), 0 < t → ∀ j : Fin n, ∃ (C : Set (WM.X n)) (R : ℝ), WM.fluxData u q t j C R) (h_T010 : ∀ (k : ℕ) (j : Fin (k+1)) (R : ℝ), 0 < R → MeasurePreserving (fun p : ℝ × WM.X k => (Fin.insertNth j p.1 p.2 : WM.X (k+1))) volume volume ∧ (Set.image (fun p : ℝ × WM.X k => (Fin.insertNth j p.1 p.2 : WM.X (k+1))) (Set.Icc (-R) R ×ˢ WM.box k R) = WM.box (k+1) R) ∧ (∀ d : WM.X (k+1) → ℝ, Continuous d → (∫ x in WM.box (k+1) R, d x) = ∫ z in WM.box k R, ∫ y in Set.Icc (-R) R, d (Fin.insertNth j y z))) :
    ∀ (t : ℝ), 0 < t → ∀ j : Fin n, (∫ x, WM.divFlux u j (x,t)) = 0 := by
  obtain ⟨k, rfl⟩ := Nat.exists_eq_succ_of_ne_zero (Nat.ne_of_gt h_H001.1)
  intro t ht j
  obtain ⟨C, R, hloc, hg, hgoodg, hdiv⟩ := h_T009 t ht j
  rcases hloc with ⟨hgeom, hbox, hvol, hfin, hiter, hgoods⟩
  rcases hgeom with ⟨hC, hR, hsub, hconst⟩
  have htI : t ∈ Set.Ioo (t / 2) (3 * t / 2) := by constructor <;> linarith
  have hd := (hgoods t htI).2.2.2 j |>.2.2
  rcases hd with ⟨hdcont, hdbound, hdzero, hdint⟩
  rcases hgoodg with ⟨hgcont, hgbound, hgzero, hgint⟩
  have hins (z : WM.X k) (y : ℝ) : HasDerivAt (fun r : ℝ => (Fin.insertNth j r z : WM.X (k+1))) (Pi.single j 1) y := by
    have hf : Function.update (Fin.insertNth j 0 z : WM.X (k+1)) j = (fun r : ℝ => (Fin.insertNth j r z : WM.X (k+1))) := by
      funext r
      simp only [Fin.update_insertNth]
    rw [← hf]
    exact hasDerivAt_update _ _ _
  have hder (z : WM.X k) (y : ℝ) :
      HasDerivAt (fun r => WM.flux u j (Fin.insertNth j r z,t))
        (WM.divFlux u j (Fin.insertNth j y z,t)) y := by
    exact (hg.differentiable (by simp) |>.differentiableAt.hasFDerivAt).comp_hasDerivAt y (hins z y)
  have hslice (z : WM.X k) : (∫ y in Set.Icc (-R) R, WM.divFlux u j (Fin.insertNth j y z,t)) = 0 := by
    have hcins : Continuous (fun y : ℝ => (Fin.insertNth j y z : WM.X (k+1))) := continuous_iff_continuousAt.mpr (fun y => (hins z y).continuousAt)
    have hc := hdcont.comp hcins
    have hs : HasCompactSupport (fun y => WM.divFlux u j (Fin.insertNth j y z,t)) := by
      apply HasCompactSupport.of_support_subset_isCompact isCompact_Icc
      intro y hy
      by_contra hyout
      apply hy
      apply hdzero
      intro hin
      have hi := hsub hin j
      simp only [Fin.insertNth_apply_same] at hi
      exact hyout ⟨hi.1.le, hi.2.le⟩
    have he (y : ℝ) (hy : y = -R ∨ y = R) : WM.flux u j (Fin.insertNth j y z,t) = 0 := by
      apply hgzero
      intro hin
      have hi := hsub hin j
      simp only [Fin.insertNth_apply_same] at hi
      rcases hy with rfl | rfl <;> linarith [hi.1, hi.2]
    rw [MeasureTheory.integral_Icc_eq_integral_Ioc, ← intervalIntegral.integral_of_le (by linarith : -R ≤ R)]
    rw [intervalIntegral.integral_eq_sub_of_hasDerivAt (fun y _ => hder z y) ((hc.integrable_of_hasCompactSupport hs).intervalIntegrable)]
    rw [he R (Or.inr rfl), he (-R) (Or.inl rfl), sub_self]
  have hQ : (∫ x in WM.box (k+1) R, WM.divFlux u j (x,t)) = 0 := by
    rw [(h_T010 k j R hR).2.2 _ hdcont]
    simp_rw [hslice]
    simp
  rw [← MeasureTheory.setIntegral_eq_integral_of_forall_compl_eq_zero (s := WM.box (k+1) R) (fun x hx => hdzero x (fun hc => hx (fun i => ⟨(hsub hc i).1.le, (hsub hc i).2.le⟩)))]
  exact hQ

theorem T012 (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_T009 : ∀ (t : ℝ), 0 < t → ∀ j : Fin n, ∃ (C : Set (WM.X n)) (R : ℝ), WM.fluxData u q t j C R) (h_T011 : ∀ (t : ℝ), 0 < t → ∀ j : Fin n, (∫ x, WM.divFlux u j (x,t)) = 0) :
    ∀ (t : ℝ), 0 < t → ∀ j : Fin n, Integrable (fun x => WM.bTerm u j (x,t)) ∧ Integrable (fun x => WM.cTerm u j (x,t)) ∧ (∫ x, WM.bTerm u j (x,t)) = -(∫ x, WM.cTerm u j (x,t)) := by
  intro t ht j
  obtain ⟨C, R, hdata⟩ := h_T009 t ht j
  rcases hdata with ⟨hlocal, hsmooth, hgood, hprod⟩
  have htI : t ∈ Set.Ioo (t / 2) (3 * t / 2) := by constructor <;> linarith
  have hsections := hlocal.2.2.2.2.2 t htI
  have hb : Integrable (fun x => WM.bTerm u j (x,t)) := (hsections.2.2.2 j).1.2.2.2
  have hc : Integrable (fun x => WM.cTerm u j (x,t)) := (hsections.2.2.2 j).2.1.2.2.2
  refine ⟨hb, hc, ?_⟩
  have heq : (∫ x, WM.divFlux u j (x,t)) = (∫ x, WM.bTerm u j (x,t)) + (∫ x, WM.cTerm u j (x,t)) := by
    simp_rw [hprod]
    exact integral_add hb hc
  have hz := h_T011 t ht j
  linarith

theorem T013 (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_T001 : ∀ (x : WM.X n) (t : ℝ), 0 < t → inner ℝ (u (x,t)) (WM.ut u (x,t)) = 0 ∧ inner ℝ (WM.ut u (x,t)) (WM.utt u (x,t) - WM.lap u x t) = 0) (h_T004 : WM.supportAndRegularity u q) (h_T008 : ∀ t : ℝ, 0 < t → DifferentiableAt ℝ (WM.energy u) t ∧ deriv (WM.energy u) t = ∫ x, WM.et u (x,t)) (h_T012 : ∀ (t : ℝ), 0 < t → ∀ j : Fin n, Integrable (fun x => WM.bTerm u j (x,t)) ∧ Integrable (fun x => WM.cTerm u j (x,t)) ∧ (∫ x, WM.bTerm u j (x,t)) = -(∫ x, WM.cTerm u j (x,t))) :
    ∀ t : ℝ, 0 < t → Integrable (fun x => WM.e u (x,t)) ∧ HasDerivAt (WM.energy u) 0 t ∧ deriv (WM.energy u) t = 0 := by
  intro t ht
  rcases h_T004 with ⟨hreg, he, hlocal⟩
  rcases hreg with ⟨hut, hutt, hxu, hec, hetc, hformula, hmix⟩
  rcases hlocal t ht with ⟨C, R, hgeom, hbox, hvol, hfinite, hvan, hgood⟩
  have htime : t ∈ Set.Ioo (t / 2) (3 * t / 2) := ⟨by linarith, by linarith⟩
  have ha : Integrable (fun x => WM.aTerm u (x,t)) := (hgood t htime).2.2.1.2.2.2
  have hb : ∀ j : Fin n, Integrable (fun x => WM.bTerm u j (x,t)) := fun j => (h_T012 t ht j).1
  have hc : ∀ j : Fin n, Integrable (fun x => WM.cTerm u j (x,t)) := fun j => (h_T012 t ht j).2.1
  have hbs := integrable_finsetSum Finset.univ (fun j _ => hb j)
  have hcs := integrable_finsetSum Finset.univ (fun j _ => hc j)
  have hz : (∫ x, WM.aTerm u (x,t)) - ∑ j, (∫ x, WM.cTerm u j (x,t)) = 0 := by
    rw [← integral_finsetSum Finset.univ (fun j _ => hc j), ← integral_sub ha hcs]
    have hp : (fun x => WM.aTerm u (x,t) - ∑ j, WM.cTerm u j (x,t)) = (fun _ : WM.X n => (0 : ℝ)) := by
      funext x
      have h := (h_T001 x t ht).2
      simpa [WM.aTerm, WM.cTerm, WM.lap, inner_sub_right, inner_sum] using h
    rw [hp]
    simp
  have hd : deriv (WM.energy u) t = 0 := by
    rw [(h_T008 t ht).2]
    calc
      (∫ x, WM.et u (x,t)) = ∫ x, (2 * WM.aTerm u (x,t) + 2 * ∑ j, WM.bTerm u j (x,t)) := by
        apply integral_congr_ae
        exact Filter.Eventually.of_forall (fun x => hformula x t ht)
      _ = 2 * (∫ x, WM.aTerm u (x,t)) + 2 * ∑ j, (∫ x, WM.bTerm u j (x,t)) := by
        rw [integral_add (ha.const_mul 2) (hbs.const_mul 2), integral_const_mul, integral_const_mul, integral_finsetSum Finset.univ (fun j _ => hb j)]
      _ = 2 * (∫ x, WM.aTerm u (x,t)) - 2 * ∑ j, (∫ x, WM.cTerm u j (x,t)) := by
        simp_rw [(h_T012 t ht _).2.2]
        rw [Finset.sum_neg_distrib]
        ring
      _ = 0 := by linarith
  refine ⟨he t ht, ?_, hd⟩
  simpa only [hd] using (h_T008 t ht).1.hasDerivAt

theorem T014 (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_T013 : ∀ t : ℝ, 0 < t → Integrable (fun x => WM.e u (x,t)) ∧ HasDerivAt (WM.energy u) 0 t ∧ deriv (WM.energy u) t = 0) :
    (∀ t : ℝ, 0 < t → Integrable (fun x => WM.e u (x,t))) ∧ DifferentiableOn ℝ (WM.energy u) (Set.Ioi 0) ∧ (∀ t : ℝ, 0 < t → deriv (WM.energy u) t = 0) ∧ (∀ s t : ℝ, 0 < s → 0 < t → WM.energy u s = WM.energy u t) := by
  refine ⟨(fun t ht => (h_T013 t ht).1), ?_, (fun t ht => (h_T013 t ht).2.2), ?_⟩
  · intro t ht
    exact (h_T013 t ht).2.1.differentiableAt.differentiableWithinAt
  · have ordered : ∀ s t : ℝ, 0 < s → s < t → WM.energy u s = WM.energy u t := by
      intro s t hs hst
      have hd : ∀ r ∈ Set.Icc s t,
          HasDerivWithinAt (WM.energy u) (0 : ℝ) (Set.Icc s t) r := by
        intro r hr
        exact (h_T013 r (lt_of_lt_of_le hs hr.1)).2.1.hasDerivWithinAt
      have hb : ∀ r ∈ Set.Ico s t, ‖(0 : ℝ)‖ ≤ (0 : ℝ) := by
        intros
        simp
      have h := norm_image_sub_le_of_norm_deriv_le_segment' hd hb t
        (show t ∈ Set.Icc s t from ⟨le_of_lt hst, le_rfl⟩)
      have hz : WM.energy u t - WM.energy u s = 0 :=
        norm_eq_zero.mp (le_antisymm (by simpa using h) (norm_nonneg _))
      exact (sub_eq_zero.mp hz).symm
    intro s t hs ht
    rcases lt_trichotomy s t with hst | hst | hts
    · exact ordered s t hs hst
    · rw [hst]
    · exact (ordered t s ht hts).symm

set_option Elab.async false in
theorem P (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_H001 : 1 ≤ n ∧ 1 ≤ m) (h_H002 : ContDiffOn ℝ ∞ u (WM.dom n)) (h_H003 : ‖q‖ = 1) (h_H004 : ∀ (x : WM.X n) (t : ℝ), 0 < t → ‖u (x,t)‖ = 1) (h_H005 : ∀ (x : WM.X n) (t : ℝ), 0 < t → ∃ a : ℝ, WM.utt u (x,t) - WM.lap u x t = a • u (x,t)) (h_H006 : ∀ (s t : ℝ), 0 < s → s < t → ∃ C : Set (WM.X n), IsCompact C ∧ ∀ x, x ∉ C → ∀ r ∈ Set.Icc s t, u (x,r) = q) :
    (∀ t : ℝ, 0 < t → Integrable (fun x => WM.e u (x,t))) ∧ DifferentiableOn ℝ (WM.energy u) (Set.Ioi 0) ∧ (∀ t : ℝ, 0 < t → deriv (WM.energy u) t = 0) ∧ (∀ s t : ℝ, 0 < s → 0 < t → WM.energy u s = WM.energy u t) := by
  have h_T001 : ∀ (x : WM.X n) (t : ℝ), 0 < t → inner ℝ (u (x,t)) (WM.ut u (x,t)) = 0 ∧ inner ℝ (WM.ut u (x,t)) (WM.utt u (x,t) - WM.lap u x t) = 0 := @T001 n m u q h_H002 h_H004 h_H005
  have h_T002 : WM.regular u := @T002 n m u q h_H002
  have h_T003 : ∀ τ : ℝ, 0 < τ → ∃ (C : Set (WM.X n)) (R : ℝ), WM.geometry u q τ C R := @T003 n m u q h_H006
  have h_T004 : WM.supportAndRegularity u q := @T004 n m u q h_H001 h_H002 h_T002 h_T003
  have h_T005 : ∀ t : ℝ, 0 < t → ∃ (C : Set (WM.X n)) (R B : ℝ), WM.localData u q t C R ∧ 0 ≤ B ∧ ∀ x ∈ WM.box n R, ∀ r ∈ Set.Icc (t-t/4) (t+t/4), |WM.et u (x,r)| ≤ B := @T005 n m u q h_T004
  have h_T006 : ∀ (t : ℝ), 0 < t → ∀ (C : Set (WM.X n)) (R B : ℝ), WM.localData u q t C R → 0 ≤ B → (∀ x ∈ WM.box n R, ∀ r ∈ Set.Icc (t-t/4) (t+t/4), |WM.et u (x,r)| ≤ B) → ((∀ h : ℝ, 0 < |h| → |h| < t/4 → Integrable (WM.quot u t h) ∧ AEStronglyMeasurable (WM.quot u t h) ∧ ∀ x, |WM.quot u t h x| ≤ WM.major R B x) ∧ (∀ x, Filter.Tendsto (fun h => WM.quot u t h x) (nhdsWithin 0 ({0}ᶜ)) (nhds (WM.et u (x,t))))) := @T006 n m u q h_T004
  have h_T007 : ∀ t : ℝ, 0 < t → Filter.Tendsto (fun h => ∫ x, WM.quot u t h x) (nhdsWithin 0 ({0}ᶜ)) (nhds (∫ x, WM.et u (x,t))) := @T007 n m u q h_T004 h_T005 h_T006
  have h_T008 : ∀ t : ℝ, 0 < t → DifferentiableAt ℝ (WM.energy u) t ∧ deriv (WM.energy u) t = ∫ x, WM.et u (x,t) := @T008 n m u q h_T004 h_T007
  have h_T009 : ∀ (t : ℝ), 0 < t → ∀ j : Fin n, ∃ (C : Set (WM.X n)) (R : ℝ), WM.fluxData u q t j C R := @T009 n m u q h_H001 h_H002 h_T004
  have h_T010 : ∀ (k : ℕ) (j : Fin (k+1)) (R : ℝ), 0 < R → MeasurePreserving (fun p : ℝ × WM.X k => (Fin.insertNth j p.1 p.2 : WM.X (k+1))) volume volume ∧ (Set.image (fun p : ℝ × WM.X k => (Fin.insertNth j p.1 p.2 : WM.X (k+1))) (Set.Icc (-R) R ×ˢ WM.box k R) = WM.box (k+1) R) ∧ (∀ d : WM.X (k+1) → ℝ, Continuous d → (∫ x in WM.box (k+1) R, d x) = ∫ z in WM.box k R, ∫ y in Set.Icc (-R) R, d (Fin.insertNth j y z)) := @T010 n m u q 
  have h_T011 : ∀ (t : ℝ), 0 < t → ∀ j : Fin n, (∫ x, WM.divFlux u j (x,t)) = 0 := @T011 n m u q h_H001 h_T009 h_T010
  have h_T012 : ∀ (t : ℝ), 0 < t → ∀ j : Fin n, Integrable (fun x => WM.bTerm u j (x,t)) ∧ Integrable (fun x => WM.cTerm u j (x,t)) ∧ (∫ x, WM.bTerm u j (x,t)) = -(∫ x, WM.cTerm u j (x,t)) := @T012 n m u q h_T009 h_T011
  have h_T013 : ∀ t : ℝ, 0 < t → Integrable (fun x => WM.e u (x,t)) ∧ HasDerivAt (WM.energy u) 0 t ∧ deriv (WM.energy u) t = 0 := @T013 n m u q h_T001 h_T004 h_T008 h_T012
  have h_T014 : (∀ t : ℝ, 0 < t → Integrable (fun x => WM.e u (x,t))) ∧ DifferentiableOn ℝ (WM.energy u) (Set.Ioi 0) ∧ (∀ t : ℝ, 0 < t → deriv (WM.energy u) t = 0) ∧ (∀ s t : ℝ, 0 < s → 0 < t → WM.energy u s = WM.energy u t) := @T014 n m u q h_T013
  exact h_T014

#check @P
#print axioms P

end Translation
