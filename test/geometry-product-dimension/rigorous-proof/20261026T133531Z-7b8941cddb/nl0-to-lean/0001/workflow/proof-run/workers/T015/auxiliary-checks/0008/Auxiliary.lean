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
theorem checked (n : ℕ) (E : Set (V n)) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) : yui_aux_type% "∀ a : ℝ, Hmeasure a unitI = 0 → dimH unitI ≤ ENNReal.ofReal a" := by
  intro a hz
  let f := (ULift.up : ℝ → ULift ℝ)
  have hp := h_T002 (ULift ℝ) (f '' unitI) a
  have hf : Isometry f := fun x y => rfl
  have hs : ∀ δ : ℝ, Hscale a δ (f '' unitI) ≤ Hscale a δ unitI := by
    intro δ
    unfold Hscale
    refine le_iInf fun U => le_iInf fun hU => ?_
    have hcov : IsCover δ (f '' unitI) (fun i => f '' U i) := by
      constructor
      · rintro _ ⟨x, hx, rfl⟩
        rcases Set.mem_iUnion.mp (hU.1 hx) with ⟨i, hi⟩
        exact Set.mem_iUnion.mpr ⟨i, ⟨x, hi, rfl⟩⟩
      · intro i
        rw [hf.ediam_image]
        exact hU.2 i
    have hcost : coverCost a (fun i => f '' U i) = coverCost a U := by
      simp only [coverCost, Set.image_nonempty, hf.ediam_image]
    exact iInf_le_of_le (fun i => f '' U i) (iInf_le_of_le hcov hcost.le)
  have hz' : Hmeasure a (f '' unitI) = 0 := by
    apply le_antisymm _ bot_le
    rw [← hz]
    exact iSup_mono fun δ => iSup_mono fun _ => hs δ
  by_cases ha : 0 < a
  · rw [← hf.dimH_image unitI]
    exact (hp ha).2.2.2.1 hz'
  · have : a ≤ 0 := le_of_not_gt ha
    -- this helper requires positivity
    exact False.elim (by linarith)
#check @checked
#print axioms checked
end YuiAuxiliary
