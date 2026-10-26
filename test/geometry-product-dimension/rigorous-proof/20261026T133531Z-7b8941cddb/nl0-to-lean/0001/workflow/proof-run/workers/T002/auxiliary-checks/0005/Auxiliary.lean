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
theorem checked (n : ℕ) (E : Set (V n)) (h_T001 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A) : yui_aux_type% "∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), Hmeasure s A = Hnative s A" := by
  intro X inst A s
  letI : MeasurableSpace X := borel X
  letI : BorelSpace X := ⟨rfl⟩
  change Hmeasure s A = MeasureTheory.Measure.hausdorffMeasure s A
  rw [MeasureTheory.Measure.hausdorffMeasure_apply]
  apply le_antisymm
  · unfold Hmeasure
    refine iSup₂_le fun δ hδ => ?_
    refine le_iSup₂_of_le (ENNReal.ofReal δ) (ENNReal.ofReal_pos.mpr hδ) ?_
    unfold Hscale IsCover coverCost
    simp only [iInf_and]
    rfl
  · refine iSup₂_le fun r hr => ?_
    obtain ⟨q, hq, hqr⟩ := ENNReal.lt_iff_exists_nnreal_btwn.mp hr
    have hqR : 0 < (q : ℝ) := by exact_mod_cast (ENNReal.coe_pos.mp hq)
    refine le_iSup₂_of_le (q : ℝ) hqR ?_
    unfold Hscale IsCover coverCost
    refine le_iInf fun U => le_iInf fun hU => ?_
    refine iInf_le_of_le U (iInf_le_of_le hU.1 (iInf_le_of_le ?_ le_rfl))
    intro i
    exact (hU.2 i).trans ((ENNReal.coe_nnreal_eq q).symm.trans_le hqr.le)
#check @checked
#print axioms checked
end YuiAuxiliary
