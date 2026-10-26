import Mathlib
open scoped ENNReal NNReal
abbrev V (n : ℕ) := EuclideanSpace ℝ (Fin n)
abbrev W (n : ℕ) := EuclideanSpace ℝ (Fin n ⊕ Unit)
noncomputable def pack (n : ℕ) (x : V n) (t : ℝ) : W n := WithLp.toLp 2 (Sum.elim (fun i => x i) (fun _ => t))
noncomputable def projX (n : ℕ) (z : W n) : V n := WithLp.toLp 2 (fun i => z (Sum.inl i))
noncomputable def projT (n : ℕ) (z : W n) : ℝ := z (Sum.inr ())
def unitI : Set ℝ := Set.Icc 0 1
def cyl (n : ℕ) (E : Set (V n)) : Set (W n) := {z | projX n z ∈ E ∧ projT n z ∈ unitI}
noncomputable def coverCost {X : Type*} [MetricSpace X] (s : ℝ) (U : ℕ → Set X) : ℝ≥0∞ := ∑' i, ⨆ (_ : (U i).Nonempty), (Metric.ediam (U i)) ^ s
def IsCover {X : Type*} [MetricSpace X] (δ : ℝ) (A : Set X) (U : ℕ → Set X) : Prop := A ⊆ ⋃ i, U i ∧ ∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ
noncomputable def Hscale {X : Type*} [MetricSpace X] (s δ : ℝ) (A : Set X) : ℝ≥0∞ := ⨅ (U : ℕ → Set X) (_ : IsCover δ A U), coverCost s U
noncomputable def Hmeasure {X : Type*} [MetricSpace X] (s : ℝ) (A : Set X) : ℝ≥0∞ := ⨆ (δ : ℝ) (_ : 0 < δ), Hscale s δ A
noncomputable def Hnative {X : Type*} [MetricSpace X] (s : ℝ) (A : Set X) : ℝ≥0∞ := letI : MeasurableSpace X := borel X; letI : BorelSpace X := ⟨rfl⟩; MeasureTheory.Measure.hausdorffMeasure s A

namespace Translation
set_option autoImplicit false

theorem T001 (n : ℕ) (E : Set (V n))  :
    ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A := by
  intro X inst A s hs
  letI : MeasurableSpace X := borel X
  letI : BorelSpace X := ⟨rfl⟩
  let F : ℝ≥0∞ → ℝ≥0∞ := fun r =>
    ⨅ (U : ℕ → Set X) (_ : A ⊆ ⋃ i, U i) (_ : ∀ i, Metric.ediam (U i) ≤ r), coverCost s U
  have hscale (δ : ℝ) : Hscale s δ A = F (ENNReal.ofReal δ) := by
    apply le_antisymm
    · refine le_iInf fun U => le_iInf fun hA => le_iInf fun hd => ?_
      exact iInf_le_of_le U (iInf_le_of_le ⟨hA, hd⟩ le_rfl)
    · refine le_iInf fun U => le_iInf fun hU => ?_
      exact iInf_le_of_le U (iInf_le_of_le hU.1 (iInf_le_of_le hU.2 le_rfl))
  have hmono : Antitone F := by
    intro r q hrq
    refine le_iInf fun U => le_iInf fun hA => le_iInf fun hd => ?_
    exact iInf_le_of_le U (iInf_le_of_le hA (iInf_le_of_le (fun i => (hd i).trans hrq) le_rfl))
  change Hmeasure s A = MeasureTheory.Measure.hausdorffMeasure s A
  rw [MeasureTheory.Measure.hausdorffMeasure_apply]
  change Hmeasure s A = ⨆ (r : ℝ≥0∞) (_ : 0 < r), F r
  apply le_antisymm
  · refine iSup_le fun δ => iSup_le fun hδ => ?_
    rw [hscale]
    exact le_iSup_of_le (ENNReal.ofReal δ) (le_iSup_of_le (ENNReal.ofReal_pos.mpr hδ) le_rfl)
  · refine iSup_le fun r => iSup_le fun hr => ?_
    by_cases htop : r = ∞
    · subst r
      calc
        F ∞ ≤ F (ENNReal.ofReal 1) := hmono le_top
        _ = Hscale s 1 A := (hscale 1).symm
        _ ≤ Hmeasure s A := le_iSup_of_le 1 (le_iSup_of_le (by norm_num : (0 : ℝ) < 1) le_rfl)
    · have hpos : 0 < r.toReal := ENNReal.toReal_pos_iff.mpr ⟨hr, lt_top_iff_ne_top.mpr htop⟩
      have heq : ENNReal.ofReal r.toReal = r := ENNReal.ofReal_toReal htop
      calc
        F r = Hscale s r.toReal A := by rw [hscale, heq]
        _ ≤ Hmeasure s A := le_iSup_of_le r.toReal (le_iSup_of_le hpos le_rfl)

theorem T002 (n : ℕ) (E : Set (V n)) (h_T001 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A) :
    ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A) := by
  intro X inst A s hs
  letI : MeasurableSpace X := borel X
  letI : BorelSpace X := ⟨rfl⟩
  -- Re-establish the bridge at the target universe, since the premise's
  -- universe is independent of the universe of X.
  have hbridge : Hmeasure s A = Hnative s A := by
    change Hmeasure s A = MeasureTheory.Measure.hausdorffMeasure s A
    rw [MeasureTheory.Measure.hausdorffMeasure_apply]
    apply le_antisymm
    · unfold Hmeasure
      refine iSup₂_le fun δ hδ => ?_
      refine le_iSup₂_of_le (ENNReal.ofReal δ) (ENNReal.ofReal_pos.mpr hδ) ?_
      unfold Hscale IsCover coverCost
      simp only [iInf_and]
      rfl
    · refine iSup₂_le fun r hr => ?_
      obtain ⟨q, hq, hqr⟩ := ENNReal.lt_iff_exists_nnreal_btwn.mp hr
      have hqR : 0 < (q : ℝ) := by exact_mod_cast (ENNReal.coe_pos.mp hq)
      refine le_iSup₂_of_le (q : ℝ) hqR ?_
      unfold Hscale IsCover coverCost
      refine le_iInf fun U => le_iInf fun hU => ?_
      refine iInf_le_of_le U (iInf_le_of_le hU.1 (iInf_le_of_le ?_ le_rfl))
      intro i
      exact (hU.2 i).trans ((ENNReal.coe_nnreal_eq q).symm.trans_le hqr.le)
  let d : NNReal := ⟨s, hs.le⟩
  have hd : (d : ENNReal) = ENNReal.ofReal s := ENNReal.coe_nnreal_eq d
  have htrans : Hmeasure s A = MeasureTheory.Measure.hausdorffMeasure (d : ℝ) A := hbridge
  refine ⟨hbridge, ?_, ?_, ?_, ?_⟩
  · intro h
    rw [htrans]
    exact hausdorffMeasure_of_dimH_lt (s := A) (d := d) (hd.symm ▸ h)
  · intro h
    rw [htrans]
    exact hausdorffMeasure_of_lt_dimH (s := A) (d := d) (hd.symm ▸ h)
  · intro h
    have hz : MeasureTheory.Measure.hausdorffMeasure (d : ℝ) A = 0 := htrans.symm.trans h
    rw [← hd]
    exact dimH_le_of_hausdorffMeasure_ne_top (s := A) (d := d) (by simp [hz])
  · intro h
    have ht : MeasureTheory.Measure.hausdorffMeasure (d : ℝ) A = ⊤ := htrans.symm.trans h
    rw [← hd]
    exact le_dimH_of_hausdorffMeasure_eq_top (s := A) (d := d) ht

