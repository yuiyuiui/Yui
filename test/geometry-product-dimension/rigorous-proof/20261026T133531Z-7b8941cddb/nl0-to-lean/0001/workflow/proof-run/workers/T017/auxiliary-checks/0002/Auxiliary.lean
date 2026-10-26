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
theorem checked (n : ℕ) (E : Set (V n)) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) (h_T015 : dimH unitI ≤ 1) (h_T016 : ∀ δ : ℝ, 0 < δ → ∀ U : ℕ → Set ℝ, IsCover δ unitI U → (1 : ℝ≥0∞) ≤ ∑' i, Metric.ediam (U i)) : yui_aux_type% "∀ (s δ : ℝ), 0 < s → s < 1 → 0 < δ → ∀ ρ : ℝ≥0∞, ρ ≤ ENNReal.ofReal δ → ENNReal.ofReal (δ ^ (s - 1)) * ρ ≤ ρ ^ s" := by
  intro s δ hs hs1 hδ ρ hρ
  have hfin : ρ ≠ ⊤ := ne_top_of_le_ne_top ENNReal.ofReal_ne_top hρ
  have hle : ρ.toReal ≤ δ := (ENNReal.toReal_le_toReal hfin ENNReal.ofReal_ne_top).2 hρ |>.trans_eq (ENNReal.toReal_ofReal hδ.le)
  have hreal : δ ^ (s - 1) * ρ.toReal ≤ ρ.toReal ^ s := by
    by_cases hz : ρ.toReal = 0
    · simp [hz, Real.zero_rpow hs.ne']
    · have hp : 0 < ρ.toReal := lt_of_le_of_ne ENNReal.toReal_nonneg (Ne.symm hz)
      calc
        _ ≤ ρ.toReal ^ (s - 1) * ρ.toReal := mul_le_mul_of_nonneg_right (Real.rpow_le_rpow_of_nonpos hp hle (by linarith)) ENNReal.toReal_nonneg
        _ = _ := by rw [Real.rpow_sub_one hz, div_mul_cancel₀ _ hz]
  have hc := ENNReal.ofReal_le_ofReal hreal
  rw [ENNReal.ofReal_mul (Real.rpow_nonneg hδ.le _), ← ENNReal.ofReal_rpow_of_nonneg ENNReal.toReal_nonneg hs.le, ENNReal.ofReal_toReal hfin] at hc
  exact hc
#check @checked
#print axioms checked
end YuiAuxiliary
