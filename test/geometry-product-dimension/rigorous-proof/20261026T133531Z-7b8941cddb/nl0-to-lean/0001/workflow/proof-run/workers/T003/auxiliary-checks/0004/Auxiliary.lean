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
theorem checked (n : ℕ) (E : Set (V n)) (h_H002 : IsCompact E) : yui_aux_type% "∀ (s δ : ℝ) (k : ℕ) (U : Fin k → Set (V n)), 0 < s → E ⊆ ⋃ i, U i → (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) → Hscale s δ E < ⊤" := by
  classical
  intro s δ k U hs hcov hd
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
#check @checked
#print axioms checked
end YuiAuxiliary
