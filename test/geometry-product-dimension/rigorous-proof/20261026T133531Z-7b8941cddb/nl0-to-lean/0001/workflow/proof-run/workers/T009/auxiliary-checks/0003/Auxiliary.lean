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
theorem checked (n : ℕ) (E : Set (V n)) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) (h_T005 : Bornology.IsBounded E ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) ∧ 0 ≤ dimH E ∧ dimH E ≤ (n : ℝ≥0∞) ∧ dimH E < ⊤ ∧ (n = 0 → E = Set.univ ∧ dimH E = 0)) (h_T006 : n = 0 → dimH (cyl n E) ≤ dimH E + 1) (h_T008 : 0 < n → ∀ (q δ ε : ℝ), dimH E < ENNReal.ofReal q → 0 < δ → 0 < ε → Hscale (q + 1) δ (cyl n E) ≤ ENNReal.ofReal (2 * (Real.sqrt 2) ^ (q + 1) * ε)) : yui_aux_type% "0 < n → ∀ q δ : ℝ, dimH E < ENNReal.ofReal q → 0 < δ → Hscale (q + 1) δ (cyl n E) = 0" := by
  intro hn q δ hq hδ
  apply le_antisymm _ (zero_le _)
  apply ENNReal.le_of_forall_pos_le_add
  intro e he _
  have heR : (0 : ℝ) < (e : ℝ) := he
  have hC : 0 < 2 * (Real.sqrt 2) ^ (q + 1) := mul_pos (by norm_num) (Real.rpow_pos_of_pos (Real.sqrt_pos.2 (by norm_num)) _)
  have hb := h_T008 hn q δ ((e : ℝ) / (2 * (Real.sqrt 2) ^ (q + 1))) hq hδ (div_pos heR hC)
  have hc : 2 * (Real.sqrt 2) ^ (q + 1) * ((e : ℝ) / (2 * (Real.sqrt 2) ^ (q + 1))) = (e : ℝ) := mul_div_cancel₀ _ (ne_of_gt hC)
  simpa only [hc, ENNReal.ofReal_coe_nnreal, zero_add] using hb
#check @checked
#print axioms checked
end YuiAuxiliary
