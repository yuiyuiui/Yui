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
theorem checked (n : ℕ) (E : Set (V n)) (h_H001 : E.Nonempty) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) (h_T003 : Bornology.IsBounded E ∧ (∃ B : ℝ, 1 ≤ B ∧ ∀ x ∈ E, ‖x‖ ≤ B) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤)) (h_T004 : 0 < n → ∀ a : ℝ, (n : ℝ) < a → (∀ δ : ℝ, 0 < δ → Hscale a δ E = 0) ∧ Hmeasure a E = 0) : yui_aux_type% "∀ s : ℝ, 0 < s → Hmeasure s E = 0 → dimH E ≤ ENNReal.ofReal s" := by
  intro s hs hz
  let L := ULift (V n)
  let f : V n → L := ULift.up
  have hf : Isometry f := fun _ _ => rfl
  have hm : Hmeasure s (f '' E) ≤ Hmeasure s E := by
    apply iSup_le
    intro δ
    apply iSup_le
    intro hδ
    refine le_trans ?_ (le_iSup_of_le δ (le_iSup_of_le hδ le_rfl))
    change Hscale s δ (f '' E) ≤ Hscale s δ E
    apply le_iInf
    intro U
    apply le_iInf
    intro hU
    let U' : ℕ → Set L := fun i => f '' U i
    have hU' : IsCover δ (f '' E) U' := by
      constructor
      · rintro _ ⟨x, hx, rfl⟩
        obtain ⟨i, hi⟩ := Set.mem_iUnion.mp (hU.1 hx)
        exact Set.mem_iUnion.mpr ⟨i, ⟨x, hi, rfl⟩⟩
      · intro i
        simpa only [U', hf.ediam_image] using hU.2 i
    calc
      Hscale s δ (f '' E) ≤ coverCost s U' := iInf_le_of_le U' (iInf_le_of_le hU' le_rfl)
      _ = coverCost s U := by
        simp only [coverCost, U', Set.image_nonempty, hf.ediam_image]
  have hz' : Hmeasure s (f '' E) = 0 := le_antisymm (hm.trans_eq hz) bot_le
  have hd := (h_T002 L (f '' E) s hs).2.2.2.1 hz'
  have hi : AntilipschitzWith 1 f := hf.antilipschitz
  exact (hi.le_dimH_image E).trans hd
#check @checked
#print axioms checked
end YuiAuxiliary