theorem T003 (n : ℕ) (E : Set (V n)) (h_H002 : IsCompact E) :
    Bornology.IsBounded E ∧ (∃ B : ℝ, 1 ≤ B ∧ ∀ x ∈ E, ‖x‖ ≤ B) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) := by
  classical
  have hc : E ⊆ ⋃ m : ℕ, Metric.ball (0 : V n) (m + 1 : ℝ) := by
    intro x hx
    obtain ⟨m, hm⟩ := exists_nat_gt ‖x‖
    exact Set.mem_iUnion.mpr ⟨m, by simpa only [Metric.mem_ball, dist_zero_right] using (show ‖x‖ < (m + 1 : ℝ) by exact lt_trans hm (by linarith))⟩
  obtain ⟨t, ht⟩ := h_H002.elim_finite_subcover (fun m : ℕ => Metric.ball (0 : V n) (m + 1 : ℝ)) (fun _ => Metric.isOpen_ball) hc
  have hnorm : ∀ x ∈ E, ‖x‖ ≤ ∑ m ∈ t, (m + 1 : ℝ) := by
    intro x hx
    obtain ⟨m, hmt, hxm⟩ := Set.mem_iUnion₂.mp (ht hx)
    have hm : ‖x‖ < (m + 1 : ℝ) := by simpa using hxm
    exact hm.le.trans (Finset.single_le_sum (f := fun j : ℕ => (j + 1 : ℝ)) (fun j hj => by positivity) hmt)
  have hb : Bornology.IsBounded E := isBounded_iff_forall_norm_le.mpr ⟨_, hnorm⟩
  have hB : ∃ B : ℝ, 1 ≤ B ∧ ∀ x ∈ E, ‖x‖ ≤ B := by
    have hbounded : BddAbove ((fun x : V n => ‖x‖) '' E) := by
      refine ⟨∑ m ∈ t, (m + 1 : ℝ), ?_⟩
      rintro y ⟨x, hx, rfl⟩
      exact hnorm x hx
    refine ⟨max 1 (sSup ((fun x : V n => ‖x‖) '' E)), le_max_left _ _, ?_⟩
    intro x hx
    exact (le_csSup hbounded ⟨x, hx, rfl⟩).trans (le_max_right _ _)
  have hfinite : ∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤ := by
    intro s δ hs hδ
    have hc : E ⊆ ⋃ x : E, Metric.ball (x : V n) (δ / 2) := by
      intro x hx
      exact Set.mem_iUnion.mpr ⟨⟨x, hx⟩, Metric.mem_ball_self (half_pos hδ)⟩
    obtain ⟨t, ht⟩ := h_H002.elim_finite_subcover (fun x : E => Metric.ball (x : V n) (δ / 2)) (fun _ => Metric.isOpen_ball) hc
    let e := Fintype.equivFin t
    let U : Fin (Fintype.card t) → Set (V n) := fun i => Metric.ball ((e.symm i).val : V n) (δ / 2)
    have hcov : E ⊆ ⋃ i, U i := by
      intro x hx
      obtain ⟨y, hyt, hxy⟩ := Set.mem_iUnion₂.mp (ht hx)
      refine Set.mem_iUnion.mpr ⟨e ⟨y, hyt⟩, ?_⟩
      simpa [U] using hxy
    have hd : ∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ := by
      intro i
      apply Metric.ediam_le_of_forall_dist_le
      intro x hx y hy
      have hx' : dist x ((e.symm i).val : V n) < δ / 2 := hx
      have hy' : dist y ((e.symm i).val : V n) < δ / 2 := hy
      have ht := dist_triangle x ((e.symm i).val : V n) y
      rw [dist_comm ((e.symm i).val : V n) y] at ht
      linarith
    refine ⟨Fintype.card t, U, hcov, hd, ?_⟩
    apply ENNReal.sum_lt_top.mpr
    intro i hi
    exact ENNReal.rpow_lt_top_of_nonneg hs.le (ne_of_lt ((hd i).trans_lt ENNReal.ofReal_lt_top))
  refine ⟨hb, hB, hfinite, ?_⟩
  intro s δ hs hδ
  obtain ⟨k, U, hcov, hd, hsum⟩ := hfinite s δ hs hδ
  let P : ℕ → Set (V n) := fun j => if h : j < k then U ⟨j,h⟩ else ∅
  have hp : IsCover δ E P := by
    constructor
    · intro x hx
      obtain ⟨i, hi⟩ := Set.mem_iUnion.mp (hcov hx)
      refine Set.mem_iUnion.mpr ⟨i.val, ?_⟩
      simpa [P, i.isLt] using hi
    · intro j
      by_cases hj : j < k
      · simpa [P, hj] using hd ⟨j,hj⟩
      · simp [P, hj]
  have hc : coverCost s P < ⊤ := by
    unfold coverCost
    rw [tsum_eq_sum (s := Finset.range k)]
    · apply ENNReal.sum_lt_top.mpr
      intro j hj
      have hj' : j < k := Finset.mem_range.mp hj
      have hdj : Metric.ediam (P j) < ⊤ := by
        simpa [P, hj'] using (hd ⟨j,hj'⟩).trans_lt ENNReal.ofReal_lt_top
      exact lt_of_le_of_lt (iSup_le fun _ => le_rfl) (ENNReal.rpow_lt_top_of_nonneg hs.le hdj.ne)
    · intro j hj
      have hj' : ¬ j < k := by simpa using hj
      simp [P, hj']
  exact lt_of_le_of_lt (iInf_le_of_le P (iInf_le_of_le hp le_rfl)) hc

theorem T004 (n : ℕ) (E : Set (V n)) (h_T003 : Bornology.IsBounded E ∧ (∃ B : ℝ, 1 ≤ B ∧ ∀ x ∈ E, ‖x‖ ≤ B) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤)) :
    0 < n → ∀ a : ℝ, (n : ℝ) < a → (∀ δ : ℝ, 0 < δ → Hscale a δ E = 0) ∧ Hmeasure a E = 0 := by
  classical
  intro hn a ha
  have ha0 : 0 ≤ a := (Nat.cast_nonneg n).trans ha.le
  obtain ⟨B, hB, hE⟩ := h_T003.2.1
  have grid : ∀ k : ℕ, 0 < k → ∃ U : (Fin n → Fin k) → Set (V n), E ⊆ ⋃ i, U i ∧ ∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal (Real.sqrt n * (2 * (B + 1) / k)) := by
    intro k hk
    let h : ℝ := 2 * (B + 1) / k
    have hk' : (0 : ℝ) < k := by exact_mod_cast hk
    have hh : 0 < h := div_pos (by linarith) hk'
    have hhk : h * k = 2 * (B + 1) := by dsimp [h]; field_simp
    let U : (Fin n → Fin k) → Set (V n) := fun j => {x | ∀ i, -(B+1) + (j i : ℕ) * h ≤ x i ∧ x i ≤ -(B+1) + ((j i : ℕ) + 1) * h}
    refine ⟨U, ?_, ?_⟩
    · intro x hx
      have hb : ∀ i, |x i| ≤ B := fun i => (PiLp.norm_apply_le x i).trans (hE x hx)
      have hr : ∀ i, 0 ≤ (x i + (B+1)) / h ∧ (x i + (B+1)) / h < k := by
        intro i
        have hi := abs_le.mp (hb i)
        constructor
        · exact div_nonneg (by linarith) hh.le
        · apply (div_lt_iff₀ hh).2
          nlinarith [hhk]
      let j : Fin n → Fin k := fun i => ⟨⌊(x i + (B+1)) / h⌋₊, (Nat.floor_lt (hr i).1).2 (hr i).2⟩
      apply Set.mem_iUnion.mpr
      refine ⟨j, ?_⟩
      intro i
      have hlo := (le_div_iff₀ hh).mp (Nat.floor_le (hr i).1)
      have hhi := (div_lt_iff₀ hh).mp (Nat.lt_floor_add_one ((x i + (B+1)) / h))
      change -(B+1) + (⌊(x i + (B+1)) / h⌋₊ : ℝ) * h ≤ x i ∧ x i ≤ -(B+1) + ((⌊(x i + (B+1)) / h⌋₊ : ℝ) + 1) * h
      constructor <;> linarith
    · intro j
      apply Metric.ediam_le_iff.mpr
      intro x hx y hy
      have hd : ∀ i, dist (x i) (y i) ≤ h := by
        intro i
        have hxi := hx i
        have hyi := hy i
        rw [Real.dist_eq, abs_le]
        constructor <;> linarith
      have hs : ∑ i : Fin n, dist (x i) (y i) ^ 2 ≤ (n : ℝ) * h ^ 2 := by
        calc
          _ ≤ ∑ _i : Fin n, h ^ 2 := Finset.sum_le_sum fun i _ => pow_le_pow_left₀ (dist_nonneg) (hd i) 2
          _ = _ := by simp
      have hdist : dist x y ≤ Real.sqrt n * h := by
        rw [EuclideanSpace.dist_eq]
        calc
          _ ≤ Real.sqrt ((n : ℝ) * h ^ 2) := Real.sqrt_le_sqrt hs
          _ = _ := by rw [Real.sqrt_mul (Nat.cast_nonneg n), Real.sqrt_sq hh.le]
      rw [edist_dist]
      exact ENNReal.ofReal_le_ofReal hdist
  have finite_bound : ∀ (δ d : ℝ), d ≤ δ → ∀ {ι : Type} [Fintype ι] (U : ι → Set (V n)), E ⊆ ⋃ i, U i → (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal d) → Hscale a δ E ≤ (Fintype.card ι : ℝ≥0∞) * (ENNReal.ofReal d) ^ a := by
    intro δ d hd ι _ U hU hdiam
    let c := Fintype.card ι
    let e : Fin c ≃ ι := (Fintype.equivFin ι).symm
    let T : ℕ → Set (V n) := fun i => if hi : i < c then U (e ⟨i, hi⟩) else ∅
    have hcov : IsCover δ E T := by
      constructor
      · intro x hx
        obtain ⟨i, hi⟩ := Set.mem_iUnion.mp (hU hx)
        refine Set.mem_iUnion.mpr ⟨(e.symm i).val, ?_⟩
        simp only [T, dif_pos (e.symm i).isLt, Fin.eta, Equiv.apply_symm_apply]
        exact hi
      · intro i
        dsimp [T]
        split_ifs with hi
        · exact (hdiam _).trans (ENNReal.ofReal_le_ofReal hd)
        · simp
    have hcost : coverCost a T ≤ (c : ℝ≥0∞) * (ENNReal.ofReal d) ^ a := by
      unfold coverCost
      rw [tsum_eq_sum (s := Finset.range c) (fun i hi => ?_)]
      · calc
          _ ≤ ∑ _i ∈ Finset.range c, (ENNReal.ofReal d) ^ a := by
            apply Finset.sum_le_sum
            intro i hi
            have hi' : i < c := Finset.mem_range.mp hi
            dsimp [T]
            rw [dif_pos hi']
            apply iSup_le
            intro _
            exact ENNReal.rpow_le_rpow (hdiam (e ⟨i, hi'⟩)) ha0
          _ = _ := by simp
      · have hi' : ¬ i < c := by simpa using hi
        simp [T, hi']
    have hle : Hscale a δ E ≤ coverCost a T := by
      unfold Hscale
      exact iInf_le_of_le T (iInf_le_of_le hcov le_rfl)
    exact hle.trans hcost
  let K : ℝ := Real.sqrt n * (2 * (B + 1))
  have hK : 0 ≤ K := mul_nonneg (Real.sqrt_nonneg _) (by linarith)
  have cost_id : ∀ k : ℕ, 0 < k → (k : ℝ≥0∞)^n * (ENNReal.ofReal (K / k))^a = ENNReal.ofReal (K^a * ((k : ℝ)⁻¹)^(a-n)) := by
    intro k hk
    have hk' : (0 : ℝ) < k := by exact_mod_cast hk
    have hid : (k : ℝ)^n * (K / k)^a = K^a * ((k : ℝ)⁻¹)^(a-n) := by
      rw [Real.div_rpow hK hk'.le, Real.inv_rpow hk'.le, Real.rpow_sub hk', Real.rpow_natCast]
      field_simp
    have hc : ENNReal.ofReal ((k : ℝ)^n) = (k : ℝ≥0∞)^n := by rw [ENNReal.ofReal_pow hk'.le]; simp
    rw [← hc, ENNReal.ofReal_rpow_of_nonneg (div_nonneg hK hk'.le) ha0, ← ENNReal.ofReal_mul (pow_nonneg hk'.le n), hid]
  have hi : Filter.Tendsto (fun k : ℕ => ((k : ℝ)⁻¹)) Filter.atTop (nhds 0) := tendsto_inv_atTop_zero.comp tendsto_natCast_atTop_atTop
  have hp : Filter.Tendsto (fun k : ℕ => ((k : ℝ)⁻¹)^(a-n)) Filter.atTop (nhds 0) := by
    have ht := ((Real.continuous_rpow_const (sub_pos.mpr ha).le).tendsto 0).comp hi
    simpa only [Function.comp_def, Real.zero_rpow (sub_pos.mpr ha).ne'] using ht
  have hc : Filter.Tendsto (fun k : ℕ => ENNReal.ofReal (K^a * ((k : ℝ)⁻¹)^(a-n))) Filter.atTop (nhds 0) := by
    simpa using ENNReal.tendsto_ofReal (hp.const_mul (K^a))
  have hd : Filter.Tendsto (fun k : ℕ => K / (k : ℝ)) Filter.atTop (nhds 0) := by
    simpa [div_eq_mul_inv] using hi.const_mul K
  have hz : ∀ δ : ℝ, 0 < δ → Hscale a δ E = 0 := by
    intro δ hδ
    apply le_antisymm _ bot_le
    apply ge_of_tendsto hc
    have hev : ∀ᶠ k : ℕ in Filter.atTop, K / (k : ℝ) < δ := hd.eventually (gt_mem_nhds hδ)
    have hkpos : ∀ᶠ k : ℕ in Filter.atTop, 0 < k := Filter.eventually_atTop.2 ⟨1, fun k hk => hk⟩
    filter_upwards [hev, hkpos] with k hkd hk
    obtain ⟨U, hU, hdiam⟩ := grid k hk
    have hdiam' : ∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal (K / k) := by
      simpa only [K, mul_div_assoc] using hdiam
    have hb := finite_bound δ (K / k) hkd.le U hU hdiam'
    rw [Fintype.card_fun, Fintype.card_fin, Fintype.card_fin, Nat.cast_pow, cost_id k hk] at hb
    exact hb
  refine ⟨hz, ?_⟩
  unfold Hmeasure
  apply le_antisymm _ bot_le
  apply iSup_le
  intro δ
  apply iSup_le
  intro hδ
  rw [hz δ hδ]
  exact le_rfl

theorem T005 (n : ℕ) (E : Set (V n)) (h_H001 : E.Nonempty) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) (h_T003 : Bornology.IsBounded E ∧ (∃ B : ℝ, 1 ≤ B ∧ ∀ x ∈ E, ‖x‖ ≤ B) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤)) (h_T004 : 0 < n → ∀ a : ℝ, (n : ℝ) < a → (∀ δ : ℝ, 0 < δ → Hscale a δ E = 0) ∧ Hmeasure a E = 0) :
    Bornology.IsBounded E ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) ∧ 0 ≤ dimH E ∧ dimH E ≤ (n : ℝ≥0∞) ∧ dimH E < ⊤ ∧ (n = 0 → E = Set.univ ∧ dimH E = 0) := by
  have hzero_dim : ∀ s : ℝ, 0 < s → Hmeasure s E = 0 → dimH E ≤ ENNReal.ofReal s := by
    intro s hs hz
    let L := ULift (V n)
    let f : V n → L := ULift.up
    have hf : Isometry f := fun _ _ => rfl
    have hm : Hmeasure s (f '' E) ≤ Hmeasure s E := by
      apply iSup_le
      intro δ
      apply iSup_le
      intro hδ
      refine le_trans ?_ (le_iSup_of_le δ (le_iSup_of_le hδ le_rfl))
      change Hscale s δ (f '' E) ≤ Hscale s δ E
      apply le_iInf
      intro U
      apply le_iInf
      intro hU
      let U' : ℕ → Set L := fun i => f '' U i
      have hU' : IsCover δ (f '' E) U' := by
        constructor
        · rintro _ ⟨x, hx, rfl⟩
          obtain ⟨i, hi⟩ := Set.mem_iUnion.mp (hU.1 hx)
          exact Set.mem_iUnion.mpr ⟨i, ⟨x, hi, rfl⟩⟩
        · intro i
          simpa only [U', hf.ediam_image] using hU.2 i
      calc
        Hscale s δ (f '' E) ≤ coverCost s U' := iInf_le_of_le U' (iInf_le_of_le hU' le_rfl)
        _ = coverCost s U := by
          simp only [coverCost, U', Set.image_nonempty, hf.ediam_image]
    have hz' : Hmeasure s (f '' E) = 0 := le_antisymm (hm.trans_eq hz) bot_le
    have hd := (h_T002 L (f '' E) s hs).2.2.2.1 hz'
    have hi : AntilipschitzWith 1 f := hf.antilipschitz
    exact (hi.le_dimH_image E).trans hd
  have hz : n = 0 → E = Set.univ ∧ ∀ s : ℝ, 0 < s → Hmeasure s E = 0 := by
    intro hn
    subst n
    have hE : E = Set.univ := by
      apply Set.eq_univ_of_forall
      intro x
      obtain ⟨y, hy⟩ := h_H001
      simpa only [Subsingleton.elim x y] using hy
    refine ⟨hE, ?_⟩
    intro s hs
    have hd : Metric.ediam E = 0 := Metric.ediam_subsingleton (fun _ _ _ _ => Subsingleton.elim _ _)
    have hc : coverCost s (fun _ : ℕ => E) = 0 := by
      simp [coverCost, hd, ENNReal.zero_rpow_of_pos hs]
    apply le_antisymm _ bot_le
    change (⨆ δ : ℝ, ⨆ (_ : 0 < δ), Hscale s δ E) ≤ 0
    apply iSup_le
    intro δ
    apply iSup_le
    intro hδ
    have hcov : IsCover δ E (fun _ : ℕ => E) := by
      constructor
      · intro x hx
        exact Set.mem_iUnion.mpr ⟨0, hx⟩
      · intro i
        rw [hd]
        exact bot_le
    calc
      Hscale s δ E ≤ coverCost s (fun _ : ℕ => E) := iInf_le_of_le (fun _ : ℕ => E) (iInf_le_of_le hcov le_rfl)
      _ = 0 := hc
  have ha : ∀ a : ℝ, (n : ℝ) < a → dimH E ≤ ENNReal.ofReal a := by
    intro a hna
    have hapos : 0 < a := lt_of_le_of_lt (Nat.cast_nonneg n) hna
    apply hzero_dim a hapos
    by_cases hn : n = 0
    · exact (hz hn).2 a hapos
    · exact (h_T004 (Nat.pos_of_ne_zero hn) a hna).2
  have hb : dimH E ≤ (n : ℝ≥0∞) := by
    apply ENNReal.le_of_forall_pos_le_add
    intro ε hε _
    have hep : (0 : ℝ) < (ε : ℝ) := by exact_mod_cast hε
    have h := ha ((n : ℝ) + (ε : ℝ)) (by linarith)
    have heq : ENNReal.ofReal ((n : ℝ) + (ε : ℝ)) = (n : ℝ≥0∞) + (ε : ℝ≥0∞) := by
      rw [ENNReal.ofReal_add (Nat.cast_nonneg n) ε.coe_nonneg]
      simp
    rwa [heq] at h
  refine ⟨h_T003.1, h_T003.2.2.1, h_T003.2.2.2, bot_le, hb, ?_, ?_⟩
  · exact lt_of_le_of_lt hb (by simp)
  · intro hn
    refine ⟨(hz hn).1, ?_⟩
    apply le_antisymm _ bot_le
    change dimH E ≤ 0
    simpa [hn] using hb

theorem T006 (n : ℕ) (E : Set (V n)) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) (h_T005 : Bornology.IsBounded E ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) ∧ 0 ≤ dimH E ∧ dimH E ≤ (n : ℝ≥0∞) ∧ dimH E < ⊤ ∧ (n = 0 → E = Set.univ ∧ dimH E = 0)) :
    n = 0 → dimH (cyl n E) ≤ dimH E + 1 := by
  classical
  intro hn
  obtain ⟨hE, hD⟩ := h_T005.2.2.2.2.2.2 hn
  subst n
  rw [hD, zero_add, hE]
  have hcyl : cyl 0 (Set.univ : Set (V 0)) = (fun t : ℝ => pack 0 0 t) '' unitI := by
    ext z
    constructor
    · intro hz
      refine ⟨projT 0 z, hz.2, ?_⟩
      apply PiLp.ext
      intro i
      cases i with
      | inl i => exact Fin.elim0 i
      | inr u => cases u; rfl
    · rintro ⟨t, ht, rfl⟩
      exact ⟨Set.mem_univ _, ht⟩
  rw [hcyl]
  have hp : Isometry (fun t : ℝ => pack 0 0 t) := by
    apply Isometry.of_dist_eq
    intro x y
    simp [dist_eq_norm, pack, PiLp.norm_eq_of_L2, Real.sqrt_sq_eq_abs]
  have hup : Isometry (ULift.up : W 0 → ULift.{u_1,0} (W 0)) := fun _ _ => rfl
  let f : ℝ → ULift.{u_1,0} (W 0) := fun t => ULift.up (pack 0 0 t)
  have hf : Isometry f := hup.comp hp
  have htransport : dimH (f '' unitI) = dimH ((fun t : ℝ => pack 0 0 t) '' unitI) := by
    simpa only [f, Set.image_image, Function.comp_def] using hup.dimH_image ((fun t : ℝ => pack 0 0 t) '' unitI)
  rw [← htransport]
  have partition : ∀ (r : ℝ), 0 ≤ r → ∀ (M : ℕ), 0 < M → ∀ t : ℝ, 0 ≤ t → t ≤ M * r → ∃ i : ℕ, i < M ∧ t ∈ Set.Icc ((i : ℝ) * r) (((i : ℝ) + 1) * r) := by
    intro r hr M
    induction M with
    | zero => simp
    | succ M ih =>
      intro hM t ht htM
      by_cases hzero : M = 0
      · subst M
        refine ⟨0, by omega, ?_⟩
        simpa using And.intro ht htM
      · by_cases hle : t ≤ (M : ℝ) * r
        · obtain ⟨i, hi, hti⟩ := ih (Nat.pos_of_ne_zero hzero) t ht hle
          exact ⟨i, Nat.lt_succ_of_lt hi, hti⟩
        · exact ⟨M, Nat.lt_succ_self _, le_of_lt (lt_of_not_ge hle), by simpa [Nat.cast_add, Nat.cast_one] using htM⟩
  have hcover : ∀ (a δ : ℝ) (N : ℕ), 1 < a → 0 < N → 1 / (N : ℝ) ≤ δ → Hscale a δ (f '' unitI) ≤ (N : ℝ≥0∞) * (ENNReal.ofReal (1 / (N : ℝ))) ^ a := by
    intro a δ N ha hN hδ
    let r : ℝ := 1 / (N : ℝ)
    have hNp : 0 < (N : ℝ) := by exact_mod_cast hN
    have hr : 0 < r := by dsimp [r]; positivity
    let U : ℕ → Set (ULift.{u_1,0} (W 0)) := fun i => if i < N then f '' Set.Icc ((i : ℝ) * r) (((i : ℝ) + 1) * r) else ∅
    have hd : ∀ i, i < N → Metric.ediam (U i) = ENNReal.ofReal r := by
      intro i hi
      simp only [U, if_pos hi, hf.ediam_image, Real.ediam_Icc]
      congr 1
      ring
    have hc : IsCover δ (f '' unitI) U := by
      constructor
      · rintro z ⟨t, ht, rfl⟩
        have ht' : t ≤ (N : ℝ) * r := by simpa [r, hNp.ne'] using ht.2
        obtain ⟨i, hi, hti⟩ := partition r hr.le N hN t ht.1 ht'
        exact Set.mem_iUnion.mpr ⟨i, by simpa only [U, if_pos hi] using Set.mem_image_of_mem f hti⟩
      · intro i
        by_cases hi : i < N
        · rw [hd i hi]
          exact ENNReal.ofReal_le_ofReal hδ
        · simp [U, hi]
    have hscale : Hscale a δ (f '' unitI) ≤ coverCost a U := by
      unfold Hscale
      exact iInf_le_of_le U (iInf_le_of_le hc le_rfl)
    refine hscale.trans ?_
    change (∑' i, ⨆ (_ : (U i).Nonempty), Metric.ediam (U i) ^ a) ≤ _
    rw [tsum_eq_sum (s := Finset.range N) (fun i hi => by
      have hi' : ¬ i < N := by simpa only [Finset.mem_range] using hi
      simp [U, hi'])]
    calc
      (∑ i ∈ Finset.range N, ⨆ (_ : (U i).Nonempty), Metric.ediam (U i) ^ a) ≤ ∑ i ∈ Finset.range N, (ENNReal.ofReal r) ^ a := by
        apply Finset.sum_le_sum
        intro i hi
        apply iSup_le
        intro _
        rw [hd i (Finset.mem_range.mp hi)]
      _ = _ := by simp [r]
  have hcost : ∀ (N : ℕ) (a : ℝ), 0 < N → 1 < a → (N : ℝ≥0∞) * (ENNReal.ofReal (1 / (N : ℝ))) ^ a = ENNReal.ofReal ((N : ℝ) ^ (1-a)) := by
    intro N a hN ha
    have hNp : 0 < (N : ℝ) := by exact_mod_cast hN
    rw [ENNReal.ofReal_rpow_of_pos (by positivity), ← ENNReal.ofReal_natCast, ← ENNReal.ofReal_mul (le_of_lt hNp)]
    congr 1
    rw [Real.rpow_one_sub' (le_of_lt hNp) (by linarith), one_div, Real.inv_rpow (le_of_lt hNp), div_eq_mul_inv]
  have hdim : ∀ a : ℝ, 1 < a → dimH (f '' unitI) ≤ ENNReal.ofReal a := by
    intro a ha
    have hlim : Filter.Tendsto (fun N : ℕ => ENNReal.ofReal ((N : ℝ) ^ (1-a))) Filter.atTop (nhds 0) := by
      have h : Filter.Tendsto (fun N : ℕ => (N : ℝ) ^ (1-a)) Filter.atTop (nhds 0) := by
        simpa only [Function.comp_def, neg_sub] using (tendsto_rpow_neg_atTop (sub_pos.mpr ha)).comp (tendsto_natCast_atTop_atTop (R := ℝ))
      simpa using ENNReal.tendsto_ofReal h
    have hzero : Hmeasure a (f '' unitI) = 0 := by
      apply le_antisymm _ bot_le
      unfold Hmeasure
      apply iSup_le
      intro δ
      apply iSup_le
      intro hδ
      apply ge_of_tendsto hlim
      have hinv : Filter.Tendsto (fun N : ℕ => 1 / (N : ℝ)) Filter.atTop (nhds 0) := by
        simpa only [Function.comp_def, one_div] using tendsto_inv_atTop_zero.comp (tendsto_natCast_atTop_atTop (R := ℝ))
      filter_upwards [Filter.eventually_gt_atTop 0, hinv.eventually (gt_mem_nhds hδ)] with N hN hNd
      rw [← hcost N a hN ha]
      exact hcover a δ N ha hN hNd.le
    exact (h_T002 (ULift.{u_1,0} (W 0)) (f '' unitI) a (by linarith)).2.2.2.1 hzero
  apply ENNReal.le_of_forall_pos_le_add
  intro ε hε _
  have hεr : 0 < (ε : ℝ) := by exact_mod_cast hε
  have h := hdim (1 + (ε : ℝ)) (by linarith)
  simpa only [ENNReal.ofReal_add (by norm_num : (0 : ℝ) ≤ 1) ε.coe_nonneg, ENNReal.ofReal_one, ENNReal.ofReal_coe_nnreal] using h

theorem T007 (n : ℕ) (E : Set (V n)) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) (h_T005 : Bornology.IsBounded E ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) ∧ 0 ≤ dimH E ∧ dimH E ≤ (n : ℝ≥0∞) ∧ dimH E < ⊤ ∧ (n = 0 → E = Set.univ ∧ dimH E = 0)) :
    0 < n → ∀ (q r ε : ℝ), dimH E < ENNReal.ofReal q → 0 < r → r ≤ 1 → 0 < ε → ∃ U : ℕ → Set (V n), IsCover r E U ∧ (∀ i, (U i).Nonempty → 0 < Metric.ediam (U i)) ∧ coverCost q U < ENNReal.ofReal ε := by
  classical
  intro hn q r ε hdim hr hr1 hε
  have hq : 0 < q := ENNReal.ofReal_pos.mp (lt_of_le_of_lt bot_le hdim)
  have hsmallCover : ∃ U : ℕ → Set (V n), IsCover r E U ∧ coverCost q U < ENNReal.ofReal (ε/2) := by
    have hh := h_T002 (ULift (V n)) (ULift.up '' E) q hq
    have hi : Isometry (ULift.up : V n → ULift (V n)) := fun _ _ => rfl
    have hm : Hmeasure q (ULift.up '' E : Set (ULift (V n))) = 0 := hh.2.1 (by rw [hi.dimH_image]; exact hdim)
    have hz : Hscale q r (ULift.up '' E : Set (ULift (V n))) = 0 := by
      apply le_antisymm _ bot_le
      calc Hscale q r (ULift.up '' E : Set (ULift (V n))) ≤ Hmeasure q (ULift.up '' E : Set (ULift (V n))) := le_iSup_of_le r (le_iSup_of_le hr le_rfl)
           _ = 0 := hm
    have hsmall : Hscale q r (ULift.up '' E : Set (ULift (V n))) < ENNReal.ofReal (ε/2) := by rw [hz]; exact ENNReal.ofReal_pos.mpr (by positivity)
    obtain ⟨C, hC, hcost⟩ : ∃ C : ℕ → Set (ULift (V n)), IsCover r (ULift.up '' E) C ∧ coverCost q C < ENNReal.ofReal (ε/2) := by
      simpa only [Hscale, iInf_lt_iff, exists_prop] using hsmall
    let U : ℕ → Set (V n) := fun i => ULift.up ⁻¹' C i
    have hed (i : ℕ) : Metric.ediam (U i) ≤ Metric.ediam (C i) := by
      simpa using hi.antilipschitz.ediam_preimage_le (C i)
    refine ⟨U, ⟨?_, fun i => (hed i).trans (hC.2 i)⟩, lt_of_le_of_lt ?_ hcost⟩
    · intro x hx
      obtain ⟨i, hi⟩ := Set.mem_iUnion.mp (hC.1 (Set.mem_image_of_mem ULift.up hx))
      exact Set.mem_iUnion.mpr ⟨i, hi⟩
    · apply ENNReal.tsum_le_tsum
      intro i
      apply iSup_le
      intro hne
      have hneC : (C i).Nonempty := hne.image ULift.up |>.mono (Set.image_preimage_subset _ _)
      exact (ENNReal.rpow_le_rpow (hed i) hq.le).trans (le_iSup_of_le hneC le_rfl)
  obtain ⟨U, hU, hcost⟩ := hsmallCover
  have hball : ∀ (b : ℝ), 0 < b → ∀ x : V n, ∃ B : Set (V n), x ∈ B ∧ 0 < Metric.ediam B ∧ Metric.ediam B ≤ ENNReal.ofReal r ∧ (Metric.ediam B)^q < ENNReal.ofReal b := by
    intro b hb x
    letI : Nonempty (Fin n) := ⟨⟨0, hn⟩⟩
    have hc : ContinuousAt (fun t : ℝ => t ^ q) 0 := Real.continuousAt_rpow_const 0 q (Or.inr hq.le)
    obtain ⟨d, hd, hdc⟩ := Metric.continuousAt_iff.mp hc b hb
    let a : ℝ := min r d / 4
    have ha : 0 < a := by dsimp [a]; positivity
    have har : 2 * a ≤ r := by dsimp [a]; have := min_le_left r d; linarith
    have had : 2 * a < d := by dsimp [a]; have := min_le_right r d; linarith
    have hp : (2*a)^q < b := by
      have hh := hdc (show dist (2*a) 0 < d by simpa [Real.dist_eq, abs_of_pos ha] using had)
      rw [Real.zero_rpow hq.ne'] at hh
      have hnn := Real.rpow_nonneg (by positivity : 0 ≤ 2*a) q
      simpa [Real.dist_eq, abs_of_nonneg hnn] using hh
    have he : Metric.ediam (Metric.ball x a) = ENNReal.ofReal (2*a) := by
      rw [← Metric.diam_ball_eq x ha.le, Metric.diam, ENNReal.ofReal_toReal Metric.isBounded_ball.ediam_ne_top]
    refine ⟨Metric.ball x a, Metric.mem_ball_self ha, ?_, ?_, ?_⟩
    · rw [he]; exact ENNReal.ofReal_pos.mpr (by positivity)
    · rw [he]; exact ENNReal.ofReal_le_ofReal har
    · rw [he, ENNReal.ofReal_rpow_of_nonneg (by positivity) hq.le]
      exact (ENNReal.ofReal_lt_ofReal_iff hb).mpr hp
  let b : ℕ → ℝ := fun i => ε / 2 / 2 / 2^i
  have hb (i : ℕ) : 0 < b i := by dsimp [b]; positivity
  have hreplace (i : ℕ) : ∃ B : Set (V n), U i ⊆ B ∧ Metric.ediam B ≤ ENNReal.ofReal r ∧ (B.Nonempty → 0 < Metric.ediam B) ∧ (⨆ (_ : B.Nonempty), Metric.ediam B ^ q) ≤ (⨆ (_ : (U i).Nonempty), Metric.ediam (U i)^q) + ENNReal.ofReal (b i) := by
    by_cases hne : (U i).Nonempty
    · by_cases hd : Metric.ediam (U i) = 0
      · obtain ⟨x, hx⟩ := hne
        obtain ⟨B, hxB, hpos, hdiam, hpow⟩ := hball (b i) (hb i) x
        refine ⟨B, ?_, hdiam, fun _ => hpos, ?_⟩
        · intro y hy
          have heq : y = x := (Metric.ediam_eq_zero_iff.mp hd) hy hx
          simpa [heq] using hxB
        · exact iSup_le fun _ => hpow.le.trans (le_add_left le_rfl)
      · refine ⟨U i, Set.Subset.rfl, hU.2 i, fun _ => pos_iff_ne_zero.mpr hd, le_add_of_nonneg_right bot_le⟩
    · refine ⟨∅, ?_, ?_, ?_, ?_⟩
      · simpa only [Set.not_nonempty_iff_eq_empty.mp hne] using (Set.empty_subset (∅ : Set (V n)))
      · simp
      · simp
      · simp
  choose B hsub hdiam hpos hbound using hreplace
  refine ⟨B, ⟨?_, hdiam⟩, hpos, ?_⟩
  · intro x hx
    obtain ⟨i, hi⟩ := Set.mem_iUnion.mp (hU.1 hx)
    exact Set.mem_iUnion.mpr ⟨i, hsub i hi⟩
  · have hsum : (∑' i, ENNReal.ofReal (b i)) = ENNReal.ofReal (ε/2) := by
      have hs : Summable (fun i : ℕ => (ε/2) / 2 / 2^i) := summable_geometric_two' (ε/2)
      dsimp [b]
      rw [← ENNReal.ofReal_tsum_of_nonneg (fun i => by positivity) hs, tsum_geometric_two']
    calc
      coverCost q B ≤ coverCost q U + ENNReal.ofReal (ε/2) := by
        simpa only [coverCost, ENNReal.tsum_add, hsum] using ENNReal.tsum_le_tsum hbound
      _ < ENNReal.ofReal (ε/2) + ENNReal.ofReal (ε/2) := ENNReal.add_lt_add_right ENNReal.ofReal_ne_top hcost
      _ = ENNReal.ofReal ε := by rw [← ENNReal.ofReal_add (by positivity) (by positivity)]; congr 1; ring

theorem T008 (n : ℕ) (E : Set (V n)) (h_T007 : 0 < n → ∀ (q r ε : ℝ), dimH E < ENNReal.ofReal q → 0 < r → r ≤ 1 → 0 < ε → ∃ U : ℕ → Set (V n), IsCover r E U ∧ (∀ i, (U i).Nonempty → 0 < Metric.ediam (U i)) ∧ coverCost q U < ENNReal.ofReal ε) :
    0 < n → ∀ (q δ ε : ℝ), dimH E < ENNReal.ofReal q → 0 < δ → 0 < ε → Hscale (q + 1) δ (cyl n E) ≤ ENNReal.ofReal (2 * (Real.sqrt 2) ^ (q + 1) * ε) := by
  classical
  intro hn q δ ε hq hδ hε
  have hqpos : 0 < q := ENNReal.ofReal_pos.mp (lt_of_le_of_lt bot_le hq)
  have hp : 0 ≤ q + 1 := by linarith
  have hs : 0 < Real.sqrt 2 := Real.sqrt_pos.2 (by norm_num)
  let r := min 1 (δ / Real.sqrt 2)
  have hr : 0 < r := lt_min (by norm_num) (div_pos hδ hs)
  have hr1 : r ≤ 1 := min_le_left _ _
  have hrδ : Real.sqrt 2 * r ≤ δ := by
    have h := min_le_right (1 : ℝ) (δ / Real.sqrt 2)
    simpa only [mul_comm] using (le_div_iff₀ hs).1 h
  obtain ⟨U, hU, hUpos, hcost⟩ := h_T007 hn q r ε hq hr hr1 hε
  let d : ℕ → ℝ := fun i => (Metric.ediam (U i)).toReal
  have hfin (i : ℕ) : Metric.ediam (U i) ≠ ∞ := ne_top_of_le_ne_top ENNReal.ofReal_ne_top (hU.2 i)
  have hd0 (i : ℕ) : 0 ≤ d i := ENNReal.toReal_nonneg
  have hdle (i : ℕ) : d i ≤ r := ENNReal.toReal_le_of_le_ofReal hr.le (hU.2 i)
  have hdeq (i : ℕ) : ENNReal.ofReal (d i) = Metric.ediam (U i) := ENNReal.ofReal_toReal (hfin i)
  have hdpos (i : ℕ) (hi : (U i).Nonempty) : 0 < d i := ENNReal.toReal_pos (ne_of_gt (hUpos i hi)) (hfin i)
  let N : ℕ → ℕ := fun i => ⌈1 / d i⌉₊
  have hN (i : ℕ) (hi : (U i).Nonempty) : 0 < N i ∧ 1 / (N i : ℝ) ≤ d i ∧ (N i : ℝ) ≤ 2 / d i := by
    have hd := hdpos i hi
    have hNr : (0 : ℝ) < N i := lt_of_lt_of_le (one_div_pos.mpr hd) (Nat.le_ceil (1 / d i))
    refine ⟨by exact_mod_cast hNr, ?_, ?_⟩
    · apply (div_le_iff₀ hNr).2
      have h := (div_le_iff₀ hd).1 (Nat.le_ceil (1 / d i))
      nlinarith
    · have h := (Nat.ceil_lt_add_one (le_of_lt (one_div_pos.mpr hd))).le
      calc
        (N i : ℝ) ≤ 1 / d i + 1 := h
        _ ≤ 2 / d i := by
          apply (le_div_iff₀ hd).2
          have hdi : d i ≤ 1 := (hdle i).trans hr1
          field_simp
          nlinarith
  have partition : ∀ (M : ℕ), 0 < M → ∀ t ∈ unitI, ∃ j : ℕ, j < M ∧ t ∈ Set.Icc ((j : ℝ) / M) (((j : ℝ) + 1) / M) := by
    intro M hM t ht
    have hMr : (0 : ℝ) < M := by exact_mod_cast hM
    change 0 ≤ t ∧ t ≤ 1 at ht
    by_cases ht1 : t = 1
    · refine ⟨M - 1, by omega, ?_⟩
      have hcast : ((M - 1 : ℕ) : ℝ) + 1 = M := by exact_mod_cast Nat.sub_add_cancel hM
      rw [ht1]
      constructor
      · apply (div_le_iff₀ hMr).2
        linarith
      · rw [hcast, div_self (ne_of_gt hMr)]
    · have htlt : t < 1 := lt_of_le_of_ne ht.2 ht1
      refine ⟨⌊t * M⌋₊, ?_, ?_, ?_⟩
      · apply (Nat.floor_lt (mul_nonneg ht.1 hMr.le)).2
        nlinarith
      · exact (div_le_iff₀ hMr).2 (Nat.floor_le (mul_nonneg ht.1 hMr.le))
      · exact (le_div_iff₀ hMr).2 (Nat.lt_floor_add_one (t * M)).le
  have geom : ∀ (a b : W n) (c : ℝ), 0 ≤ c → dist (projX n a) (projX n b) ≤ c → dist (projT n a) (projT n b) ≤ c → dist a b ≤ Real.sqrt 2 * c := by
    intro a b c hc hx ht
    have hid : dist a b ^ 2 = dist (projX n a) (projX n b) ^ 2 + dist (projT n a) (projT n b) ^ 2 := by
      rw [EuclideanSpace.dist_sq_eq a b, EuclideanSpace.dist_sq_eq (projX n a) (projX n b)]
      simp [projX, projT, Fintype.sum_sum_type]
    have hs2 : (Real.sqrt 2) ^ 2 = (2 : ℝ) := Real.sq_sqrt (by norm_num)
    have hx2 : dist (projX n a) (projX n b) ^ 2 ≤ c ^ 2 := (sq_le_sq₀ dist_nonneg hc).2 hx
    have ht2 : dist (projT n a) (projT n b) ^ 2 ≤ c ^ 2 := (sq_le_sq₀ dist_nonneg hc).2 ht
    have hnon : 0 ≤ Real.sqrt 2 * c := mul_nonneg hs.le hc
    nlinarith [dist_nonneg (x := a) (y := b), sq_nonneg (Real.sqrt 2 * c - dist a b)]
  let T : ℕ → ℕ → Set (W n) := fun i j => if j < N i then {z | projX n z ∈ U i ∧ projT n z ∈ Set.Icc ((j : ℝ) / N i) (((j : ℝ) + 1) / N i)} else ∅
  have hTdiam (i j : ℕ) : Metric.ediam (T i j) ≤ ENNReal.ofReal (Real.sqrt 2 * d i) := by
    apply Metric.ediam_le_of_forall_dist_le
    intro a ha b hb
    by_cases hj : j < N i
    · simp only [T, if_pos hj, Set.mem_setOf_eq] at ha hb
      apply geom a b (d i) (hd0 i)
      · exact Metric.dist_le_diam_of_mem' (hfin i) ha.1 hb.1
      · have hinv := (hN i ⟨projX n a, ha.1⟩).2.1
        have hlen : ((j : ℝ) + 1) / (N i : ℝ) - (j : ℝ) / N i = 1 / (N i : ℝ) := by ring
        rw [Real.dist_eq, abs_le]
        constructor <;> linarith [ha.2.1, ha.2.2, hb.2.1, hb.2.2]
    · simp [T, hj] at ha
  let e : ℕ ≃ ℕ × ℕ := Nat.pairEquiv.symm
  let B : ℕ → Set (W n) := fun k => T (e k).1 (e k).2
  have hB : IsCover δ (cyl n E) B := by
    constructor
    · intro z hz
      obtain ⟨i, hi⟩ := Set.mem_iUnion.mp (hU.1 hz.1)
      obtain ⟨j, hj, ht⟩ := partition (N i) (hN i ⟨projX n z, hi⟩).1 (projT n z) hz.2
      apply Set.mem_iUnion.mpr
      refine ⟨e.symm (i,j), ?_⟩
      simpa [B, T, hj] using And.intro hi ht
    · intro k
      exact (hTdiam _ _).trans (ENNReal.ofReal_le_ofReal ((mul_le_mul_of_nonneg_left (hdle _) hs.le).trans hrδ))
  let C : ℝ := 2 * (Real.sqrt 2) ^ (q + 1)
  have hC : 0 ≤ C := by dsimp [C]; positivity
  have powbound (i : ℕ) (hi : (U i).Nonempty) : (N i : ℝ≥0∞) * (ENNReal.ofReal (Real.sqrt 2 * d i)) ^ (q + 1) ≤ ENNReal.ofReal C * (Metric.ediam (U i)) ^ q := by
    have hd := hdpos i hi
    have hpow : (N i : ℝ) * (Real.sqrt 2 * d i) ^ (q + 1) ≤ C * (d i) ^ q := by
      calc
        (N i : ℝ) * (Real.sqrt 2 * d i) ^ (q + 1) ≤ (2 / d i) * (Real.sqrt 2 * d i) ^ (q + 1) := mul_le_mul_of_nonneg_right (hN i hi).2.2 (Real.rpow_nonneg (by positivity) _)
        _ = _ := by dsimp [C]; rw [Real.mul_rpow hs.le hd.le, Real.rpow_add_one hd.ne']; field_simp
    have hconv1 : ENNReal.ofReal ((N i : ℝ) * (Real.sqrt 2 * d i) ^ (q + 1)) = (N i : ℝ≥0∞) * (ENNReal.ofReal (Real.sqrt 2 * d i)) ^ (q + 1) := by
      rw [ENNReal.ofReal_mul (by positivity), ENNReal.ofReal_rpow_of_pos (mul_pos hs hd)]
      simp
    have hconv2 : ENNReal.ofReal (C * (d i) ^ q) = ENNReal.ofReal C * (Metric.ediam (U i)) ^ q := by
      rw [ENNReal.ofReal_mul hC, ← ENNReal.ofReal_rpow_of_pos hd, hdeq i]
    rw [← hconv1, ← hconv2]
    exact ENNReal.ofReal_le_ofReal hpow
  have inner (i : ℕ) : (∑' j, ⨆ (_ : (T i j).Nonempty), (Metric.ediam (T i j)) ^ (q + 1)) ≤ ENNReal.ofReal C * (⨆ (_ : (U i).Nonempty), (Metric.ediam (U i)) ^ q) := by
    by_cases hi : (U i).Nonempty
    · simp only [ciSup_pos hi]
      apply le_trans (b := (N i : ℝ≥0∞) * (ENNReal.ofReal (Real.sqrt 2 * d i)) ^ (q + 1)) ?_ (powbound i hi)
      calc
        (∑' j, ⨆ (_ : (T i j).Nonempty), (Metric.ediam (T i j)) ^ (q + 1)) ≤ ∑' j, if j < N i then (ENNReal.ofReal (Real.sqrt 2 * d i)) ^ (q + 1) else 0 := by
          apply ENNReal.tsum_le_tsum
          intro j
          by_cases hj : j < N i
          · rw [if_pos hj]
            exact iSup_le fun _ => ENNReal.rpow_le_rpow (hTdiam i j) hp
          · simp [T, hj]
        _ = _ := by
          rw [tsum_eq_sum (s := Finset.range (N i)) (fun j hj => by simp only [Finset.mem_range] at hj; simp [hj])]
          simp [Finset.sum_ite, Finset.filter_true_of_mem, Finset.sum_const, nsmul_eq_mul]
    · have hempty : U i = ∅ := Set.not_nonempty_iff_eq_empty.mp hi
      have hTempty (j : ℕ) : T i j = ∅ := by ext z; simp [T, hempty]
      simp [hTempty, hi]
  have hBcost : coverCost (q + 1) B ≤ ENNReal.ofReal C * coverCost q U := by
    unfold coverCost
    change (∑' k, (fun p : ℕ × ℕ => ⨆ (_ : (T p.1 p.2).Nonempty), Metric.ediam (T p.1 p.2) ^ (q + 1)) (e k)) ≤ _
    rw [e.tsum_eq (fun p : ℕ × ℕ => ⨆ (_ : (T p.1 p.2).Nonempty), Metric.ediam (T p.1 p.2) ^ (q + 1)), ENNReal.tsum_prod']
    exact (ENNReal.tsum_le_tsum inner).trans_eq ENNReal.tsum_mul_left
  calc
    Hscale (q + 1) δ (cyl n E) ≤ coverCost (q + 1) B := iInf_le_of_le B (iInf_le_of_le hB le_rfl)
    _ ≤ ENNReal.ofReal C * coverCost q U := hBcost
    _ ≤ ENNReal.ofReal C * ENNReal.ofReal ε := mul_le_mul_left' hcost.le _
    _ = ENNReal.ofReal (2 * (Real.sqrt 2) ^ (q + 1) * ε) := (ENNReal.ofReal_mul hC).symm

theorem T009 (n : ℕ) (E : Set (V n)) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) (h_T005 : Bornology.IsBounded E ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) ∧ 0 ≤ dimH E ∧ dimH E ≤ (n : ℝ≥0∞) ∧ dimH E < ⊤ ∧ (n = 0 → E = Set.univ ∧ dimH E = 0)) (h_T006 : n = 0 → dimH (cyl n E) ≤ dimH E + 1) (h_T008 : 0 < n → ∀ (q δ ε : ℝ), dimH E < ENNReal.ofReal q → 0 < δ → 0 < ε → Hscale (q + 1) δ (cyl n E) ≤ ENNReal.ofReal (2 * (Real.sqrt 2) ^ (q + 1) * ε)) :
    dimH (cyl n E) ≤ dimH E + 1 := by
  by_cases hn : n = 0
  · exact h_T006 hn
  have hnpos : 0 < n := Nat.pos_of_ne_zero hn
  have hzero : ∀ q δ : ℝ, dimH E < ENNReal.ofReal q → 0 < δ → Hscale (q + 1) δ (cyl n E) = 0 := by
    intro q δ hq hδ
    apply le_antisymm _ zero_le
    apply ENNReal.le_of_forall_pos_le_add
    intro e he _
    have heR : (0 : ℝ) < (e : ℝ) := he
    have hC : 0 < 2 * (Real.sqrt 2) ^ (q + 1) := mul_pos (by norm_num) (Real.rpow_pos_of_pos (Real.sqrt_pos.2 (by norm_num)) _)
    have hb := h_T008 hnpos q δ ((e : ℝ) / (2 * (Real.sqrt 2) ^ (q + 1))) hq hδ (div_pos heR hC)
    have hc : 2 * (Real.sqrt 2) ^ (q + 1) * ((e : ℝ) / (2 * (Real.sqrt 2) ^ (q + 1))) = (e : ℝ) := mul_div_cancel₀ _ (ne_of_gt hC)
    simpa only [hc, ENNReal.ofReal_coe_nnreal, zero_add] using hb
  have hi : Isometry (ULift.up : W n → ULift.{u_1} (W n)) := fun _ _ => rfl
  have hlift : ∀ s δ : ℝ, Hscale s δ (ULift.up '' cyl n E : Set (ULift.{u_1} (W n))) ≤ Hscale s δ (cyl n E) := by
    intro s δ
    refine le_iInf fun U => le_iInf fun hU => ?_
    have hcov : IsCover δ (ULift.up '' cyl n E) (fun i => ULift.up '' U i) := by
      constructor
      · rintro _ ⟨x, hx, rfl⟩
        obtain ⟨i, hi⟩ := Set.mem_iUnion.mp (hU.1 hx)
        exact Set.mem_iUnion.mpr ⟨i, ⟨x, hi, rfl⟩⟩
      · intro i
        rw [hi.ediam_image]
        exact hU.2 i
    have hb : Hscale s δ (ULift.up '' cyl n E : Set (ULift.{u_1} (W n))) ≤ coverCost s (fun i => ULift.up '' U i) := by
      exact iInf_le_of_le (fun i => ULift.up '' U i) (iInf_le_of_le hcov le_rfl)
    apply hb.trans
    unfold coverCost
    simp only [hi.ediam_image, Set.image_nonempty]
    exact le_rfl
  have hbound : ∀ q : ℝ, dimH E < ENNReal.ofReal q → dimH (cyl n E) ≤ ENNReal.ofReal (q + 1) := by
    intro q hq
    have hq0 : 0 < q := ENNReal.ofReal_pos.mp (lt_of_le_of_lt zero_le hq)
    have hm : Hmeasure (q + 1) (ULift.up '' cyl n E : Set (ULift.{u_1} (W n))) = 0 := by
      apply le_antisymm _ zero_le
      unfold Hmeasure
      refine iSup_le fun δ => iSup_le fun hδ => ?_
      exact (hlift (q + 1) δ).trans (le_of_eq (hzero q δ hq hδ))
    have hd := (h_T002 (ULift.{u_1} (W n)) (ULift.up '' cyl n E) (q + 1) (by linarith)).2.2.2.1 hm
    rwa [hi.dimH_image] at hd
  apply ENNReal.le_of_forall_pos_le_add
  intro e he _
  have hD : dimH E ≠ ⊤ := h_T005.2.2.2.2.2.1.ne
  have heR : (0 : ℝ) < (e : ℝ) := he
  have hD0 : 0 ≤ (dimH E).toReal := ENNReal.toReal_nonneg
  have hq : dimH E < ENNReal.ofReal ((dimH E).toReal + (e : ℝ)) := by
    calc
      dimH E = ENNReal.ofReal (dimH E).toReal := (ENNReal.ofReal_toReal hD).symm
      _ < ENNReal.ofReal ((dimH E).toReal + (e : ℝ)) := (ENNReal.ofReal_lt_ofReal_iff (by positivity)).2 (by linarith)
  have hconv : ENNReal.ofReal (((dimH E).toReal + (e : ℝ)) + 1) = dimH E + 1 + (e : ℝ≥0∞) := by
    rw [ENNReal.ofReal_add (by positivity) (by norm_num), ENNReal.ofReal_add hD0 (le_of_lt heR), ENNReal.ofReal_toReal hD]
    simp [add_comm, add_left_comm]
  rw [← hconv]
  exact hbound _ hq

theorem T010 (n : ℕ) (E : Set (V n)) (h_T005 : Bornology.IsBounded E ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) ∧ 0 ≤ dimH E ∧ dimH E ≤ (n : ℝ≥0∞) ∧ dimH E < ⊤ ∧ (n = 0 → E = Set.univ ∧ dimH E = 0)) :
    ∀ (s δ ε : ℝ), 0 < s → 0 < δ → 0 < ε → ∀ Vc : ℕ → Set (W n), IsCover δ (cyl n E) Vc → ∃ J : ℕ → Set ℝ, (∀ i, IsOpen (J i) ∧ projT n '' Vc i ⊆ J i ∧ MeasureTheory.volume (J i) ≤ Metric.ediam (Vc i) + ENNReal.ofReal ε * (1 / 2 : ℝ≥0∞) ^ (i + 1) / (1 + (Metric.ediam (Vc i)) ^ s)) ∧ (∀ t ∈ unitI, Hscale s δ E ≤ ∑' i, (J i).indicator (fun _ : ℝ => (Metric.ediam (Vc i)) ^ s) t) ∧ (∀ i, Measurable ((J i).indicator (fun _ : ℝ => (Metric.ediam (Vc i)) ^ s))) := by
  classical
  intro s δ ε hs hδ hε Vc hVc
  have hcfinite : Hscale s δ E < ⊤ := h_T005.2.2.1 s δ hs hδ
  have hproj : LipschitzWith 1 (projX n) ∧ LipschitzWith 1 (projT n) := by
    constructor
    · apply LipschitzWith.of_dist_le_mul
      intro x y
      simp only [NNReal.coe_one, one_mul]
      have h : dist x y ^ 2 = dist (projX n x) (projX n y) ^ 2 + dist (projT n x) (projT n y) ^ 2 := by
        simp [PiLp.dist_sq_eq_of_L2, projX, projT, Fintype.sum_sum_type]
      nlinarith [sq_nonneg (dist (projT n x) (projT n y)), dist_nonneg (x := projX n x) (y := projX n y), dist_nonneg (x := x) (y := y)]
    · apply LipschitzWith.of_dist_le_mul
      intro x y
      simpa [projT] using PiLp.dist_apply_le x y (Sum.inr ())
  have enclose : ∀ (B : Set ℝ) (R e : ℝ≥0∞), Metric.ediam B ≤ R → R ≠ ⊤ → 0 < e → e ≠ ⊤ → ∃ J : Set ℝ, IsOpen J ∧ B ⊆ J ∧ MeasureTheory.volume J ≤ R + e := by
    intro B R e hBR hR he het
    by_cases hB : B.Nonempty
    · have hb : Bornology.IsBounded B := Metric.isBounded_iff_ediam_ne_top.mpr (ne_top_of_le_ne_top hR hBR)
      have hp : 0 < e.toReal := ENNReal.toReal_pos he.ne' het
      refine ⟨Set.Ioo (sInf B - e.toReal / 2) (sSup B + e.toReal / 2), isOpen_Ioo, ?_, ?_⟩
      · intro x hx
        obtain ⟨hl, hu⟩ := hb.subset_Icc_sInf_sSup hx
        constructor <;> linarith
      · rw [Real.volume_Ioo]
        have heq : sSup B + e.toReal / 2 - (sInf B - e.toReal / 2) = (sSup B - sInf B) + e.toReal := by ring
        rw [heq, ENNReal.ofReal_add (sub_nonneg.mpr (Real.sInf_le_sSup B hb.bddBelow hb.bddAbove)) ENNReal.toReal_nonneg, ENNReal.ofReal_toReal het, ← Real.ediam_eq hb]
        exact add_le_add hBR le_rfl
    · refine ⟨∅, isOpen_empty, ?_, ?_⟩
      · simpa [Set.not_nonempty_iff_eq_empty.mp hB]
      · simp
  let err : ℕ → ℝ≥0∞ := fun i => ENNReal.ofReal ε * (1 / 2 : ℝ≥0∞) ^ (i + 1) / (1 + (Metric.ediam (Vc i)) ^ s)
  have hR (i : ℕ) : Metric.ediam (Vc i) ≠ ⊤ := ne_top_of_le_ne_top ENNReal.ofReal_ne_top (hVc.2 i)
  have herr (i : ℕ) : 0 < err i ∧ err i ≠ ⊤ := by
    have hr : (Metric.ediam (Vc i)) ^ s ≠ ⊤ := ENNReal.rpow_ne_top_of_nonneg hs.le (hR i)
    have hd : 1 + (Metric.ediam (Vc i)) ^ s ≠ ⊤ := by finiteness
    have hd0 : 1 + (Metric.ediam (Vc i)) ^ s ≠ 0 := by positivity
    have hn : ENNReal.ofReal ε * (1 / 2 : ℝ≥0∞) ^ (i + 1) ≠ 0 := mul_ne_zero (ENNReal.ofReal_pos.mpr hε).ne' (pow_ne_zero _ (by norm_num))
    exact ⟨ENNReal.div_pos_iff.mpr ⟨hn, hd⟩, ENNReal.div_ne_top (by finiteness) hd0⟩
  have hex (i : ℕ) : ∃ J : Set ℝ, IsOpen J ∧ projT n '' Vc i ⊆ J ∧ MeasureTheory.volume J ≤ Metric.ediam (Vc i) + err i := by
    apply enclose (projT n '' Vc i) (Metric.ediam (Vc i)) (err i)
    · simpa using hproj.2.ediam_image_le (Vc i)
    · exact hR i
    · exact (herr i).1
    · exact (herr i).2
  choose J hJ using hex
  refine ⟨J, hJ, ?_, ?_⟩
  · intro t ht
    let U : ℕ → Set (V n) := fun i => if t ∈ J i then projX n '' Vc i else ∅
    have hd (i : ℕ) : Metric.ediam (projX n '' Vc i) ≤ Metric.ediam (Vc i) := by simpa using hproj.1.ediam_image_le (Vc i)
    have hU : IsCover δ E U := by
      constructor
      · intro x hxE
        have hp : pack n x t ∈ cyl n E := by simpa [cyl, projX, projT, pack] using And.intro hxE ht
        obtain ⟨i, hi⟩ := Set.mem_iUnion.mp (hVc.1 hp)
        have hti : t ∈ J i := (hJ i).2.1 ⟨pack n x t, hi, by simp [projT, pack]⟩
        apply Set.mem_iUnion.mpr
        refine ⟨i, ?_⟩
        simp only [U, if_pos hti]
        exact ⟨pack n x t, hi, by ext j; simp [projX, pack]⟩
      · intro i
        dsimp [U]
        split_ifs
        · exact (hd i).trans (hVc.2 i)
        · simp
    have hc : Hscale s δ E ≤ coverCost s U := iInf_le_of_le U (iInf_le_of_le hU le_rfl)
    refine hc.trans (ENNReal.tsum_le_tsum fun i => ?_)
    change (⨆ (_ : (U i).Nonempty), Metric.ediam (U i) ^ s) ≤ _
    apply iSup_le
    intro hne
    by_cases hi : t ∈ J i
    · simp only [Set.indicator_of_mem hi, U, if_pos hi]
      exact ENNReal.rpow_le_rpow (hd i) hs.le
    · have : U i = ∅ := by simp [U, hi]
      simp [this] at hne
  · intro i
    exact measurable_const.indicator (hJ i).1.measurableSet

theorem T011 (n : ℕ) (E : Set (V n)) (h_T005 : Bornology.IsBounded E ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) ∧ 0 ≤ dimH E ∧ dimH E ≤ (n : ℝ≥0∞) ∧ dimH E < ⊤ ∧ (n = 0 → E = Set.univ ∧ dimH E = 0)) (h_T010 : ∀ (s δ ε : ℝ), 0 < s → 0 < δ → 0 < ε → ∀ Vc : ℕ → Set (W n), IsCover δ (cyl n E) Vc → ∃ J : ℕ → Set ℝ, (∀ i, IsOpen (J i) ∧ projT n '' Vc i ⊆ J i ∧ MeasureTheory.volume (J i) ≤ Metric.ediam (Vc i) + ENNReal.ofReal ε * (1 / 2 : ℝ≥0∞) ^ (i + 1) / (1 + (Metric.ediam (Vc i)) ^ s)) ∧ (∀ t ∈ unitI, Hscale s δ E ≤ ∑' i, (J i).indicator (fun _ : ℝ => (Metric.ediam (Vc i)) ^ s) t) ∧ (∀ i, Measurable ((J i).indicator (fun _ : ℝ => (Metric.ediam (Vc i)) ^ s)))) :
    ∀ (s δ ε : ℝ), 0 < s → 0 < δ → 0 < ε → ∀ Vc : ℕ → Set (W n), IsCover δ (cyl n E) Vc → Hscale s δ E ≤ coverCost (s + 1) Vc + ENNReal.ofReal ε := by
  intro s δ ε hs hδ hε Vc hc
  obtain ⟨J, hJ, hp, hm⟩ := h_T010 s δ ε hs hδ hε Vc hc
  have hmass : MeasureTheory.volume unitI = 1 := by simp [unitI, Real.volume_Icc]
  have hint := MeasureTheory.setLIntegral_mono' (μ := MeasureTheory.volume) (s := unitI) (f := fun _ => Hscale s δ E) (g := fun t => ∑' i, (J i).indicator (fun _ : ℝ => Metric.ediam (Vc i) ^ s) t) measurableSet_Icc hp
  rw [MeasureTheory.setLIntegral_const, hmass, mul_one] at hint
  rw [MeasureTheory.lintegral_tsum (fun i => (hm i).aemeasurable)] at hint
  have hint' : Hscale s δ E ≤ ∑' i, Metric.ediam (Vc i) ^ s * MeasureTheory.volume (J i ∩ unitI) := by
    simpa only [MeasureTheory.lintegral_indicator_const (hJ _).1.measurableSet, MeasureTheory.Measure.restrict_apply (hJ _).1.measurableSet] using hint
  have hcost : (∑' i, Metric.ediam (Vc i) ^ (s + 1)) = coverCost (s + 1) Vc := by
    unfold coverCost
    apply tsum_congr
    intro i
    by_cases hi : (Vc i).Nonempty
    · simp [hi]
    · have he : Vc i = ∅ := Set.not_nonempty_iff_eq_empty.mp hi
      simp [he, Metric.ediam_empty, ENNReal.zero_rpow_of_pos (show 0 < s + 1 by linarith)]
  have hgeom : (∑' i : ℕ, (1 / 2 : ℝ≥0∞) ^ (i + 1)) = 1 := by
    rw [ENNReal.tsum_geometric_add_one]
    norm_num
    exact ENNReal.inv_mul_cancel (by norm_num) (by norm_num)
  calc
    Hscale s δ E ≤ ∑' i, Metric.ediam (Vc i) ^ s * MeasureTheory.volume (J i ∩ unitI) := hint'
    _ ≤ ∑' i, Metric.ediam (Vc i) ^ s * (Metric.ediam (Vc i) + ENNReal.ofReal ε * (1 / 2 : ℝ≥0∞) ^ (i + 1) / (1 + Metric.ediam (Vc i) ^ s)) := by
      apply ENNReal.tsum_le_tsum
      intro i
      exact mul_le_mul_left' ((MeasureTheory.measure_mono Set.inter_subset_left).trans (hJ i).2.2) _
    _ ≤ ∑' i, (Metric.ediam (Vc i) ^ (s + 1) + ENNReal.ofReal ε * (1 / 2 : ℝ≥0∞) ^ (i + 1)) := by
      apply ENNReal.tsum_le_tsum
      intro i
      rw [mul_add, ENNReal.rpow_add_of_nonneg s 1 hs.le zero_le_one, ENNReal.rpow_one]
      exact add_le_add le_rfl ((mul_le_mul_right' (le_add_left le_rfl : Metric.ediam (Vc i) ^ s ≤ 1 + Metric.ediam (Vc i) ^ s) _).trans ENNReal.mul_div_le)
    _ = coverCost (s + 1) Vc + ENNReal.ofReal ε := by
      rw [ENNReal.tsum_add, hcost, ENNReal.tsum_mul_left, hgeom, mul_one]

theorem T012 (n : ℕ) (E : Set (V n)) (h_T011 : ∀ (s δ ε : ℝ), 0 < s → 0 < δ → 0 < ε → ∀ Vc : ℕ → Set (W n), IsCover δ (cyl n E) Vc → Hscale s δ E ≤ coverCost (s + 1) Vc + ENNReal.ofReal ε) :
    ∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E ≤ Hscale (s + 1) δ (cyl n E) := by
  intro s δ hs hδ
  unfold Hscale
  refine le_iInf fun Vc => le_iInf fun hVc => ?_
  by_cases htop : coverCost (s + 1) Vc = ⊤
  · rw [htop]
    exact le_top
  · apply ENNReal.le_of_forall_pos_le_add
    intro ε hε _
    have hεreal : 0 < (ε : ℝ) := by exact_mod_cast hε
    have hεcoe : ENNReal.ofReal (ε : ℝ) = (ε : ℝ≥0∞) := by simp
    have h := h_T011 s δ (ε : ℝ) hs hδ hεreal Vc hVc
    rw [hεcoe] at h
    exact h

theorem T013 (n : ℕ) (E : Set (V n)) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) (h_T005 : Bornology.IsBounded E ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) ∧ 0 ≤ dimH E ∧ dimH E ≤ (n : ℝ≥0∞) ∧ dimH E < ⊤ ∧ (n = 0 → E = Set.univ ∧ dimH E = 0)) (h_T012 : ∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E ≤ Hscale (s + 1) δ (cyl n E)) :
    ∀ s : ℝ, 0 < s → ENNReal.ofReal s < dimH E → ENNReal.ofReal (s + 1) ≤ dimH (cyl n E) := by
  have hscale : ∀ (X : Type) [MetricSpace X] (s δ : ℝ) (A : Set X), Hscale s δ (ULift.up '' A : Set (ULift.{u_1} X)) = Hscale s δ A := by
    intro X _ s δ A
    have hup : Isometry (ULift.up : X → ULift.{u_1} X) := fun _ _ => rfl
    have hdown : Isometry (ULift.down : ULift.{u_1} X → X) := fun _ _ => rfl
    have costup (U : ℕ → Set X) : coverCost s (fun i => ULift.up '' U i : ℕ → Set (ULift.{u_1} X)) = coverCost s U := by
      unfold coverCost
      simp only [Set.image_nonempty, hup.ediam_image]
    have costdown (U : ℕ → Set (ULift.{u_1} X)) : coverCost s (fun i => ULift.down '' U i) = coverCost s U := by
      unfold coverCost
      simp only [Set.image_nonempty, hdown.ediam_image]
    apply le_antisymm
    · refine le_iInf fun U => le_iInf fun hU => ?_
      have hc : IsCover δ (ULift.up '' A : Set (ULift.{u_1} X)) (fun i => ULift.up '' U i) := by
        constructor
        · rintro _ ⟨x, hx, rfl⟩
          obtain ⟨i, hi⟩ := Set.mem_iUnion.mp (hU.1 hx)
          exact Set.mem_iUnion.mpr ⟨i, ⟨x, hi, rfl⟩⟩
        · intro i
          simpa only [hup.ediam_image] using hU.2 i
      calc
        _ ≤ coverCost s (fun i => ULift.up '' U i : ℕ → Set (ULift.{u_1} X)) := iInf_le_of_le _ (iInf_le _ hc)
        _ = _ := costup U
    · refine le_iInf fun U => le_iInf fun hU => ?_
      have hc : IsCover δ A (fun i => ULift.down '' U i) := by
        constructor
        · intro x hx
          obtain ⟨i, hi⟩ := Set.mem_iUnion.mp (hU.1 ⟨x, hx, rfl⟩)
          exact Set.mem_iUnion.mpr ⟨i, ⟨ULift.up x, hi, rfl⟩⟩
        · intro i
          simpa only [hdown.ediam_image] using hU.2 i
      calc
        _ ≤ coverCost s (fun i => ULift.down '' U i) := iInf_le_of_le _ (iInf_le _ hc)
        _ = _ := costdown U
  have hmeasure (X : Type) [MetricSpace X] (s : ℝ) (A : Set X) : Hmeasure s (ULift.up '' A : Set (ULift.{u_1} X)) = Hmeasure s A := by
    simp only [Hmeasure, hscale]
  have hdim (X : Type) [MetricSpace X] (A : Set X) : dimH (ULift.up '' A : Set (ULift.{u_1} X)) = dimH A := by
    have hup : Isometry (ULift.up : X → ULift.{u_1} X) := fun _ _ => rfl
    exact hup.dimH_image A
  intro s hs hsd
  have hEup : Hmeasure s (ULift.up '' E : Set (ULift.{u_1} (V n))) = ⊤ :=
    (h_T002 (ULift.{u_1} (V n)) (ULift.up '' E) s hs).2.2.1 (by simpa only [hdim] using hsd)
  have hE : Hmeasure s E = ⊤ := by
    simpa only [hmeasure] using hEup
  have hmono : Hmeasure s E ≤ Hmeasure (s + 1) (cyl n E) := by
    unfold Hmeasure
    exact iSup_mono fun δ => iSup_mono fun hδ => h_T012 s δ hs hδ
  have hF : Hmeasure (s + 1) (cyl n E) = ⊤ := by
    apply top_unique
    simpa only [hE] using hmono
  have hFup : Hmeasure (s + 1) (ULift.up '' cyl n E : Set (ULift.{u_1} (W n))) = ⊤ := by
    simpa only [hmeasure] using hF
  have hb := (h_T002 (ULift.{u_1} (W n)) (ULift.up '' cyl n E) (s + 1) (by linarith)).2.2.2.2 hFup
  simpa only [hdim] using hb

theorem T014 (n : ℕ) (E : Set (V n)) (h_T005 : Bornology.IsBounded E ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) ∧ 0 ≤ dimH E ∧ dimH E ≤ (n : ℝ≥0∞) ∧ dimH E < ⊤ ∧ (n = 0 → E = Set.univ ∧ dimH E = 0)) (h_T013 : ∀ s : ℝ, 0 < s → ENNReal.ofReal s < dimH E → ENNReal.ofReal (s + 1) ≤ dimH (cyl n E)) :
    0 < dimH E → dimH E + 1 ≤ dimH (cyl n E) := by
  intro hpos
  have hfinite : dimH E ≠ ⊤ := ne_of_lt h_T005.2.2.2.2.2.1
  have hD : 0 < (dimH E).toReal := ENNReal.toReal_pos_iff.mpr ⟨hpos, lt_top_iff_ne_top.mpr hfinite⟩
  have hrepr : ENNReal.ofReal ((dimH E).toReal + 1) = dimH E + 1 := by
    rw [ENNReal.ofReal_add (le_of_lt hD) (by norm_num), ENNReal.ofReal_toReal hfinite]
    simp
  by_cases hF : dimH (cyl n E) = ⊤
  · simp [hF]
  · rw [← hrepr, ENNReal.ofReal_le_iff_le_toReal hF]
    by_contra h
    have hlt : (dimH (cyl n E)).toReal < (dimH E).toReal + 1 := lt_of_not_ge h
    have hm : max 0 ((dimH (cyl n E)).toReal - 1) < (dimH E).toReal :=
      max_lt hD (by linarith)
    obtain ⟨s, hs₁, hs₂⟩ := exists_between hm
    have hspos : 0 < s := lt_of_le_of_lt (le_max_left _ _) hs₁
    have hsD : ENNReal.ofReal s < dimH E :=
      (ENNReal.ofReal_lt_iff_lt_toReal hspos.le hfinite).mpr hs₂
    have hbound : s + 1 ≤ (dimH (cyl n E)).toReal :=
      (ENNReal.ofReal_le_iff_le_toReal hF).mp (h_T013 s hspos hsD)
    have : (dimH (cyl n E)).toReal - 1 < s :=
      lt_of_le_of_lt (le_max_right _ _) hs₁
    linarith

theorem T015 (n : ℕ) (E : Set (V n)) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) :
    dimH unitI ≤ 1 := by
  classical
  let U : ℕ → ℕ → Set ℝ := fun N i => if i < N then Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N) else ∅
  have hcover : ∀ N : ℕ, 0 < N → unitI ⊆ ⋃ i, U N i := by
    intro N hN x hx
    have hNr : (0 : ℝ) < N := by exact_mod_cast hN
    rcases hx with ⟨hx0, hx1⟩
    by_cases hx : x = 1
    · refine Set.mem_iUnion.mpr ⟨N-1, ?_⟩
      change x ∈ if N-1 < N then _ else ∅
      rw [if_pos (by omega)]
      have hc : ((N-1 : ℕ) : ℝ) = (N : ℝ) - 1 := by rw [Nat.cast_sub (by omega)]; norm_num
      simp only [Set.mem_Icc, hc, hx]
      constructor
      · apply (div_le_iff₀ hNr).2; linarith
      · apply (le_div_iff₀ hNr).2; linarith
    · have hxl : x < 1 := lt_of_le_of_ne hx1 hx
      let i := ⌊x * N⌋₊
      have hi0 : (i : ℝ) ≤ x * N := Nat.floor_le (by positivity)
      have hi1 : x * N < (i : ℝ) + 1 := Nat.lt_floor_add_one _
      have hiN : i < N := by
        have : (i : ℝ) < N := lt_of_le_of_lt hi0 (by nlinarith)
        exact_mod_cast this
      refine Set.mem_iUnion.mpr ⟨i, ?_⟩
      change x ∈ if i < N then _ else ∅
      rw [if_pos hiN]
      exact ⟨(div_le_iff₀ hNr).2 hi0, (le_div_iff₀ hNr).2 hi1.le⟩
  have hdiam : ∀ N i : ℕ, i < N → Metric.ediam (U N i) = ENNReal.ofReal (1 / (N : ℝ)) := by
    intro N i hi
    rw [show U N i = Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N) from if_pos hi, Real.ediam_Icc]
    congr 1
    ring
  have hcost : ∀ (N : ℕ) (a : ℝ), 0 < N → coverCost a (U N) ≤ ENNReal.ofReal ((N : ℝ) ^ (1-a)) := by
    intro N a hN
    have hNr : (0 : ℝ) < N := by exact_mod_cast hN
    have hconv : (N : ℝ≥0∞) * (ENNReal.ofReal (1 / (N : ℝ))) ^ a = ENNReal.ofReal ((N : ℝ) ^ (1-a)) := by
      rw [ENNReal.ofReal_rpow_of_pos (one_div_pos.mpr hNr), ← ENNReal.ofReal_natCast, ← ENNReal.ofReal_mul (Nat.cast_nonneg N)]
      congr 1
      rw [Real.rpow_sub hNr, Real.div_rpow (by norm_num) hNr.le, Real.one_rpow, Real.rpow_one]
      ring
    rw [← hconv]
    unfold coverCost
    rw [tsum_eq_sum (s := Finset.range N) (fun i hi => by simp [U, show ¬ i < N from by simpa using hi])]
    calc
      _ ≤ ∑ i ∈ Finset.range N, (ENNReal.ofReal (1 / (N : ℝ))) ^ a := by
        apply Finset.sum_le_sum
        intro i hi
        apply iSup_le
        intro _
        rw [hdiam N i (Finset.mem_range.mp hi)]
      _ = _ := by simp
  have hzero : ∀ a : ℝ, 1 < a → Hmeasure a unitI = 0 := by
    intro a ha
    apply le_antisymm ?_ bot_le
    unfold Hmeasure
    refine iSup_le fun δ => iSup_le fun hδ => ?_
    have hn : Filter.Tendsto (fun N : ℕ => (N : ℝ)) Filter.atTop Filter.atTop := tendsto_natCast_atTop_atTop
    have hc : Filter.Tendsto (fun N : ℕ => (N : ℝ) ^ (1-a)) Filter.atTop (nhds 0) := by
      simpa only [neg_sub, Function.comp_def] using (tendsto_rpow_neg_atTop (sub_pos.mpr ha)).comp hn
    have hc' : Filter.Tendsto (fun N : ℕ => ENNReal.ofReal ((N : ℝ) ^ (1-a))) Filter.atTop (nhds 0) := by
      simpa only [Function.comp_def, ENNReal.ofReal_zero] using (ENNReal.continuous_ofReal.tendsto 0).comp hc
    have hm : Filter.Tendsto (fun N : ℕ => 1 / (N : ℝ)) Filter.atTop (nhds 0) := by
      simpa only [one_div, Function.comp_def] using tendsto_inv_atTop_zero.comp hn
    apply ge_of_tendsto hc'
    filter_upwards [Filter.eventually_gt_atTop (0 : ℕ), hm.eventually (gt_mem_nhds hδ)] with N hN hmN
    have hcov : IsCover δ unitI (U N) := by
      refine ⟨hcover N hN, fun i => ?_⟩
      by_cases hi : i < N
      · rw [hdiam N i hi]
        exact ENNReal.ofReal_le_ofReal hmN.le
      · simp [U, hi]
    have hb : Hscale a δ unitI ≤ coverCost a (U N) := by
      unfold Hscale
      exact iInf_le_of_le (U N) (iInf_le_of_le hcov le_rfl)
    exact hb.trans (hcost N a hN)
  have hdim : ∀ a : ℝ, 1 < a → dimH unitI ≤ ENNReal.ofReal a := by
    intro a ha
    let f := (ULift.up : ℝ → ULift ℝ)
    have hp := h_T002 (ULift ℝ) (f '' unitI) a
    have hf : Isometry f := fun x y => rfl
    have hs : ∀ δ : ℝ, Hscale a δ (f '' unitI) ≤ Hscale a δ unitI := by
      intro δ
      unfold Hscale
      refine le_iInf fun C => le_iInf fun hC => ?_
      have hcov : IsCover δ (f '' unitI) (fun i => f '' C i) := by
        constructor
        · rintro _ ⟨x, hx, rfl⟩
          rcases Set.mem_iUnion.mp (hC.1 hx) with ⟨i, hi⟩
          exact Set.mem_iUnion.mpr ⟨i, ⟨x, hi, rfl⟩⟩
        · intro i
          rw [hf.ediam_image]
          exact hC.2 i
      have hcost' : coverCost a (fun i => f '' C i) = coverCost a C := by
        simp only [coverCost, Set.image_nonempty, hf.ediam_image]
      exact iInf_le_of_le (fun i => f '' C i) (iInf_le_of_le hcov hcost'.le)
    have hz' : Hmeasure a (f '' unitI) = 0 := by
      apply le_antisymm ?_ bot_le
      change Hmeasure a (f '' unitI) ≤ (0 : ℝ≥0∞)
      rw [← hzero a ha]
      exact iSup_mono fun δ => iSup_mono fun _ => hs δ
    rw [← hf.dimH_image unitI]
    exact (hp (by linarith)).2.2.2.1 hz'
  apply ENNReal.le_of_forall_pos_le_add
  intro ε hε _
  have he : (0 : ℝ) < ε := by exact_mod_cast hε
  have hh := hdim (1 + (ε : ℝ)) (by linarith)
  simpa [ENNReal.ofReal_add (by norm_num : (0 : ℝ) ≤ 1) ε.coe_nonneg] using hh

theorem T016 (n : ℕ) (E : Set (V n))  :
    ∀ δ : ℝ, 0 < δ → ∀ U : ℕ → Set ℝ, IsCover δ unitI U → (1 : ℝ≥0∞) ≤ ∑' i, Metric.ediam (U i) := by
  classical
  intro δ hδ U hU
  have hb (i : ℕ) : Bornology.IsBounded (U i) :=
    Metric.isBounded_iff_ediam_ne_top.mpr (ne_top_of_le_ne_top ENNReal.ofReal_ne_top (hU.2 i))
  apply ENNReal.le_of_forall_pos_le_add
  intro ε hε hfin
  let e : ℕ → ℝ := fun i => (ε : ℝ) / 2 / 2 ^ i
  have he (i : ℕ) : 0 < e i := by
    dsimp [e]
    exact div_pos (div_pos (by exact_mod_cast hε) (by norm_num)) (pow_pos (by norm_num) _)
  let J : ℕ → Set ℝ := fun i => if (U i).Nonempty then
    Set.Ioo (sInf (U i) - e i / 2) (sSup (U i) + e i / 2) else ∅
  have hsub (i : ℕ) : U i ⊆ J i := by
    intro x hx
    have hx' := (hb i).subset_Icc_sInf_sSup hx
    simp only [J, if_pos (Set.nonempty_of_mem hx), Set.mem_Ioo]
    constructor <;> linarith [he i, hx'.1, hx'.2]
  have hcov : unitI ⊆ ⋃ i, J i := by
    intro x hx
    obtain ⟨i, hi⟩ := Set.mem_iUnion.mp (hU.1 hx)
    exact Set.mem_iUnion.mpr ⟨i, hsub i hi⟩
  have hvol (i : ℕ) : MeasureTheory.volume (J i) ≤ Metric.ediam (U i) + ENNReal.ofReal (e i) := by
    by_cases hi : (U i).Nonempty
    · rw [show J i = Set.Ioo (sInf (U i) - e i / 2) (sSup (U i) + e i / 2) from if_pos hi]
      rw [Real.volume_Ioo, Real.ediam_eq (hb i)]
      have heq : sSup (U i) + e i / 2 - (sInf (U i) - e i / 2) = (sSup (U i) - sInf (U i)) + e i := by ring
      rw [heq]
      exact ENNReal.ofReal_add_le
    · simp [J, hi]
  have hsum : (∑' i, ENNReal.ofReal (e i)) = (ε : ℝ≥0∞) := by
    dsimp [e]
    rw [← ENNReal.ofReal_tsum_of_nonneg (fun i => by positivity) (hasSum_geometric_two' (ε : ℝ)).summable, (hasSum_geometric_two' (ε : ℝ)).tsum_eq]
    simp
  calc
    (1 : ℝ≥0∞) = MeasureTheory.volume unitI := by simp [unitI, Real.volume_Icc]
    _ ≤ MeasureTheory.volume (⋃ i, J i) := MeasureTheory.measure_mono hcov
    _ ≤ ∑' i, MeasureTheory.volume (J i) := MeasureTheory.measure_iUnion_le J
    _ ≤ ∑' i, (Metric.ediam (U i) + ENNReal.ofReal (e i)) := ENNReal.tsum_le_tsum hvol
    _ = (∑' i, Metric.ediam (U i)) + ε := by rw [ENNReal.tsum_add, hsum]

theorem T017 (n : ℕ) (E : Set (V n)) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) (h_T015 : dimH unitI ≤ 1) (h_T016 : ∀ δ : ℝ, 0 < δ → ∀ U : ℕ → Set ℝ, IsCover δ unitI U → (1 : ℝ≥0∞) ≤ ∑' i, Metric.ediam (U i)) :
    dimH unitI = 1 ∧ ∀ s : ℝ, 0 < s → s < 1 → Hmeasure s unitI = ⊤ := by
  classical
  have hterm : ∀ (s δ : ℝ), 0 < s → s < 1 → 0 < δ → ∀ ρ : ℝ≥0∞, ρ ≤ ENNReal.ofReal δ → ENNReal.ofReal (δ ^ (s - 1)) * ρ ≤ ρ ^ s := by
    intro s δ hs hs1 hδ ρ hρ
    have hfin : ρ ≠ ⊤ := ne_top_of_le_ne_top ENNReal.ofReal_ne_top hρ
    have hle : ρ.toReal ≤ δ := (ENNReal.toReal_le_toReal hfin ENNReal.ofReal_ne_top).2 hρ |>.trans_eq (ENNReal.toReal_ofReal hδ.le)
    have hreal : δ ^ (s - 1) * ρ.toReal ≤ ρ.toReal ^ s := by
      by_cases hz : ρ.toReal = 0
      · simp [hz, Real.zero_rpow hs.ne']
      · have hp : 0 < ρ.toReal := lt_of_le_of_ne ENNReal.toReal_nonneg (Ne.symm hz)
        calc
          _ ≤ ρ.toReal ^ (s - 1) * ρ.toReal := mul_le_mul_of_nonneg_right (Real.rpow_le_rpow_of_nonpos hp hle (by linarith)) ENNReal.toReal_nonneg
          _ = _ := by rw [Real.rpow_sub_one hz, div_mul_cancel₀ _ hz]
    have hc := ENNReal.ofReal_le_ofReal hreal
    rw [ENNReal.ofReal_mul (Real.rpow_nonneg hδ.le _), ← ENNReal.ofReal_rpow_of_nonneg ENNReal.toReal_nonneg hs.le, ENNReal.ofReal_toReal hfin] at hc
    exact hc
  have hscale : ∀ s : ℝ, 0 < s → s < 1 → ∀ δ : ℝ, 0 < δ → ENNReal.ofReal (δ ^ (s - 1)) ≤ Hscale s δ unitI := by
    intro s hs hs1 δ hδ
    refine le_iInf fun U => le_iInf fun hU => ?_
    calc
      ENNReal.ofReal (δ ^ (s - 1)) = ENNReal.ofReal (δ ^ (s - 1)) * 1 := (mul_one _).symm
      _ ≤ ENNReal.ofReal (δ ^ (s - 1)) * ∑' i, Metric.ediam (U i) := mul_le_mul_left' (h_T016 δ hδ U hU) _
      _ = ∑' i, ENNReal.ofReal (δ ^ (s - 1)) * Metric.ediam (U i) := ENNReal.tsum_mul_left.symm
      _ ≤ coverCost s U := by
        apply ENNReal.tsum_le_tsum
        intro i
        by_cases hi : (U i).Nonempty
        · exact (hterm s δ hs hs1 hδ _ (hU.2 i)).trans (le_iSup_of_le hi le_rfl)
        · have he : U i = ∅ := Set.not_nonempty_iff_eq_empty.mp hi
          simp [he]
  have hinf : ∀ s : ℝ, 0 < s → s < 1 → Hmeasure s unitI = ⊤ := by
    intro s hs hs1
    apply ENNReal.eq_top_of_forall_nnreal_le
    intro M
    have ht := tendsto_rpow_neg_nhdsGT_zero (show s - 1 < 0 by linarith)
    have he : ∀ᶠ δ : ℝ in nhdsWithin 0 (Set.Ioi 0), (M : ℝ) ≤ δ ^ (s - 1) := ht.eventually (Filter.eventually_ge_atTop (M : ℝ))
    have hp : ∀ᶠ δ : ℝ in nhdsWithin 0 (Set.Ioi 0), 0 < δ := self_mem_nhdsWithin
    obtain ⟨δ, hM, hδ⟩ := (he.and hp).exists
    calc
      (M : ℝ≥0∞) = ENNReal.ofReal (M : ℝ) := by simp
      _ ≤ ENNReal.ofReal (δ ^ (s - 1)) := ENNReal.ofReal_le_ofReal hM
      _ ≤ Hscale s δ unitI := hscale s hs hs1 δ hδ
      _ ≤ Hmeasure s unitI := le_iSup_of_le δ (le_iSup_of_le hδ le_rfl)
  have hdim_lower : ∀ s : ℝ, 0 < s → Hmeasure s unitI = ⊤ → ENNReal.ofReal s ≤ dimH unitI := by
    intro s hs ht
    have hiso : Isometry (ULift.down : ULift.{u_1} ℝ → ℝ) := fun x y => rfl
    have hcost : ∀ U : ℕ → Set (ULift.{u_1} ℝ), coverCost s (fun i => ULift.down '' U i) = coverCost s U := by
      intro U
      unfold coverCost
      congr 1
      funext i
      rw [hiso.ediam_image]
      simp only [Set.image_nonempty]
    have htrans : Hmeasure s unitI ≤ Hmeasure s (ULift.down ⁻¹' unitI : Set (ULift.{u_1} ℝ)) := by
      refine iSup_le fun δ => iSup_le fun hδ => ?_
      apply le_trans ?_ (le_iSup_of_le δ (le_iSup_of_le hδ le_rfl))
      refine le_iInf fun U => le_iInf fun hU => ?_
      have hc : IsCover δ unitI (fun i => ULift.down '' U i) := by
        constructor
        · intro x hx
          have hu := hU.1 (show (ULift.up x : ULift.{u_1} ℝ) ∈ ULift.down ⁻¹' unitI from hx)
          obtain ⟨i, hi⟩ := Set.mem_iUnion.mp hu
          exact Set.mem_iUnion.mpr ⟨i, ⟨ULift.up x, hi, rfl⟩⟩
        · intro i
          rw [hiso.ediam_image]
          exact hU.2 i
      calc
        Hscale s δ unitI ≤ coverCost s (fun i => ULift.down '' U i) := iInf_le_of_le _ (iInf_le_of_le hc le_rfl)
        _ = coverCost s U := hcost U
    have hlift : Hmeasure s (ULift.down ⁻¹' unitI : Set (ULift.{u_1} ℝ)) = ⊤ := top_unique (ht ▸ htrans)
    have hb := (h_T002 (ULift.{u_1} ℝ) (ULift.down ⁻¹' unitI) s hs).2.2.2.2 hlift
    have he : ULift.down '' (ULift.down ⁻¹' unitI : Set (ULift.{u_1} ℝ)) = unitI := by
      ext x
      constructor
      · rintro ⟨y, hy, rfl⟩; exact hy
      · intro hx; exact ⟨ULift.up x, hx, rfl⟩
    have hd := hiso.dimH_image (ULift.down ⁻¹' unitI)
    rw [he] at hd
    rwa [← hd] at hb
  refine ⟨le_antisymm h_T015 ?_, hinf⟩
  have hd : dimH unitI ≠ ⊤ := ne_top_of_le_ne_top (by simp) h_T015
  have hr : 1 ≤ (dimH unitI).toReal := by
    by_contra h
    have hlt : (dimH unitI).toReal < 1 := lt_of_not_ge h
    let s : ℝ := ((dimH unitI).toReal + 1) / 2
    have hs : 0 < s := by dsimp [s]; have := ENNReal.toReal_nonneg (a := dimH unitI); linarith
    have hs1 : s < 1 := by dsimp [s]; linarith
    have hb : ENNReal.ofReal s ≤ dimH unitI := hdim_lower s hs (hinf s hs hs1)
    have hb' : s ≤ (dimH unitI).toReal := (ENNReal.ofReal_le_iff_le_toReal hd).1 hb
    dsimp [s] at hb'
    linarith
  simpa using (ENNReal.ofReal_le_iff_le_toReal hd).2 hr

theorem T018 (n : ℕ) (E : Set (V n)) (h_H001 : E.Nonempty) :
    ∀ (b δ : ℝ), 0 < b → 0 < δ → Hscale b δ unitI ≤ Hscale b δ (cyl n E) := by
  classical
  intro b δ hb hδ
  obtain ⟨x0, hx0⟩ := h_H001
  have hd (t u : ℝ) : dist (pack n x0 t) (pack n x0 u) = dist t u := by
    rw [EuclideanSpace.dist_eq]
    simp [pack, Fintype.sum_sum_type, Real.sqrt_sq (dist_nonneg : 0 ≤ dist t u)]
  have he (t u : ℝ) : edist (pack n x0 t) (pack n x0 u) = edist t u := by
    simp only [edist_dist, hd]
  unfold Hscale
  refine le_iInf fun Q => le_iInf fun hQ => ?_
  let P : ℕ → Set ℝ := fun i => {t | t ∈ unitI ∧ pack n x0 t ∈ Q i}
  have hdiam (i : ℕ) : Metric.ediam (P i) ≤ Metric.ediam (Q i) := by
    apply Metric.ediam_le
    intro t ht u hu
    rw [← he]
    exact Metric.edist_le_ediam_of_mem ht.2 hu.2
  have hP : IsCover δ unitI P := by
    constructor
    · intro t ht
      have hmem : pack n x0 t ∈ cyl n E := by
        constructor
        · simpa [projX, pack] using hx0
        · simpa [projT, pack] using ht
      obtain ⟨i, hi⟩ := Set.mem_iUnion.mp (hQ.1 hmem)
      exact Set.mem_iUnion.mpr ⟨i, ht, hi⟩
    · intro i
      exact (hdiam i).trans (hQ.2 i)
  have hscale : Hscale b δ unitI ≤ coverCost b P :=
    iInf_le_of_le P (iInf_le_of_le hP le_rfl)
  refine hscale.trans ?_
  unfold coverCost
  apply ENNReal.tsum_le_tsum
  intro i
  refine iSup_le fun hPi => ?_
  have hQi : (Q i).Nonempty := by
    obtain ⟨t, ht⟩ := hPi
    exact ⟨pack n x0 t, ht.2⟩
  exact (ENNReal.rpow_le_rpow (hdiam i) hb.le).trans (le_iSup_of_le hQi le_rfl)

theorem T019 (n : ℕ) (E : Set (V n)) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) (h_T017 : dimH unitI = 1 ∧ ∀ s : ℝ, 0 < s → s < 1 → Hmeasure s unitI = ⊤) (h_T018 : ∀ (b δ : ℝ), 0 < b → 0 < δ → Hscale b δ unitI ≤ Hscale b δ (cyl n E)) :
    dimH E = 0 → (1 : ℝ≥0∞) ≤ dimH (cyl n E) ∧ (1 : ℝ≥0∞) = dimH E + 1 := by
  intro hD
  have hm : ∀ b : ℝ, 0 < b → Hmeasure b unitI ≤ Hmeasure b (cyl n E) := by
    intro b hb
    unfold Hmeasure
    exact iSup_mono fun δ => iSup_mono fun hδ => h_T018 b δ hb hδ
  have hi : Isometry (ULift.down : ULift.{u_1} (W n) → W n) := by intro x y; rfl
  have hlift : ∀ a : ℝ, Hmeasure a (cyl n E) ≤ Hmeasure a (ULift.down ⁻¹' cyl n E : Set (ULift.{u_1} (W n))) := by
    intro a
    have hs : ∀ δ : ℝ, Hscale a δ (cyl n E) ≤ Hscale a δ (ULift.down ⁻¹' cyl n E : Set (ULift.{u_1} (W n))) := by
      intro δ
      refine le_iInf fun U => le_iInf fun hU => ?_
      let Q : ℕ → Set (W n) := fun i => ULift.down '' U i
      have hQ : IsCover δ (cyl n E) Q := by
        constructor
        · intro x hx
          have hx' : (ULift.up x : ULift.{u_1} (W n)) ∈ ⋃ i, U i := hU.1 hx
          obtain ⟨i, hi⟩ := Set.mem_iUnion.mp hx'
          exact Set.mem_iUnion.mpr ⟨i, ⟨ULift.up x, hi, rfl⟩⟩
        · intro i
          exact (hi.ediam_image (U i)).le.trans (hU.2 i)
      have hc : coverCost a Q = coverCost a U := by
        simp only [coverCost, Q, hi.ediam_image, Set.image_nonempty]
      exact iInf_le_of_le Q (iInf_le_of_le hQ hc.le)
    unfold Hmeasure
    exact iSup_mono fun δ => iSup_mono fun _ => hs δ
  have hd : ∀ a : ℝ, 0 < a → a < 1 → ENNReal.ofReal a ≤ dimH (cyl n E) := by
    intro a ha ha1
    have hinf : Hmeasure a (cyl n E) = ⊤ := by
      apply top_unique
      rw [← h_T017.2 a ha ha1]
      exact hm a ha
    have hinf' : Hmeasure a (ULift.down ⁻¹' cyl n E : Set (ULift.{u_1} (W n))) = ⊤ := by
      apply top_unique
      rw [← hinf]
      exact hlift a
    have himg : ULift.down '' (ULift.down ⁻¹' cyl n E : Set (ULift.{u_1} (W n))) = cyl n E := by
      ext x
      simp
    have hd' := (h_T002 (ULift.{u_1} (W n)) (ULift.down ⁻¹' cyl n E) a ha).2.2.2.2 hinf'
    rw [← hi.dimH_image, himg] at hd'
    exact hd'
  constructor
  · apply ENNReal.le_of_forall_pos_nnreal_lt
    intro r hr hr1
    have hrpos : 0 < (r : ℝ) := by exact_mod_cast hr
    have hrlt : (r : ℝ) < 1 := by exact_mod_cast hr1
    have hcoe : ENNReal.ofReal (r : ℝ) = (r : ℝ≥0∞) := by simp
    rw [← hcoe]
    exact hd (r : ℝ) hrpos hrlt
  · simp [hD]

theorem T020 (n : ℕ) (E : Set (V n)) (h_T005 : Bornology.IsBounded E ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) ∧ 0 ≤ dimH E ∧ dimH E ≤ (n : ℝ≥0∞) ∧ dimH E < ⊤ ∧ (n = 0 → E = Set.univ ∧ dimH E = 0)) (h_T009 : dimH (cyl n E) ≤ dimH E + 1) (h_T014 : 0 < dimH E → dimH E + 1 ≤ dimH (cyl n E)) (h_T019 : dimH E = 0 → (1 : ℝ≥0∞) ≤ dimH (cyl n E) ∧ (1 : ℝ≥0∞) = dimH E + 1) :
    dimH (cyl n E) = dimH E + 1 := by
  apply le_antisymm h_T009
  by_cases hpos : 0 < dimH E
  · exact h_T014 hpos
  · have hz : dimH E = 0 := le_antisymm (le_of_not_gt hpos) bot_le
    obtain ⟨hlower, heq⟩ := h_T019 hz
    rw [← heq]
    exact hlower

set_option Elab.async false in
theorem P (n : ℕ) (E : Set (V n)) (h_H001 : E.Nonempty) (h_H002 : IsCompact E) :
    dimH (cyl n E) = dimH E + 1 := by
  have h_T001 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A := @T001 n E 
  have h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A) := @T002 n E h_T001
  have h_T003 : Bornology.IsBounded E ∧ (∃ B : ℝ, 1 ≤ B ∧ ∀ x ∈ E, ‖x‖ ≤ B) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) := @T003 n E h_H002
  have h_T004 : 0 < n → ∀ a : ℝ, (n : ℝ) < a → (∀ δ : ℝ, 0 < δ → Hscale a δ E = 0) ∧ Hmeasure a E = 0 := @T004 n E h_T003
  have h_T005 : Bornology.IsBounded E ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) ∧ 0 ≤ dimH E ∧ dimH E ≤ (n : ℝ≥0∞) ∧ dimH E < ⊤ ∧ (n = 0 → E = Set.univ ∧ dimH E = 0) := @T005 n E h_H001 h_T002 h_T003 h_T004
  have h_T006 : n = 0 → dimH (cyl n E) ≤ dimH E + 1 := @T006 n E h_T002 h_T005
  have h_T007 : 0 < n → ∀ (q r ε : ℝ), dimH E < ENNReal.ofReal q → 0 < r → r ≤ 1 → 0 < ε → ∃ U : ℕ → Set (V n), IsCover r E U ∧ (∀ i, (U i).Nonempty → 0 < Metric.ediam (U i)) ∧ coverCost q U < ENNReal.ofReal ε := @T007 n E h_T002 h_T005
  have h_T008 : 0 < n → ∀ (q δ ε : ℝ), dimH E < ENNReal.ofReal q → 0 < δ → 0 < ε → Hscale (q + 1) δ (cyl n E) ≤ ENNReal.ofReal (2 * (Real.sqrt 2) ^ (q + 1) * ε) := @T008 n E h_T007
  have h_T009 : dimH (cyl n E) ≤ dimH E + 1 := @T009 n E h_T002 h_T005 h_T006 h_T008
  have h_T010 : ∀ (s δ ε : ℝ), 0 < s → 0 < δ → 0 < ε → ∀ Vc : ℕ → Set (W n), IsCover δ (cyl n E) Vc → ∃ J : ℕ → Set ℝ, (∀ i, IsOpen (J i) ∧ projT n '' Vc i ⊆ J i ∧ MeasureTheory.volume (J i) ≤ Metric.ediam (Vc i) + ENNReal.ofReal ε * (1 / 2 : ℝ≥0∞) ^ (i + 1) / (1 + (Metric.ediam (Vc i)) ^ s)) ∧ (∀ t ∈ unitI, Hscale s δ E ≤ ∑' i, (J i).indicator (fun _ : ℝ => (Metric.ediam (Vc i)) ^ s) t) ∧ (∀ i, Measurable ((J i).indicator (fun _ : ℝ => (Metric.ediam (Vc i)) ^ s))) := @T010 n E h_T005
  have h_T011 : ∀ (s δ ε : ℝ), 0 < s → 0 < δ → 0 < ε → ∀ Vc : ℕ → Set (W n), IsCover δ (cyl n E) Vc → Hscale s δ E ≤ coverCost (s + 1) Vc + ENNReal.ofReal ε := @T011 n E h_T005 h_T010
  have h_T012 : ∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E ≤ Hscale (s + 1) δ (cyl n E) := @T012 n E h_T011
  have h_T013 : ∀ s : ℝ, 0 < s → ENNReal.ofReal s < dimH E → ENNReal.ofReal (s + 1) ≤ dimH (cyl n E) := @T013 n E h_T002 h_T005 h_T012
  have h_T014 : 0 < dimH E → dimH E + 1 ≤ dimH (cyl n E) := @T014 n E h_T005 h_T013
  have h_T015 : dimH unitI ≤ 1 := @T015 n E h_T002
  have h_T016 : ∀ δ : ℝ, 0 < δ → ∀ U : ℕ → Set ℝ, IsCover δ unitI U → (1 : ℝ≥0∞) ≤ ∑' i, Metric.ediam (U i) := @T016 n E 
  have h_T017 : dimH unitI = 1 ∧ ∀ s : ℝ, 0 < s → s < 1 → Hmeasure s unitI = ⊤ := @T017 n E h_T002 h_T015 h_T016
  have h_T018 : ∀ (b δ : ℝ), 0 < b → 0 < δ → Hscale b δ unitI ≤ Hscale b δ (cyl n E) := @T018 n E h_H001
  have h_T019 : dimH E = 0 → (1 : ℝ≥0∞) ≤ dimH (cyl n E) ∧ (1 : ℝ≥0∞) = dimH E + 1 := @T019 n E h_T002 h_T017 h_T018
  have h_T020 : dimH (cyl n E) = dimH E + 1 := @T020 n E h_T005 h_T009 h_T014 h_T019
  exact h_T020

#check @P
#print axioms P

end Translation

namespace AuditBExport
set_option autoImplicit false

end AuditBExport

open Lean Meta Elab Command in
run_cmd do
  let result ← liftTermElabM do
    let info ← getConstInfo `Translation.P
    forallTelescope info.type fun xs body => do
      let mut retained := #[]
      let omitted : Array String := #[]
      for x in xs do
        let decl ← getFVarLocalDecl x
        if !omitted.contains decl.userName.toString then
          retained := retained.push x
      let exported ← mkForallFVars retained body
      let used := (collectLevelParams {} exported).params.toList
      return Json.mkObj [("parameters", toJson (info.levelParams.map Name.toString)),
        ("export_used_parameters", toJson (used.map Name.toString))]
  logInfo m!"YUI_ASSEMBLY_LEVELS_JSON:{result.compress}"
