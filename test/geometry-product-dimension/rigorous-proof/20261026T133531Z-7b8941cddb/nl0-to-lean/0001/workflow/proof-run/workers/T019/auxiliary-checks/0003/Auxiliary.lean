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
theorem checked (n : ℕ) (E : Set (V n)) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) (h_T017 : dimH unitI = 1 ∧ ∀ s : ℝ, 0 < s → s < 1 → Hmeasure s unitI = ⊤) (h_T018 : ∀ (b δ : ℝ), 0 < b → 0 < δ → Hscale b δ unitI ≤ Hscale b δ (cyl n E)) : yui_aux_type% "∀ a : ℝ, Hmeasure a (cyl n E) ≤ Hmeasure a (ULift.down ⁻¹' cyl n E : Set (ULift.{u_1} (W n)))" := by
  intro a
  have hi : Isometry (ULift.down : ULift.{u_1} (W n) → W n) := by intro x y; rfl
  have hs : ∀ δ : ℝ, Hscale a δ (cyl n E) ≤ Hscale a δ (ULift.down ⁻¹' cyl n E : Set (ULift.{u_1} (W n))) := by
    intro δ
    refine le_iInf fun U => le_iInf fun hU => ?_
    let Q : ℕ → Set (W n) := fun i => ULift.down '' U i
    have hQ : IsCover δ (cyl n E) Q := by
      constructor
      · intro x hx
        have hx' : (ULift.up x : ULift.{u_1} (W n)) ∈ ⋃ i, U i := hU.1 hx
        obtain ⟨i, hi⟩ := Set.mem_iUnion.mp hx'
        exact Set.mem_iUnion.mpr ⟨i, ⟨ULift.up x, hi, rfl⟩⟩
      · intro i
        exact (hi.ediam_image (U i)).le.trans (hU.2 i)
    have hc : coverCost a Q = coverCost a U := by
      simp only [coverCost, Q, hi.ediam_image, Set.image_nonempty]
    exact iInf_le_of_le Q (iInf_le_of_le hQ hc.le)
  unfold Hmeasure
  exact iSup_mono fun δ => iSup_mono fun _ => hs δ
#check @checked
#print axioms checked
end YuiAuxiliary
