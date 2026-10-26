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
theorem checked (n : ℕ) (E : Set (V n)) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) : yui_aux_type% "∀ (N : ℕ) (a : ℝ), coverCost a (fun i : ℕ => if i < N then Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N) else ∅) ≤ (N : ℝ≥0∞) * (ENNReal.ofReal (1 / (N : ℝ))) ^ a" := by
  classical
  intro N a
  let U := fun i : ℕ => if i < N then Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N) else ∅
  change coverCost a U ≤ _
  unfold coverCost
  rw [tsum_eq_sum (s := Finset.range N) (fun i hi => by simp [U, show ¬ i < N from by simpa using hi])]
  calc
    _ ≤ ∑ i ∈ Finset.range N, (ENNReal.ofReal (1 / (N : ℝ))) ^ a := by
      apply Finset.sum_le_sum
      intro i hi
      apply iSup_le
      intro _
      have hd : Metric.ediam (U i) = ENNReal.ofReal (1 / (N : ℝ)) := by
        rw [show U i = Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N) from if_pos (Finset.mem_range.mp hi), Real.ediam_Icc]
        congr 1
        ring
      rw [hd]
    _ = _ := by simp
#check @checked
#print axioms checked
end YuiAuxiliary
