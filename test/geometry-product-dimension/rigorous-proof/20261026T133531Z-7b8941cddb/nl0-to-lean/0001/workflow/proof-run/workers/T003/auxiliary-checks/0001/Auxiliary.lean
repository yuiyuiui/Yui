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
theorem checked (n : ℕ) (E : Set (V n)) (h_H002 : IsCompact E) : yui_aux_type% "∃ C : ℝ, ∀ x ∈ E, ‖x‖ ≤ C" := by
  classical
  have hc : E ⊆ ⋃ m : ℕ, Metric.ball (0 : V n) (m + 1 : ℝ) := by
    intro x hx
    obtain ⟨m, hm⟩ := exists_nat_gt ‖x‖
    exact Set.mem_iUnion.mpr ⟨m, by simpa only [Metric.mem_ball, dist_zero_right] using (show ‖x‖ < (m + 1 : ℝ) by exact lt_trans hm (by linarith))⟩
  obtain ⟨t, ht⟩ := h_H002.elim_finite_subcover (fun m : ℕ => Metric.ball (0 : V n) (m + 1 : ℝ)) (fun _ => Metric.isOpen_ball) hc
  refine ⟨∑ m ∈ t, (m + 1 : ℝ), ?_⟩
  intro x hx
  obtain ⟨m, hmt, hxm⟩ := Set.mem_iUnion₂.mp (ht hx)
  have hm : ‖x‖ < (m + 1 : ℝ) := by simpa using hxm
  exact hm.le.trans (Finset.single_le_sum (fun j hj => by positivity) hmt)
#check @checked
#print axioms checked
end YuiAuxiliary
