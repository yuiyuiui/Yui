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
theorem checked (n : ℕ) (E : Set (V n)) (h_T003 : Bornology.IsBounded E ∧ (∃ B : ℝ, 1 ≤ B ∧ ∀ x ∈ E, ‖x‖ ≤ B) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤)) : yui_aux_type% "∀ a K : ℝ, (n : ℝ) < a → Filter.Tendsto (fun k : ℕ => ENNReal.ofReal (K^a * ((k : ℝ)⁻¹)^(a-n))) Filter.atTop (nhds 0) ∧ Filter.Tendsto (fun k : ℕ => K / (k : ℝ)) Filter.atTop (nhds 0)" := by
  intro a K ha
  have hi : Filter.Tendsto (fun k : ℕ => ((k : ℝ)⁻¹)) Filter.atTop (nhds 0) := tendsto_inv_atTop_zero.comp tendsto_natCast_atTop_atTop
  have hp : Filter.Tendsto (fun k : ℕ => ((k : ℝ)⁻¹)^(a-n)) Filter.atTop (nhds 0) := by
    simpa [Real.zero_rpow (sub_pos.mpr ha).ne'] using ((Real.continuous_rpow_const (sub_pos.mpr ha).le).tendsto 0).comp hi
  constructor
  · simpa using ENNReal.tendsto_ofReal (hp.const_mul (K^a))
  · simpa [div_eq_mul_inv] using hi.const_mul K
#check @checked
#print axioms checked
end YuiAuxiliary
