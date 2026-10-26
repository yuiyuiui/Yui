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
theorem checked (n : ℕ) (E : Set (V n)) (h_T003 : Bornology.IsBounded E ∧ (∃ B : ℝ, 1 ≤ B ∧ ∀ x ∈ E, ‖x‖ ≤ B) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤)) : yui_aux_type% "∀ (a K : ℝ), 0 ≤ a → 0 ≤ K → ∀ k : ℕ, 0 < k → (k : ℝ≥0∞)^n * (ENNReal.ofReal (K / k))^a = ENNReal.ofReal (K^a * ((k : ℝ)⁻¹)^(a-n))" := by
  intro a K ha hK k hk
  have hk' : (0 : ℝ) < k := by exact_mod_cast hk
  have hid : (k : ℝ)^n * (K / k)^a = K^a * ((k : ℝ)⁻¹)^(a-n) := by
    rw [Real.div_rpow hK hk'.le, Real.inv_rpow hk'.le, Real.rpow_sub hk', Real.rpow_natCast]
    field_simp
  have hc : ENNReal.ofReal ((k : ℝ)^n) = (k : ℝ≥0∞)^n := by rw [ENNReal.ofReal_pow hk'.le]; simp
  rw [← hc, ← ENNReal.ofReal_rpow_of_nonneg (div_nonneg hK hk'.le) ha, ← ENNReal.ofReal_mul (pow_nonneg hk'.le n), hid]
#check @checked
#print axioms checked
end YuiAuxiliary
