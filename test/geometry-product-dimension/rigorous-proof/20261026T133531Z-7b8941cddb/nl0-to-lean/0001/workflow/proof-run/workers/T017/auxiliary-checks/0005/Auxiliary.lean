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
theorem checked (n : ℕ) (E : Set (V n)) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) (h_T015 : dimH unitI ≤ 1) (h_T016 : ∀ δ : ℝ, 0 < δ → ∀ U : ℕ → Set ℝ, IsCover δ unitI U → (1 : ℝ≥0∞) ≤ ∑' i, Metric.ediam (U i)) : yui_aux_type% "∀ s : ℝ, 0 < s → Hmeasure s unitI = ⊤ → ENNReal.ofReal s ≤ dimH unitI" := by
  intro s hs ht
  have hiso : Isometry (ULift.down : ULift.{u_1} ℝ → ℝ) := fun x y => rfl
  have hcost : ∀ U : ℕ → Set (ULift.{u_1} ℝ), coverCost s (fun i => ULift.down '' U i) = coverCost s U := by
    intro U
    unfold coverCost
    congr 1
    funext i
    rw [hiso.ediam_image]
    simp only [Set.image_nonempty]
  have htrans : Hmeasure s unitI ≤ Hmeasure s (ULift.down ⁻¹' unitI : Set (ULift.{u_1} ℝ)) := by
    refine iSup_le fun δ => iSup_le fun hδ => ?_
    apply le_trans ?_ (le_iSup_of_le δ (le_iSup_of_le hδ le_rfl))
    refine le_iInf fun U => le_iInf fun hU => ?_
    have hc : IsCover δ unitI (fun i => ULift.down '' U i) := by
      constructor
      · intro x hx
        have hu := hU.1 (show (ULift.up x : ULift.{u_1} ℝ) ∈ ULift.down ⁻¹' unitI from hx)
        obtain ⟨i, hi⟩ := Set.mem_iUnion.mp hu
        exact Set.mem_iUnion.mpr ⟨i, ⟨ULift.up x, hi, rfl⟩⟩
      · intro i
        rw [hiso.ediam_image]
        exact hU.2 i
    calc
      Hscale s δ unitI ≤ coverCost s (fun i => ULift.down '' U i) := iInf_le_of_le _ (iInf_le_of_le hc le_rfl)
      _ = coverCost s U := hcost U
  have hlift : Hmeasure s (ULift.down ⁻¹' unitI : Set (ULift.{u_1} ℝ)) = ⊤ := top_unique (ht ▸ htrans)
  have hb := (h_T002 (ULift.{u_1} ℝ) (ULift.down ⁻¹' unitI) s hs).2.2.2.2 hlift
  have he : ULift.down '' (ULift.down ⁻¹' unitI : Set (ULift.{u_1} ℝ)) = unitI := by
    ext x
    constructor
    · rintro ⟨y, hy, rfl⟩; exact hy
    · intro hx; exact ⟨ULift.up x, hx, rfl⟩
  have hd := hiso.dimH_image (ULift.down ⁻¹' unitI)
  rw [he] at hd
  rwa [← hd] at hb
#check @checked
#print axioms checked
end YuiAuxiliary
