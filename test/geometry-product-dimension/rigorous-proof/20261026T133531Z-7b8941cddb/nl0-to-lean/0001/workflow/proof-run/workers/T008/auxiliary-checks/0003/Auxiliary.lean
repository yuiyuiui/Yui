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
theorem checked (n : ℕ) (E : Set (V n)) (h_T007 : 0 < n → ∀ (q r ε : ℝ), dimH E < ENNReal.ofReal q → 0 < r → r ≤ 1 → 0 < ε → ∃ U : ℕ → Set (V n), IsCover r E U ∧ (∀ i, (U i).Nonempty → 0 < Metric.ediam (U i)) ∧ coverCost q U < ENNReal.ofReal ε) : yui_aux_type% "∀ (a b : W n) (d : ℝ), 0 ≤ d → dist (projX n a) (projX n b) ≤ d → dist (projT n a) (projT n b) ≤ d → dist a b ≤ Real.sqrt 2 * d" := by
  intro a b d hd hx ht
  have hid : dist a b ^ 2 = dist (projX n a) (projX n b) ^ 2 + dist (projT n a) (projT n b) ^ 2 := by
    rw [EuclideanSpace.dist_sq_eq a b, EuclideanSpace.dist_sq_eq (projX n a) (projX n b)]
    simp [projX, projT, Fintype.sum_sum_type]
  have hs : (Real.sqrt 2) ^ 2 = (2 : ℝ) := Real.sq_sqrt (by norm_num)
  have hx2 : dist (projX n a) (projX n b) ^ 2 ≤ d ^ 2 := sq_le_sq₀ (dist_nonneg) hd |>.2 hx
  have ht2 : dist (projT n a) (projT n b) ^ 2 ≤ d ^ 2 := sq_le_sq₀ (dist_nonneg) hd |>.2 ht
  have hn : 0 ≤ Real.sqrt 2 * d := mul_nonneg (Real.sqrt_nonneg _) hd
  nlinarith [dist_nonneg (x := a) (y := b), sq_nonneg (Real.sqrt 2 * d - dist a b)]
#check @checked
#print axioms checked
end YuiAuxiliary
