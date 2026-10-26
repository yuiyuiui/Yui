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
theorem checked (n : ℕ) (E : Set (V n)) (h_H002 : IsCompact E) : yui_aux_type% "∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤" := by
  classical
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
#check @checked
#print axioms checked
end YuiAuxiliary
