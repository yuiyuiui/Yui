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
theorem checked (n : ℕ) (E : Set (V n)) (h_T007 : 0 < n → ∀ (q r ε : ℝ), dimH E < ENNReal.ofReal q → 0 < r → r ≤ 1 → 0 < ε → ∃ U : ℕ → Set (V n), IsCover r E U ∧ (∀ i, (U i).Nonempty → 0 < Metric.ediam (U i)) ∧ coverCost q U < ENNReal.ofReal ε) : yui_aux_type% "∀ (d q : ℝ) (N : ℕ), 0 < d → (N : ℝ) ≤ 2 / d → (N : ℝ≥0∞) * (ENNReal.ofReal (Real.sqrt 2 * d)) ^ (q + 1) ≤ ENNReal.ofReal (2 * (Real.sqrt 2) ^ (q + 1)) * (ENNReal.ofReal d) ^ q" := by
  intro d q N hd hN
  have hs : 0 < Real.sqrt 2 := Real.sqrt_pos.2 (by norm_num)
  have hpow : (N : ℝ) * (Real.sqrt 2 * d) ^ (q + 1) ≤ (2 * (Real.sqrt 2) ^ (q + 1)) * d ^ q := by
    calc
      (N : ℝ) * (Real.sqrt 2 * d) ^ (q + 1) ≤ (2 / d) * (Real.sqrt 2 * d) ^ (q + 1) := mul_le_mul_of_nonneg_right hN (Real.rpow_nonneg (by positivity) _)
      _ = _ := by rw [Real.mul_rpow hs.le hd.le, Real.rpow_add_one hd.ne']; field_simp
  have hconv1 : ENNReal.ofReal ((N : ℝ) * (Real.sqrt 2 * d) ^ (q + 1)) = (N : ℝ≥0∞) * (ENNReal.ofReal (Real.sqrt 2 * d)) ^ (q + 1) := by
    rw [ENNReal.ofReal_mul (by positivity), ENNReal.ofReal_rpow_of_pos (mul_pos hs hd)]
    simp
  have hconv2 : ENNReal.ofReal ((2 * (Real.sqrt 2) ^ (q + 1)) * d ^ q) = ENNReal.ofReal (2 * (Real.sqrt 2) ^ (q + 1)) * (ENNReal.ofReal d) ^ q := by
    rw [ENNReal.ofReal_mul (by positivity), ENNReal.ofReal_rpow_of_pos hd]
  rw [← hconv1, ← hconv2]
  exact ENNReal.ofReal_le_ofReal hpow
#check @checked
#print axioms checked
end YuiAuxiliary
