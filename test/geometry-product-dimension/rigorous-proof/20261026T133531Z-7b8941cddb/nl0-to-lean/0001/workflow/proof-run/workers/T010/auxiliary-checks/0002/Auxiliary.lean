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
theorem checked (n : ℕ) (E : Set (V n)) (h_T005 : Bornology.IsBounded E ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) ∧ 0 ≤ dimH E ∧ dimH E ≤ (n : ℝ≥0∞) ∧ dimH E < ⊤ ∧ (n = 0 → E = Set.univ ∧ dimH E = 0)) : yui_aux_type% "∀ (B : Set ℝ) (R e : ℝ≥0∞), Metric.ediam B ≤ R → R ≠ ⊤ → 0 < e → e ≠ ⊤ → ∃ J : Set ℝ, IsOpen J ∧ B ⊆ J ∧ MeasureTheory.volume J ≤ R + e" := by
  intro B R e hBR hR he het
  classical
  by_cases hB : B.Nonempty
  · have hb : Bornology.IsBounded B := Metric.isBounded_iff_ediam_ne_top.mpr (ne_top_of_le_ne_top hR hBR)
    have hp : 0 < e.toReal := ENNReal.toReal_pos he.ne' het
    refine ⟨Set.Ioo (sInf B - e.toReal / 2) (sSup B + e.toReal / 2), isOpen_Ioo, ?_, ?_⟩
    · intro x hx
      have hx' := hb.subset_Icc_sInf_sSup hx
      constructor <;> linarith
    · rw [Real.volume_Ioo]
      have heq : sSup B + e.toReal / 2 - (sInf B - e.toReal / 2) = (sSup B - sInf B) + e.toReal := by ring
      rw [heq, ENNReal.ofReal_add (sub_nonneg.mpr (Real.sInf_le_sSup B hb.bddBelow hb.bddAbove)) ENNReal.toReal_nonneg, ENNReal.ofReal_toReal het, ← Real.ediam_eq hb]
      exact add_le_add_right hBR e
  · refine ⟨∅, isOpen_empty, ?_, ?_⟩
    · simpa [Set.not_nonempty_iff_eq_empty.mp hB]
    · simp
#check @checked
#print axioms checked
end YuiAuxiliary
