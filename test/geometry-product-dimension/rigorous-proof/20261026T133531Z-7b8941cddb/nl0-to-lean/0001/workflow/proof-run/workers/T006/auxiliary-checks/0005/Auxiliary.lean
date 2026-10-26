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

open Lean Elab Term
elab "yui_aux_type% " text:str : term => do
  let parsed ← ofExcept <| Parser.runParserCategory (← getEnv) `term text.getString
  Term.elabTerm parsed none

namespace YuiAuxiliary
set_option autoImplicit false
theorem checked (n : ℕ) (E : Set (V n)) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) (h_T005 : Bornology.IsBounded E ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) ∧ 0 ≤ dimH E ∧ dimH E ≤ (n : ℝ≥0∞) ∧ dimH E < ⊤ ∧ (n = 0 → E = Set.univ ∧ dimH E = 0)) : yui_aux_type% "∀ (a δ : ℝ) (N : ℕ), 1 < a → 0 < N → 1 / (N : ℝ) ≤ δ → Hscale a δ ((fun t : ℝ => pack 0 0 t) '' unitI) ≤ (N : ℝ≥0∞) * (ENNReal.ofReal (1 / (N : ℝ))) ^ a" := by
  classical
  intro a δ N ha hN hδ
  have hf : Isometry (fun t : ℝ => pack 0 0 t) := by
    apply Isometry.of_dist_eq
    intro x y
    simp [dist_eq_norm, pack, PiLp.norm_eq_of_L2, Real.sqrt_sq_eq_abs]
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
  let r : ℝ := 1 / (N : ℝ)
  have hNp : 0 < (N : ℝ) := by exact_mod_cast hN
  have hr : 0 < r := by dsimp [r]; positivity
  let U : ℕ → Set (W 0) := fun i => if i < N then (fun t : ℝ => pack 0 0 t) '' Set.Icc ((i : ℝ) * r) (((i : ℝ) + 1) * r) else ∅
  have hd : ∀ i, i < N → Metric.ediam (U i) = ENNReal.ofReal r := by
    intro i hi
    simp only [U, if_pos hi, hf.ediam_image, Real.ediam_Icc]
    congr 1
    ring
  have hc : IsCover δ ((fun t : ℝ => pack 0 0 t) '' unitI) U := by
    constructor
    · rintro z ⟨t, ht, rfl⟩
      have ht' : t ≤ (N : ℝ) * r := by simpa [r, hNp.ne'] using ht.2
      obtain ⟨i, hi, hti⟩ := partition r hr.le N hN t ht.1 ht'
      exact Set.mem_iUnion.mpr ⟨i, by simpa only [U, if_pos hi] using Set.mem_image_of_mem (fun t : ℝ => pack 0 0 t) hti⟩
    · intro i
      by_cases hi : i < N
      · rw [hd i hi]
        exact ENNReal.ofReal_le_ofReal hδ
      · simp [U, hi]
  refine (iInf_le_of_le U (iInf_le_of_le hc le_rfl)).trans ?_
  change (∑' i, ⨆ (_ : (U i).Nonempty), Metric.ediam (U i) ^ a) ≤ _
  rw [tsum_eq_sum (s := Finset.range N) (fun i hi => by simp [U, Nat.not_lt.mpr (Finset.not_mem_range.mp hi)])]
  calc
    (∑ i ∈ Finset.range N, ⨆ (_ : (U i).Nonempty), Metric.ediam (U i) ^ a) ≤ ∑ i ∈ Finset.range N, (ENNReal.ofReal r) ^ a := by
      apply Finset.sum_le_sum
      intro i hi
      apply iSup_le
      intro _
      rw [hd i (Finset.mem_range.mp hi)]
    _ = _ := by simp [r]
#check @checked
#print axioms checked
end YuiAuxiliary
